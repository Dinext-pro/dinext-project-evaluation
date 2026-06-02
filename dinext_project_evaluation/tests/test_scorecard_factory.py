from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from dinext_project_evaluation.scoring import scorecard_factory, scorecard_provision
from dinext_project_evaluation.scoring import project_hooks


class TestScorecardFactory(unittest.TestCase):
	@patch("dinext_project_evaluation.scoring.scorecard_factory.frappe.db.exists", return_value=True)
	def test_project_has_non_canceled_scorecards(self, _exists):
		self.assertTrue(scorecard_factory.project_has_non_canceled_scorecards("PRJ-001"))

	@patch(
		"dinext_project_evaluation.scoring.scorecard_factory.frappe.db.get_value",
		return_value="PSC-001",
	)
	def test_find_scorecard_for_stage_instance(self, _get_value):
		self.assertEqual(
			scorecard_factory.find_scorecard_for_stage_instance("PRJ-001-STAGE-001"),
			"PSC-001",
		)

	@patch.object(scorecard_factory, "create_draft_scorecard")
	@patch.object(scorecard_factory, "find_scorecard_for_stage_instance", return_value=None)
	@patch.object(scorecard_factory, "get_project_scoring_profile", return_value="PROFILE-001")
	def test_ensure_scorecard_for_stage_instance_creates_draft(
		self, _profile, _find, create_draft
	):
		create_draft.return_value = SimpleNamespace(name="PSC-NEW")
		stage_instance = SimpleNamespace(
			name="PRJ-001-STAGE-001",
			project="PRJ-001",
			stage="IDEA",
			status="Active",
		)

		result = scorecard_factory.ensure_scorecard_for_stage_instance(stage_instance)

		self.assertEqual(result, "PSC-NEW")
		create_draft.assert_called_once_with(
			"PRJ-001",
			"PROFILE-001",
			stage_instance="PRJ-001-STAGE-001",
		)

	@patch.object(scorecard_factory, "find_scorecard_for_stage_instance", return_value="PSC-001")
	@patch.object(scorecard_factory, "get_project_scoring_profile", return_value="PROFILE-001")
	def test_ensure_scorecard_for_stage_instance_is_idempotent(self, _profile, _find):
		stage_instance = SimpleNamespace(
			name="PRJ-001-STAGE-001",
			project="PRJ-001",
			stage="IDEA",
			status="Active",
		)

		result = scorecard_factory.ensure_scorecard_for_stage_instance(stage_instance)

		self.assertEqual(result, "PSC-001")

	@patch("dinext_project_evaluation.scoring.scorecard_factory._clear_project_last_score_fields")
	@patch("dinext_project_evaluation.scoring.scorecard_factory.frappe.get_doc")
	@patch(
		"dinext_project_evaluation.scoring.scorecard_factory.frappe.get_all",
		return_value=["PSC-001", "PSC-002"],
	)
	def test_cancel_project_scorecards(self, _get_all, get_doc, _clear):
		doc = MagicMock()
		get_doc.return_value = doc

		canceled = scorecard_factory.cancel_project_scorecards("PRJ-001")

		self.assertEqual(canceled, ["PSC-001", "PSC-002"])
		self.assertEqual(doc.status, "Canceled")
		self.assertEqual(doc.save.call_count, 2)
		_clear.assert_called_once_with("PRJ-001")


class TestScorecardProvision(unittest.TestCase):
	@patch.object(scorecard_provision, "ensure_scorecard_for_stage_instance", return_value="PSC-001")
	def test_on_stage_instance_update_on_active_transition(self, ensure):
		doc = SimpleNamespace(
			status="Active",
			get_doc_before_save=lambda: SimpleNamespace(status="Planned"),
		)

		scorecard_provision.on_stage_instance_update(doc)

		ensure.assert_called_once_with(doc)

	@patch.object(scorecard_provision, "ensure_scorecard_for_stage_instance")
	def test_on_stage_instance_update_skips_when_already_active(self, ensure):
		doc = SimpleNamespace(
			status="Active",
			get_doc_before_save=lambda: SimpleNamespace(status="Active"),
		)

		scorecard_provision.on_stage_instance_update(doc)

		ensure.assert_not_called()


class TestProjectScoringHooks(unittest.TestCase):
	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=True,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value", return_value="PROFILE-OLD")
	def test_validate_requires_confirmation(self, _get_value, get_meta, _has_scorecards):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta

		doc = SimpleNamespace(
			is_new=lambda: False,
			name="PRJ-001",
			custom_project_scoring_profile="PROFILE-NEW",
			confirm_scoring_profile_reset=0,
		)
		doc.get = lambda key, default=None: getattr(doc, key, default)

		with self.assertRaises(Exception):
			project_hooks.validate_project_scoring_profile_change(doc)

	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=False,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value", return_value=None)
	def test_validate_allows_initial_profile_without_confirmation(
		self, _get_value, get_meta, _has_scorecards
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta

		doc = SimpleNamespace(
			is_new=lambda: False,
			name="PRJ-001",
			custom_project_scoring_profile="PROFILE-NEW",
			confirm_scoring_profile_reset=0,
		)
		doc.get = lambda key, default=None: getattr(doc, key, default)

		project_hooks.validate_project_scoring_profile_change(doc)

	@patch(
		"dinext_project_evaluation.scoring.project_hooks.cancel_project_scorecards",
		return_value=["PSC-001"],
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value", return_value="PROFILE-OLD")
	def test_before_save_cancels_with_confirmation(self, _get_value, get_meta, cancel):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta

		doc = SimpleNamespace(
			is_new=lambda: False,
			name="PRJ-001",
			custom_project_scoring_profile="PROFILE-NEW",
			confirm_scoring_profile_reset=1,
		)
		doc.get = lambda key, default=None: getattr(doc, key, default)

		project_hooks.before_save_project_scoring_profile_reset(doc)

		cancel.assert_called_once_with("PRJ-001")
		self.assertEqual(doc.confirm_scoring_profile_reset, 0)


if __name__ == "__main__":
	unittest.main()
