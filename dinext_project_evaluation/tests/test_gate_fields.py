import unittest
from types import SimpleNamespace

from dinext_project_evaluation.scoring.gate_fields import (
	applicable_gate_fields,
	build_gate_rule_values,
	coerce_gate_threshold_value,
	sanitize_profile_criterion_gate_fields,
)


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
		row = SimpleNamespace(
			requirement_level="Desired",
			minimum_normalized_score=0.4,
			minimum_raw_value=10,
			maximum_raw_value=20,
		)

		sanitize_profile_criterion_gate_fields(row, "Number")

		self.assertIsNone(row.minimum_normalized_score)
		self.assertIsNone(row.minimum_raw_value)
		self.assertIsNone(row.maximum_raw_value)

	def test_sanitize_keeps_normalized_only_for_mandatory_scale(self):
		row = SimpleNamespace(
			requirement_level="Mandatory",
			minimum_normalized_score=0.4,
			minimum_raw_value=10,
			maximum_raw_value=20,
		)

		sanitize_profile_criterion_gate_fields(row, "Scale")

		self.assertEqual(row.minimum_normalized_score, 0.4)
		self.assertIsNone(row.minimum_raw_value)
		self.assertIsNone(row.maximum_raw_value)

	def test_coerce_gate_threshold_value_treats_blank_as_none(self):
		self.assertIsNone(coerce_gate_threshold_value(None))
		self.assertIsNone(coerce_gate_threshold_value(""))
		self.assertIsNone(coerce_gate_threshold_value("   "))

	def test_coerce_gate_threshold_value_preserves_explicit_zero_for_raw_minimum(self):
		self.assertEqual(coerce_gate_threshold_value(0, "minimum_raw_value"), 0.0)
		self.assertEqual(coerce_gate_threshold_value(0, "minimum_normalized_score"), 0.0)

	def test_coerce_gate_threshold_value_treats_zero_maximum_raw_as_unset(self):
		self.assertIsNone(coerce_gate_threshold_value(0, "maximum_raw_value"))

	def test_sanitize_normalizes_blank_applicable_gate_fields_on_numeric_row(self):
		row = SimpleNamespace(
			requirement_level="Mandatory",
			minimum_normalized_score="",
			minimum_raw_value=0,
			maximum_raw_value=0,
		)

		sanitize_profile_criterion_gate_fields(row, "Number")

		self.assertIsNone(row.minimum_normalized_score)
		self.assertEqual(row.minimum_raw_value, 0.0)
		self.assertIsNone(row.maximum_raw_value)

	def test_build_gate_rule_values_preserves_configured_thresholds(self):
		row = SimpleNamespace(
			requirement_level="Mandatory",
			minimum_normalized_score=0.4,
			minimum_raw_value=10,
			maximum_raw_value=100,
		)

		values = build_gate_rule_values(row, "Percent")

		self.assertEqual(values["minimum_normalized_score"], 0.4)
		self.assertEqual(values["minimum_raw_value"], 10.0)
		self.assertEqual(values["maximum_raw_value"], 100.0)


if __name__ == "__main__":
	unittest.main()
