import sys
import types
import unittest
from types import SimpleNamespace

try:
	import frappe  # noqa: F401
except ModuleNotFoundError:
	_frappe_stub = types.ModuleType("frappe")
	_frappe_stub._ = lambda value, *args, **kwargs: value
	_frappe_stub.get_all = lambda *args, **kwargs: []
	_frappe_stub.db = SimpleNamespace(get_all=lambda *args, **kwargs: [])
	_frappe_stub._dict = lambda value=None: SimpleNamespace(**(value or {}))
	sys.modules["frappe"] = _frappe_stub
	_frappe_utils_stub = types.ModuleType("frappe.utils")
	_frappe_utils_stub.cint = int
	sys.modules["frappe.utils"] = _frappe_utils_stub

from dinext_project_evaluation.dinext_project_evaluation.report.project_scoring_report import (  # noqa: E402
	project_scoring_report,
)
from dinext_project_evaluation.dinext_project_evaluation.report.project_scoring_report import (  # noqa: E402
	metric_registry,
)


class TestProjectScoringMetricRegistry(unittest.TestCase):
	def test_metric_catalog_exposes_axis_size_and_color_groups(self):
		catalog = metric_registry.get_metric_catalog()

		self.assertIn("axis", catalog)
		self.assertIn("size", catalog)
		self.assertIn("color", catalog)
		self.assertIn("defaults", catalog)

		axis_ids = {entry["id"] for entry in catalog["axis"]}
		size_ids = {entry["id"] for entry in catalog["size"]}
		color_ids = {entry["id"] for entry in catalog["color"]}

		self.assertIn("integral_score", axis_ids)
		self.assertIn("risk_score_norm", axis_ids)
		self.assertIn("ecv_raw", axis_ids)
		self.assertIn("cost_score_norm_inverse", size_ids)
		self.assertIn("gate_pass", color_ids)
		self.assertIn("risk_band", color_ids)

	def test_metric_catalog_defaults_follow_chart_plan(self):
		self.assertEqual(
			metric_registry.get_default_metric_config(),
			{
				"x_axis": "risk_score_norm",
				"y_axis": "integral_score",
				"size_metric": "cost_score_norm_inverse",
				"color_metric": "gate_pass",
			},
		)

	def test_metric_config_maps_legacy_axis_names_to_new_registry_ids(self):
		self.assertEqual(
			metric_registry.resolve_metric_config(
				{
					"x_axis": "risk_score",
					"y_axis": "benefit_score",
					"size_metric": "cost_score",
				}
			),
			{
				"x_axis": "risk_score_norm",
				"y_axis": "benefit_score_norm",
				"size_metric": "cost_score_norm_inverse",
				"color_metric": "gate_pass",
			},
		)


class TestProjectScoringBubblePayload(unittest.TestCase):
	def test_build_bubble_chart_payload_uses_metric_catalog_and_server_legend(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"portfolio": "PORT-001",
				"project_stage": "Discovery",
				"evaluated_stage": "Discovery",
				"scorecard": "PSC-001",
				"profile": "Default",
				"evaluation_date": "2026-06-08 00:00:00",
				"integral_score": 0.81,
				"metric_values": {
					"risk_score_norm": 0.42,
					"cost_score_norm_inverse": 0.67,
				},
				"color_values": {
					"gate_pass": {
						"value": "pass",
						"token": "gate-pass",
						"label": "Gate passed",
					}
				},
				"gate_pass": 1,
			}
		]

		payload = project_scoring_report.build_bubble_chart_payload(
			rows,
			{
				"x_axis": "risk_score_norm",
				"y_axis": "integral_score",
				"size_metric": "cost_score_norm_inverse",
				"color_metric": "gate_pass",
			},
		)

		self.assertEqual(payload["config"]["x_axis"], "risk_score_norm")
		self.assertEqual(payload["config"]["y_axis"], "integral_score")
		self.assertEqual(payload["legend"]["items"][0]["token"], "gate-pass")
		self.assertEqual(payload["points"][0]["x"]["value"], 0.42)
		self.assertEqual(payload["points"][0]["y"]["value"], 0.81)
		self.assertEqual(payload["points"][0]["size"]["value"], 0.67)
		self.assertEqual(payload["points"][0]["color"]["token"], "gate-pass")
		self.assertEqual(payload["points"][0]["meta"]["evaluation_date"], "2026-06-08 00:00:00")

	def test_build_bubble_chart_payload_skips_rows_without_selected_numeric_axes(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"integral_score": 0.81,
				"metric_values": {},
				"color_values": {
					"gate_pass": {"value": "pass", "token": "gate-pass", "label": "Gate passed"}
				},
			}
		]

		payload = project_scoring_report.build_bubble_chart_payload(
			rows,
			{
				"x_axis": "risk_score_norm",
				"y_axis": "integral_score",
				"size_metric": "cost_score_norm_inverse",
				"color_metric": "gate_pass",
			},
		)

		self.assertEqual(payload["points"], [])

	def test_build_bubble_chart_payload_falls_back_to_populated_axis_when_selected_one_is_empty(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"integral_score": 0.81,
				"metric_values": {
					"benefit_score_norm": 0.66,
					"integral_score": 0.81,
				},
				"color_values": {
					"gate_pass": {"value": "pass", "token": "gate-pass", "label": "Gate passed"}
				},
			}
		]

		payload = project_scoring_report.build_bubble_chart_payload(
			rows,
			{
				"x_axis": "risk_score_norm",
				"y_axis": "integral_score",
				"size_metric": "cost_score_norm_inverse",
				"color_metric": "gate_pass",
			},
		)

		self.assertEqual(payload["config"]["x_axis"], "benefit_score_norm")
		self.assertEqual(payload["points"][0]["x"]["value"], 0.66)


class TestProjectScoringFilterAssembly(unittest.TestCase):
	def test_scorecard_filters_keep_both_date_bounds(self):
		filters = project_scoring_report.build_scorecard_filters(
			["PRJ-001"],
			{
				"from_date": "2026-06-01",
				"to_date": "2026-06-30",
			},
		)

		self.assertIn(["evaluation_date", ">=", "2026-06-01 00:00:00"], filters)
		self.assertIn(["evaluation_date", "<=", "2026-06-30 23:59:59"], filters)

