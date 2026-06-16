import frappe
from frappe import _

from dinext_project_evaluation.scoring.workflow import (
	approve_scorecard_via_workflow,
	mark_scorecard_reviewed,
)
from dinext_project_evaluation.scoring.scorecard_factory import (
	create_draft_scorecard,
	ensure_scorecard_for_stage_instance,
	get_applicable_criteria_for_stage,
	get_project_scoring_profile,
)
from dinext_project_evaluation.scoring.stage_gate_integration import (
	get_checkpoint_scorecard_summary_for_api,
)


def _get_permitted_doc(doctype: str, name: str, ptype: str = "read"):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission(ptype)
	return doc


@frappe.whitelist()
def get_applicable_criteria(project: str, profile: str, stage: str | None = None):
	project_doc = _get_permitted_doc("Project", project)
	_get_permitted_doc("Project Scoring Profile", profile)
	current_stage = stage or project_doc.get("current_stage")
	return get_applicable_criteria_for_stage(project, profile, current_stage)


@frappe.whitelist()
def create_scorecard(project: str, profile: str | None = None):
	project_doc = _get_permitted_doc("Project", project)
	profile = profile or get_project_scoring_profile(project)
	if not profile:
		frappe.throw(_("Project Scoring Profile must be set on the project."))
	_get_permitted_doc("Project Scoring Profile", profile)

	stage_instance = frappe.db.get_value("Project", project, "current_stage_instance")
	if stage_instance and frappe.db.exists("Project Stage Instance", stage_instance):
		instance = _get_permitted_doc("Project Stage Instance", stage_instance)
		if instance.status == "Active":
			name = ensure_scorecard_for_stage_instance(instance)
			if name:
				return _get_permitted_doc("Project Scorecard", name).as_dict()

	scorecard = create_draft_scorecard(project, profile)
	scorecard.check_permission("read")
	return scorecard.as_dict()


@frappe.whitelist()
def calculate_scorecard(scorecard: str):
	"""Apply workflow action Mark Reviewed (replaces legacy Calculated status)."""
	_get_permitted_doc("Project Scorecard", scorecard, "write")
	doc = mark_scorecard_reviewed(scorecard)
	return doc.as_dict()


@frappe.whitelist()
def recalculate_scorecard(scorecard: str):
	"""Recalculate integral score and gate in place without changing workflow status."""
	doc = _get_permitted_doc("Project Scorecard", scorecard, "write")
	doc.recalculate_in_place()
	doc.reload()
	return doc.as_dict()


@frappe.whitelist()
def approve_scorecard(scorecard: str):
	_get_permitted_doc("Project Scorecard", scorecard, "write")
	doc = approve_scorecard_via_workflow(scorecard)
	return doc.as_dict()


@frappe.whitelist()
def get_checkpoint_scorecard_summary(checkpoint: str):
	"""Return normalized scorecard summary for a Project Gate Checkpoint form refresh."""
	_get_permitted_doc("Project Gate Checkpoint", checkpoint)
	return get_checkpoint_scorecard_summary_for_api(checkpoint)
