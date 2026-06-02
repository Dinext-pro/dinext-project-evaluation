import unittest
from types import SimpleNamespace

from dinext_project_evaluation.scoring.gate_fields import (
	applicable_gate_fields,
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


if __name__ == "__main__":
	unittest.main()
