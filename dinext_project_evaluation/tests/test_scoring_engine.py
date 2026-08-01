import unittest

from dinext_project_evaluation.scoring.engine import (
	BoolCriterion,
	CriterionInput,
	GateRule,
	NumericCriterion,
	ProfileCriterion,
	ScaleCriterion,
	ScoringConfigurationError,
	calculate_scorecard,
	filter_applicable_criteria,
	normalize_bool,
	normalize_numeric,
	normalize_scale,
)


class TestScoringEngine(unittest.TestCase):
	def test_scale_normalization_uses_score_range(self):
		criterion = ScaleCriterion(scores=[0, 2, 5], influence_direction="higher_is_better")

		self.assertEqual(normalize_scale(criterion, 2), 0.4)

	def test_scale_normalization_inverts_lower_is_better(self):
		criterion = ScaleCriterion(scores=[1, 3, 5], influence_direction="lower_is_better")

		self.assertEqual(normalize_scale(criterion, 5), 0.0)
		self.assertEqual(normalize_scale(criterion, 1), 1.0)

	def test_numeric_normalization_clips_to_range(self):
		criterion = NumericCriterion(min_value=10, max_value=20, influence_direction="higher_is_better")

		self.assertEqual(normalize_numeric(criterion, 5), 0.0)
		self.assertEqual(normalize_numeric(criterion, 25), 1.0)
		self.assertEqual(normalize_numeric(criterion, 15), 0.5)

	def test_numeric_normalization_inverts_lower_is_better(self):
		criterion = NumericCriterion(min_value=10, max_value=20, influence_direction="lower_is_better")

		self.assertEqual(normalize_numeric(criterion, 10), 1.0)
		self.assertEqual(normalize_numeric(criterion, 20), 0.0)

	def test_bool_normalization_uses_configured_scores(self):
		criterion = BoolCriterion(true_score=0, false_score=1, influence_direction="higher_is_better")

		self.assertEqual(normalize_bool(criterion, True), 0.0)
		self.assertEqual(normalize_bool(criterion, False), 1.0)

	def test_filter_applicable_criteria_includes_global_and_current_stage(self):
		stage_1 = ProfileCriterion(code="A", weight=1, stages=[])
		stage_2 = ProfileCriterion(code="B", weight=1, stages=["S2"])
		stage_3 = ProfileCriterion(code="C", weight=1, stages=["S3"])

		result = filter_applicable_criteria([stage_1, stage_2, stage_3], current_stage="S2")

		self.assertEqual([item.code for item in result], ["A", "B"])

	def test_filter_applicable_criteria_prefers_stage_specific_over_global(self):
		global_row = ProfileCriterion(code="MKT_SHARE", weight=1, stages=[])
		stage_row = ProfileCriterion(code="MKT_SHARE", weight=2, stages=["S2"])

		result = filter_applicable_criteria([global_row, stage_row], current_stage="S2")

		self.assertEqual(result, [stage_row])

	def test_calculate_scorecard_uses_weighted_average(self):
		result = calculate_scorecard(
			criteria=[
				ProfileCriterion(code="strategy", weight=2),
				ProfileCriterion(code="risk", weight=1),
			],
			inputs={
				"strategy": CriterionInput(normalized_score=1),
				"risk": CriterionInput(normalized_score=0.25),
			},
		)

		self.assertAlmostEqual(result.integral_score, 0.75)
		self.assertTrue(result.gate_pass)

	def test_calculate_scorecard_rejects_zero_weight_sum(self):
		with self.assertRaises(ScoringConfigurationError):
			calculate_scorecard(
				criteria=[ProfileCriterion(code="strategy", weight=0)],
				inputs={"strategy": CriterionInput(normalized_score=1)},
			)

	def test_calculate_scorecard_fails_gate_when_mandatory_value_missing(self):
		result = calculate_scorecard(
			criteria=[ProfileCriterion(code="strategy", weight=1, requirement_level="Mandatory")],
			inputs={},
		)

		self.assertFalse(result.gate_pass)
		self.assertEqual(result.messages, ["Missing mandatory value for strategy"])

	def test_calculate_scorecard_fails_gate_when_threshold_not_met(self):
		result = calculate_scorecard(
			criteria=[
				ProfileCriterion(
					code="strategy",
					weight=1,
					requirement_level="Mandatory",
					gate_rule=GateRule(minimum_normalized_score=0.7),
				)
			],
			inputs={"strategy": CriterionInput(normalized_score=0.6)},
		)

		self.assertFalse(result.gate_pass)
		self.assertEqual(result.messages, ["strategy normalized score 0.6000 is below required 0.7000"])

	def test_calculate_scorecard_fails_gate_when_raw_value_below_minimum(self):
		result = calculate_scorecard(
			criteria=[
				ProfileCriterion(
					code="npv",
					weight=1,
					requirement_level="Mandatory",
					gate_rule=GateRule(minimum_raw_value=100),
				)
			],
			inputs={"npv": CriterionInput(normalized_score=0.5, raw_numeric_value=50)},
		)

		self.assertFalse(result.gate_pass)
		self.assertEqual(result.messages, ["npv raw value 50.0000 is below required 100.0000"])

	def test_calculate_scorecard_fails_gate_when_raw_value_above_maximum(self):
		result = calculate_scorecard(
			criteria=[
				ProfileCriterion(
					code="cost",
					weight=1,
					requirement_level="Mandatory",
					gate_rule=GateRule(maximum_raw_value=1000),
				)
			],
			inputs={"cost": CriterionInput(normalized_score=0.2, raw_numeric_value=1500)},
		)

		self.assertFalse(result.gate_pass)
		self.assertEqual(result.messages, ["cost raw value 1500.0000 is above allowed 1000.0000"])

	def test_gate_rule_with_zero_is_active(self):
		result = calculate_scorecard(
			criteria=[
				ProfileCriterion(
					code="cost",
					weight=1,
					requirement_level="Mandatory",
					gate_rule=GateRule(maximum_raw_value=0),
				)
			],
			inputs={"cost": CriterionInput(normalized_score=0.2, raw_numeric_value=1)},
		)

		self.assertFalse(result.gate_pass)
		self.assertEqual(result.messages, ["cost raw value 1.0000 is above allowed 0.0000"])

	def test_gate_rule_with_none_is_inactive(self):
		result = calculate_scorecard(
			criteria=[
				ProfileCriterion(
					code="cost",
					weight=1,
					requirement_level="Mandatory",
					gate_rule=GateRule(maximum_raw_value=None),
				)
			],
			inputs={"cost": CriterionInput(normalized_score=0.2, raw_numeric_value=1)},
		)

		self.assertTrue(result.gate_pass)
		self.assertEqual(result.messages, [])


if __name__ == "__main__":
	unittest.main()
