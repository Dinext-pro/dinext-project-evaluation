import frappe

from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_AGREED_DOCSTATUS,
	STATUS_APPROVED,
	STATUS_CANCELED,
)


def execute():
	"""Backfill docstatus for submittable Project Scorecard rollout."""
	frappe.db.sql(
		"""
		UPDATE `tabProject Scorecard`
		SET docstatus = %s
		WHERE status = %s
			AND docstatus = 0
		""",
		(SCORECARD_AGREED_DOCSTATUS, STATUS_APPROVED),
	)
	frappe.db.sql(
		"""
		UPDATE `tabProject Scorecard`
		SET docstatus = 2
		WHERE status = %s
			AND docstatus = 0
		""",
		(STATUS_CANCELED,),
	)
