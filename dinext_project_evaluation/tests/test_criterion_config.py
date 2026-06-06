from types import SimpleNamespace
import unittest

import frappe

from dinext_project_evaluation.scoring.criterion_config import (
	collect_scorecard_item_validation_errors,
	sanitize_criterion_config,
	scorecard_validation_error_message,
	validate_criterion_config,
	validate_scorecard_item_value,
)


def criterion(**kwargs):
	defaults = {
		"input_type": "Scale",
		"influence_direction": "higher_is_better",
		"scale_rows": [],
		"min_value": None,
		"max_value": None,
		"boolean_true_score": 1,
		"boolean_false_score": 0,
		"criterion_code": "TEST",
	}
	defaults.update(kwargs)
	return SimpleNamespace(**defaults)


def scale_row(score, label="Label"):
	return SimpleNamespace(score=score, scale_label=label)


class TestCriterionConfig(unittest.TestCase):
	def test_sanitize_numeric_criterion_clears_scale_fields(self):
		doc = criterion(
			input_type="Number",
			scale_rows=[scale_row(1)],
			boolean_true_score=1,
			boolean_false_score=0,
			min_value=0,
			max_value=100,
		)

		sanitize_criterion_config(doc)

		self.assertEqual(doc.scale_rows, [])
		self.assertIsNone(doc.boolean_true_score)
		self.assertIsNone(doc.boolean_false_score)

	def test_sanitize_scale_criterion_clears_numeric_range(self):
		doc = criterion(
			input_type="Scale",
			scale_rows=[scale_row(1)],
			min_value=0,
			max_value=100,
		)

		sanitize_criterion_config(doc)

		self.assertIsNone(doc.min_value)
		self.assertIsNone(doc.max_value)

	def test_validate_discrete_scale_requires_rows(self):
		doc = criterion(input_type="Scale", scale_rows=[])

		with self.assertRaises(frappe.ValidationError):
			validate_criterion_config(doc)

	def test_validate_discrete_scale_rejects_duplicate_scores(self):
		doc = criterion(
			input_type="Scale",
			scale_rows=[scale_row(1), scale_row(1)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_criterion_config(doc)

	def test_validate_numeric_requires_valid_range(self):
		doc = criterion(input_type="Number", min_value=10, max_value=5)

		with self.assertRaises(frappe.ValidationError):
			validate_criterion_config(doc)

	def test_validate_scale_item_rejects_unknown_option(self):
		crit = criterion(
			scale_rows=[scale_row(1), scale_row(5)],
			criterion_code="STR_ALIGN",
		)
		item = SimpleNamespace(
			criterion_input_type="Scale",
			scale_value="3",
			raw_value="3",
		)

		errors = validate_scorecard_item_value(item, crit)

		self.assertEqual(errors, ["STR_ALIGN: value must be one of the configured scale options"])

	def test_validate_numeric_item_rejects_out_of_range(self):
		crit = criterion(
			input_type="Number",
			min_value=0,
			max_value=100,
			criterion_code="RISK_PROB",
		)
		item = SimpleNamespace(
			criterion_input_type="Number",
			number_value=150,
		)

		errors = validate_scorecard_item_value(item, crit)

		self.assertTrue(errors[0].startswith("RISK_PROB: value 150.0 is outside allowed range"))

	def test_scorecard_validation_error_message_lists_missing_and_invalid(self):
		crit = criterion(
			input_type="Number",
			min_value=0,
			max_value=100,
			criterion_code="RISK_PROB",
			name="RISK_PROB",
		)
		items = [
			SimpleNamespace(
				criterion="RISK_PROB",
				criterion_code="RISK_PROB",
				criterion_input_type="Number",
				requirement_level="Mandatory",
				number_value=None,
				requires_comment=0,
			),
			SimpleNamespace(
				criterion="RISK_PROB",
				criterion_code="RISK_PROB",
				criterion_input_type="Number",
				requirement_level="Desired",
				number_value=150,
				requires_comment=0,
			),
		]

		message = scorecard_validation_error_message(items, {"RISK_PROB": crit})

		self.assertIn("Mandatory criteria require a value: RISK_PROB", message)
		self.assertIn("outside allowed range", message)

	def test_collect_scorecard_item_validation_errors_skips_empty_values(self):
		crit = criterion(input_type="Number", min_value=0, max_value=100, criterion_code="RISK_PROB")
		items = [
			SimpleNamespace(
				criterion="RISK_PROB",
				criterion_input_type="Number",
				number_value=None,
			)
		]

		self.assertEqual(collect_scorecard_item_validation_errors(items, {"RISK_PROB": crit}), [])


if __name__ == "__main__":
	unittest.main()
