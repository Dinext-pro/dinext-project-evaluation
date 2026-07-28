import json
import unittest
from pathlib import Path


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "dinext_project_evaluation" / "fixtures"
GROUPS_FIXTURE = FIXTURES_DIR / "project_scoring_criterion_group.json"
CRITERIA_FIXTURE = FIXTURES_DIR / "project_scoring_criterion.json"
PROFILE_FIXTURE = FIXTURES_DIR / "project_scoring_profile.json"

EXPECTED_GROUP_NAMES = {
	"Strategy": "Стратегическое соответствие",
	"Benefits": "Выгоды",
	"Market": "Рынок и клиенты",
	"Finance": "Финансовая эффективность",
	"Risks": "Риски",
	"Resources": "Ресурсная обеспеченность",
	"Regulatory": "Нормативные ограничения",
	"Priority": "Приоритет и срочность",
	"Innovation": "Инновационный потенциал",
	"Environment": "Среда и зависимости",
}

EXPECTED_NUMERIC_RANGES = {
	"COST": (0.0, 500_000_000.0),
	"NPV": (-200_000_000.0, 1_000_000_000.0),
	"IRR": (0.0, 60.0),
	"PP": (0.0, 84.0),
	"PI": (0.0, 3.0),
	"ECV": (-50_000_000.0, 500_000_000.0),
	"RD_COST": (0.0, 200_000_000.0),
	"MFG_COST": (0.0, 500_000_000.0),
	"TECH_SUCCESS": (0.0, 100.0),
}


def _load_fixture(path: Path):
	return json.loads(path.read_text(encoding="utf-8"))


class TestScoringDemoCatalog(unittest.TestCase):
	def test_groups_are_russian_with_stable_keys(self):
		payload = _load_fixture(GROUPS_FIXTURE)
		self.assertEqual(len(payload), len(EXPECTED_GROUP_NAMES))
		actual = {row["name"]: row["group_name"] for row in payload}
		self.assertEqual(actual, EXPECTED_GROUP_NAMES)

	def test_criteria_have_realistic_descriptions_and_ranges(self):
		payload = _load_fixture(CRITERIA_FIXTURE)
		self.assertEqual(len(payload), 21)

		for row in payload:
			self.assertTrue((row.get("description") or "").strip(), f"Missing description for {row['name']}")
			if row["input_type"] == "Scale":
				self.assertGreaterEqual(len(row["scale_rows"]), 5, f"Too few scale rows for {row['name']}")
				for scale_row in row["scale_rows"]:
					self.assertTrue((scale_row.get("scale_label") or "").strip(), f"Blank scale label for {row['name']}")
					self.assertTrue((scale_row.get("key_phrases") or "").strip(), f"Blank key phrases for {row['name']}")
					self.assertNotIn("очень низко", scale_row["scale_label"], f"Generic scale label left in {row['name']}")
					self.assertNotEqual(
						scale_row["key_phrases"],
						"Критерий не выполняется или данных нет",
						f"Generic key phrase left in {row['name']}",
					)

		criteria_by_name = {row["name"]: row for row in payload}
		for criterion_name, (min_value, max_value) in EXPECTED_NUMERIC_RANGES.items():
			row = criteria_by_name[criterion_name]
			self.assertEqual((row["min_value"], row["max_value"]), (min_value, max_value))

		self.assertEqual(
			[row["scale_label"] for row in criteria_by_name["STR_ALIGN"]["scale_rows"]],
			[
				"0 - не поддерживает стратегию",
				"1 - слабое соответствие",
				"2 - локальное улучшение",
				"3 - поддерживает одно направление",
				"4 - существенно поддерживает цели",
				"5 - стратегический приоритет",
			],
		)
		self.assertEqual(
			[row["scale_label"] for row in criteria_by_name["RISK_PROB"]["scale_rows"]],
			[
				"0 - практически исключено",
				"1 - маловероятно",
				"2 - низкая вероятность",
				"3 - вероятность заметная",
				"4 - высокая вероятность",
				"5 - почти неизбежно",
			],
		)
		self.assertEqual(
			[row["scale_label"] for row in criteria_by_name["DEP_INT"]["scale_rows"]],
			[
				"0 - автономная реализация",
				"1 - немного внутренних зависимостей",
				"2 - управляемые зависимости",
				"3 - несколько критичных связей",
				"4 - высокая зависимость от контрагентов",
				"5 - критическая сеть зависимостей",
			],
		)

	def test_default_profile_fixture_is_present_and_stage_aware(self):
		payload = _load_fixture(PROFILE_FIXTURE)
		self.assertEqual(len(payload), 1, "Expected exactly one versioned demo profile")

		profile = payload[0]
		self.assertEqual(profile["name"], "Default Project Scoring Profile")
		self.assertEqual(profile["profile_name"], "Базовый профиль оценки проектов")
		self.assertEqual(profile["status"], "Active")
		self.assertTrue((profile.get("description") or "").strip())
		self.assertGreater(len(profile["criteria"]), 21)

		stage_specific_pairs = {
			(row["criterion"], row.get("stage"))
			for row in profile["criteria"]
			if row.get("stage")
		}
		self.assertTrue(
			{
				("STR_ALIGN", "Инициирование"),
				("BEN_FIN", "Идея"),
				("TECH_SUCCESS", "Реализация"),
				("REG", "Завершение"),
				("NPV", "Завершение"),
			}.issubset(stage_specific_pairs)
		)

		rows_by_pair = {(row["criterion"], row.get("stage")): row for row in profile["criteria"]}
		self.assertEqual(rows_by_pair[("STR_ALIGN", "Инициирование")]["requirement_level"], "Mandatory")
		self.assertEqual(rows_by_pair[("STR_ALIGN", "Инициирование")]["minimum_normalized_score"], "0.6")
		self.assertEqual(rows_by_pair[("TECH_SUCCESS", "Реализация")]["minimum_raw_value"], "65")
		self.assertEqual(rows_by_pair[("TECH_SUCCESS", "Реализация")]["maximum_raw_value"], "100")
		self.assertEqual(rows_by_pair[("REG", "Завершение")]["minimum_normalized_score"], "0.8")
		self.assertEqual(rows_by_pair[("NPV", "Завершение")]["minimum_raw_value"], "50000000")


if __name__ == "__main__":
	unittest.main()
