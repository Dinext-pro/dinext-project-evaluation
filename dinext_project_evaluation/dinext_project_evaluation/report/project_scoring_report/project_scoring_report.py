from __future__ import annotations

import math
import re

import frappe
from frappe import _

from dinext_project_evaluation.dinext_project_evaluation.report.project_scoring_report import metric_registry
from dinext_project_evaluation.scoring.workflow_constants import SCORECARD_AGREED_DOCSTATUS


PROJECT_LIMIT = 100
SCORECARD_ITEM_LIMIT = 5000
REPORT_FETCH_LIMIT = 5000

RISK_CODES = ("RISK_IMP", "RISK_PROB")
BENEFIT_CODES = ("STR_ALIGN", "BEN_FIN", "BEN_NONFIN", "MKT_SHARE", "SALES_POT")
COST_CODES = ("COST", "RD_COST", "MFG_COST")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	metric_config = metric_registry.resolve_metric_config(filters)
	columns = get_columns()
	data, total_rows = get_data(filters)
	message = build_report_message(data, filters, total_rows, metric_config)
	report_summary = build_report_summary(data, message["bubble_chart"]["points"], total_rows)
	return columns, data, message, None, report_summary


def get_columns():
	return [
		{"fieldname": "project", "label": _("Project"), "fieldtype": "Link", "options": "Project", "width": 180},
		{"fieldname": "project_name", "label": _("Project Name"), "fieldtype": "Data", "width": 220},
		{"fieldname": "portfolio", "label": _("Portfolio"), "fieldtype": "Link", "options": "Project Portfolio", "width": 180},
		{
			"fieldname": "project_stage",
			"label": _("Current Stage", context="Dinext.StageGateModel"),
			"fieldtype": "Link",
			"options": "Project Stage",
			"width": 160,
		},
		{
			"fieldname": "evaluated_stage",
			"label": _("Evaluated Stage", context="Dinext.StageGateModel"),
			"fieldtype": "Link",
			"options": "Project Stage",
			"width": 160,
		},
		{"fieldname": "scorecard", "label": _("Scorecard"), "fieldtype": "Link", "options": "Project Scorecard", "width": 180},
		{"fieldname": "profile", "label": _("Profile"), "fieldtype": "Link", "options": "Project Scoring Profile", "width": 180},
		{"fieldname": "evaluation_date", "label": _("Evaluation Date"), "fieldtype": "Datetime", "width": 170},
		{"fieldname": "integral_score", "label": _("Integral Score"), "fieldtype": "Float", "width": 120},
		{"fieldname": "gate_pass", "label": _("Gate Pass"), "fieldtype": "Check", "width": 90},
		{"fieldname": "risk_score_norm", "label": _("Risk Score"), "fieldtype": "Float", "width": 110},
		{"fieldname": "benefit_score_norm", "label": _("Benefit Score"), "fieldtype": "Float", "width": 110},
		{"fieldname": "cost_score_norm", "label": _("Cost Score"), "fieldtype": "Float", "width": 110},
	]


def get_data(filters):
	projects = _get_projects(filters)
	scorecards_by_project = _get_latest_agreed_scorecards([project["name"] for project in projects], filters)
	scorecard_metrics = _get_scorecard_metrics(
		[scorecard["name"] for scorecard in scorecards_by_project.values() if scorecard.get("name")]
	)

	rows = []
	for project in projects:
		scorecard = scorecards_by_project.get(project["name"])
		if not scorecard and _requires_matching_scorecard(filters):
			continue
		rows.append(_build_row(project, scorecard, scorecard_metrics.get(scorecard["name"]) if scorecard else None))

	rows.sort(key=_sort_key)
	total_rows = len(rows)
	return rows[:PROJECT_LIMIT], total_rows


def build_report_message(rows, filters, total_rows, metric_config=None):
	metric_config = metric_config or metric_registry.resolve_metric_config(filters)
	bubble_chart = build_bubble_chart_payload(rows, metric_config)
	notice = None
	if total_rows > PROJECT_LIMIT:
		notice = _("Showing first {0} projects. Narrow filters to reduce chart overload.").format(PROJECT_LIMIT)
	return {
		"summary": {
			"total_rows": total_rows,
			"displayed_rows": len(rows),
			"plotted_points": len(bubble_chart["points"]),
			"notice": notice,
		},
		"metric_catalog": metric_registry.get_metric_catalog(),
		"bubble_chart": bubble_chart,
	}


def build_report_summary(rows, points, total_rows):
	return [
		{"value": total_rows, "label": _("Projects"), "datatype": "Int"},
		{"value": sum(1 for row in rows if row.get("scorecard")), "label": _("Scored Projects"), "datatype": "Int"},
		{"value": len(points), "label": _("Plotted Projects"), "datatype": "Int"},
	]


def build_bubble_chart_payload(rows, filters):
	metric_config = metric_registry.resolve_metric_config(filters)
	x_metric, y_metric = _resolve_plot_axis_metrics(rows, metric_config["x_axis"], metric_config["y_axis"])
	size_metric = metric_config["size_metric"]
	color_metric = metric_config["color_metric"]
	metric_config["x_axis"] = x_metric
	metric_config["y_axis"] = y_metric

	points = []
	raw_sizes = []

	for row in rows:
		x_value = _get_numeric_metric_value(row, x_metric)
		y_value = _get_numeric_metric_value(row, y_metric)
		if x_value is None or y_value is None:
			continue

		size_value = _get_numeric_metric_value(row, size_metric)
		color_descriptor = _get_color_descriptor(row, color_metric)
		point = {
			"project": row.get("project"),
			"label": row.get("project_name") or row.get("project"),
			"portfolio": row.get("portfolio"),
			"project_stage": row.get("project_stage"),
			"evaluated_stage": row.get("evaluated_stage"),
			"scorecard": row.get("scorecard"),
			"profile": row.get("profile"),
			"gate_pass": row.get("gate_pass"),
			"x": _build_numeric_descriptor(x_metric, x_value),
			"y": _build_numeric_descriptor(y_metric, y_value),
			"size": _build_numeric_descriptor(size_metric, size_value),
			"color": color_descriptor,
			"meta": {
				"integral_score": row.get("integral_score"),
				"evaluation_date": row.get("evaluation_date"),
				"metric_values": dict(row.get("metric_values") or {}),
			},
		}
		points.append(point)
		raw_sizes.append(size_value)

	for point, normalized_size in zip(points, _normalize_bubble_sizes(raw_sizes)):
		point["size"]["normalized"] = normalized_size

	return {
		"config": metric_config,
		"legend": {
			"metric": color_metric,
			"items": _build_legend(points),
		},
		"points": points,
	}


def _resolve_plot_axis_metrics(rows, x_metric, y_metric):
	if _metric_has_plot_values(rows, x_metric, y_metric):
		return x_metric, y_metric

	candidates = [
		entry["id"]
		for entry in metric_registry.get_metric_catalog()["axis"]
		if entry["id"] != y_metric and _metric_has_any_values(rows, entry["id"])
	]
	for candidate in candidates:
		if _metric_has_plot_values(rows, candidate, y_metric):
			return candidate, y_metric

	if _metric_has_any_values(rows, x_metric):
		for candidate in [
			entry["id"]
			for entry in metric_registry.get_metric_catalog()["axis"]
			if entry["id"] != x_metric and _metric_has_any_values(rows, entry["id"])
		]:
			if _metric_has_plot_values(rows, x_metric, candidate):
				return x_metric, candidate

	return x_metric, y_metric


def _get_projects(filters):
	project_filters = {}
	if filters.get("project_portfolio"):
		project_filters["custom_project_portfolio"] = filters["project_portfolio"]
	if filters.get("project_stage"):
		project_filters["current_stage"] = filters["project_stage"]
	if filters.get("project"):
		project_names = filters.project if isinstance(filters.project, list) else [filters.project]
		project_filters["name"] = ["in", project_names]

	return frappe.db.get_all(
		"Project",
		filters=project_filters,
		fields=["name", "project_name", "custom_project_portfolio", "current_stage", "modified"],
		order_by="modified desc",
		limit_page_length=REPORT_FETCH_LIMIT,
	)


def _get_latest_agreed_scorecards(project_names, filters):
	if not project_names:
		return {}

	scorecards = frappe.db.get_all(
		"Project Scorecard",
		filters=build_scorecard_filters(project_names, filters),
		fields=[
			"name",
			"project",
			"profile",
			"evaluation_date",
			"integral_score",
			"gate_pass",
			"stage_at_evaluation",
			"modified",
		],
		order_by="evaluation_date desc, modified desc, name desc",
		limit_page_length=REPORT_FETCH_LIMIT,
	)

	latest_by_project = {}
	for scorecard in scorecards:
		latest_by_project.setdefault(scorecard["project"], scorecard)
	return latest_by_project


def build_scorecard_filters(project_names, filters):
	scorecard_filters = [
		["project", "in", project_names],
		["docstatus", "=", SCORECARD_AGREED_DOCSTATUS],
	]
	if filters.get("profile"):
		scorecard_filters.append(["profile", "=", filters["profile"]])
	if filters.get("evaluated_stage"):
		scorecard_filters.append(["stage_at_evaluation", "=", filters["evaluated_stage"]])
	if filters.get("gate_pass") in (0, 1, "0", "1"):
		scorecard_filters.append(["gate_pass", "=", int(filters["gate_pass"])])
	if filters.get("from_date"):
		scorecard_filters.append(["evaluation_date", ">=", f"{filters['from_date']} 00:00:00"])
	if filters.get("to_date"):
		scorecard_filters.append(["evaluation_date", "<=", f"{filters['to_date']} 23:59:59"])
	return scorecard_filters


def _get_scorecard_metrics(scorecard_names):
	if not scorecard_names:
		return {}

	items = frappe.db.get_all(
		"Project Scorecard Item",
		filters={"parent": ["in", scorecard_names]},
		fields=["parent", "criterion_code", "normalized_score", "raw_numeric_value"],
		order_by="idx asc",
		limit_page_length=SCORECARD_ITEM_LIMIT,
	)

	scorecard_metrics = {}
	for item in items:
		target = scorecard_metrics.setdefault(item["parent"], {"normalized": {}, "raw": {}})
		code = item.get("criterion_code")
		if not code:
			continue
		target["normalized"][code] = item.get("normalized_score")
		target["raw"][code] = item.get("raw_numeric_value")
	return scorecard_metrics


def _build_row(project, scorecard, scorecard_metrics):
	scorecard_metrics = scorecard_metrics or {"normalized": {}, "raw": {}}
	metric_values = _build_metric_values(scorecard, scorecard_metrics)
	row = {
		"project": project.get("name"),
		"project_name": project.get("project_name"),
		"portfolio": project.get("custom_project_portfolio"),
		"project_stage": project.get("current_stage"),
		"evaluated_stage": scorecard.get("stage_at_evaluation") if scorecard else None,
		"scorecard": scorecard.get("name") if scorecard else None,
		"profile": scorecard.get("profile") if scorecard else None,
		"evaluation_date": scorecard.get("evaluation_date") if scorecard else None,
		"integral_score": scorecard.get("integral_score") if scorecard else None,
		"gate_pass": scorecard.get("gate_pass") if scorecard else None,
		"risk_score_norm": metric_values.get("risk_score_norm"),
		"benefit_score_norm": metric_values.get("benefit_score_norm"),
		"cost_score_norm": metric_values.get("cost_score_norm"),
		"metric_values": metric_values,
		"color_values": {},
		"_project_modified": project.get("modified"),
	}
	row["color_values"] = _build_color_values(row)
	return row


def _build_metric_values(scorecard, scorecard_metrics):
	normalized = scorecard_metrics.get("normalized") or {}
	raw = scorecard_metrics.get("raw") or {}

	metric_values = {
		"integral_score": scorecard.get("integral_score") if scorecard else None,
		"risk_score_norm": _average([normalized.get(code) for code in RISK_CODES]),
		"benefit_score_norm": _average([normalized.get(code) for code in BENEFIT_CODES]),
		"cost_score_norm": _average([normalized.get(code) for code in COST_CODES]),
		"strategic_alignment_norm": normalized.get("STR_ALIGN"),
		"market_potential_norm": normalized.get("SALES_POT") or normalized.get("MKT_SHARE"),
		"urgency_norm": normalized.get("URGENCY"),
		"regulatory_fit_norm": normalized.get("REG"),
		"capability_norm": normalized.get("CAP_HUM_TECH"),
		"innovation_patent_norm": normalized.get("PATENT"),
		"cost_raw": raw.get("COST"),
		"npv_raw": raw.get("NPV"),
		"irr_raw": raw.get("IRR"),
		"payback_period_raw": raw.get("PP"),
		"profitability_index_raw": raw.get("PI"),
		"ecv_raw": raw.get("ECV"),
		"rd_cost_raw": raw.get("RD_COST"),
		"mfg_cost_raw": raw.get("MFG_COST"),
		"tech_success_pct_raw": raw.get("TECH_SUCCESS"),
	}
	if metric_values["cost_score_norm"] is not None:
		metric_values["cost_score_norm_inverse"] = max(0, 1 - metric_values["cost_score_norm"])
	else:
		metric_values["cost_score_norm_inverse"] = None

	rd_cost = metric_values.get("rd_cost_raw")
	mfg_cost = metric_values.get("mfg_cost_raw")
	if rd_cost is not None or mfg_cost is not None:
		metric_values["innovation_cost_total_raw"] = (rd_cost or 0) + (mfg_cost or 0)
	else:
		metric_values["innovation_cost_total_raw"] = None

	return metric_values


def _build_color_values(row):
	risk_value = row["metric_values"].get("risk_score_norm")
	return {
		"gate_pass": _gate_pass_color(row.get("gate_pass")),
		"risk_band": _risk_band_color(risk_value),
		"current_stage": _tokenized_color(row.get("project_stage"), "stage", _("No current stage")),
		"profile": _tokenized_color(row.get("profile"), "profile", _("No profile")),
		"portfolio": _tokenized_color(row.get("portfolio"), "portfolio", _("No portfolio")),
	}


def _gate_pass_color(gate_pass):
	if gate_pass in (1, "1", True):
		return {"value": "pass", "token": "gate-pass", "label": _("Gate passed")}
	if gate_pass in (0, "0", False):
		return {"value": "fail", "token": "gate-fail", "label": _("Gate failed")}
	return {"value": "unknown", "token": "gate-unknown", "label": _("No agreed scorecard")}


def _risk_band_color(risk_score):
	if risk_score is None:
		return {"value": "unknown", "token": "risk-unknown", "label": _("Risk unknown")}
	if risk_score >= 0.67:
		return {"value": "low", "token": "risk-low", "label": _("Low risk")}
	if risk_score >= 0.34:
		return {"value": "medium", "token": "risk-medium", "label": _("Medium risk")}
	return {"value": "high", "token": "risk-high", "label": _("High risk")}


def _tokenized_color(value, prefix, empty_label):
	if not value:
		return {"value": "unknown", "token": f"{prefix}-unknown", "label": empty_label}
	token = _slugify(value)
	return {"value": value, "token": f"{prefix}-{token}", "label": value}


def _slugify(value):
	return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-") or "unknown"


def _get_numeric_metric_value(row, metric_id):
	if metric_id in row:
		return row.get(metric_id)
	return (row.get("metric_values") or {}).get(metric_id)


def _metric_has_any_values(rows, metric_id):
	return any(_get_numeric_metric_value(row, metric_id) is not None for row in rows)


def _metric_has_plot_values(rows, x_metric, y_metric):
	for row in rows:
		if _get_numeric_metric_value(row, x_metric) is not None and _get_numeric_metric_value(row, y_metric) is not None:
			return True
	return False


def _get_color_descriptor(row, metric_id):
	return (row.get("color_values") or {}).get(metric_id) or {
		"value": "unknown",
		"token": f"{metric_id}-unknown",
		"label": _("Unknown"),
	}


def _build_numeric_descriptor(metric_id, value):
	definition = metric_registry.get_metric_definition(metric_id) or {"label": metric_id, "format": "float_2"}
	return {
		"metric": metric_id,
		"label": definition["label"],
		"value": value,
		"display": _format_metric_value(value, definition.get("format")),
	}


def _build_legend(points):
	legend_items = []
	seen = set()
	for point in points:
		color = point["color"]
		key = (color["value"], color["token"])
		if key in seen:
			continue
		seen.add(key)
		legend_items.append(
			{
				"value": color["value"],
				"token": color["token"],
				"label": color["label"],
			}
		)
	return legend_items


def _format_metric_value(value, fmt):
	if value is None:
		return _("N/A")
	if fmt == "currency":
		return f"{value:,.2f}"
	if fmt == "percent":
		return f"{value:.2f}%"
	if fmt == "int":
		return str(int(value))
	return f"{value:.2f}"


def _normalize_bubble_sizes(values):
	normalized = [value for value in values if value is not None]
	if not normalized:
		return [18 for _ in values]

	minimum = min(normalized)
	maximum = max(normalized)
	if math.isclose(minimum, maximum):
		return [18 if value is not None else 12 for value in values]

	result = []
	for value in values:
		if value is None:
			result.append(12)
			continue
		scale = (value - minimum) / (maximum - minimum)
		result.append(8 + scale * 26)
	return result


def _requires_matching_scorecard(filters):
	return bool(
		filters.get("profile")
		or filters.get("evaluated_stage")
		or filters.get("from_date")
		or filters.get("to_date")
		or filters.get("gate_pass") in (0, 1, "0", "1")
	)


def _sort_key(row):
	integral_score = row.get("integral_score")
	return (
		integral_score is None,
		-(integral_score or -1),
		row.get("_project_modified") or "",
	)


def _average(values):
	values = [value for value in values if value is not None]
	return sum(values) / len(values) if values else None
