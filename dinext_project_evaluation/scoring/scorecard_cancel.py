from __future__ import annotations

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import cint

from dinext_project_evaluation.scoring.scorecard_factory import (
	create_draft_scorecard,
	find_scorecard_for_stage_instance,
)
from dinext_project_evaluation.scoring.workflow_constants import (
	ACTION_CANCEL,
	SCORECARD_CANCEL_ROLES,
	SCORECARD_CANCELED_DOCSTATUS,
	STATUS_CANCELED,
	get_workflow_state_for_docstatus,
	is_canceled_scorecard,
)


def user_can_cancel_scorecard(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return bool(SCORECARD_CANCEL_ROLES.intersection(set(frappe.get_roles(user))))


def stage_instance_is_active(stage_instance: str | None) -> bool:
	if not stage_instance:
		return False
	if not frappe.db.exists("DocType", "Project Stage Instance"):
		return False
	return frappe.db.get_value("Project Stage Instance", stage_instance, "status") == "Active"


def validate_scorecard_cancel_allowed(doc) -> None:
	if not user_can_cancel_scorecard():
		frappe.throw(_("Only a Project Scorecard approver can cancel this scorecard."))

	if not stage_instance_is_active(getattr(doc, "stage_instance_at_evaluation", None)):
		frappe.throw(
			_("Project Scorecard can only be canceled while its evaluation stage instance is Active.")
		)


def create_replacement_draft_after_cancel(canceled_doc) -> str | None:
	stage_instance = getattr(canceled_doc, "stage_instance_at_evaluation", None)
	if not stage_instance or not stage_instance_is_active(stage_instance):
		return None

	if find_scorecard_for_stage_instance(stage_instance):
		return None

	profile = getattr(canceled_doc, "profile", None)
	project = getattr(canceled_doc, "project", None)
	if not profile or not project:
		return None

	replacement = create_draft_scorecard(
		project,
		profile,
		stage_instance=stage_instance,
	)
	return replacement.name


def cancel_scorecard_document(doc, *, skip_permission_checks: bool = False) -> frappe.Document:
	if is_canceled_scorecard(doc):
		return doc

	if skip_permission_checks:
		frappe.flags.skip_scorecard_cancel_validation = True

	try:
		if not skip_permission_checks:
			validate_scorecard_cancel_allowed(doc)

		cancel_transitions = [
			transition
			for transition in get_transitions(doc)
			if transition.action == ACTION_CANCEL
		]
		if cancel_transitions:
			apply_workflow(doc, ACTION_CANCEL)
			doc.reload()
			return doc

		canceled_status = get_workflow_state_for_docstatus(SCORECARD_CANCELED_DOCSTATUS) or STATUS_CANCELED
		doc.status = canceled_status
		if cint(doc.docstatus) == 1:
			doc.cancel()
		elif cint(doc.docstatus) == 0:
			frappe.db.set_value(
				doc.doctype,
				doc.name,
				{"status": canceled_status, "docstatus": SCORECARD_CANCELED_DOCSTATUS},
				update_modified=True,
			)
			doc.status = canceled_status
			doc.docstatus = SCORECARD_CANCELED_DOCSTATUS
			create_replacement_draft_after_cancel(doc)
		doc.reload()
		return doc
	finally:
		if skip_permission_checks:
			frappe.flags.skip_scorecard_cancel_validation = False


def cancel_project_scorecards(project: str) -> list[str]:
	scorecard_names = frappe.get_all(
		"Project Scorecard",
		filters={"project": project, "docstatus": ["!=", SCORECARD_CANCELED_DOCSTATUS]},
		pluck="name",
	)
	canceled = []
	for name in scorecard_names:
		doc = frappe.get_doc("Project Scorecard", name)
		cancel_scorecard_document(doc, skip_permission_checks=True)
		canceled.append(name)

	from dinext_project_evaluation.scoring.scorecard_factory import _clear_project_last_score_fields

	_clear_project_last_score_fields(project)
	return canceled
