import frappe

from dinext_project_evaluation.scoring.workflow_constants import STATUS_REVIEWED


def execute():
	"""Map legacy Calculated status to Reviewed after workflow rollout."""
	frappe.db.sql(
		"""
		UPDATE `tabProject Scorecard`
		SET status = %s
		WHERE status = 'Calculated'
		""",
		(STATUS_REVIEWED,),
	)
