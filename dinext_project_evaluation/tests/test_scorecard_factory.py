from types import SimpleNamespace
import json
import unittest
from unittest.mock import MagicMock, patch

from dinext_project_evaluation.scoring import scorecard_factory, scorecard_provision
from dinext_project_evaluation.scoring import project_hooks


class TestBuildScaleOptions(unittest.TestCase):
	def test_build_scale_options_sorts_by_sort_order_and_includes_metadata(self):
		scale_rows = [
			SimpleNamespace(
				scale_label="High",
				score=5,
				sort_order=2,
				key_phrases="Full alignment",
			),
			SimpleNamespace(
				scale_label="Low",
				score=0,
				sort_order=1,
				key_phrases="No alignment",
			),
		]

		options = scorecard_factory.build_scale_options(scale_rows)

		self.assertEqual([option["label"] for option in options], ["Low", "High"])
		self.assertEqual(options[0]["key_phrases"], "No alignment")
		self.assertEqual(options[1]["sort_order"], 2)
		self.assertEqual(options[1]["value"], "5")

	def test_build_scale_options_falls_back_to_index_when_sort_order_missing(self):
		scale_rows = [
			SimpleNamespace(scale_label="A", score=1, sort_order=None, key_phrases=""),
			SimpleNamespace(scale_label="B", score=2, sort_order=None, key_phrases=""),
		]

		options = scorecard_factory.build_scale_options(scale_rows)

		self.assertEqual([option["label"] for option in options], ["A", "B"])


class TestScorecardFactory(unittest.TestCase):
	@patch.object(
		scorecard_factory,
		"get_applicable_criteria_for_stage",
		return_value=[
			{
				"criterion": "STR_ALIGN",
				"criterion_code": "STR_ALIGN",
				"criterion_name": "Strategic Alignment",
				"input_type": "Scale",
				"weight": 2,
				"requirement_level": "Mandatory",
				"requires_comment": 1,
				"scale_options": [
					{
						"label": "Low",
						"value": "0",
						"score": 0,
						"sort_order": 1,
						"key_phrases": "No alignment",
					},
					{
						"label": "High",
						"value": "5",
						"score": 5,
						"sort_order": 2,
						"key_phrases": "Full alignment",
					},
				],
				"scale_rows": [SimpleNamespace(score=0), SimpleNamespace(score=5)],
			},
			{
				"criterion": "RISK_PROB",
				"criterion_code": "RISK_PROB",
				"criterion_name": "Risk Probability",
				"input_type": "Percent",
				"weight": 1,
				"requirement_level": "Desired",
				"requires_comment": 0,
				"scale_rows": [],
			},
		],
	)
	def test_sync_scorecard_items_rebuilds_rows_and_preserves_values(self, _criteria):
		scorecard = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			stage_at_evaluation="S1",
			items=[
				SimpleNamespace(
					criterion="RISK_PROB",
					criterion_code="RISK_OLD",
					criterion_name="Old Risk",
					criterion_input_type="Percent",
					percent_value=25,
					value_display="25",
					comment="Keep me",
				),
				SimpleNamespace(
					criterion="LEGACY",
					criterion_code="LEGACY",
					criterion_name="Legacy",
					raw_value="stale",
					comment="Drop me",
				),
			],
		)
		scorecard.set = lambda fieldname, value: setattr(scorecard, fieldname, value)

		scorecard_factory.sync_scorecard_items(scorecard, "PROFILE-001")

		self.assertEqual([row["criterion"] for row in scorecard.items], ["STR_ALIGN", "RISK_PROB"])
		self.assertEqual(scorecard.items[0]["criterion_name"], "Strategic Alignment")
		self.assertEqual(scorecard.items[0]["criterion_input_type"], "Scale")
		self.assertEqual(scorecard.items[1]["criterion_code"], "RISK_PROB")
		self.assertEqual(scorecard.items[1]["percent_value"], 25)
		self.assertEqual(scorecard.items[1]["value_display"], "25")
		self.assertEqual(scorecard.items[1]["comment"], "Keep me")
		self.assertEqual(scorecard.items[0]["requirement_level"], "Mandatory")
		self.assertEqual(scorecard.items[0]["requires_comment"], 1)
		self.assertEqual(scorecard.items[1]["requirement_level"], "Desired")
		self.assertEqual(scorecard.items[1]["requires_comment"], 0)

		scale_options = json.loads(scorecard.items[0]["scale_options_json"])
		self.assertEqual(scale_options[0]["key_phrases"], "No alignment")
		self.assertEqual(scale_options[1]["sort_order"], 2)

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
