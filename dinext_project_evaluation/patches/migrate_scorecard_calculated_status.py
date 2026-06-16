import frappe

from dinext_project_evaluation.scoring.workflow_constants import STATUS_REVIEWED


def execute():
	"""Map legacy Calculated status to Reviewed after workflow rollout."""
	if not frappe.db.table_exists("tabProject Scorecard"):
		return
	rows = frappe.get_all(
		"Project Scorecard",
		filters={"status": "Calculated"},
		fields=["name"],
	)
	for row in rows:
		frappe.db.set_value("Project Scorecard", row.name, "status", STATUS_REVIEWED, update_modified=False)
