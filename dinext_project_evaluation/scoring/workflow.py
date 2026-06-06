"""Helpers for Project Scorecard Frappe Workflow transitions."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow

from dinext_project_evaluation.scoring.workflow_constants import (
	ACTION_APPROVE,
	ACTION_MARK_REVIEWED,
	ACTION_SUBMIT_FOR_REVIEW,
	is_agreed_scorecard,
	is_canceled_scorecard,
	STATUS_DRAFT,
	STATUS_REVIEWED,
	STATUS_SUBMITTED,
)
from dinext_project_evaluation.scoring.scorecard_cancel import cancel_scorecard_document


def apply_scorecard_workflow_action(scorecard: str, action: str) -> frappe.Document:
	"""Run a workflow action on a Project Scorecard and return the updated document."""
	doc = frappe.get_doc("Project Scorecard", scorecard)
	if is_canceled_scorecard(doc):
		frappe.throw(_("Canceled Project Scorecard cannot be updated."))

	apply_workflow(doc, action)
	doc.reload()
	return doc


def mark_scorecard_reviewed(scorecard: str) -> frappe.Document:
	"""Move scorecard to Reviewed; from Draft runs submit + review actions."""
	doc = frappe.get_doc("Project Scorecard", scorecard)
	if is_canceled_scorecard(doc):
		frappe.throw(_("Canceled Project Scorecard cannot be calculated."))
	if doc.status == STATUS_DRAFT:
		apply_workflow(doc, ACTION_SUBMIT_FOR_REVIEW)
		doc.reload()
	if doc.status == STATUS_SUBMITTED:
		apply_workflow(doc, ACTION_MARK_REVIEWED)
		doc.reload()
		return doc
	if doc.status == STATUS_REVIEWED:
		return doc
	frappe.throw(
		_("Project Scorecard must be in Draft or Submitted for Review to calculate. Current status: {0}").format(
			doc.status
		)
	)


def approve_scorecard_via_workflow(scorecard: str) -> frappe.Document:
	doc = frappe.get_doc("Project Scorecard", scorecard)
	if doc.status == STATUS_REVIEWED:
		return apply_scorecard_workflow_action(scorecard, ACTION_APPROVE)
	if is_agreed_scorecard(doc):
		return doc
	frappe.throw(
		_("Project Scorecard must be in Reviewed status to approve. Current status: {0}").format(doc.status)
	)


def cancel_scorecard_via_workflow(scorecard: str, *, skip_permission_checks: bool = False) -> frappe.Document:
	doc = frappe.get_doc("Project Scorecard", scorecard)
	return cancel_scorecard_document(doc, skip_permission_checks=skip_permission_checks)
