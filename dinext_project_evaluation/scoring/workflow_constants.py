"""Project Scorecard workflow roles, states, and legacy role mapping."""

from __future__ import annotations

import frappe
from frappe.utils import cint

WORKFLOW_NAME = "Dinext Project Scorecard Approval"

ROLE_AUTHOR = "Project Scorecard Author"
ROLE_REVIEWER = "Project Scorecard Reviewer"
ROLE_APPROVER = "Project Scorecard Approver"
ROLE_ADMIN = "Project Scorecard Admin"

SCORECARD_WORKFLOW_ROLES = (
	ROLE_AUTHOR,
	ROLE_REVIEWER,
	ROLE_APPROVER,
	ROLE_ADMIN,
)

STATUS_DRAFT = "Draft"
STATUS_SUBMITTED = "Submitted for Review"
STATUS_REVIEWED = "Reviewed"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_CANCELED = "Canceled"

SCORECARD_WORKFLOW_STATES = (
	STATUS_DRAFT,
	STATUS_SUBMITTED,
	STATUS_REVIEWED,
	STATUS_APPROVED,
	STATUS_REJECTED,
	STATUS_CANCELED,
)

# States where integral score / gate are calculated on save.
SCORECARD_CALCULATION_STATUSES = frozenset(
	{STATUS_SUBMITTED, STATUS_REVIEWED, STATUS_APPROVED}
)

# States visible in portfolio/report as finalized scores (agreed = submitted docstatus).
SCORECARD_AGREED_DOCSTATUS = 1
SCORECARD_CANCELED_DOCSTATUS = 2

# docstatus values where manual in-place recalculation is blocked.
SCORECARD_NON_RECALCULABLE_DOCSTATUSES = frozenset(
	{SCORECARD_AGREED_DOCSTATUS, SCORECARD_CANCELED_DOCSTATUS}
)

# Deprecated: portfolio/report filters use docstatus; kept for backward compatibility only.
SCORECARD_REPORT_STATUSES = (STATUS_REVIEWED, STATUS_APPROVED)

# Roles allowed to cancel a scorecard via workflow/native cancel.
SCORECARD_CANCEL_ROLES = frozenset({ROLE_APPROVER})

# Only Draft allows manual edits to criterion values, comments, and row content.
SCORECARD_CONTENT_EDITABLE_STATUSES = frozenset({STATUS_DRAFT})

# Legacy fixture/migration names only; business checks use docstatus helpers below.
SCORECARD_TERMINAL_STATUSES = frozenset({STATUS_APPROVED, STATUS_CANCELED})

# Backward-compatible alias (Approved/Canceled terminal lock).
SCORECARD_LOCKED_STATUSES = SCORECARD_TERMINAL_STATUSES


def scorecard_docstatus(doc_or_value) -> int:
	if isinstance(doc_or_value, (int, float, str)):
		return cint(doc_or_value)
	return cint(getattr(doc_or_value, "docstatus", 0))


def is_agreed_scorecard(doc_or_docstatus) -> bool:
	return scorecard_docstatus(doc_or_docstatus) == SCORECARD_AGREED_DOCSTATUS


def is_canceled_scorecard(doc_or_docstatus) -> bool:
	return scorecard_docstatus(doc_or_docstatus) == SCORECARD_CANCELED_DOCSTATUS


def is_terminal_scorecard(doc_or_docstatus) -> bool:
	return scorecard_docstatus(doc_or_docstatus) in SCORECARD_NON_RECALCULABLE_DOCSTATUSES


def workflow_state_targets_docstatus(state: str | None, target_docstatus: int) -> bool:
	if not state:
		return False
	doc_status = frappe.db.get_value(
		"Workflow Document State",
		{
			"parent": WORKFLOW_NAME,
			"parenttype": "Workflow",
			"state": state,
		},
		"doc_status",
	)
	return cint(doc_status) == cint(target_docstatus)


def get_workflow_state_for_docstatus(target_docstatus: int) -> str | None:
	return frappe.db.get_value(
		"Workflow Document State",
		{
			"parent": WORKFLOW_NAME,
			"parenttype": "Workflow",
			"doc_status": str(cint(target_docstatus)),
		},
		"state",
	)


def should_calculate_scorecard_on_validate(doc) -> bool:
	if is_canceled_scorecard(doc):
		return False
	if doc.status in {STATUS_SUBMITTED, STATUS_REVIEWED}:
		return True
	if is_agreed_scorecard(doc):
		return False
	return workflow_state_targets_docstatus(doc.status, SCORECARD_AGREED_DOCSTATUS)

ACTION_SUBMIT_FOR_REVIEW = "Submit for Review"
ACTION_RETURN_TO_DRAFT = "Return to Draft"
ACTION_MARK_REVIEWED = "Mark Reviewed"
ACTION_REQUEST_REWORK = "Request Rework"
ACTION_REJECT = "Reject"
ACTION_APPROVE = "Approve"
ACTION_CANCEL = "Cancel"

SCORECARD_WORKFLOW_ACTIONS = (
	ACTION_SUBMIT_FOR_REVIEW,
	ACTION_RETURN_TO_DRAFT,
	ACTION_MARK_REVIEWED,
	ACTION_REQUEST_REWORK,
	ACTION_REJECT,
	ACTION_APPROVE,
	ACTION_CANCEL,
)

# Optional mapping for assigning scorecard roles from existing Dinext roles.
LEGACY_ROLE_TO_SCORECARD = {
	"Dinext_Project_Manager": ROLE_AUTHOR,
	"Project Governance Admin": ROLE_ADMIN,
}
