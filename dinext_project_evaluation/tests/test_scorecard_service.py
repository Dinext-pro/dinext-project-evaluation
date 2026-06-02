from types import SimpleNamespace
import unittest

from dinext_project_evaluation.scoring.scorecard_service import calculate_scorecard_document


def row(**kwargs):
	return SimpleNamespace(**kwargs)


class TestScorecardService(unittest.TestCase):
	def test_calculates_items_and_gate_summary_from_documents(self):
		profile = row(
			name="Default",
			criteria=[
				row(
					criterion="STR_ALIGN",
					stage="S1",
					weight=2,
					requirement_level="Mandatory",
					minimum_normalized_score=0.5,
					minimum_raw_value=None,
					maximum_raw_value=None,
				),
				row(
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

	def test_excludes_profile_rows_for_other_stages(self):
		profile = row(
			name="Default",
			criteria=[
				row(
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


if __name__ == "__main__":
	unittest.main()
