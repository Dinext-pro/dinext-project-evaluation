from types import SimpleNamespace
import unittest

from dinext_project_evaluation.scoring.profile_stages import (
	find_duplicate_criterion_stage_pair,
	resolve_stage_overridden_profile_rows,
)


def criterion_row(**kwargs):
	return SimpleNamespace(**kwargs)


class TestProfileCriterionStageValidation(unittest.TestCase):
	def test_detects_duplicate_criterion_for_same_stage(self):
		criteria = [
			criterion_row(criterion="STR_ALIGN", stage="S1"),
			criterion_row(criterion="STR_ALIGN", stage="S1"),
		]

		self.assertEqual(find_duplicate_criterion_stage_pair(criteria), ("STR_ALIGN", "S1"))

	def test_allows_same_criterion_for_different_stages(self):
		criteria = [
			criterion_row(criterion="STR_ALIGN", stage="S1"),
			criterion_row(criterion="STR_ALIGN", stage="S2"),
		]

		self.assertIsNone(find_duplicate_criterion_stage_pair(criteria))

	def test_allows_global_and_stage_specific_rows_for_same_criterion(self):
		criteria = [
			criterion_row(criterion="STR_ALIGN", stage=None),
			criterion_row(criterion="STR_ALIGN", stage="S1"),
		]

		self.assertIsNone(find_duplicate_criterion_stage_pair(criteria))

	def test_detects_duplicate_global_rows(self):
		criteria = [
			criterion_row(criterion="STR_ALIGN", stage=None),
			criterion_row(criterion="STR_ALIGN", stage=""),
		]

		self.assertEqual(find_duplicate_criterion_stage_pair(criteria), ("STR_ALIGN", None))

	def test_resolve_stage_overridden_profile_rows_prefers_stage_specific_over_global(self):
		global_row = criterion_row(criterion="MKT_SHARE", stage=None, weight=1.0)
		stage_row = criterion_row(criterion="MKT_SHARE", stage="Идея", weight=2.0)
		criteria = [global_row, stage_row]

		resolved = resolve_stage_overridden_profile_rows(criteria, "Идея")

		self.assertEqual(resolved, [stage_row])

	def test_resolve_stage_overridden_profile_rows_keeps_global_when_no_stage_override(self):
		global_row = criterion_row(criterion="MKT_SHARE", stage=None, weight=1.0)
		stage_row = criterion_row(criterion="MKT_SHARE", stage="Идея", weight=2.0)
		criteria = [global_row, stage_row]

		resolved = resolve_stage_overridden_profile_rows(criteria, "Реализация")

		self.assertEqual(resolved, [global_row])

	def test_resolve_stage_overridden_profile_rows_preserves_profile_order(self):
		global_mkt = criterion_row(criterion="MKT_SHARE", stage=None, weight=1.0)
		global_urgency = criterion_row(criterion="URGENCY", stage=None, weight=1.0)
		stage_mkt = criterion_row(criterion="MKT_SHARE", stage="Идея", weight=2.0)
		criteria = [global_mkt, global_urgency, stage_mkt]

		resolved = resolve_stage_overridden_profile_rows(criteria, "Идея")

		self.assertEqual(resolved, [global_urgency, stage_mkt])


if __name__ == "__main__":
	unittest.main()
