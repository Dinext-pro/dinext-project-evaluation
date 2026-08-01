import unittest
from types import SimpleNamespace

from dinext_project_evaluation.scoring.gate_fields import (
	GATE_FIELD_NAMES,
	applicable_gate_fields,
	build_gate_rule_values,
	coerce_gate_threshold_value,
	sanitize_profile_criterion_gate_fields,
	validate_profile_criterion_gate_fields,
)


def gate_row(**kwargs):
	return SimpleNamespace(**kwargs)


class TestGateFields(unittest.TestCase):
	def test_applicable_gate_fields_for_desired_criterion(self):
		self.assertEqual(applicable_gate_fields("Desired", "Number"), set())

	def test_applicable_gate_fields_for_mandatory_scale(self):
		self.assertEqual(
			applicable_gate_fields("Mandatory", "Scale"),
			{"minimum_normalized_score"},
		)

	def test_applicable_gate_fields_for_mandatory_numeric(self):
		self.assertEqual(
			applicable_gate_fields("Mandatory", "Percent"),
			{
				"minimum_normalized_score",
				"minimum_raw_value",
				"maximum_raw_value",
			},
		)

	def test_sanitize_clears_irrelevant_fields(self):
		row = gate_row(
			requirement_level="Desired",
			minimum_normalized_score="0.4",
			minimum_raw_value="10",
			maximum_raw_value="20",
		)

		sanitize_profile_criterion_gate_fields(row, "Number")

		self.assertIsNone(row.minimum_normalized_score)
		self.assertIsNone(row.minimum_raw_value)
		self.assertIsNone(row.maximum_raw_value)

	def test_sanitize_keeps_normalized_only_for_mandatory_scale(self):
		row = gate_row(
			requirement_level="Mandatory",
			minimum_normalized_score="0.4",
			minimum_raw_value="10",
			maximum_raw_value="20",
		)

		sanitize_profile_criterion_gate_fields(row, "Scale")

		self.assertEqual(row.minimum_normalized_score, "0.4")
		self.assertIsNone(row.minimum_raw_value)
		self.assertIsNone(row.maximum_raw_value)

	def test_coerce_gate_threshold_value_treats_blank_as_none(self):
		self.assertIsNone(coerce_gate_threshold_value(None))
		self.assertIsNone(coerce_gate_threshold_value(""))
		self.assertIsNone(coerce_gate_threshold_value("   "))

	def test_coerce_gate_threshold_value_treats_explicit_zero_as_active(self):
		self.assertEqual(coerce_gate_threshold_value("0"), 0.0)
		self.assertEqual(coerce_gate_threshold_value(0), 0.0)

	def test_coerce_gate_threshold_value_preserves_explicit_zero_for_all_fields(self):
		for fieldname in GATE_FIELD_NAMES:
			self.assertEqual(coerce_gate_threshold_value("0", fieldname), 0.0)

	def test_sanitize_normalizes_blank_thresholds_on_numeric_row(self):
		row = gate_row(
			requirement_level="Mandatory",
			minimum_normalized_score="",
			minimum_raw_value=None,
			maximum_raw_value="",
		)

		sanitize_profile_criterion_gate_fields(row, "Number")

		self.assertIsNone(row.minimum_normalized_score)
		self.assertIsNone(row.minimum_raw_value)
		self.assertIsNone(row.maximum_raw_value)

	def test_sanitize_preserves_explicit_zero_thresholds_on_numeric_row(self):
		row = gate_row(
			requirement_level="Mandatory",
			minimum_normalized_score="0",
			minimum_raw_value="0",
			maximum_raw_value="0",
		)

		sanitize_profile_criterion_gate_fields(row, "Number")

		self.assertEqual(row.minimum_normalized_score, "0")
		self.assertEqual(row.minimum_raw_value, "0")
		self.assertEqual(row.maximum_raw_value, "0")

	def test_build_gate_rule_values_preserves_configured_thresholds(self):
		row = gate_row(
			requirement_level="Mandatory",
			minimum_normalized_score="0.4",
			minimum_raw_value="10",
			maximum_raw_value="100",
		)

		values = build_gate_rule_values(row, "Percent")

		self.assertEqual(values["minimum_normalized_score"], 0.4)
		self.assertEqual(values["minimum_raw_value"], 10.0)
		self.assertEqual(values["maximum_raw_value"], 100.0)

	def test_validate_rejects_non_numeric_threshold_on_applicable_field(self):
		row = gate_row(
			criterion="RISK_PROB",
			requirement_level="Mandatory",
			minimum_normalized_score="abc",
			minimum_raw_value="10",
			maximum_raw_value=None,
		)

		errors = validate_profile_criterion_gate_fields(row, "Number")

		self.assertEqual(
			errors,
			["Criterion RISK_PROB: Minimum Normalized Score must be numeric."],
		)

	def test_validate_ignores_non_numeric_values_on_inapplicable_fields(self):
		row = gate_row(
			criterion="STR_ALIGN",
			requirement_level="Desired",
			minimum_normalized_score="abc",
			minimum_raw_value="xyz",
			maximum_raw_value="oops",
		)

		self.assertEqual(validate_profile_criterion_gate_fields(row, "Scale"), [])

	def test_validate_allows_blank_and_numeric_thresholds(self):
		row = gate_row(
			criterion="RISK_PROB",
			requirement_level="Mandatory",
			minimum_normalized_score="0.4",
			minimum_raw_value="",
			maximum_raw_value="0",
		)

		self.assertEqual(validate_profile_criterion_gate_fields(row, "Percent"), [])

	def test_build_gate_rule_values_ignores_blank_thresholds(self):
		row = gate_row(
			requirement_level="Mandatory",
			minimum_normalized_score=None,
			minimum_raw_value="",
			maximum_raw_value=None,
		)

		values = build_gate_rule_values(row, "Percent")

		self.assertIsNone(values["minimum_normalized_score"])
		self.assertIsNone(values["minimum_raw_value"])
		self.assertIsNone(values["maximum_raw_value"])


if __name__ == "__main__":
	unittest.main()
