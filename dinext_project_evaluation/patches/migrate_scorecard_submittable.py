import frappe

from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_AGREED_DOCSTATUS,
	STATUS_APPROVED,
	STATUS_CANCELED,
)


def execute():
	"""Backfill docstatus for submittable Project Scorecard rollout."""
	if not frappe.db.table_exists("tabProject Scorecard"):
		return
	_update_docstatus_for_status(STATUS_APPROVED, SCORECARD_AGREED_DOCSTATUS)
	_update_docstatus_for_status(STATUS_CANCELED, 2)


def _update_docstatus_for_status(status: str, docstatus: int):
	rows = frappe.get_all(
		"Project Scorecard",
		filters={"status": status, "docstatus": 0},
		fields=["name"],
	)
	for row in rows:
		frappe.db.set_value("Project Scorecard", row.name, "docstatus", docstatus, update_modified=False)
