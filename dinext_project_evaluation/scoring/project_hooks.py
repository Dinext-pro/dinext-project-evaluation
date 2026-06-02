from __future__ import annotations

import frappe
from frappe import _

from dinext_project_evaluation.scoring.scorecard_factory import (
	cancel_project_scorecards,
	ensure_scorecard_for_stage_instance,
	get_project_scoring_profile_fieldname,
	project_has_non_canceled_scorecards,
)


def validate_project_scoring_profile_change(doc, method=None):
	if doc.is_new() or not doc.name:
		return

	fieldname = get_project_scoring_profile_fieldname()
	if not frappe.get_meta("Project").has_field(fieldname):
		return

	previous_profile = frappe.db.get_value("Project", doc.name, fieldname)
	next_profile = doc.get(fieldname)
	if previous_profile == next_profile:
		return

	if not project_has_non_canceled_scorecards(doc.name):
		return

	if not int(doc.get("confirm_scoring_profile_reset") or 0):
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
	if not frappe.get_meta("Project").has_field(fieldname):
		return

	previous_profile = frappe.db.get_value("Project", doc.name, fieldname)
	next_profile = doc.get(fieldname)
	if previous_profile == next_profile:
		doc.confirm_scoring_profile_reset = 0
		return

	if not int(doc.get("confirm_scoring_profile_reset") or 0):
		return

	cancel_project_scorecards(doc.name)
	doc.confirm_scoring_profile_reset = 0


def after_save_project_scoring_profile(doc, method=None):
	if doc.is_new() or not doc.name:
		return

	fieldname = get_project_scoring_profile_fieldname()
	if not frappe.get_meta("Project").has_field(fieldname):
		return

	if not doc.get(fieldname):
		return

	if not doc.get("current_stage_instance"):
		return

	if not frappe.db.exists("DocType", "Project Stage Instance"):
		return

	stage_instance = frappe.get_cached_doc("Project Stage Instance", doc.current_stage_instance)
	if stage_instance.status == "Active":
		ensure_scorecard_for_stage_instance(stage_instance)
