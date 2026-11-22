"""Workflow defaults for the documents owned by this application."""


def email_profiles():
	approval_states = ("Submitted for Review", "Reviewed")
	rejection_states = ("Rejected", "Отклонено")
	return {
		"Project Scorecard": {
			"workflow": "Dinext Project Scorecard Approval",
			"approval_states": approval_states,
			"migration": {
				"workflow_fields": {
					"send_email_alert": 1,
					"custom_group_workflow_action_emails": 1,
					"custom_group_interval_unit": "Days",
					"custom_group_interval_value": 1,
					"custom_group_send_times": "08:00, 17:00",
					"custom_group_send_time": "08:00:00",
					"custom_group_email_template": "Dinext Workflow Digest",
					"custom_workflow_action_email_template": "Dinext Workflow Action",
					"custom_attach_document_pdf": 0,
				},
				"enabled_states": approval_states + rejection_states,
				"state_overrides": {
					state: {
						"custom_group_workflow_action_emails": 0,
						"next_action_email_template": "Dinext Workflow Correction",
					}
					for state in rejection_states
				},
				"creator_notification_states": rejection_states,
				"suppress_open_tasks_in_states": rejection_states,
			},
		},
	}
