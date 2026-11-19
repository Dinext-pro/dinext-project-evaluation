"""Workflow defaults for the documents owned by this application."""


def email_profiles():
	return {
		"Project Scorecard": {"workflow": "Dinext Project Scorecard Approval", "approval_states": ('Submitted for Review', 'Reviewed')},
	}
