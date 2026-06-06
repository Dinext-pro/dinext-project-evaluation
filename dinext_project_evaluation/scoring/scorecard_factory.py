from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint

from dinext_project_evaluation.scoring.profile_stages import get_applicable_stages

PROJECT_SCORING_PROFILE_FIELD = "custom_project_scoring_profile"


def _scale_row_sort_key(scale, index: int) -> tuple:
	sort_order = scale.sort_order
	if sort_order in (None, ""):
		return (1, index, float(scale.score))
	return (0, cint(sort_order), index, float(scale.score))


def build_scale_options(scale_rows) -> list[dict]:
	rows = list(scale_rows or [])
	sorted_rows = sorted(enumerate(rows), key=lambda item: _scale_row_sort_key(item[1], item[0]))
	return [
		{
			"label": scale.scale_label or str(scale.score),
			"value": str(scale.score),
			"score": scale.score,
			"sort_order": scale.sort_order,
			"key_phrases": scale.key_phrases,
		}
		for _, scale in sorted_rows
	]


ITEM_VALUE_FIELDS = (
	"value_display",
	"scale_value",
	"boolean_value",
	"boolean_value_set",
	"number_value",
	"currency_value",
	"percent_value",
	"raw_value",
	"raw_numeric_value",
	"comment",
)


def get_project_scoring_profile_fieldname() -> str:
	meta = frappe.get_meta("Project")
	if meta.has_field(PROJECT_SCORING_PROFILE_FIELD):
		return PROJECT_SCORING_PROFILE_FIELD
	return PROJECT_SCORING_PROFILE_FIELD


def get_project_scoring_profile(project: str) -> str | None:
	fieldname = get_project_scoring_profile_fieldname()
	if not frappe.get_meta("Project").has_field(fieldname):
		return None
	return frappe.db.get_value("Project", project, fieldname)


def get_applicable_criteria_for_stage(project: str, profile: str, current_stage: str | None):
	profile_doc = frappe.get_doc("Project Scoring Profile", profile)
	rows = []

	for profile_row in profile_doc.criteria:
		stages = get_applicable_stages(profile_row)
		if stages and current_stage not in stages:
			continue

		criterion = frappe.get_doc("Project Scoring Criterion", profile_row.criterion)
		scale_options = build_scale_options(criterion.scale_rows)
		rows.append(
			{
				"criterion": criterion.name,
				"criterion_code": criterion.criterion_code,
				"criterion_name": criterion.criterion_name,
				"description": criterion.description,
				"criterion_group": criterion.criterion_group,
				"input_type": criterion.input_type,
				"min_value": criterion.min_value,
				"max_value": criterion.max_value,
				"influence_direction": criterion.influence_direction,
				"weight": profile_row.weight,
				"requirement_level": profile_row.requirement_level,
				"requires_comment": cint(criterion.requires_comment),
				"scale_options": scale_options,
				"scale_rows": [
					{
						"scale_label": option["label"],
						"score": option["score"],
						"sort_order": option.get("sort_order"),
						"key_phrases": option.get("key_phrases"),
					}
					for option in scale_options
				],
			}
		)

	return rows


def find_scorecard_for_stage_instance(stage_instance: str, *, include_canceled: bool = False) -> str | None:
	filters = {"stage_instance_at_evaluation": stage_instance}
	if not include_canceled:
		filters["status"] = ["!=", "Canceled"]
	return frappe.db.get_value("Project Scorecard", filters, "name")


def create_draft_scorecard(
	project: str,
	profile: str,
	*,
	stage_instance: str | None = None,
	stage: str | None = None,
) -> frappe.Document:
	if stage_instance:
		existing = find_scorecard_for_stage_instance(stage_instance)
		if existing:
			return frappe.get_doc("Project Scorecard", existing)

	scorecard = frappe.new_doc("Project Scorecard")
	scorecard.project = project
	scorecard.profile = profile
	scorecard.status = "Draft"

	if stage_instance:
		instance = frappe.get_cached_doc("Project Stage Instance", stage_instance)
		scorecard.stage_at_evaluation = instance.stage
		scorecard.stage_instance_at_evaluation = instance.name
	elif stage:
		scorecard.stage_at_evaluation = stage

	sync_scorecard_items(scorecard, profile)
	scorecard.insert()
	return scorecard


def ensure_scorecard_for_stage_instance(stage_instance_doc) -> str | None:
	if stage_instance_doc.status != "Active":
		return None

	profile = get_project_scoring_profile(stage_instance_doc.project)
	if not profile:
		return None

	existing = find_scorecard_for_stage_instance(stage_instance_doc.name)
	if existing:
		return existing

	scorecard = create_draft_scorecard(
		stage_instance_doc.project,
		profile,
		stage_instance=stage_instance_doc.name,
	)
	return scorecard.name


def cancel_project_scorecards(project: str) -> list[str]:
	scorecard_names = frappe.get_all(
		"Project Scorecard",
		filters={"project": project, "status": ["!=", "Canceled"]},
		pluck="name",
	)
	canceled = []
	for name in scorecard_names:
		doc = frappe.get_doc("Project Scorecard", name)
		doc.status = "Canceled"
		doc.save(ignore_permissions=True)
		canceled.append(name)

	_clear_project_last_score_fields(project)
	return canceled


def _clear_project_last_score_fields(project: str) -> None:
	meta = frappe.get_meta("Project")
	values = {}
	for fieldname in ("custom_last_scorecard", "custom_last_integral_score", "custom_last_score_date"):
		if meta.has_field(fieldname):
			values[fieldname] = None
	if values:
		frappe.db.set_value("Project", project, values, update_modified=False)


def project_has_non_canceled_scorecards(project: str) -> bool:
	return bool(
		frappe.db.exists(
			"Project Scorecard",
			{"project": project, "status": ["!=", "Canceled"]},
		)
	)


def sync_scorecard_items(scorecard, profile: str | None = None) -> None:
	profile_name = profile or getattr(scorecard, "profile", None)
	project = getattr(scorecard, "project", None)
	if not profile_name or not project:
		return

	current_stage = getattr(scorecard, "stage_at_evaluation", None) or frappe.db.get_value(
		"Project", project, "current_stage"
	)
	existing_rows = {
		getattr(item, "criterion", None): item
		for item in list(getattr(scorecard, "items", None) or [])
		if getattr(item, "criterion", None)
	}
	items = []
	for criterion in get_applicable_criteria_for_stage(project, profile_name, current_stage):
		existing_row = existing_rows.get(criterion["criterion"])
		item = {
			"criterion": criterion["criterion"],
			"criterion_code": criterion["criterion_code"],
			"criterion_name": criterion["criterion_name"],
			"criterion_input_type": criterion["input_type"],
			"criterion_min_value": criterion.get("min_value"),
			"criterion_max_value": criterion.get("max_value"),
			"weight": criterion["weight"],
			"requirement_level": criterion.get("requirement_level") or "Desired",
			"requires_comment": cint(criterion.get("requires_comment")),
			"scale_options_json": json.dumps(criterion.get("scale_options", []), ensure_ascii=False),
			"value_display": None,
			"scale_value": None,
			"boolean_value": 0,
			"boolean_value_set": 0,
			"number_value": None,
			"currency_value": None,
			"percent_value": None,
			"raw_value": None,
			"raw_numeric_value": None,
			"comment": None,
		}
		if existing_row:
			for fieldname in ITEM_VALUE_FIELDS:
				if hasattr(existing_row, fieldname):
					item[fieldname] = getattr(existing_row, fieldname)
		item["value_display"] = item["value_display"] or _compact_value_display(
			criterion["input_type"],
			item,
			criterion.get("scale_options", []),
		)
		items.append(item)

	_set_table_value(scorecard, "items", items)


def _set_table_value(document, fieldname: str, value) -> None:
	if hasattr(document, "set"):
		document.set(fieldname, value)
		return
	setattr(document, fieldname, value)


def _compact_value_display(input_type: str, item: dict, scale_options: list[dict]) -> str | None:
	if input_type == "Scale":
		raw_value = item.get("scale_value") or item.get("raw_value")
		if raw_value in (None, ""):
			return None
		for option in scale_options or []:
			if str(option.get("value")) == str(raw_value):
				return option.get("label") or str(raw_value)
		return str(raw_value)

	if input_type == "Boolean":
		if item.get("boolean_value_set"):
			return _("Yes") if item.get("boolean_value") else _("No")
		raw_value = item.get("raw_value")
		if raw_value in (None, ""):
			return None
		return _("Yes") if str(raw_value).lower() in {"1", "true", "yes", "да"} else _("No")

	if input_type == "Number":
		value = item.get("number_value")
	elif input_type == "Currency":
		value = item.get("currency_value")
	elif input_type == "Percent":
		value = item.get("percent_value")
	else:
		value = item.get("raw_numeric_value") if item.get("raw_numeric_value") not in (None, "") else item.get("raw_value")

	if value in (None, ""):
		return None
	return str(value)
