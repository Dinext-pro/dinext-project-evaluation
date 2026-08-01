# Copyright (c) 2026, Dinext and Contributors
# See license.txt

from types import SimpleNamespace

from frappe.tests.utils import FrappeTestCase

from dinext_project_evaluation.scoring.criterion_config import (
	get_field_visibility,
	sanitize_criterion_config,
)


class TestProjectScoringCriterion(FrappeTestCase):
	def test_field_visibility_for_scale(self):
		doc = SimpleNamespace(input_type="Scale")
		visibility = get_field_visibility(doc)

		self.assertTrue(visibility["scale_rows"])
		self.assertFalse(visibility["min_value"])
		self.assertFalse(visibility["max_value"])

	def test_field_visibility_for_number(self):
		doc = SimpleNamespace(input_type="Number")
		visibility = get_field_visibility(doc)

		self.assertFalse(visibility["scale_rows"])
		self.assertTrue(visibility["min_value"])
		self.assertTrue(visibility["max_value"])

	def test_field_visibility_for_boolean(self):
		doc = SimpleNamespace(input_type="Boolean")
		visibility = get_field_visibility(doc)

		self.assertTrue(visibility["boolean_true_score"])
		self.assertFalse(visibility["scale_rows"])

	def test_sanitize_boolean_criterion_clears_numeric_fields(self):
		doc = SimpleNamespace(
			input_type="Boolean",
			scale_rows=[SimpleNamespace(score=1)],
			min_value=0,
			max_value=1,
			boolean_true_score=1,
			boolean_false_score=0,
		)

		sanitize_criterion_config(doc)

		self.assertEqual(doc.scale_rows, [])
		self.assertIsNone(doc.min_value)
		self.assertIsNone(doc.max_value)
