import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils import now_datetime

from dinext_project_evaluation.scoring.profile_stages import get_applicable_stages
from dinext_project_evaluation.scoring.scorecard_factory import sync_scorecard_items
from dinext_project_evaluation.scoring.scorecard_service import (
	calculate_scorecard_document,
	scorecard_has_missing_required_items,
)
from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_CALCULATION_STATUSES,
	SCORECARD_LOCKED_STATUSES,
	STATUS_CANCELED,
	STATUS_DRAFT,
)


class ProjectScorecard(Document):
	def before_save(self):
		self._prevent_locked_edits()

	def onload(self):
		self._hydrate_project_context()
		self._sync_items_from_profile()
		self._prepare_item_inputs()

	def validate(self):
		self._hydrate_project_context()
		self._sync_items_from_profile()
		self._prepare_item_inputs()
		self._validate_unique_stage_instance()
		self._validate_required_items()
		if self.status in SCORECARD_CALCULATION_STATUSES:
			self.calculate()

	def on_update(self):
		if self.status in SCORECARD_CALCULATION_STATUSES:
			self._update_project_last_score()

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
		self.gate_messages = "\n".join(result.messages)
		self.evaluation_date = now_datetime()
		self.profile_snapshot = json.dumps(_profile_snapshot(profile), ensure_ascii=False)

	def _hydrate_project_context(self):
		if not self.project:
			return

		project = frappe.get_cached_doc("Project", self.project)
		self.portfolio = project.get("custom_project_portfolio")
		if not self.stage_at_evaluation:
			self.stage_at_evaluation = project.get("current_stage")
		if not self.stage_instance_at_evaluation:
			self.stage_instance_at_evaluation = project.get("current_stage_instance")

	def _prevent_locked_edits(self):
		if self.is_new() or self.status in SCORECARD_LOCKED_STATUSES:
			return

		previous_status = frappe.db.get_value(self.doctype, self.name, "status")
		if previous_status in SCORECARD_LOCKED_STATUSES:
			frappe.throw(
				_("Approved or canceled Project Scorecard cannot be edited. Create a new scorecard instead.")
			)

	def _sync_items_from_profile(self):
		if not self.project or not self.profile:
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
		if self.status == STATUS_CANCELED or self.status == STATUS_DRAFT:
			return

		if scorecard_has_missing_required_items(self.items):
			frappe.throw(_("Mandatory fields required in {0}").format(_("Items")))

	def _validate_unique_stage_instance(self):
		if not self.stage_instance_at_evaluation or self.status == STATUS_CANCELED:
			return

		existing = frappe.db.get_value(
			"Project Scorecard",
			{
				"stage_instance_at_evaluation": self.stage_instance_at_evaluation,
				"name": ["!=", self.name or ""],
				"status": ["!=", "Canceled"],
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


def _load_criteria(profile):
	criteria_names = [row.criterion for row in profile.criteria]
	return {name: frappe.get_doc("Project Scoring Criterion", name) for name in criteria_names}


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
