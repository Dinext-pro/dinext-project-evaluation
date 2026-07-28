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
	@patch("dinext_project_evaluation.scoring.scorecard_factory.frappe.get_doc")
	def test_get_applicable_criteria_for_stage_includes_description(self, get_doc):
		criterion = SimpleNamespace(
			name="STR_ALIGN",
			criterion_code="STR_ALIGN",
			criterion_name="Strategic Alignment",
			description="Explain how well the project aligns with strategy.",
			criterion_group="Strategy",
			input_type="Scale",
			min_value=None,
			max_value=None,
			influence_direction="higher_is_better",
			requires_comment=0,
			scale_rows=[],
		)
		profile_row = SimpleNamespace(
			criterion="STR_ALIGN",
			weight=2,
			requirement_level="Mandatory",
		)
		profile_doc = SimpleNamespace(criteria=[profile_row])
		get_doc.side_effect = lambda doctype, name: {
			("Project Scoring Profile", "PROFILE-001"): profile_doc,
			("Project Scoring Criterion", "STR_ALIGN"): criterion,
		}[doctype, name]

		rows = scorecard_factory.get_applicable_criteria_for_stage(
			"PRJ-001",
			"PROFILE-001",
			"S1",
		)

		self.assertEqual(len(rows), 1)
		self.assertEqual(
			rows[0]["description"],
			"Explain how well the project aligns with strategy.",
		)

	@patch("dinext_project_evaluation.scoring.scorecard_factory.frappe.get_doc")
	def test_get_applicable_criteria_for_stage_prefers_stage_specific_over_global(self, get_doc):
		criterion = SimpleNamespace(
			name="MKT_SHARE",
			criterion_code="MKT_SHARE",
			criterion_name="Доля рынка / новые рынки",
			description="Market share",
			criterion_group="Market",
			input_type="Scale",
			min_value=None,
			max_value=None,
			influence_direction="higher_is_better",
			requires_comment=0,
			scale_rows=[],
		)
		global_row = SimpleNamespace(
			criterion="MKT_SHARE",
			weight=1,
			requirement_level="Desired",
			stage=None,
		)
		stage_row = SimpleNamespace(
			criterion="MKT_SHARE",
			weight=2,
			requirement_level="Desired",
			stage="Идея",
		)
		profile_doc = SimpleNamespace(criteria=[global_row, stage_row])
		get_doc.side_effect = lambda doctype, name: {
			("Project Scoring Profile", "PROFILE-001"): profile_doc,
			("Project Scoring Criterion", "MKT_SHARE"): criterion,
		}[doctype, name]

		rows = scorecard_factory.get_applicable_criteria_for_stage(
			"PRJ-001",
			"PROFILE-001",
			"Идея",
		)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["criterion"], "MKT_SHARE")
		self.assertEqual(rows[0]["weight"], 2)

	@patch("dinext_project_evaluation.scoring.scorecard_factory.frappe.get_doc")
	def test_sync_scorecard_items_deduplicates_stage_overridden_criteria(self, get_doc):
		criterion = SimpleNamespace(
			name="MKT_SHARE",
			criterion_code="MKT_SHARE",
			criterion_name="Доля рынка / новые рынки",
			description="Market share",
			criterion_group="Market",
			input_type="Scale",
			min_value=None,
			max_value=None,
			influence_direction="higher_is_better",
			requires_comment=0,
			scale_rows=[],
		)
		global_row = SimpleNamespace(
			criterion="MKT_SHARE",
			weight=1,
			requirement_level="Desired",
			stage=None,
		)
		stage_row = SimpleNamespace(
			criterion="MKT_SHARE",
			weight=2,
			requirement_level="Desired",
			stage="Идея",
		)
		profile_doc = SimpleNamespace(criteria=[global_row, stage_row])
		get_doc.side_effect = lambda doctype, name: {
			("Project Scoring Profile", "PROFILE-001"): profile_doc,
			("Project Scoring Criterion", "MKT_SHARE"): criterion,
		}[doctype, name]
		scorecard = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			stage_at_evaluation="Идея",
			items=[],
		)
		scorecard.set = lambda fieldname, value: setattr(scorecard, fieldname, value)

		scorecard_factory.sync_scorecard_items(scorecard, "PROFILE-001")

		self.assertEqual([row["criterion"] for row in scorecard.items], ["MKT_SHARE"])
		self.assertEqual(scorecard.items[0]["weight"], 2)

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

	@patch("dinext_project_evaluation.scoring.scorecard_factory.frappe.db.exists", return_value=True)
	def test_project_has_agreed_scorecards(self, _exists):
		self.assertTrue(scorecard_factory.project_has_agreed_scorecards("PRJ-001"))

	@patch(
		"dinext_project_evaluation.scoring.scorecard_factory.frappe.db.get_value",
		return_value="PSC-AGREED",
	)
	def test_find_agreed_scorecard_for_stage_instance(self, _get_value):
		self.assertEqual(
			scorecard_factory.find_agreed_scorecard_for_stage_instance("PRJ-001-STAGE-001"),
			"PSC-AGREED",
		)

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
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.cancel_scorecard_document",
	)
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.get_doc",
		return_value=MagicMock(),
	)
	@patch(
		"dinext_project_evaluation.scoring.scorecard_cancel.frappe.get_all",
		return_value=["PSC-001", "PSC-002"],
	)
	def test_cancel_project_scorecards(self, _get_all, _get_doc, cancel_document, _clear):
		cancel_document.return_value = MagicMock()

		canceled = scorecard_factory.cancel_project_scorecards("PRJ-001")

		self.assertEqual(canceled, ["PSC-001", "PSC-002"])
		self.assertEqual(cancel_document.call_count, 2)
		for call in cancel_document.call_args_list:
			self.assertTrue(call.kwargs.get("skip_permission_checks"))
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
	def test_project_provision_hook_registered_on_update(self):
		import dinext_project_evaluation.hooks as app_hooks

		project_hooks = app_hooks.doc_events.get("Project", {})
		self.assertIn(
			"dinext_project_evaluation.scoring.project_hooks.after_save_project_scoring_profile",
			project_hooks.get("on_update", ""),
		)
		self.assertNotIn("after_save", project_hooks)

	def _make_project_doc(self, **overrides):
		defaults = {
			"is_new": lambda: False,
			"name": "PRJ-001",
			"governance_model": "GM-OLD",
			"custom_project_scoring_profile": None,
			"confirm_scoring_profile_reset": 0,
			"confirm_governance_reset": 0,
		}
		defaults.update(overrides)
		doc = SimpleNamespace(**defaults)
		doc.get = lambda key, default=None: getattr(doc, key, default)
		doc.set = lambda key, value: setattr(doc, key, value)
		return doc

	def _db_get_value(self, *, profile=None, governance="GM-OLD"):
		def get_value(_doctype, _name, fieldname, *_args, **_kwargs):
			values = {
				"custom_project_scoring_profile": profile,
				"governance_model": governance,
			}
			return values.get(fieldname)

		return get_value

	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=True,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_validate_requires_confirmation(self, get_value, get_meta, _has_scorecards):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._db_get_value(profile="PROFILE-OLD")

		doc = self._make_project_doc(custom_project_scoring_profile="PROFILE-NEW")

		with self.assertRaises(Exception):
			project_hooks.validate_project_scoring_profile_change(doc)

	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=False,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_validate_allows_initial_profile_without_confirmation(
		self, get_value, get_meta, _has_scorecards
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._db_get_value(profile=None)

		doc = self._make_project_doc(custom_project_scoring_profile="PROFILE-NEW")

		project_hooks.validate_project_scoring_profile_change(doc)

	@patch(
		"dinext_project_evaluation.scoring.project_hooks.cancel_project_scorecards",
		return_value=["PSC-001"],
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_before_save_cancels_with_confirmation(self, get_value, get_meta, cancel):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._db_get_value(profile="PROFILE-OLD")

		doc = self._make_project_doc(
			custom_project_scoring_profile="PROFILE-NEW",
			confirm_scoring_profile_reset=1,
		)

		project_hooks.before_save_project_scoring_profile_reset(doc)

		cancel.assert_called_once_with("PRJ-001")
		self.assertEqual(doc.confirm_scoring_profile_reset, 0)

	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=True,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_validate_governance_change_requires_confirmation(
		self, get_value, get_meta, _has_scorecards
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._db_get_value(profile="PROFILE-OLD", governance="GM-OLD")

		doc = self._make_project_doc(
			governance_model="GM-NEW",
			custom_project_scoring_profile="PROFILE-OLD",
		)

		with self.assertRaises(Exception):
			project_hooks.validate_project_scoring_profile_change(doc)

	@patch.object(project_hooks, "cancel_project_scorecards", return_value=["PSC-001"])
	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=True,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_before_save_governance_change_clears_profile_and_cancels_scorecards(
		self, get_value, get_meta, _has_scorecards, cancel
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._db_get_value(profile="PROFILE-OLD", governance="GM-OLD")

		doc = self._make_project_doc(
			governance_model="GM-NEW",
			custom_project_scoring_profile="PROFILE-OLD",
			confirm_governance_reset=1,
		)

		project_hooks.before_save_project_scoring_profile_reset(doc)

		cancel.assert_called_once_with("PRJ-001")
		self.assertIsNone(doc.custom_project_scoring_profile)
		self.assertEqual(doc.confirm_scoring_profile_reset, 0)

	@patch.object(project_hooks, "cancel_project_scorecards")
	@patch(
		"dinext_project_evaluation.scoring.project_hooks.project_has_non_canceled_scorecards",
		return_value=False,
	)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_before_save_governance_clear_without_scorecards_skips_cancel(
		self, get_value, get_meta, _has_scorecards, cancel
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._db_get_value(profile="PROFILE-OLD", governance="GM-OLD")

		doc = self._make_project_doc(
			governance_model=None,
			custom_project_scoring_profile="PROFILE-OLD",
		)

		project_hooks.before_save_project_scoring_profile_reset(doc)

		cancel.assert_not_called()
		self.assertIsNone(doc.custom_project_scoring_profile)

	def _after_save_db_get_value(self, *, stage_instance=None):
		def get_value(_doctype, _name, fieldname, *_args, **_kwargs):
			if fieldname == "current_stage_instance":
				return stage_instance
			return None

		return get_value

	@patch.object(project_hooks, "ensure_scorecard_for_stage_instance")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_cached_doc")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.exists", return_value=True)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_after_save_provisions_from_db_stage_instance_when_doc_lacks_it(
		self, get_value, get_meta, _exists, get_cached_doc, ensure
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._after_save_db_get_value(
			stage_instance="PRJ-001-STAGE-001"
		)
		stage_instance = SimpleNamespace(
			name="PRJ-001-STAGE-001",
			project="PRJ-001",
			status="Active",
		)
		get_cached_doc.return_value = stage_instance

		doc = self._make_project_doc(custom_project_scoring_profile="PROFILE-NEW")

		project_hooks.after_save_project_scoring_profile(doc)

		get_cached_doc.assert_called_once_with(
			"Project Stage Instance", "PRJ-001-STAGE-001"
		)
		ensure.assert_called_once_with(stage_instance)

	@patch.object(project_hooks, "ensure_scorecard_for_stage_instance")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_cached_doc")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.exists", return_value=True)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_after_save_skips_when_no_stage_instance(
		self, get_value, get_meta, _exists, get_cached_doc, ensure
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._after_save_db_get_value(stage_instance=None)

		doc = self._make_project_doc(custom_project_scoring_profile="PROFILE-NEW")

		project_hooks.after_save_project_scoring_profile(doc)

		get_cached_doc.assert_not_called()
		ensure.assert_not_called()

	@patch.object(project_hooks, "ensure_scorecard_for_stage_instance")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_cached_doc")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.exists", return_value=True)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_after_save_skips_when_stage_instance_not_active(
		self, get_value, get_meta, _exists, get_cached_doc, ensure
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		get_value.side_effect = self._after_save_db_get_value(
			stage_instance="PRJ-001-STAGE-001"
		)
		get_cached_doc.return_value = SimpleNamespace(
			name="PRJ-001-STAGE-001",
			project="PRJ-001",
			status="Planned",
		)

		doc = self._make_project_doc(
			custom_project_scoring_profile="PROFILE-NEW",
			current_stage_instance="PRJ-001-STAGE-001",
		)

		project_hooks.after_save_project_scoring_profile(doc)

		ensure.assert_not_called()

	@patch.object(project_hooks, "ensure_scorecard_for_stage_instance")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_cached_doc")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.exists", return_value=True)
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.get_meta")
	@patch("dinext_project_evaluation.scoring.project_hooks.frappe.db.get_value")
	def test_after_save_uses_doc_stage_instance_without_db_lookup(
		self, get_value, get_meta, _exists, get_cached_doc, ensure
	):
		meta = MagicMock()
		meta.has_field.return_value = True
		get_meta.return_value = meta
		stage_instance = SimpleNamespace(
			name="PRJ-001-STAGE-001",
			project="PRJ-001",
			status="Active",
		)
		get_cached_doc.return_value = stage_instance

		doc = self._make_project_doc(
			custom_project_scoring_profile="PROFILE-NEW",
			current_stage_instance="PRJ-001-STAGE-001",
		)

		project_hooks.after_save_project_scoring_profile(doc)

		get_value.assert_not_called()
		ensure.assert_called_once_with(stage_instance)


if __name__ == "__main__":
	unittest.main()
