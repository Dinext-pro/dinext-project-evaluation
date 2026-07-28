import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from dinext_project_evaluation import api


class TestApi(unittest.TestCase):
	@patch("dinext_project_evaluation.api.frappe.get_doc")
	def test_get_permitted_doc_checks_permission(self, get_doc):
		doc = MagicMock()
		get_doc.return_value = doc

		result = api._get_permitted_doc("Project", "PRJ-001", "write")

		self.assertIs(result, doc)
		get_doc.assert_called_once_with("Project", "PRJ-001")
		doc.check_permission.assert_called_once_with("write")

	@patch("dinext_project_evaluation.api.get_applicable_criteria_for_stage", return_value=["criterion"])
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_get_applicable_criteria_uses_project_stage_and_checks_permissions(
		self, get_permitted_doc, get_criteria
	):
		project_doc = MagicMock()
		project_doc.get.return_value = "STAGE-001"
		profile_doc = MagicMock()
		get_permitted_doc.side_effect = [project_doc, profile_doc]

		result = api.get_applicable_criteria("PRJ-001", "PROFILE-001")

		self.assertEqual(result, ["criterion"])
		self.assertEqual(
			get_permitted_doc.call_args_list,
			[
				(("Project", "PRJ-001"), {}),
				(("Project Scoring Profile", "PROFILE-001"), {}),
			],
		)
		get_criteria.assert_called_once_with("PRJ-001", "PROFILE-001", "STAGE-001")

	@patch("dinext_project_evaluation.api.create_draft_scorecard")
	@patch("dinext_project_evaluation.api.ensure_scorecard_for_stage_instance", return_value="PSC-001")
	@patch("dinext_project_evaluation.api.frappe.db.exists", return_value=True)
	@patch("dinext_project_evaluation.api.frappe.db.get_value", return_value="STAGE-001")
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_create_scorecard_returns_existing_stage_scorecard_when_active(
		self,
		get_permitted_doc,
		get_value,
		db_exists,
		ensure_scorecard,
		create_draft,
	):
		project_doc = MagicMock()
		profile_doc = MagicMock()
		stage_instance = MagicMock(status="Active")
		scorecard = MagicMock()
		scorecard.as_dict.return_value = {"name": "PSC-001"}
		get_permitted_doc.side_effect = [project_doc, profile_doc, stage_instance, scorecard]

		result = api.create_scorecard("PRJ-001", "PROFILE-001")

		self.assertEqual(result, {"name": "PSC-001"})
		ensure_scorecard.assert_called_once_with(stage_instance)
		create_draft.assert_not_called()
		get_value.assert_called_once_with("Project", "PRJ-001", "current_stage_instance")
		db_exists.assert_called_once_with("Project Stage Instance", "STAGE-001")

	@patch("dinext_project_evaluation.api.create_draft_scorecard")
	@patch("dinext_project_evaluation.api.frappe.db.exists", return_value=False)
	@patch("dinext_project_evaluation.api.frappe.db.get_value", return_value=None)
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_create_scorecard_creates_draft_and_checks_read_permission(
		self, get_permitted_doc, get_value, db_exists, create_draft
	):
		project_doc = MagicMock()
		profile_doc = MagicMock()
		get_permitted_doc.side_effect = [project_doc, profile_doc]
		scorecard = MagicMock()
		scorecard.as_dict.return_value = {"name": "PSC-NEW"}
		create_draft.return_value = scorecard

		result = api.create_scorecard("PRJ-001", "PROFILE-001")

		self.assertEqual(result, {"name": "PSC-NEW"})
		create_draft.assert_called_once_with("PRJ-001", "PROFILE-001")
		scorecard.check_permission.assert_called_once_with("read")
		get_value.assert_called_once_with("Project", "PRJ-001", "current_stage_instance")
		db_exists.assert_not_called()

	@patch("dinext_project_evaluation.api.get_project_scoring_profile", return_value=None)
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_create_scorecard_requires_profile(self, get_permitted_doc, get_profile):
		project_doc = MagicMock()
		get_permitted_doc.return_value = project_doc

		with self.assertRaises(frappe.ValidationError):
			api.create_scorecard("PRJ-001")

		get_profile.assert_called_once_with("PRJ-001")

	@patch("dinext_project_evaluation.api.mark_scorecard_reviewed")
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_calculate_scorecard_checks_write_permission_before_delegate(
		self, get_permitted_doc, mark_reviewed
	):
		get_permitted_doc.return_value = MagicMock()
		doc = MagicMock()
		doc.as_dict.return_value = {"name": "PSC-001"}
		mark_reviewed.return_value = doc

		result = api.calculate_scorecard("PSC-001")

		self.assertEqual(result, {"name": "PSC-001"})
		get_permitted_doc.assert_called_once_with("Project Scorecard", "PSC-001", "write")
		mark_reviewed.assert_called_once_with("PSC-001")

	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_recalculate_scorecard_reloads_document(self, get_permitted_doc):
		doc = MagicMock()
		doc.as_dict.return_value = {"name": "PSC-001"}
		get_permitted_doc.return_value = doc

		result = api.recalculate_scorecard("PSC-001")

		self.assertEqual(result, {"name": "PSC-001"})
		doc.recalculate_in_place.assert_called_once_with()
		doc.reload.assert_called_once_with()

	@patch("dinext_project_evaluation.api.approve_scorecard_via_workflow")
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_approve_scorecard_checks_write_permission(self, get_permitted_doc, approve_scorecard):
		get_permitted_doc.return_value = MagicMock()
		doc = MagicMock()
		doc.as_dict.return_value = {"name": "PSC-001"}
		approve_scorecard.return_value = doc

		result = api.approve_scorecard("PSC-001")

		self.assertEqual(result, {"name": "PSC-001"})
		get_permitted_doc.assert_called_once_with("Project Scorecard", "PSC-001", "write")
		approve_scorecard.assert_called_once_with("PSC-001")

	@patch("dinext_project_evaluation.api.get_checkpoint_scorecard_summary_for_api", return_value={"scorecard": "PSC-001"})
	@patch("dinext_project_evaluation.api._get_permitted_doc")
	def test_get_checkpoint_scorecard_summary_checks_read_permission(self, get_permitted_doc, get_summary):
		get_permitted_doc.return_value = SimpleNamespace()

		result = api.get_checkpoint_scorecard_summary("CHK-001")

		self.assertEqual(result, {"scorecard": "PSC-001"})
		get_permitted_doc.assert_called_once_with("Project Gate Checkpoint", "CHK-001")
		get_summary.assert_called_once_with("CHK-001")


if __name__ == "__main__":
	unittest.main()
