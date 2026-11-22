from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import frappe

from dinext_project_evaluation.scoring import scorecard_cancel, scorecard_factory


class TestScorecardCancel(unittest.TestCase):
	@patch("dinext_project_evaluation.scoring.scorecard_cancel.frappe.get_roles", return_value=["Project Scorecard Approver"])
	def test_user_can_cancel_scorecard(self, _roles):
		self.assertTrue(scorecard_cancel.user_can_cancel_scorecard("approver@example.com"))

	@patch("dinext_project_evaluation.scoring.scorecard_cancel.frappe.get_roles", return_value=["Project Scorecard Author"])
	def test_user_cannot_cancel_scorecard_without_approver_role(self, _roles):
		self.assertFalse(scorecard_cancel.user_can_cancel_scorecard("author@example.com"))

	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.db.get_value",
		return_value="Active",
	)
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.db.exists",
		return_value=True,
	)
	def test_stage_instance_is_active(self, _exists, _get_value):
		self.assertTrue(scorecard_cancel.stage_instance_is_active("STAGE-001"))

	@patch("dinext_project_evaluation.scoring.scorecard_cancel.frappe.get_roles", return_value=["Project Scorecard Author"])
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.db.get_value",
		return_value="Active",
	)
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.db.exists",
		return_value=True,
	)
	def test_validate_cancel_requires_approver_role(self, _exists, _get_value, _roles):
		doc = SimpleNamespace(stage_instance_at_evaluation="STAGE-001")
		with self.assertRaises(frappe.ValidationError):
			scorecard_cancel.validate_scorecard_cancel_allowed(doc)

	@patch("dinext_project_evaluation.scoring.scorecard_cancel.frappe.get_roles", return_value=["Project Scorecard Approver"])
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.db.get_value",
		return_value="Completed",
	)
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.db.exists",
		return_value=True,
	)
	def test_validate_cancel_requires_active_stage(self, _exists, _get_value, _roles):
		doc = SimpleNamespace(stage_instance_at_evaluation="STAGE-001")
		with self.assertRaises(frappe.ValidationError):
			scorecard_cancel.validate_scorecard_cancel_allowed(doc)

	@patch.object(scorecard_cancel, "find_scorecard_for_stage_instance", return_value=None)
	@patch.object(scorecard_factory, "find_scorecard_for_stage_instance", return_value=None)
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.stage_instance_is_active",
		return_value=True,
	)
	def test_cancel_creates_a_system_draft_when_approver_cannot_create_by_hand(
		self, _active, _find_factory, _find_cancel
	):
		canceled = SimpleNamespace(
			docstatus=2,
			project="PRJ-001",
			profile="PROFILE-001",
			stage_instance_at_evaluation="STAGE-001",
		)
		draft = SimpleNamespace(name="PSC-NEW")

		def insert(*, ignore_permissions=False):
			if not ignore_permissions:
				raise frappe.PermissionError
			return draft

		draft.insert = insert
		stage = SimpleNamespace(stage="Review", name=canceled.stage_instance_at_evaluation)
		with (
			patch.object(frappe, "new_doc", return_value=draft),
			patch.object(frappe, "get_cached_doc", return_value=stage),
			patch.object(scorecard_factory, "sync_scorecard_items"),
		):
			with self.assertRaises(frappe.PermissionError):
				scorecard_factory.create_draft_scorecard(
					canceled.project, canceled.profile, stage_instance=canceled.stage_instance_at_evaluation,
				)
			replacement_name = scorecard_cancel.create_replacement_draft_after_cancel(canceled)

		self.assertEqual(replacement_name, "PSC-NEW")
		self.assertEqual((draft.project, draft.profile, draft.status), (canceled.project, canceled.profile, "Draft"))

	@patch.object(scorecard_cancel, "apply_workflow")
	@patch.object(scorecard_cancel, "get_transitions", return_value=[SimpleNamespace(action="Cancel")])
	@patch.object(scorecard_cancel, "validate_scorecard_cancel_allowed")
	def test_cancel_scorecard_document_uses_workflow_when_available(
		self, _validate, _transitions, apply_workflow
	):
		doc = MagicMock()
		doc.status = "Reviewed"
		doc.docstatus = 0

		result = scorecard_cancel.cancel_scorecard_document(doc)

		apply_workflow.assert_called_once_with(doc, "Cancel")
		doc.reload.assert_called_once()
		self.assertIs(result, doc)


if __name__ == "__main__":
	unittest.main()
