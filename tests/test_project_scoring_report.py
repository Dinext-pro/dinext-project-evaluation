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
	_frappe_stub.get_meta = lambda doctype: None
	_frappe_stub.db = SimpleNamespace(
		get_all=lambda *args, **kwargs: [],
		has_column=lambda doctype, column: True,
		table_exists=lambda doctype: True,
	)
	_frappe_stub._dict = lambda value=None: SimpleNamespace(**(value or {}))
	sys.modules["frappe"] = _frappe_stub
	_frappe_utils_stub = types.ModuleType("frappe.utils")
	_frappe_utils_stub.cint = int
	sys.modules["frappe.utils"] = _frappe_utils_stub

import frappe  # noqa: E402

from dinext_project_evaluation.dinext_project_evaluation.report.project_scoring_report import (  # noqa: E402
	project_scoring_report,
)
from dinext_project_evaluation.dinext_project_evaluation.report.project_scoring_report import (  # noqa: E402
	metric_registry,
)


def field(fieldname, label, fieldtype, options=None):
	return SimpleNamespace(fieldname=fieldname, label=label, fieldtype=fieldtype, options=options)


def meta(fields, title_field=None):
	default_fields = [
		field("name", "ID", "Data"),
		field("creation", "Created On", "Datetime"),
		field("modified", "Last Updated On", "Datetime"),
	]
	return SimpleNamespace(fields=fields, default_fields=default_fields, title_field=title_field)


def metric_value(value, display=None, sort_value=None, label=None):
	return {
		"value": value,
		"display": display if display is not None else ("" if value is None else str(value)),
		"sort_value": sort_value if sort_value is not None else value,
		"label": label or "",
	}


class TestProjectScoringMetricRegistry(unittest.TestCase):
	def setUp(self):
		self.original_get_meta = frappe.get_meta
		self.original_db_get_all = frappe.db.get_all
		self.metas = {
			"Project": meta(
				[
					field("project_name", "Project Name", "Data"),
					field("custom_budget", "Budget", "Currency"),
					field("expected_start_date", "Expected Start Date", "Date"),
					field("priority", "Priority", "Select"),
					field("custom_project_portfolio", "Project Portfolio", "Link", "Project Portfolio"),
					field("percent_complete", "% Completed", "Percent"),
					field("is_active", "Is Active", "Check"),
					field("notes", "Notes", "Long Text"),
				],
				title_field="project_name",
			),
			"Project Scorecard": meta(
				[
					field("profile", "Profile", "Link", "Project Scoring Profile"),
					field("integral_score", "Integral Score", "Float"),
					field("evaluation_date", "Evaluation Date", "Datetime"),
					field("status", "Status", "Select"),
					field("scorecard_title", "Scorecard Title", "Data"),
					field("gate_pass", "Gate Pass", "Check"),
					field("gate_messages", "Gate Messages", "Long Text"),
				],
				title_field="scorecard_title",
			),
			"Project Portfolio": meta([field("portfolio_name", "Portfolio Name", "Data")], title_field="portfolio_name"),
			"Project Scoring Profile": meta([field("profile_name", "Profile Name", "Data")], title_field="profile_name"),
		}
		self.queryable_fields = {
			"Project": {
				"name",
				"creation",
				"modified",
				"project_name",
				"custom_budget",
				"expected_start_date",
				"priority",
				"custom_project_portfolio",
				"percent_complete",
			},
			"Project Scorecard": {
				"name",
				"creation",
				"modified",
				"profile",
				"integral_score",
				"evaluation_date",
				"status",
				"scorecard_title",
			},
		}
		frappe.get_meta = lambda doctype: self.metas[doctype]
		frappe.db.get_all = self.fake_db_get_all
		self.original_db_has_column = getattr(frappe.db, "has_column", None)
		self.original_db_table_exists = getattr(frappe.db, "table_exists", None)
		frappe.db.has_column = lambda doctype, column: column in self.queryable_fields.get(doctype, set())
		frappe.db.table_exists = lambda doctype: doctype in self.queryable_fields

	def tearDown(self):
		frappe.get_meta = self.original_get_meta
		frappe.db.get_all = self.original_db_get_all
		if self.original_db_has_column is not None:
			frappe.db.has_column = self.original_db_has_column
		if self.original_db_table_exists is not None:
			frappe.db.table_exists = self.original_db_table_exists

	def fake_db_get_all(self, doctype, filters=None, fields=None, **kwargs):
		if doctype != "Project Scoring Criterion":
			return []
		return [
			{
				"criterion_code": "FIN_VALUE",
				"criterion_name": "Financial Value",
				"input_type": "Currency",
			},
			{
				"criterion_code": "MATURITY",
				"criterion_name": "Maturity",
				"input_type": "Scale",
			},
		]

	def test_metric_catalog_uses_runtime_meta_for_axis_size_and_color_groups(self):
		catalog = metric_registry.get_metric_catalog()

		self.assertIn("axis", catalog)
		self.assertIn("size", catalog)
		self.assertIn("color", catalog)
		self.assertIn("defaults", catalog)

		axis_ids = {entry["id"] for entry in catalog["axis"]}
		size_ids = {entry["id"] for entry in catalog["size"]}
		color_ids = {entry["id"] for entry in catalog["color"]}

		self.assertIn("project:expected_start_date", axis_ids)
		self.assertIn("project:name", axis_ids)
		self.assertIn("project:priority", axis_ids)
		self.assertIn("scorecard:integral_score", axis_ids)
		self.assertIn("scorecard:creation", axis_ids)
		self.assertNotIn("project:is_active", axis_ids)
		self.assertNotIn("scorecard:gate_messages", axis_ids)

		self.assertIn("project:custom_budget", size_ids)
		self.assertIn("scorecard:integral_score", size_ids)
		self.assertIn("criterion:number:raw:FIN_VALUE", size_ids)
		self.assertIn("criterion:number:normalized:FIN_VALUE", size_ids)
		self.assertNotIn("project:priority", size_ids)

		self.assertIn("project:priority", color_ids)
		self.assertIn("project:custom_budget", color_ids)
		self.assertIn("scorecard:status", color_ids)
		self.assertIn("criterion:scale:MATURITY", color_ids)
		self.assertNotIn("project:is_active", color_ids)

	def test_metric_catalog_excludes_meta_fields_missing_db_column(self):
		self.metas["Project"].fields.append(field("custom_команда", "Команда", "Link", "Team"))
		catalog = metric_registry.get_metric_catalog()
		metric_ids = {
			entry["id"]
			for group in ("axis", "size", "color")
			for entry in catalog[group]
		}
		self.assertNotIn("project:custom_команда", metric_ids)
		fieldnames = metric_registry.get_field_metric_fieldnames(catalog, "Project")
		self.assertNotIn("custom_команда", fieldnames)

	def test_metric_catalog_defaults_are_selected_from_dynamic_runtime_catalog(self):
		catalog = metric_registry.get_metric_catalog()
		defaults = catalog["defaults"]
		axis_ids = {entry["id"] for entry in catalog["axis"]}
		size_ids = {entry["id"] for entry in catalog["size"]}
		color_ids = {entry["id"] for entry in catalog["color"]}

		self.assertIn(defaults["x_axis"], axis_ids)
		self.assertIn(defaults["y_axis"], axis_ids)
		self.assertIn(defaults["size_metric"], size_ids)
		self.assertIn(defaults["color_metric"], color_ids)
		self.assertNotEqual(defaults["x_axis"], defaults["y_axis"])


class TestProjectScoringBubblePayload(unittest.TestCase):
	def setUp(self):
		self.metric_catalog = {
			"axis": [
				{
					"id": "project:expected_start_date",
					"label": "Expected Start Date",
					"value_type": "date",
					"axis_type": "time",
					"format": "date",
				},
				{
					"id": "project:priority",
					"label": "Priority",
					"value_type": "categorical",
					"axis_type": "category",
					"format": "text",
				},
				{
					"id": "scorecard:integral_score",
					"label": "Integral Score",
					"value_type": "numeric",
					"axis_type": "value",
					"format": "float_2",
				},
			],
			"size": [
				{
					"id": "criterion:number:raw:FIN_VALUE",
					"label": "Financial Value (Raw)",
					"value_type": "numeric",
					"format": "currency",
				},
				{
					"id": "criterion:number:normalized:FIN_VALUE",
					"label": "Financial Value (Normalized)",
					"value_type": "numeric",
					"format": "float_2",
				},
			],
			"color": [
				{
					"id": "project:custom_project_portfolio",
					"label": "Project Portfolio",
					"value_type": "categorical",
					"format": "link",
				},
				{
					"id": "criterion:scale:MATURITY",
					"label": "Maturity",
					"value_type": "categorical",
					"format": "text",
				},
			],
			"defaults": {
				"x_axis": "project:expected_start_date",
				"y_axis": "scorecard:integral_score",
				"size_metric": "criterion:number:raw:FIN_VALUE",
				"color_metric": "criterion:scale:MATURITY",
			},
		}

	def test_build_bubble_chart_payload_builds_time_axis_and_category_legend(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"scorecard": "PSC-001",
				"evaluation_date": "2026-06-08 00:00:00",
				"dynamic_metric_values": {
					"project:expected_start_date": metric_value(
						"2026-06-01",
						display="2026-06-01",
						sort_value=1717200000000,
						label="Expected Start Date",
					),
					"scorecard:integral_score": metric_value(0.81, display="0.81", label="Integral Score"),
					"criterion:number:raw:FIN_VALUE": metric_value(
						150000,
						display="150000.00",
						label="Financial Value (Raw)",
					),
					"criterion:scale:MATURITY": metric_value("4", display="High", label="Maturity"),
				},
			},
			{
				"project": "PRJ-002",
				"project_name": "Beta",
				"scorecard": "PSC-002",
				"evaluation_date": "2026-06-09 00:00:00",
				"dynamic_metric_values": {
					"project:expected_start_date": metric_value(
						"2026-06-11",
						display="2026-06-11",
						sort_value=1718064000000,
						label="Expected Start Date",
					),
					"scorecard:integral_score": metric_value(0.62, display="0.62", label="Integral Score"),
					"criterion:number:raw:FIN_VALUE": metric_value(
						50000,
						display="50000.00",
						label="Financial Value (Raw)",
					),
					"criterion:scale:MATURITY": metric_value("2", display="Medium", label="Maturity"),
				},
			}
		]

		payload = project_scoring_report.build_bubble_chart_payload(
			rows,
			{
				"x_axis": "project:expected_start_date",
				"y_axis": "scorecard:integral_score",
				"size_metric": "criterion:number:raw:FIN_VALUE",
				"color_metric": "criterion:scale:MATURITY",
			},
			self.metric_catalog,
		)

		self.assertEqual(payload["axes"]["x"]["axis_type"], "time")
		self.assertEqual(payload["axes"]["y"]["axis_type"], "value")
		self.assertLess(payload["axes"]["x"]["min"], 1717200000000)
		self.assertGreater(payload["axes"]["x"]["max"], 1718064000000)
		self.assertEqual(payload["legend"]["items"][0]["label"], "High")
		self.assertEqual(payload["points"][0]["x"]["value"], "2026-06-01")
		self.assertEqual(payload["points"][0]["y"]["value"], 0.81)
		self.assertEqual(payload["points"][0]["size"]["value"], 150000)
		self.assertEqual(payload["points"][0]["color"]["label"], "High")
		self.assertEqual(payload["points"][0]["meta"]["evaluation_date"], "2026-06-08 00:00:00")

	def test_build_bubble_chart_payload_builds_category_axis_and_link_title_legend(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"scorecard": "PSC-001",
				"dynamic_metric_values": {
					"project:priority": metric_value("High", display="High", label="Priority"),
					"scorecard:integral_score": metric_value(0.81, display="0.81", label="Integral Score"),
					"criterion:number:normalized:FIN_VALUE": metric_value(
						0.75,
						display="0.75",
						label="Financial Value (Normalized)",
					),
					"project:custom_project_portfolio": metric_value(
						"PORT-001",
						display="Growth Portfolio",
						label="Project Portfolio",
					),
				},
			}
		]

		payload = project_scoring_report.build_bubble_chart_payload(
			rows,
			{
				"x_axis": "project:priority",
				"y_axis": "scorecard:integral_score",
				"size_metric": "criterion:number:normalized:FIN_VALUE",
				"color_metric": "project:custom_project_portfolio",
			},
			self.metric_catalog,
		)

		self.assertEqual(payload["axes"]["x"]["axis_type"], "category")
		self.assertEqual(payload["axes"]["x"]["categories"], ["High"])
		self.assertEqual(payload["legend"]["items"][0]["label"], "Growth Portfolio")
		self.assertEqual(payload["points"][0]["size"]["value"], 0.75)
		self.assertEqual(payload["points"][0]["color"]["display"], "Growth Portfolio")

	def test_build_bubble_chart_payload_skips_rows_without_selected_axis_values(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"dynamic_metric_values": {
					"project:expected_start_date": metric_value(
						None,
						display="N/A",
						sort_value=None,
						label="Expected Start Date",
					),
					"scorecard:integral_score": metric_value(0.81, display="0.81", label="Integral Score"),
				},
			}
		]

		payload = project_scoring_report.build_bubble_chart_payload(
			rows,
			{
				"x_axis": "project:expected_start_date",
				"y_axis": "scorecard:integral_score",
				"size_metric": "criterion:number:raw:FIN_VALUE",
				"color_metric": "criterion:scale:MATURITY",
			},
			self.metric_catalog,
		)

		self.assertEqual(payload["points"], [])


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


class TestProjectScoringDatasetAwareCatalog(unittest.TestCase):
	def setUp(self):
		self.full_catalog = {
			"axis": [
				{"id": "project:expected_start_date", "label": "Expected Start Date", "value_type": "date"},
				{"id": "project:priority", "label": "Priority", "value_type": "categorical"},
				{"id": "scorecard:integral_score", "label": "Integral Score", "value_type": "numeric"},
			],
			"size": [
				{"id": "scorecard:integral_score", "label": "Integral Score", "value_type": "numeric"},
				{"id": "criterion:number:raw:FIN_VALUE", "label": "Financial Value (Raw)", "value_type": "numeric"},
			],
			"color": [
				{"id": "project:priority", "label": "Priority", "value_type": "categorical"},
				{"id": "criterion:scale:MATURITY", "label": "Maturity", "value_type": "categorical"},
			],
			"defaults": {
				"x_axis": "project:expected_start_date",
				"y_axis": "scorecard:integral_score",
				"size_metric": "scorecard:integral_score",
				"color_metric": "project:priority",
			},
		}

	def test_collect_available_metric_ids_treats_zero_as_present(self):
		rows = [
			{
				"dynamic_metric_values": {
					"scorecard:integral_score": metric_value(0, display="0.00", label="Integral Score"),
					"project:priority": metric_value(None, display="N/A", label="Priority"),
				}
			}
		]
		available = project_scoring_report.collect_available_metric_ids(rows)
		self.assertIn("scorecard:integral_score", available)
		self.assertNotIn("project:priority", available)

	def test_filter_catalog_by_available_ids_removes_empty_metrics(self):
		filtered = metric_registry.filter_catalog_by_available_ids(
			self.full_catalog,
			{"project:expected_start_date", "scorecard:integral_score"},
		)
		axis_ids = {entry["id"] for entry in filtered["axis"]}
		size_ids = {entry["id"] for entry in filtered["size"]}
		color_ids = {entry["id"] for entry in filtered["color"]}

		self.assertEqual(axis_ids, {"project:expected_start_date", "scorecard:integral_score"})
		self.assertEqual(size_ids, {"scorecard:integral_score"})
		self.assertEqual(color_ids, set())
		self.assertIn(filtered["defaults"]["x_axis"], axis_ids)
		self.assertIn(filtered["defaults"]["y_axis"], axis_ids)

	def test_collect_available_metric_ids_scans_beyond_display_slice(self):
		rows = [{"dynamic_metric_values": {}} for _ in range(project_scoring_report.PROJECT_LIMIT)]
		rows.append(
			{
				"dynamic_metric_values": {
					"criterion:number:raw:FIN_VALUE": metric_value(1000, display="1000.00"),
				}
			}
		)
		available = project_scoring_report.collect_available_metric_ids(rows)
		self.assertIn("criterion:number:raw:FIN_VALUE", available)

	def test_resolve_metric_config_falls_back_when_selection_not_in_filtered_catalog(self):
		filtered = metric_registry.filter_catalog_by_available_ids(
			self.full_catalog,
			{"scorecard:integral_score", "project:priority"},
		)
		config = metric_registry.resolve_metric_config(
			{
				"x_axis": "project:expected_start_date",
				"y_axis": "scorecard:integral_score",
				"size_metric": "criterion:number:raw:FIN_VALUE",
				"color_metric": "criterion:scale:MATURITY",
			},
			filtered,
		)
		axis_ids = {entry["id"] for entry in filtered["axis"]}
		size_ids = {entry["id"] for entry in filtered["size"]}
		color_ids = {entry["id"] for entry in filtered["color"]}

		self.assertIn(config["x_axis"], axis_ids)
		self.assertEqual(config["y_axis"], "scorecard:integral_score")
		self.assertIn(config["size_metric"], size_ids)
		self.assertIn(config["color_metric"], color_ids)

	def test_build_report_message_returns_filtered_catalog(self):
		rows = [
			{
				"project": "PRJ-001",
				"project_name": "Alpha",
				"scorecard": "PSC-001",
				"dynamic_metric_values": {
					"project:expected_start_date": metric_value(
						"2026-06-01",
						display="2026-06-01",
						sort_value=1717200000000,
					),
					"scorecard:integral_score": metric_value(0.81, display="0.81"),
				},
			}
		]
		available = project_scoring_report.collect_available_metric_ids(rows)
		filtered_catalog = metric_registry.filter_catalog_by_available_ids(self.full_catalog, available)
		metric_config = metric_registry.resolve_metric_config({}, filtered_catalog)
		message = project_scoring_report.build_report_message(rows, {}, 1, metric_config, filtered_catalog)

		payload_axis_ids = {entry["id"] for entry in message["metric_catalog"]["axis"]}
		self.assertIn("project:expected_start_date", payload_axis_ids)
		self.assertIn("scorecard:integral_score", payload_axis_ids)
		self.assertNotIn("project:priority", payload_axis_ids)
		self.assertNotIn("criterion:number:raw:FIN_VALUE", {entry["id"] for entry in message["metric_catalog"]["size"]})

