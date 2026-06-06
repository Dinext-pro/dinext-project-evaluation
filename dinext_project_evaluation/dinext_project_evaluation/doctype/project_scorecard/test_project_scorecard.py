# Copyright (c) 2026, Dinext and Contributors
# See license.txt

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard import (
	ProjectScorecard,
	_assert_no_immutable_content_changes,
	_field_value_changed,
	_format_gate_messages_for_display,
)
from dinext_project_evaluation.scoring.workflow_constants import SCORECARD_AGREED_DOCSTATUS


class TestProjectScorecard(FrappeTestCase):
	def test_format_gate_messages_for_display_replaces_codes_with_names(self):
		messages = [
			"Missing mandatory value for STR_ALIGN",
			"RISK_PROB normalized score 0.6000 is below required 0.7000",
			"npv raw value 50.0000 is below required 100.0000",
		]
		items = [
			frappe._dict(criterion="STR_ALIGN", criterion_name="Strategic Alignment"),
			frappe._dict(criterion="RISK_PROB", criterion_name="Risk Probability"),
		]
		criteria_by_name = {
			"STR_ALIGN": frappe._dict(criterion_name="Strategic Alignment"),
			"RISK_PROB": frappe._dict(criterion_name="Risk Probability"),
			"npv": frappe._dict(criterion_name="Net Present Value"),
		}

		display_messages = _format_gate_messages_for_display(messages, items, criteria_by_name)

		self.assertEqual(
			display_messages,
			[
				"Missing mandatory value for Strategic Alignment",
				"Risk Probability normalized score 0.6000 is below required 0.7000",
				"Net Present Value raw value 50.0000 is below required 100.0000",
			],
		)

	def test_format_gate_messages_for_display_keeps_unknown_codes(self):
		messages = ["UNKNOWN normalized score 0.5000 is below required 0.7000"]
		display_messages = _format_gate_messages_for_display(messages, [], {})

		self.assertEqual(display_messages, messages)

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.now_datetime",
		return_value="2026-06-06 12:00:00",
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard._load_criteria",
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.get_doc",
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.calculate_scorecard_document",
	)
	def test_calculate_stores_gate_messages_with_criterion_names(
		self, calculate_scorecard_document, get_doc, load_criteria, _now_datetime
	):
		from dinext_project_evaluation.scoring.scorecard_service import CalculatedItem, ScorecardCalculation

		profile = SimpleNamespace(name="PROFILE-001", criteria=[])
		get_doc.return_value = profile
		load_criteria.return_value = {
			"STR_ALIGN": frappe._dict(criterion_name="Strategic Alignment"),
		}
		calculate_scorecard_document.return_value = ScorecardCalculation(
			integral_score=0.6,
			gate_pass=False,
			messages=["Missing mandatory value for STR_ALIGN"],
			items={
				"STR_ALIGN": CalculatedItem(
					criterion="STR_ALIGN",
					criterion_code="STR_ALIGN",
					raw_value=None,
					raw_numeric_value=None,
					normalized_score=0,
					weighted_score=0,
					weight=1,
					gate_pass=False,
				)
			},
			applicable_criteria=[],
		)
		doc = SimpleNamespace(
			profile="PROFILE-001",
			items=[frappe._dict(criterion="STR_ALIGN", criterion_name="Strategic Alignment")],
		)
		doc.calculate = ProjectScorecard.calculate.__get__(doc, ProjectScorecard)

		doc.calculate()

		self.assertEqual(doc.gate_messages, "Missing mandatory value for Strategic Alignment")
		self.assertNotIn("STR_ALIGN", doc.gate_messages)
		self.assertEqual(doc.integral_score, 0.6)
		self.assertEqual(doc.gate_pass, 0)

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_sync_items_from_profile_uses_server_authoritative_sync(self, sync_items):
		doc = frappe._dict(project="PRJ-001", profile="PROFILE-001", status="Draft")
		doc._sync_items_from_profile = ProjectScorecard._sync_items_from_profile.__get__(doc, frappe._dict)

		doc._sync_items_from_profile()

		sync_items.assert_called_once_with(doc, "PROFILE-001")

	def test_prepare_item_inputs_maps_typed_fields_to_raw_fields(self):
		doc = SimpleNamespace(
			items=[
				frappe._dict(
					criterion_input_type="Scale",
					scale_value="5",
					scale_options_json='[{"label":"High","value":"5","score":5}]',
				),
				frappe._dict(criterion_input_type="Boolean", boolean_value=1, boolean_value_set=1),
				frappe._dict(criterion_input_type="Percent", percent_value=25),
			]
		)
		doc._prepare_item_inputs = ProjectScorecard._prepare_item_inputs.__get__(doc, SimpleNamespace)

		doc._prepare_item_inputs()

		self.assertEqual(doc.items[0].raw_value, "5")
		self.assertEqual(doc.items[0].value_display, "High")
		self.assertIsNone(doc.items[0].raw_numeric_value)
		self.assertEqual(doc.items[1].raw_value, "1")
		self.assertEqual(doc.items[1].value_display, "Yes")
		self.assertEqual(doc.items[2].raw_numeric_value, 25)
		self.assertEqual(doc.items[2].value_display, "25")

	def test_prepare_item_inputs_supports_extended_scale_options_json(self):
		doc = SimpleNamespace(
			items=[
				frappe._dict(
					criterion_input_type="Scale",
					scale_value="5",
					scale_options_json=(
						'[{"label":"High","value":"5","score":5,'
						'"sort_order":2,"key_phrases":"Full alignment"}]'
					),
				),
			]
		)
		doc._prepare_item_inputs = ProjectScorecard._prepare_item_inputs.__get__(doc, SimpleNamespace)

		doc._prepare_item_inputs()

		self.assertEqual(doc.items[0].raw_value, "5")
		self.assertEqual(doc.items[0].value_display, "High")

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_onload_primes_scorecard_items_for_display(self, sync_items):
		doc = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			status="Draft",
			_hydrate_project_context=lambda: None,
			_prepare_item_inputs=lambda: None,
		)
		doc._sync_items_from_profile = ProjectScorecard._sync_items_from_profile.__get__(doc, SimpleNamespace)
		doc.onload = ProjectScorecard.onload.__get__(doc, SimpleNamespace)

		doc.onload()

		sync_items.assert_called_once_with(doc, "PROFILE-001")

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard._load_criteria",
		return_value={"STR_ALIGN": frappe._dict(criterion_code="STR_ALIGN", input_type="Scale", scale_rows=[])},
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.get_doc",
		return_value=SimpleNamespace(criteria=[]),
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.scorecard_validation_error_message",
		return_value="Mandatory criteria require a value: STR_ALIGN",
	)
	def test_validate_required_items_blocks_save_with_specific_message(
		self, _validation_message, _get_doc, _load_criteria
	):
		doc = SimpleNamespace(
			status="Submitted for Review",
			profile="PROFILE-001",
			items=[frappe._dict(criterion="STR_ALIGN", requirement_level="Mandatory")],
		)
		doc._validate_required_items = ProjectScorecard._validate_required_items.__get__(
			doc, ProjectScorecard
		)

		with self.assertRaises(frappe.ValidationError) as context:
			doc._validate_required_items()

		self.assertIn("STR_ALIGN", str(context.exception))

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard._load_criteria",
		return_value={},
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.get_doc",
		return_value=SimpleNamespace(criteria=[]),
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.scorecard_validation_error_message",
		return_value=None,
	)
	def test_validate_required_items_skips_when_no_validation_message(
		self, _validation_message, _get_doc, _load_criteria
	):
		doc = SimpleNamespace(status="Submitted for Review", profile="PROFILE-001", items=[])

		doc._validate_required_items = ProjectScorecard._validate_required_items.__get__(
			doc, ProjectScorecard
		)

		doc._validate_required_items()

	def test_validate_required_items_skips_canceled(self):
		doc = SimpleNamespace(status="Canceled", profile="PROFILE-001", items=[])
		doc._validate_required_items = ProjectScorecard._validate_required_items.__get__(
			doc, ProjectScorecard
		)

		doc._validate_required_items()

	def test_validate_required_items_skips_draft(self):
		doc = SimpleNamespace(status="Draft", profile="PROFILE-001", items=[])
		doc._validate_required_items = ProjectScorecard._validate_required_items.__get__(
			doc, ProjectScorecard
		)

		doc._validate_required_items()

	def test_prepare_item_inputs_maps_number_to_numeric_fields(self):
		doc = SimpleNamespace(
			items=[
				frappe._dict(
					criterion_input_type="Number",
					number_value=42,
				)
			]
		)
		doc._prepare_item_inputs = ProjectScorecard._prepare_item_inputs.__get__(doc, SimpleNamespace)

		doc._prepare_item_inputs()

		self.assertEqual(doc.items[0].raw_numeric_value, 42)
		self.assertEqual(doc.items[0].value_display, "42")

	def test_field_value_changed_treats_empty_and_numeric_equivalents(self):
		self.assertFalse(_field_value_changed(None, ""))
		self.assertFalse(_field_value_changed(25, 25.0))
		self.assertTrue(_field_value_changed("5", "6"))

	def test_assert_no_immutable_content_allows_status_only_change(self):
		item = SimpleNamespace(
			criterion="CRIT-1",
			scale_value="5",
			comment="note",
			boolean_value=0,
			boolean_value_set=0,
		)
		previous = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			portfolio=None,
			stage_at_evaluation=None,
			stage_instance_at_evaluation="STAGE-1",
			status="Submitted for Review",
			items=[item],
		)
		current = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			portfolio=None,
			stage_at_evaluation=None,
			stage_instance_at_evaluation="STAGE-1",
			status="Reviewed",
			items=[SimpleNamespace(**item.__dict__)],
		)

		_assert_no_immutable_content_changes(previous, current)

	def test_assert_no_immutable_content_blocks_comment_change(self):
		previous = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			portfolio=None,
			stage_at_evaluation=None,
			stage_instance_at_evaluation="STAGE-1",
			status="Submitted for Review",
			items=[
				SimpleNamespace(
					criterion="CRIT-1",
					scale_value="5",
					comment="original",
					boolean_value=0,
					boolean_value_set=0,
				)
			],
		)
		current = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			portfolio=None,
			stage_at_evaluation=None,
			stage_instance_at_evaluation="STAGE-1",
			status="Submitted for Review",
			items=[
				SimpleNamespace(
					criterion="CRIT-1",
					scale_value="5",
					comment="changed",
					boolean_value=0,
					boolean_value_set=0,
				)
			],
		)

		with self.assertRaises(frappe.ValidationError):
			_assert_no_immutable_content_changes(previous, current)

	def test_assert_no_immutable_content_blocks_value_change(self):
		previous = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			portfolio=None,
			stage_at_evaluation=None,
			stage_instance_at_evaluation="STAGE-1",
			status="Reviewed",
			items=[
				SimpleNamespace(
					criterion="CRIT-1",
					scale_value="5",
					comment=None,
					boolean_value=0,
					boolean_value_set=0,
				)
			],
		)
		current = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			portfolio=None,
			stage_at_evaluation=None,
			stage_instance_at_evaluation="STAGE-1",
			status="Reviewed",
			items=[
				SimpleNamespace(
					criterion="CRIT-1",
					scale_value="4",
					comment=None,
					boolean_value=0,
					boolean_value_set=0,
				)
			],
		)

		with self.assertRaises(frappe.ValidationError):
			_assert_no_immutable_content_changes(previous, current)

	def test_prevent_content_edits_skips_when_leaving_draft(self):
		doc = SimpleNamespace(
			is_new=lambda: False,
			status="Submitted for Review",
			get_doc_before_save=lambda: SimpleNamespace(status="Draft", items=[]),
		)
		doc._prevent_content_edits_outside_draft = (
			ProjectScorecard._prevent_content_edits_outside_draft.__get__(doc, ProjectScorecard)
		)

		doc._prevent_content_edits_outside_draft()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.db.get_value",
		return_value="Approved",
	)
	def test_prevent_locked_edits_blocks_terminal_status_rollback(self, _get_value):
		doc = SimpleNamespace(
			is_new=lambda: False,
			doctype="Project Scorecard",
			name="PSC-001",
			status="Draft",
			get_doc_before_save=lambda: None,
		)
		doc._prevent_locked_edits = ProjectScorecard._prevent_locked_edits.__get__(doc, ProjectScorecard)

		with self.assertRaises(frappe.ValidationError):
			doc._prevent_locked_edits()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_sync_items_from_profile_skips_outside_draft(self, sync_items):
		doc = frappe._dict(project="PRJ-001", profile="PROFILE-001", status="Submitted for Review")
		doc._sync_items_from_profile = ProjectScorecard._sync_items_from_profile.__get__(
			doc, frappe._dict
		)

		doc._sync_items_from_profile()

		sync_items.assert_not_called()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.create_replacement_draft_after_cancel",
		return_value="PSC-NEW",
	)
	def test_on_cancel_creates_replacement_draft(self, create_replacement):
		doc = SimpleNamespace()
		doc.on_cancel = ProjectScorecard.on_cancel.__get__(doc, ProjectScorecard)

		doc.on_cancel()

		create_replacement.assert_called_once_with(doc)

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.validate_scorecard_cancel_allowed"
	)
	def test_before_cancel_validates_permissions_and_stage(self, validate_cancel):
		doc = SimpleNamespace()
		doc.before_cancel = ProjectScorecard.before_cancel.__get__(doc, ProjectScorecard)

		doc.before_cancel()

		validate_cancel.assert_called_once_with(doc)

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.validate_scorecard_cancel_allowed"
	)
	def test_before_cancel_skips_validation_when_flag_set(self, validate_cancel):
		doc = SimpleNamespace()
		doc.before_cancel = ProjectScorecard.before_cancel.__get__(doc, ProjectScorecard)

		frappe.flags.skip_scorecard_cancel_validation = True
		try:
			doc.before_cancel()
		finally:
			frappe.flags.skip_scorecard_cancel_validation = False

		validate_cancel.assert_not_called()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_validate_calls_calculate_on_submitted_for_review(self, _sync_items):
		calculate = MagicMock()
		doc = SimpleNamespace(
			status="Submitted for Review",
			project="PRJ-001",
			profile="PROFILE-001",
			name="PSC-001",
			stage_instance_at_evaluation=None,
			items=[],
			is_new=lambda: False,
			get_doc_before_save=lambda: SimpleNamespace(status="Draft", items=[]),
			calculate=calculate,
		)
		for method_name in (
			"_hydrate_project_context",
			"_sync_items_from_profile",
			"_prepare_item_inputs",
			"_validate_unique_stage_instance",
			"_validate_required_items",
			"_prevent_content_edits_outside_draft",
		):
			setattr(doc, method_name, lambda: None)

		doc.validate = ProjectScorecard.validate.__get__(doc, ProjectScorecard)
		doc.validate()

		calculate.assert_called_once()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_validate_calls_calculate_on_reviewed(self, _sync_items):
		calculate = MagicMock()
		doc = SimpleNamespace(
			status="Reviewed",
			project="PRJ-001",
			profile="PROFILE-001",
			name="PSC-001",
			stage_instance_at_evaluation=None,
			items=[],
			is_new=lambda: False,
			get_doc_before_save=lambda: SimpleNamespace(status="Submitted for Review", items=[]),
			calculate=calculate,
		)
		for method_name in (
			"_hydrate_project_context",
			"_sync_items_from_profile",
			"_prepare_item_inputs",
			"_validate_unique_stage_instance",
			"_validate_required_items",
			"_prevent_content_edits_outside_draft",
		):
			setattr(doc, method_name, lambda: None)

		doc.validate = ProjectScorecard.validate.__get__(doc, ProjectScorecard)
		doc.validate()

		calculate.assert_called_once()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.get_meta"
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.db.set_value"
	)
	def test_on_submit_does_not_update_project_for_submitted_for_review(self, set_value, get_meta):
		meta = SimpleNamespace(has_field=lambda fieldname: True)
		get_meta.return_value = meta
		doc = SimpleNamespace(
			docstatus=0,
			status="Submitted for Review",
			name="PSC-001",
			project="PRJ-001",
			integral_score=4.5,
			evaluation_date="2026-06-06 12:00:00",
		)
		doc.on_submit = ProjectScorecard.on_submit.__get__(doc, ProjectScorecard)
		doc._update_project_last_score = ProjectScorecard._update_project_last_score.__get__(
			doc, ProjectScorecard
		)

		doc.on_submit()

		set_value.assert_not_called()

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.get_meta"
	)
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.frappe.db.set_value"
	)
	def test_on_submit_updates_project_last_score(self, set_value, get_meta):
		meta = SimpleNamespace(has_field=lambda fieldname: fieldname == "custom_last_scorecard")
		get_meta.return_value = meta
		doc = SimpleNamespace(
			docstatus=SCORECARD_AGREED_DOCSTATUS,
			status="Approved",
			name="PSC-001",
			project="PRJ-001",
			integral_score=4.5,
			evaluation_date="2026-06-06 12:00:00",
		)
		doc.on_submit = ProjectScorecard.on_submit.__get__(doc, ProjectScorecard)
		doc._update_project_last_score = ProjectScorecard._update_project_last_score.__get__(doc, ProjectScorecard)

		doc.on_submit()

		set_value.assert_called()
