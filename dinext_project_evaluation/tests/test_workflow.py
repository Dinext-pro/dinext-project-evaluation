from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe

from dinext_project_evaluation.scoring.workflow import (
	approve_scorecard_via_workflow,
	mark_scorecard_reviewed,
)


class TestWorkflowMessages(unittest.TestCase):
	@patch(
		"dinext_project_evaluation.scoring.workflow.get_scorecard_status_label",
		return_value="Отклонено",
	)
	@patch("dinext_project_evaluation.scoring.workflow.frappe.get_doc")
	def test_approve_scorecard_shows_localized_current_status(self, get_doc, get_label):
		get_doc.return_value = SimpleNamespace(status="Rejected")

		with self.assertRaises(frappe.ValidationError) as ctx:
			approve_scorecard_via_workflow("PSC-001")

		get_label.assert_called_once_with("Rejected")
		self.assertIn("Отклонено", str(ctx.exception))

	@patch(
		"dinext_project_evaluation.scoring.workflow.get_scorecard_status_label",
		return_value="Согласовано",
	)
	@patch("dinext_project_evaluation.scoring.workflow.frappe.get_doc")
	def test_mark_scorecard_reviewed_shows_localized_current_status(self, get_doc, get_label):
		get_doc.return_value = SimpleNamespace(status="Approved")

		with self.assertRaises(frappe.ValidationError) as ctx:
			mark_scorecard_reviewed("PSC-001")

		get_label.assert_called_once_with("Approved")
		self.assertIn("Согласовано", str(ctx.exception))


if __name__ == "__main__":
	unittest.main()
