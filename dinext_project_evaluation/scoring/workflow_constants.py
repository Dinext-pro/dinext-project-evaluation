"""Project Scorecard workflow roles, states, and legacy role mapping."""

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
SCORECARD_CALCULATION_STATUSES = frozenset({STATUS_REVIEWED, STATUS_APPROVED})

# States visible in portfolio/report as finalized scores (agreed = submitted docstatus).
SCORECARD_AGREED_DOCSTATUS = 1

# Legacy status tuple kept for calculation triggers; agreed checks use docstatus.
SCORECARD_REPORT_STATUSES = (STATUS_REVIEWED, STATUS_APPROVED)

# Roles allowed to cancel a scorecard via workflow/native cancel.
SCORECARD_CANCEL_ROLES = frozenset({ROLE_APPROVER})

# Only Draft allows manual edits to criterion values, comments, and row content.
SCORECARD_CONTENT_EDITABLE_STATUSES = frozenset({STATUS_DRAFT})

# Terminal states: workflow must not roll back to an earlier lifecycle state.
SCORECARD_TERMINAL_STATUSES = frozenset({STATUS_APPROVED, STATUS_CANCELED})

# Backward-compatible alias (Approved/Canceled terminal lock).
SCORECARD_LOCKED_STATUSES = SCORECARD_TERMINAL_STATUSES

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
