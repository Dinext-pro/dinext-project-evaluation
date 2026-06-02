# Copyright (c) 2026, Dinext and Contributors
# See license.txt

from unittest.mock import patch
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard import (
	ProjectScorecard,
)


class TestProjectScorecard(FrappeTestCase):
	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_sync_items_from_profile_uses_server_authoritative_sync(self, sync_items):
		doc = frappe._dict(project="PRJ-001", profile="PROFILE-001")
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

	@patch(
		"dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard.sync_scorecard_items"
	)
	def test_onload_primes_scorecard_items_for_display(self, sync_items):
		doc = SimpleNamespace(
			project="PRJ-001",
			profile="PROFILE-001",
			_hydrate_project_context=lambda: None,
			_prepare_item_inputs=lambda: None,
		)
		doc._sync_items_from_profile = ProjectScorecard._sync_items_from_profile.__get__(doc, SimpleNamespace)
		doc.onload = ProjectScorecard.onload.__get__(doc, SimpleNamespace)

		doc.onload()

		sync_items.assert_called_once_with(doc, "PROFILE-001")
