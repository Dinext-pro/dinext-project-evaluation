from __future__ import annotations

import frappe
from frappe import _

from dinext_project_evaluation.scoring.scorecard_factory import (
	cancel_project_scorecards,
	ensure_scorecard_for_stage_instance,
	get_project_scoring_profile_fieldname,
	project_has_non_canceled_scorecards,
)

GOVERNANCE_MODEL_FIELD = "governance_model"
CONFIRM_GOVERNANCE_RESET_FIELD = "confirm_governance_reset"
CONFIRM_SCORING_PROFILE_RESET_FIELD = "confirm_scoring_profile_reset"


def _project_has_field(fieldname: str) -> bool:
	return frappe.get_meta("Project").has_field(fieldname)


def _get_db_value(project: str, fieldname: str):
	if not _project_has_field(fieldname):
		return None
	return frappe.db.get_value("Project", project, fieldname)


def _field_changed(doc, fieldname: str) -> bool:
	if doc.is_new() or not doc.name:
		return False
	if not _project_has_field(fieldname):
		return False
	previous = _get_db_value(doc.name, fieldname)
	next_value = doc.get(fieldname)
	return previous != next_value


def _governance_model_changed(doc) -> bool:
	return _field_changed(doc, GOVERNANCE_MODEL_FIELD)


def _scoring_profile_changed(doc) -> bool:
	return _field_changed(doc, get_project_scoring_profile_fieldname())


def validate_project_scoring_profile_change(doc, method=None):
	if doc.is_new() or not doc.name:
		return

	fieldname = get_project_scoring_profile_fieldname()
	if not _project_has_field(fieldname):
		return

	if _governance_model_changed(doc):
		if project_has_non_canceled_scorecards(doc.name) and not int(
			doc.get(CONFIRM_GOVERNANCE_RESET_FIELD) or 0
		):
			frappe.throw(
				_(
					"Changing or clearing Governance Model will cancel all Project Scorecards "
					"and reset the Project Scoring Profile for this project. "
					"Confirm on the Project form, then save again."
				),
				frappe.ValidationError,
			)
		return

	if not _scoring_profile_changed(doc):
		return

	if not project_has_non_canceled_scorecards(doc.name):
		return

	if not int(doc.get(CONFIRM_SCORING_PROFILE_RESET_FIELD) or 0):
		frappe.throw(
			_(
				"Changing or clearing Project Scoring Profile will cancel all Project Scorecards "
				"for this project. Confirm on the Project form, then save again."
			),
			frappe.ValidationError,
		)


def before_save_project_scoring_profile_reset(doc, method=None):
	if doc.is_new():
		return

	fieldname = get_project_scoring_profile_fieldname()
	if not _project_has_field(fieldname):
		return

	if _governance_model_changed(doc):
		has_scorecards = project_has_non_canceled_scorecards(doc.name)
		if has_scorecards:
			if not int(doc.get(CONFIRM_GOVERNANCE_RESET_FIELD) or 0):
				return
			cancel_project_scorecards(doc.name)

		doc.set(fieldname, None)
		doc.set(CONFIRM_SCORING_PROFILE_RESET_FIELD, 0)
		return

	if not _scoring_profile_changed(doc):
		doc.set(CONFIRM_SCORING_PROFILE_RESET_FIELD, 0)
		return

	if not int(doc.get(CONFIRM_SCORING_PROFILE_RESET_FIELD) or 0):
		return

	cancel_project_scorecards(doc.name)
	doc.set(CONFIRM_SCORING_PROFILE_RESET_FIELD, 0)


def _get_current_stage_instance(doc) -> str | None:
	stage_instance = doc.get("current_stage_instance")
	if stage_instance:
		return stage_instance
	if doc.is_new() or not doc.name:
		return None
	if not _project_has_field("current_stage_instance"):
		return None
	return _get_db_value(doc.name, "current_stage_instance")


def after_save_project_scoring_profile(doc, method=None):
	if not doc.name:
		return

	fieldname = get_project_scoring_profile_fieldname()
	if not _project_has_field(fieldname):
		return

	if not doc.get(fieldname):
		return

	stage_instance_name = _get_current_stage_instance(doc)
	if not stage_instance_name:
		return

	if not frappe.db.exists("DocType", "Project Stage Instance"):
		return

	stage_instance = frappe.get_cached_doc("Project Stage Instance", stage_instance_name)
	if stage_instance.status == "Active":
		ensure_scorecard_for_stage_instance(stage_instance)
