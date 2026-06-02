from __future__ import annotations

import frappe
from frappe import _

from dinext_project_evaluation.scoring.profile_stages import get_applicable_stages

PROJECT_SCORING_PROFILE_FIELD = "custom_project_scoring_profile"


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
		rows.append(
			{
				"criterion": criterion.name,
				"criterion_code": criterion.criterion_code,
				"criterion_name": criterion.criterion_name,
				"criterion_group": criterion.criterion_group,
				"input_type": criterion.input_type,
				"influence_direction": criterion.influence_direction,
				"weight": profile_row.weight,
				"requirement_level": profile_row.requirement_level,
				"scale_rows": [
					{
						"scale_label": scale.scale_label,
						"score": scale.score,
						"sort_order": scale.sort_order,
						"key_phrases": scale.key_phrases,
					}
					for scale in criterion.scale_rows
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

	current_stage = scorecard.stage_at_evaluation or frappe.db.get_value("Project", project, "current_stage")
	for criterion in get_applicable_criteria_for_stage(project, profile, current_stage):
		scorecard.append(
			"items",
			{
				"criterion": criterion["criterion"],
				"criterion_code": criterion["criterion_code"],
				"weight": criterion["weight"],
			},
		)

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
