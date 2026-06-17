from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_AGREED_DOCSTATUS,
	SCORECARD_CANCELED_DOCSTATUS,
	get_scorecard_status_label,
	is_agreed_scorecard,
	is_canceled_scorecard,
	is_terminal_scorecard,
	should_calculate_scorecard_on_validate,
	workflow_state_targets_docstatus,
)


class TestWorkflowConstants(unittest.TestCase):
	def test_is_agreed_scorecard_uses_docstatus_not_status_label(self):
		self.assertTrue(is_agreed_scorecard(SimpleNamespace(status="Согласовано", docstatus=1)))
		self.assertFalse(is_agreed_scorecard(SimpleNamespace(status="Approved", docstatus=0)))

	def test_is_canceled_scorecard_uses_docstatus_not_status_label(self):
		self.assertTrue(is_canceled_scorecard(SimpleNamespace(status="Отменено", docstatus=2)))
		self.assertFalse(is_canceled_scorecard(SimpleNamespace(status="Canceled", docstatus=0)))

	def test_is_terminal_scorecard(self):
		self.assertTrue(is_terminal_scorecard(1))
		self.assertTrue(is_terminal_scorecard(2))
		self.assertFalse(is_terminal_scorecard(0))

	def test_should_calculate_scorecard_on_validate_skips_canceled_docstatus(self):
		doc = SimpleNamespace(status="Отменено", docstatus=SCORECARD_CANCELED_DOCSTATUS)
		self.assertFalse(should_calculate_scorecard_on_validate(doc))

	def test_should_calculate_scorecard_on_validate_allows_submitted_and_reviewed(self):
		for status in ("Submitted for Review", "Reviewed"):
			doc = SimpleNamespace(status=status, docstatus=0)
			self.assertTrue(should_calculate_scorecard_on_validate(doc))

	def test_should_calculate_scorecard_on_validate_skips_already_submitted(self):
		doc = SimpleNamespace(status="Согласовано", docstatus=SCORECARD_AGREED_DOCSTATUS)
		self.assertFalse(should_calculate_scorecard_on_validate(doc))

	@patch(
		"dinext_project_evaluation.scoring.workflow_constants.frappe.db.get_value",
		return_value="1",
	)
	def test_should_calculate_scorecard_on_validate_uses_workflow_state_for_approve_boundary(
		self, _get_value
	):
		doc = SimpleNamespace(status="Согласовано", docstatus=0)
		self.assertTrue(should_calculate_scorecard_on_validate(doc))

	@patch(
		"dinext_project_evaluation.scoring.workflow_constants.frappe.db.get_value",
		return_value="1",
	)
	def test_workflow_state_targets_docstatus(self, _get_value):
		self.assertTrue(workflow_state_targets_docstatus("Согласовано", SCORECARD_AGREED_DOCSTATUS))
		self.assertFalse(workflow_state_targets_docstatus(None, SCORECARD_AGREED_DOCSTATUS))

	@patch(
		"dinext_project_evaluation.scoring.workflow_constants._",
		side_effect=lambda status: {
			"Reviewed": "Проверено",
			"Submitted for Review": "На проверке",
		}.get(status, status),
	)
	def test_get_scorecard_status_label_uses_translation_lookup(self, _translate):
		self.assertEqual(get_scorecard_status_label("Reviewed"), "Проверено")
		self.assertEqual(get_scorecard_status_label("Submitted for Review"), "На проверке")
		self.assertEqual(get_scorecard_status_label("Unknown"), "Unknown")
		self.assertEqual(get_scorecard_status_label(None), "")
		self.assertEqual(get_scorecard_status_label(""), "")


if __name__ == "__main__":
	unittest.main()
