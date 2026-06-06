# Copyright (c) 2026, Dinext and Contributors
# See license.txt

from unittest.mock import patch
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard import (
	ProjectScorecard,
	_assert_no_immutable_content_changes,
	_field_value_changed,
)


class TestProjectScorecard(FrappeTestCase):
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
