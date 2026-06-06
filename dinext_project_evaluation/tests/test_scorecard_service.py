from types import SimpleNamespace
import unittest

from dinext_project_evaluation.scoring.criterion_config import (
	item_has_input_value,
	item_missing_mandatory_value,
	item_missing_required_comment,
	scorecard_has_missing_required_items,
)
from dinext_project_evaluation.scoring.scorecard_service import (
	calculate_scorecard_document,
	missing_mandatory_criterion_codes,
	normalize_item,
)


def row(**kwargs):
	return SimpleNamespace(**kwargs)


def profile_criterion_row(**kwargs):
	return row(**kwargs)


class TestScorecardService(unittest.TestCase):
	def test_calculates_items_and_gate_summary_from_documents(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="STR_ALIGN",
					stage="S1",
					weight=2,
					requirement_level="Mandatory",
					minimum_normalized_score="0.5",
					minimum_raw_value=None,
					maximum_raw_value=None,
				),
				profile_criterion_row(
					criterion="RISK_PROB",
					stage=None,
					weight=1,
					requirement_level="Desired",
					minimum_normalized_score=None,
					minimum_raw_value=None,
					maximum_raw_value=None,
				),
			],
		)
		criteria_by_name = {
			"STR_ALIGN": row(criterion_code="STR_ALIGN", input_type="Scale", influence_direction="higher_is_better", scale_rows=[row(score=0), row(score=5)]),
			"RISK_PROB": row(criterion_code="RISK_PROB", input_type="Number", influence_direction="lower_is_better", min_value=0, max_value=100),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[
				row(criterion="STR_ALIGN", raw_value="5", raw_numeric_value=None),
				row(criterion="RISK_PROB", raw_value=None, raw_numeric_value=25),
			],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertAlmostEqual(result.integral_score, (1 * 2 + 0.75 * 1) / 3)
		self.assertTrue(result.gate_pass)
		self.assertEqual(result.messages, [])
		self.assertEqual(result.items["STR_ALIGN"].criterion_code, "STR_ALIGN")
		self.assertEqual(result.items["RISK_PROB"].normalized_score, 0.75)
		self.assertTrue(result.items["STR_ALIGN"].gate_pass)

	def test_excludes_profile_rows_for_other_stages(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="STR_ALIGN",
					stage="S2",
					weight=1,
					requirement_level="Desired",
					minimum_normalized_score=None,
					minimum_raw_value=None,
					maximum_raw_value=None,
				)
			],
		)
		criteria_by_name = {
			"STR_ALIGN": row(criterion_code="STR_ALIGN", input_type="Scale", influence_direction="higher_is_better", scale_rows=[row(score=0), row(score=5)]),
		}
		scorecard = row(stage_at_evaluation="S1", items=[row(criterion="STR_ALIGN", raw_value="5", raw_numeric_value=None)])

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertEqual(result.applicable_criteria, [])

	def test_marks_item_gate_pass_false_when_mandatory_threshold_fails(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="STR_ALIGN",
					stage="S1",
					weight=1,
					requirement_level="Mandatory",
					minimum_normalized_score="0.8",
					minimum_raw_value=None,
					maximum_raw_value=None,
				)
			],
		)
		criteria_by_name = {
			"STR_ALIGN": row(
				criterion_code="STR_ALIGN",
				input_type="Scale",
				influence_direction="higher_is_better",
				scale_rows=[row(score=0), row(score=5)],
			),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[row(criterion="STR_ALIGN", raw_value="3", raw_numeric_value=None)],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertFalse(result.gate_pass)
		self.assertFalse(result.items["STR_ALIGN"].gate_pass)

	def test_marks_missing_mandatory_item_input_as_row_gate_fail(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="STR_ALIGN",
					stage="S1",
					weight=1,
					requirement_level="Mandatory",
					minimum_normalized_score="0.5",
					minimum_raw_value=None,
					maximum_raw_value=None,
				)
			],
		)
		criteria_by_name = {
			"STR_ALIGN": row(
				criterion_code="STR_ALIGN",
				input_type="Scale",
				influence_direction="higher_is_better",
				scale_rows=[row(score=0), row(score=5)],
			),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[row(criterion="STR_ALIGN", raw_value=None, raw_numeric_value=None)],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertFalse(result.gate_pass)
		self.assertIn("Missing mandatory value for STR_ALIGN", result.messages)
		self.assertFalse(result.items["STR_ALIGN"].gate_pass)
		self.assertEqual(result.items["STR_ALIGN"].normalized_score, 0)

	def test_missing_mandatory_criterion_codes_extracts_codes_from_messages(self):
		messages = [
			"Missing mandatory value for STR_ALIGN",
			"RISK_PROB normalized score 0.6000 is below required 0.7000",
			"Missing mandatory value for COST",
		]

		self.assertEqual(missing_mandatory_criterion_codes(messages), ["STR_ALIGN", "COST"])

	def test_item_missing_mandatory_value_and_required_comment(self):
		mandatory_empty = row(
			criterion_input_type="Scale",
			requirement_level="Mandatory",
		)
		self.assertTrue(item_missing_mandatory_value(mandatory_empty))

		mandatory_filled = row(
			criterion_input_type="Scale",
			requirement_level="Mandatory",
			scale_value="5",
		)
		self.assertFalse(item_missing_mandatory_value(mandatory_filled))
		self.assertTrue(item_has_input_value(mandatory_filled))

		comment_required = row(requires_comment=1, comment="")
		self.assertTrue(item_missing_required_comment(comment_required))

		comment_optional = row(requires_comment=0, comment="")
		self.assertFalse(item_missing_required_comment(comment_optional))

		items = [
			row(requirement_level="Mandatory", criterion_input_type="Scale"),
			row(requires_comment=1, comment="filled"),
		]
		self.assertTrue(scorecard_has_missing_required_items(items))

	def test_normalize_number_uses_numeric_range(self):
		crit = row(
			input_type="Number",
			influence_direction="higher_is_better",
			min_value=0,
			max_value=100,
			scale_rows=[],
		)
		item = row(raw_value=None, raw_numeric_value=50)

		self.assertAlmostEqual(normalize_item(crit, item), 0.5)

	def test_blank_maximum_raw_threshold_does_not_fail_gate(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="RISK_PROB",
					stage="S1",
					weight=1,
					requirement_level="Mandatory",
					minimum_normalized_score=None,
					minimum_raw_value=None,
					maximum_raw_value=None,
				)
			],
		)
		criteria_by_name = {
			"RISK_PROB": row(
				criterion_code="RISK_PROB",
				input_type="Number",
				influence_direction="lower_is_better",
				min_value=0,
				max_value=100,
			),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[row(criterion="RISK_PROB", raw_value=None, raw_numeric_value=25)],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertTrue(result.gate_pass)
		self.assertEqual(result.messages, [])
		self.assertTrue(result.items["RISK_PROB"].gate_pass)

	def test_explicit_maximum_raw_zero_threshold_fails_gate(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="RISK_PROB",
					stage="S1",
					weight=1,
					requirement_level="Mandatory",
					minimum_normalized_score=None,
					minimum_raw_value=None,
					maximum_raw_value="0",
				)
			],
		)
		criteria_by_name = {
			"RISK_PROB": row(
				criterion_code="RISK_PROB",
				input_type="Number",
				influence_direction="lower_is_better",
				min_value=0,
				max_value=100,
			),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[row(criterion="RISK_PROB", raw_value=None, raw_numeric_value=25)],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertFalse(result.gate_pass)
		self.assertEqual(
			result.messages,
			["RISK_PROB raw value 25.0000 is above allowed 0.0000"],
		)
		self.assertFalse(result.items["RISK_PROB"].gate_pass)

	def test_explicit_minimum_raw_zero_threshold_still_fails_gate(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="RISK_PROB",
					stage="S1",
					weight=1,
					requirement_level="Mandatory",
					minimum_normalized_score=None,
					minimum_raw_value="0",
					maximum_raw_value=None,
				)
			],
		)
		criteria_by_name = {
			"RISK_PROB": row(
				criterion_code="RISK_PROB",
				input_type="Number",
				influence_direction="higher_is_better",
				min_value=-100,
				max_value=100,
			),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[row(criterion="RISK_PROB", raw_value=None, raw_numeric_value=-5)],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertFalse(result.gate_pass)
		self.assertEqual(
			result.messages,
			["RISK_PROB raw value -5.0000 is below required 0.0000"],
		)
		self.assertFalse(result.items["RISK_PROB"].gate_pass)

	def test_explicit_minimum_normalized_zero_threshold_is_active(self):
		profile = row(
			name="Default",
			criteria=[
				profile_criterion_row(
					criterion="STR_ALIGN",
					stage="S1",
					weight=1,
					requirement_level="Mandatory",
					minimum_normalized_score="0",
					minimum_raw_value=None,
					maximum_raw_value=None,
				)
			],
		)
		criteria_by_name = {
			"STR_ALIGN": row(
				criterion_code="STR_ALIGN",
				input_type="Scale",
				influence_direction="higher_is_better",
				scale_rows=[row(score=0), row(score=5)],
			),
		}
		scorecard = row(
			stage_at_evaluation="S1",
			items=[row(criterion="STR_ALIGN", raw_value="0", raw_numeric_value=None)],
		)

		result = calculate_scorecard_document(scorecard, profile, criteria_by_name)

		self.assertTrue(result.gate_pass)
		self.assertTrue(result.items["STR_ALIGN"].gate_pass)


if __name__ == "__main__":
	unittest.main()
