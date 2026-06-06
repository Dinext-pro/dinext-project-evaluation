import frappe
from frappe import _

from dinext_project_evaluation.scoring.workflow import (
	approve_scorecard_via_workflow,
	mark_scorecard_reviewed,
)
from dinext_project_evaluation.scoring.workflow_constants import SCORECARD_CANCELED_DOCSTATUS
from dinext_project_evaluation.scoring.scorecard_factory import (
	create_draft_scorecard,
	ensure_scorecard_for_stage_instance,
	get_applicable_criteria_for_stage,
	get_project_scoring_profile,
)


@frappe.whitelist()
def get_applicable_criteria(project: str, profile: str, stage: str | None = None):
	project_doc = frappe.get_doc("Project", project)
	current_stage = stage or project_doc.get("current_stage")
	return get_applicable_criteria_for_stage(project, profile, current_stage)


@frappe.whitelist()
def create_scorecard(project: str, profile: str | None = None):
	profile = profile or get_project_scoring_profile(project)
	if not profile:
		frappe.throw(_("Project Scoring Profile must be set on the project."))

	stage_instance = frappe.db.get_value("Project", project, "current_stage_instance")
	if stage_instance and frappe.db.exists("Project Stage Instance", stage_instance):
		instance = frappe.get_doc("Project Stage Instance", stage_instance)
		if instance.status == "Active":
			name = ensure_scorecard_for_stage_instance(instance)
			return frappe.get_doc("Project Scorecard", name).as_dict()

	scorecard = create_draft_scorecard(project, profile)
	return scorecard.as_dict()


@frappe.whitelist()
def calculate_scorecard(scorecard: str):
	"""Apply workflow action Mark Reviewed (replaces legacy Calculated status)."""
	doc = mark_scorecard_reviewed(scorecard)
	return doc.as_dict()


@frappe.whitelist()
def recalculate_scorecard(scorecard: str):
	"""Recalculate integral score and gate in place without changing workflow status."""
	doc = frappe.get_doc("Project Scorecard", scorecard)
	doc.recalculate_in_place()
	doc.reload()
	return doc.as_dict()


@frappe.whitelist()
def approve_scorecard(scorecard: str):
	doc = approve_scorecard_via_workflow(scorecard)
	return doc.as_dict()


@frappe.whitelist()
def get_scorecard_history(project: str, limit: int = 10):
	return frappe.get_all(
		"Project Scorecard",
		filters={"project": project, "docstatus": ["!=", SCORECARD_CANCELED_DOCSTATUS]},
		fields=["name", "profile", "status", "evaluation_date", "integral_score", "gate_pass", "modified"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)
