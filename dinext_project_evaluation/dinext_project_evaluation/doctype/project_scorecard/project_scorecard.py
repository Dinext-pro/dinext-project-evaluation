import json

import frappe
from frappe import _
from frappe.desk.search import get_link_title
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils import now_datetime

from dinext_project_evaluation.scoring.profile_stages import get_applicable_stages
from dinext_project_evaluation.scoring.scorecard_factory import sync_scorecard_items
from dinext_project_evaluation.scoring.scorecard_cancel import (
	create_replacement_draft_after_cancel,
	validate_scorecard_cancel_allowed,
)
from dinext_project_evaluation.scoring.scorecard_service import (
	MANDATORY_MISSING_PREFIX,
	calculate_scorecard_document,
	scorecard_validation_error_message,
)
from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_AGREED_DOCSTATUS,
	SCORECARD_CANCELED_DOCSTATUS,
	SCORECARD_CONTENT_EDITABLE_STATUSES,
	SCORECARD_NON_RECALCULABLE_DOCSTATUSES,
	is_agreed_scorecard,
	is_canceled_scorecard,
	is_terminal_scorecard,
	scorecard_docstatus,
	should_calculate_scorecard_on_validate,
	STATUS_DRAFT,
)

PARENT_IMMUTABLE_OUTSIDE_DRAFT = (
	"project",
	"profile",
	"portfolio",
	"stage_at_evaluation",
	"stage_instance_at_evaluation",
)

ITEM_STRUCTURE_FIELDS = ("criterion",)

# User-entered criterion values; excludes derived fields recomputed in _prepare_item_inputs().
ITEM_USER_EDITABLE_VALUE_FIELDS = (
	"scale_value",
	"boolean_value",
	"boolean_value_set",
	"number_value",
	"currency_value",
	"percent_value",
	"comment",
)

PARENT_CALCULATION_FIELDS = (
	"integral_score",
	"gate_pass",
	"gate_messages",
	"evaluation_date",
	"profile_snapshot",
)

ITEM_CALCULATION_FIELDS = (
	"criterion_code",
	"normalized_score",
	"weighted_score",
	"weight",
	"gate_pass",
)


class ProjectScorecard(Document):
	def before_save(self):
		self._prevent_locked_edits()

	def onload(self):
		self._hydrate_project_context()
		self._sync_scorecard_title()
		self._sync_items_from_profile()
		self._prepare_item_inputs()

	def validate(self):
		self._hydrate_project_context()
		self._sync_scorecard_title()
		self._sync_items_from_profile()
		self._prepare_item_inputs()
		self._validate_unique_stage_instance()
		self._validate_required_items()
		if should_calculate_scorecard_on_validate(self):
			self.calculate()
		self._prevent_content_edits_outside_draft()

	def on_update(self):
		if cint(self.docstatus) == SCORECARD_AGREED_DOCSTATUS:
			self._update_project_last_score()

	def before_cancel(self):
		if frappe.flags.get("skip_scorecard_cancel_validation"):
			return
		validate_scorecard_cancel_allowed(self)

	def on_cancel(self):
		create_replacement_draft_after_cancel(self)

	def on_submit(self):
		if is_agreed_scorecard(self):
			self._update_project_last_score()

	def get_title(self):
		return self.scorecard_title or build_scorecard_title(self.project, self.stage_at_evaluation) or self.name

	def calculate(self):
		profile = frappe.get_doc("Project Scoring Profile", self.profile)
		criteria_by_name = _load_criteria(profile)
		result = calculate_scorecard_document(self, profile, criteria_by_name)

		for item in self.items:
			calculated_item = result.items.get(item.criterion)
			if not calculated_item:
				continue
			item.criterion_code = calculated_item.criterion_code
			item.normalized_score = calculated_item.normalized_score
			item.weighted_score = calculated_item.weighted_score
			item.weight = calculated_item.weight
			item.gate_pass = 1 if calculated_item.gate_pass else 0

		self.integral_score = result.integral_score
		self.gate_pass = 1 if result.gate_pass else 0
		self.gate_messages = "\n".join(
			_format_gate_messages_for_display(result.messages, self.items, criteria_by_name)
		)
		self.evaluation_date = now_datetime()
		self.profile_snapshot = json.dumps(_profile_snapshot(profile), ensure_ascii=False)

	def recalculate_in_place(self):
		if cint(self.docstatus) in SCORECARD_NON_RECALCULABLE_DOCSTATUSES:
			frappe.throw(_("Submitted or canceled Project Scorecard cannot be recalculated."))

		self.check_permission("write")
		self._prepare_item_inputs()
		self.calculate()
		self._persist_calculation_results()

	def _persist_calculation_results(self):
		parent_values = {fieldname: self.get(fieldname) for fieldname in PARENT_CALCULATION_FIELDS}
		frappe.db.set_value(self.doctype, self.name, parent_values, update_modified=True)

		for item in self.items or []:
			if not item.name:
				continue
			item_values = {fieldname: item.get(fieldname) for fieldname in ITEM_CALCULATION_FIELDS}
			frappe.db.set_value(item.doctype, item.name, item_values, update_modified=False)

		self._refresh_related_gate_checkpoints()

	def _refresh_related_gate_checkpoints(self):
		if not self.stage_instance_at_evaluation:
			return
		from dinext_project_evaluation.scoring.stage_gate_integration import (
			refresh_checkpoints_for_stage_instance,
		)

		refresh_checkpoints_for_stage_instance(self.stage_instance_at_evaluation)

	def _hydrate_project_context(self):
		if not self.project:
			return

		project = frappe.get_cached_doc("Project", self.project)
		self.portfolio = project.get("custom_project_portfolio")
		if not self.stage_at_evaluation:
			self.stage_at_evaluation = project.get("current_stage")
		if not self.stage_instance_at_evaluation:
			self.stage_instance_at_evaluation = project.get("current_stage_instance")

	def _sync_scorecard_title(self):
		self.scorecard_title = build_scorecard_title(self.project, self.stage_at_evaluation)

	def _prevent_locked_edits(self):
		if self.is_new():
			return

		previous = self.get_doc_before_save()
		if previous:
			previous_docstatus = scorecard_docstatus(previous)
		else:
			previous_docstatus = cint(
				frappe.db.get_value(self.doctype, self.name, "docstatus")
			)
		if is_terminal_scorecard(previous_docstatus) and not is_terminal_scorecard(self):
			frappe.throw(
				_("Approved or canceled Project Scorecard cannot be edited. Create a new scorecard instead.")
			)

	def _prevent_content_edits_outside_draft(self):
		if self.is_new() or self.status in SCORECARD_CONTENT_EDITABLE_STATUSES:
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		if previous.status in SCORECARD_CONTENT_EDITABLE_STATUSES:
			return

		_assert_no_immutable_content_changes(previous, self)

	def _sync_items_from_profile(self):
		if not self.project or not self.profile:
			return
		if self.status not in SCORECARD_CONTENT_EDITABLE_STATUSES:
			return
		sync_scorecard_items(self, self.profile)

	def _prepare_item_inputs(self):
		for item in self.items or []:
			input_type = item.get("criterion_input_type")
			item.raw_value = None
			item.raw_numeric_value = None
			item.value_display = None

			if input_type == "Scale":
				item.raw_value = item.get("scale_value") or None
				item.value_display = _scale_value_label(item)
			elif input_type == "Boolean":
				item.raw_value = str(cint(item.get("boolean_value"))) if cint(item.get("boolean_value_set")) else None
				if item.raw_value is not None:
					item.value_display = _("Yes") if cint(item.get("boolean_value")) else _("No")
			elif input_type == "Number":
				item.raw_numeric_value = item.get("number_value") if item.get("number_value") not in ("", None) else None
				item.value_display = _string_value(item.raw_numeric_value)
			elif input_type == "Currency":
				item.raw_numeric_value = item.get("currency_value") if item.get("currency_value") not in ("", None) else None
				item.value_display = _string_value(item.raw_numeric_value)
			elif input_type == "Percent":
				item.raw_numeric_value = item.get("percent_value") if item.get("percent_value") not in ("", None) else None
				item.value_display = _string_value(item.raw_numeric_value)

			if item.value_display is None:
				item.value_display = item.get("value_display")

	def _validate_required_items(self):
		if is_canceled_scorecard(self) or self.status == STATUS_DRAFT:
			return

		if not self.profile:
			return

		profile = frappe.get_doc("Project Scoring Profile", self.profile)
		criteria_by_name = _load_criteria(profile)
		message = scorecard_validation_error_message(self.items, criteria_by_name)
		if message:
			frappe.throw(message)

	def _validate_unique_stage_instance(self):
		if not self.stage_instance_at_evaluation or is_canceled_scorecard(self):
			return

		existing = frappe.db.get_value(
			"Project Scorecard",
			{
				"stage_instance_at_evaluation": self.stage_instance_at_evaluation,
				"name": ["!=", self.name or ""],
				"docstatus": ["!=", SCORECARD_CANCELED_DOCSTATUS],
			},
			"name",
		)
		if existing:
			frappe.throw(
				_("A Project Scorecard already exists for stage instance {0}").format(
					self.stage_instance_at_evaluation
				)
			)

	def _update_project_last_score(self):
		for fieldname, value in {
			"custom_last_scorecard": self.name,
			"custom_last_integral_score": self.integral_score,
			"custom_last_score_date": self.evaluation_date,
		}.items():
			if frappe.get_meta("Project").has_field(fieldname):
				frappe.db.set_value("Project", self.project, fieldname, value, update_modified=False)


def build_scorecard_title(project, stage_at_evaluation) -> str:
	if not project:
		return ""
	title = get_link_title("Project", project) or project
	if stage_at_evaluation:
		stage_title = get_link_title("Project Stage", stage_at_evaluation) or stage_at_evaluation
		return f"{title}: {stage_title}"
	return title


def _load_criteria(profile):
	criteria_names = [row.criterion for row in profile.criteria]
	return {name: frappe.get_doc("Project Scoring Criterion", name) for name in criteria_names}


def _format_gate_messages_for_display(messages, items, criteria_by_name):
	criterion_names = _build_criterion_display_names(items, criteria_by_name)
	display_messages = []
	for message in messages:
		code = _criterion_code_from_gate_message(message)
		if not code:
			display_messages.append(message)
			continue

		display_name = criterion_names.get(code)
		if not display_name:
			display_messages.append(message)
			continue

		if message.startswith(MANDATORY_MISSING_PREFIX):
			display_messages.append(f"{MANDATORY_MISSING_PREFIX}{display_name}")
			continue

		parts = message.split(" ", 1)
		suffix = parts[1] if len(parts) > 1 else ""
		display_messages.append(f"{display_name} {suffix}".rstrip())

	return display_messages


def _build_criterion_display_names(items, criteria_by_name):
	names = {}
	for item in items or []:
		criterion = _doc_value(item, "criterion")
		if not criterion:
			continue
		display_name = _doc_value(item, "criterion_name")
		if display_name:
			names[criterion] = display_name

	for code, criterion_doc in criteria_by_name.items():
		names.setdefault(code, _doc_value(criterion_doc, "criterion_name") or code)

	return names


def _criterion_code_from_gate_message(message):
	if message.startswith(MANDATORY_MISSING_PREFIX):
		return message[len(MANDATORY_MISSING_PREFIX) :].strip() or None

	parts = message.split(" ", 1)
	return parts[0] if parts else None


def _profile_snapshot(profile):
	return {
		"profile": profile.name,
		"criteria": [
			{
				"criterion": row.criterion,
				"weight": row.weight,
				"requirement_level": row.requirement_level,
				"minimum_normalized_score": row.minimum_normalized_score,
				"minimum_raw_value": row.minimum_raw_value,
				"maximum_raw_value": row.maximum_raw_value,
				"stage": row.stage,
				"applicable_stages": get_applicable_stages(row),
			}
			for row in profile.criteria
		],
	}


def _scale_value_label(item):
	raw_value = item.get("scale_value") or item.get("raw_value")
	if raw_value in (None, ""):
		return None
	try:
		options = json.loads(item.get("scale_options_json") or "[]")
	except (TypeError, ValueError):
		return str(raw_value)
	for option in options:
		if str(option.get("value")) == str(raw_value):
			return option.get("label") or str(raw_value)
	return str(raw_value)


def _string_value(value):
	if value in (None, ""):
		return None
	return str(value)


def _assert_no_immutable_content_changes(previous, current):
	for fieldname in PARENT_IMMUTABLE_OUTSIDE_DRAFT:
		if _field_value_changed(_doc_value(previous, fieldname), _doc_value(current, fieldname)):
			_raise_content_locked()

	_previous_items = _items_by_criterion(getattr(previous, "items", None))
	_current_items = _items_by_criterion(getattr(current, "items", None))

	if set(_previous_items) != set(_current_items):
		_raise_content_locked()

	for criterion, previous_row in _previous_items.items():
		current_row = _current_items.get(criterion)
		if not current_row:
			_raise_content_locked()

		for fieldname in ITEM_STRUCTURE_FIELDS:
			if _field_value_changed(_doc_value(previous_row, fieldname), _doc_value(current_row, fieldname)):
				_raise_content_locked()

		for fieldname in ITEM_USER_EDITABLE_VALUE_FIELDS:
			if _field_value_changed(_doc_value(previous_row, fieldname), _doc_value(current_row, fieldname)):
				_raise_content_locked()


def _doc_value(doc, fieldname):
	if doc is None:
		return None
	if hasattr(doc, "get"):
		return doc.get(fieldname)
	return getattr(doc, fieldname, None)


def _items_by_criterion(items):
	rows = {}
	for item in _iter_child_rows(items):
		criterion = item.get("criterion") if hasattr(item, "get") else getattr(item, "criterion", None)
		if criterion:
			rows[criterion] = item
	return rows


def _iter_child_rows(items):
	if items is None:
		return []
	if callable(items):
		return list(items() or [])
	return list(items)


def _field_value_changed(previous_value, current_value):
	return _normalize_field_value(previous_value) != _normalize_field_value(current_value)


def _normalize_field_value(value):
	if value in (None, ""):
		return None
	if isinstance(value, float):
		return float(value)
	if isinstance(value, int):
		return int(value)
	if isinstance(value, str):
		stripped = value.strip()
		return stripped or None
	return value


def _raise_content_locked():
	frappe.throw(
		_("Project Scorecard can only be edited in Draft. Change status to Draft or create a new scorecard.")
	)
