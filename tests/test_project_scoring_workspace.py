import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "dinext_project_evaluation" / "dinext_project_evaluation"
WORKSPACE_JSON = APP_ROOT / "workspace" / "скоринг_проектов" / "скоринг_проектов.json"
NUMBER_CARD_DIR = APP_ROOT / "number_card"

EXPECTED_CARD_LABELS = {
	"Карточки в работе",
	"Карточки на согласовании",
	"Согласованные карточки",
	"Карточки с непрохождением gate",
	"Проекты с профилем оценки",
	"Проекты без профиля оценки",
}

EXPECTED_SHORTCUT_TARGETS = {
	"Project Scorecard",
	"Project Scoring Report",
	"Project",
	"Project Portfolio",
}

EXPECTED_LINK_TARGETS = {
	"Project Scoring Profile",
	"Project Scoring Criterion",
	"Project Scoring Criterion Group",
	"Project Scorecard",
}


def _load_number_card_payloads():
	payloads = []
	for path in sorted(NUMBER_CARD_DIR.glob("*/*.json")):
		payloads.append(json.loads(path.read_text(encoding="utf-8")))
	return payloads


class TestProjectScoringWorkspace(unittest.TestCase):
	def test_workspace_json_exists(self):
		self.assertTrue(WORKSPACE_JSON.exists(), f"Missing workspace definition: {WORKSPACE_JSON}")

	def test_workspace_json_structure(self):
		payload = json.loads(WORKSPACE_JSON.read_text(encoding="utf-8"))

		self.assertEqual(payload["doctype"], "Workspace")
		self.assertEqual(payload["label"], "Скоринг проектов")
		self.assertEqual(payload["title"], "Скоринг проектов")
		self.assertEqual(payload["module"], "Dinext Project Evaluation")
		self.assertEqual(payload["public"], 1)
		self.assertEqual(payload["charts"], [])
		self.assertEqual(payload["quick_lists"], [])
		self.assertEqual(payload["custom_blocks"], [])

		workspace_card_labels = {row["label"] for row in payload["number_cards"]}
		self.assertEqual(workspace_card_labels, EXPECTED_CARD_LABELS)

		shortcut_targets = {row["link_to"] for row in payload["shortcuts"]}
		self.assertEqual(shortcut_targets, EXPECTED_SHORTCUT_TARGETS)

		link_targets = {
			row["link_to"]
			for row in payload["links"]
			if row.get("type") == "Link" and row.get("link_type") in {"DocType", "Report"}
		}
		self.assertEqual(link_targets, EXPECTED_LINK_TARGETS)

		role_names = {row["role"] for row in payload["roles"]}
		self.assertTrue(
			{
				"Project Scorecard Author",
				"Project Scorecard Reviewer",
				"Project Scorecard Approver",
				"Project Scorecard Admin",
			}.issubset(role_names)
		)

		content = json.loads(payload["content"])
		block_types = {block["type"] for block in content}
		self.assertIn("number_card", block_types)
		self.assertIn("shortcut", block_types)
		self.assertIn("card", block_types)

		declared_shortcuts = {row["label"] for row in payload["shortcuts"]}
		declared_cards = {row["label"] for row in payload["links"] if row.get("type") == "Card Break"}
		content_number_cards = {
			block["data"]["number_card_name"] for block in content if block.get("type") == "number_card"
		}
		content_shortcuts = {
			block["data"]["shortcut_name"] for block in content if block.get("type") == "shortcut"
		}
		content_cards = {block["data"]["card_name"] for block in content if block.get("type") == "card"}

		self.assertEqual(content_number_cards, EXPECTED_CARD_LABELS)
		self.assertEqual(content_shortcuts, declared_shortcuts)
		self.assertEqual(content_cards, declared_cards)

		section_text = payload["content"]
		self.assertIn("Сводка скоринга", section_text)
		self.assertIn("Работа со скоркартами", section_text)
		self.assertIn("Аналитика портфеля", section_text)
		self.assertIn("Профили и критерии", section_text)

	def test_number_card_fixture_matches_workspace(self):
		workspace = json.loads(WORKSPACE_JSON.read_text(encoding="utf-8"))
		workspace_card_names = {row["number_card_name"] for row in workspace["number_cards"]}
		card_names = {payload["name"] for payload in _load_number_card_payloads()}
		self.assertEqual(card_names, workspace_card_names)

	def test_number_card_filters_use_live_scoring_fields(self):
		payloads = _load_number_card_payloads()
		self.assertEqual(len(payloads), 6)

		for payload in payloads:
			self.assertEqual(payload["doctype"], "Number Card")
			self.assertEqual(payload["type"], "Document Type")
			self.assertEqual(payload["function"], "Count")
			self.assertEqual(payload["is_standard"], 1)
			self.assertEqual(payload["is_public"], 1)
			self.assertIn(payload["document_type"], {"Project", "Project Scorecard"})

		label_to_filters = {payload["label"]: json.loads(payload["filters_json"]) for payload in payloads}

		self.assertEqual(
			label_to_filters["Карточки в работе"],
			[["Project Scorecard", "status", "in", ["Draft", "Rejected"], False]],
		)
		self.assertEqual(
			label_to_filters["Карточки на согласовании"],
			[["Project Scorecard", "status", "in", ["Submitted for Review", "Reviewed"], False]],
		)
		self.assertEqual(
			label_to_filters["Согласованные карточки"],
			[["Project Scorecard", "status", "=", "Approved", False]],
		)
		self.assertEqual(
			label_to_filters["Карточки с непрохождением gate"],
			[
				["Project Scorecard", "status", "=", "Approved", False],
				["Project Scorecard", "gate_pass", "=", 0, False],
			],
		)
		self.assertEqual(
			label_to_filters["Проекты с профилем оценки"],
			[["Project", "custom_project_scoring_profile", "is", "set", False]],
		)
		self.assertEqual(
			label_to_filters["Проекты без профиля оценки"],
			[["Project", "custom_project_scoring_profile", "is", "not set", False]],
		)


if __name__ == "__main__":
	unittest.main()
