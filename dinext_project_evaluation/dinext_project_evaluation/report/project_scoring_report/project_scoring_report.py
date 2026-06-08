from __future__ import annotations

from datetime import datetime
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
CATEGORY_MISSING_VALUE = "__missing__"
CATEGORY_MISSING_SORT = "__missing__"
MISSING_BUBBLE_SYMBOL_SIZE = 6
MIN_SCORED_BUBBLE_SYMBOL_SIZE = 10
MAX_SCORED_BUBBLE_SYMBOL_SIZE = 34
DEFAULT_SCORED_BUBBLE_SYMBOL_SIZE = 18
SCORED_BUBBLE_SYMBOL_SIZE_RANGE = MAX_SCORED_BUBBLE_SYMBOL_SIZE - MIN_SCORED_BUBBLE_SYMBOL_SIZE


def execute(filters=None):
	filters = frappe._dict(filters or {})
	full_catalog = metric_registry.get_metric_catalog()
	columns = get_columns()
	data, total_rows, available_metric_ids = get_data(filters, full_catalog)
	filtered_catalog = metric_registry.filter_catalog_by_available_ids(full_catalog, available_metric_ids)
	metric_config = metric_registry.resolve_metric_config(filters, filtered_catalog)
	message = build_report_message(data, filters, total_rows, metric_config, filtered_catalog)
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


def get_data(filters, metric_catalog=None):
	metric_catalog = metric_catalog or metric_registry.get_metric_catalog()
	project_metric_fields = metric_registry.get_field_metric_fieldnames(metric_catalog, "Project")
	scorecard_metric_fields = metric_registry.get_field_metric_fieldnames(metric_catalog, "Project Scorecard")

	projects = _get_projects(filters, project_metric_fields)
	scorecards_by_project = _get_latest_agreed_scorecards(
		[project["name"] for project in projects],
		filters,
		scorecard_metric_fields,
	)
	scorecard_metrics = _get_scorecard_metrics(
		[scorecard["name"] for scorecard in scorecards_by_project.values() if scorecard.get("name")]
	)

	rows = []
	for project in projects:
		scorecard = scorecards_by_project.get(project["name"])
		if not scorecard and _requires_matching_scorecard(filters):
			continue
		rows.append(
			_build_row(
				project,
				scorecard,
				scorecard_metrics.get(scorecard["name"]) if scorecard else None,
				metric_catalog,
			)
		)

	rows.sort(key=_sort_key)
	total_rows = len(rows)
	available_metric_ids = collect_available_metric_ids(rows)
	return rows[:PROJECT_LIMIT], total_rows, available_metric_ids


def collect_available_metric_ids(rows) -> set[str]:
	available = set()
	for row in rows:
		for metric_id, descriptor in (row.get("dynamic_metric_values") or {}).items():
			if _has_metric_value(descriptor):
				available.add(metric_id)
	return available


def build_report_message(rows, filters, total_rows, metric_config=None, metric_catalog=None):
	metric_catalog = metric_catalog or metric_registry.get_metric_catalog()
	metric_config = metric_config or metric_registry.resolve_metric_config(filters, metric_catalog)
	bubble_chart = build_bubble_chart_payload(rows, metric_config, metric_catalog)
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
		"metric_catalog": metric_catalog,
		"bubble_chart": bubble_chart,
	}


def build_report_summary(rows, points, total_rows):
	return [
		{"value": total_rows, "label": _("Projects"), "datatype": "Int"},
		{"value": sum(1 for row in rows if row.get("scorecard")), "label": _("Scored Projects"), "datatype": "Int"},
		{"value": len(points), "label": _("Plotted Projects"), "datatype": "Int"},
	]


def build_bubble_chart_payload(rows, filters, metric_catalog=None):
	metric_catalog = metric_catalog or metric_registry.get_metric_catalog()
	metric_config = metric_registry.resolve_metric_config(filters, metric_catalog)
	x_definition = metric_registry.get_metric_definition(metric_config["x_axis"], metric_catalog)
	y_definition = metric_registry.get_metric_definition(metric_config["y_axis"], metric_catalog)
	size_definition = metric_registry.get_metric_definition(metric_config["size_metric"], metric_catalog)
	color_definition = metric_registry.get_metric_definition(metric_config["color_metric"], metric_catalog)

	points = []
	raw_sizes = []

	for row in rows:
		x_value = _resolve_axis_metric_descriptor(
			_get_metric_descriptor(row, metric_config["x_axis"], x_definition),
			x_definition,
		)
		y_value = _resolve_axis_metric_descriptor(
			_get_metric_descriptor(row, metric_config["y_axis"], y_definition),
			y_definition,
		)
		if not _has_metric_value(x_value) or not _has_metric_value(y_value):
			continue

		size_value = _get_metric_descriptor(row, metric_config["size_metric"], size_definition)
		color_value = _build_color_descriptor(row, metric_config["color_metric"], color_definition)
		point = {
			"project": row.get("project"),
			"label": row.get("project_name") or row.get("project"),
			"portfolio": row.get("portfolio_display") or row.get("portfolio"),
			"project_stage": row.get("project_stage_display") or row.get("project_stage"),
			"evaluated_stage": row.get("evaluated_stage_display") or row.get("evaluated_stage"),
			"scorecard": row.get("scorecard"),
			"profile": row.get("profile_display") or row.get("profile"),
			"gate_pass": row.get("gate_pass"),
			"x": x_value,
			"y": y_value,
			"size": size_value,
			"color": color_value,
			"meta": {
				"integral_score": row.get("integral_score"),
				"evaluation_date": row.get("evaluation_date"),
				"dynamic_metric_values": dict(row.get("dynamic_metric_values") or {}),
			},
		}
		points.append(point)
		raw_sizes.append(size_value.get("value") if size_value else None)

	for point, normalized_size in zip(points, _normalize_bubble_sizes(raw_sizes)):
		if point.get("size"):
			point["size"]["normalized"] = normalized_size

	return {
		"config": metric_config,
		"axes": {
			"x": _build_axis_definition(rows, metric_config["x_axis"], x_definition),
			"y": _build_axis_definition(rows, metric_config["y_axis"], y_definition),
		},
		"legend": {
			"metric": metric_config["color_metric"],
			"metric_label": color_definition.get("label") if color_definition else metric_config["color_metric"],
			"items": _build_legend(points),
		},
		"points": points,
	}


def _get_projects(filters, dynamic_fields):
	project_filters = {}
	if filters.get("project_portfolio"):
		project_filters["custom_project_portfolio"] = filters["project_portfolio"]
	if filters.get("project_stage"):
		project_filters["current_stage"] = filters["project_stage"]
	if filters.get("project"):
		project_names = filters.project if isinstance(filters.project, list) else [filters.project]
		project_filters["name"] = ["in", project_names]

	fields = _unique(
		["name", "project_name", "custom_project_portfolio", "current_stage", "modified"] + list(dynamic_fields or [])
	)
	return frappe.db.get_all(
		"Project",
		filters=project_filters,
		fields=fields,
		order_by="modified desc",
		limit_page_length=REPORT_FETCH_LIMIT,
	)


def _get_latest_agreed_scorecards(project_names, filters, dynamic_fields):
	if not project_names:
		return {}

	fields = _unique(
		[
			"name",
			"project",
			"profile",
			"evaluation_date",
			"integral_score",
			"gate_pass",
			"stage_at_evaluation",
			"modified",
		]
		+ list(dynamic_fields or [])
	)
	scorecards = frappe.db.get_all(
		"Project Scorecard",
		filters=build_scorecard_filters(project_names, filters),
		fields=fields,
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
		fields=[
			"parent",
			"criterion_code",
			"criterion_input_type",
			"normalized_score",
			"raw_numeric_value",
			"raw_value",
			"value_display",
		],
		order_by="idx asc",
		limit_page_length=SCORECARD_ITEM_LIMIT,
	)

	scorecard_metrics = {}
	for item in items:
		target = scorecard_metrics.setdefault(
			item["parent"],
			{"normalized": {}, "raw": {}, "scale_raw": {}, "scale_display": {}},
		)
		code = item.get("criterion_code")
		if not code:
			continue

		input_type = item.get("criterion_input_type")
		if input_type in {"Number", "Currency", "Percent"}:
			target["normalized"][code] = item.get("normalized_score")
			target["raw"][code] = item.get("raw_numeric_value")
		if input_type == "Scale":
			target["scale_raw"][code] = item.get("raw_value")
			target["scale_display"][code] = item.get("value_display")
	return scorecard_metrics


def _build_row(project, scorecard, scorecard_metrics, metric_catalog):
	scorecard_metrics = scorecard_metrics or {"normalized": {}, "raw": {}, "scale_raw": {}, "scale_display": {}}
	metric_values = _build_metric_values(scorecard, scorecard_metrics)
	link_title_cache = {}
	row = {
		"project": project.get("name"),
		"project_name": project.get("project_name"),
		"portfolio": project.get("custom_project_portfolio"),
		"portfolio_display": _get_link_display("Project Portfolio", project.get("custom_project_portfolio"), link_title_cache),
		"project_stage": project.get("current_stage"),
		"project_stage_display": _get_link_display("Project Stage", project.get("current_stage"), link_title_cache),
		"evaluated_stage": scorecard.get("stage_at_evaluation") if scorecard else None,
		"evaluated_stage_display": _get_link_display(
			"Project Stage", scorecard.get("stage_at_evaluation") if scorecard else None, link_title_cache
		),
		"scorecard": scorecard.get("name") if scorecard else None,
		"profile": scorecard.get("profile") if scorecard else None,
		"profile_display": _get_link_display(
			"Project Scoring Profile", scorecard.get("profile") if scorecard else None, link_title_cache
		),
		"evaluation_date": scorecard.get("evaluation_date") if scorecard else None,
		"integral_score": scorecard.get("integral_score") if scorecard else None,
		"gate_pass": scorecard.get("gate_pass") if scorecard else None,
		"risk_score_norm": metric_values.get("risk_score_norm"),
		"benefit_score_norm": metric_values.get("benefit_score_norm"),
		"cost_score_norm": metric_values.get("cost_score_norm"),
		"metric_values": metric_values,
		"dynamic_metric_values": _build_dynamic_metric_values(project, scorecard, scorecard_metrics, metric_catalog, link_title_cache),
		"_project_modified": project.get("modified"),
	}
	return row


def _build_metric_values(scorecard, scorecard_metrics):
	normalized = scorecard_metrics.get("normalized") or {}
	raw = scorecard_metrics.get("raw") or {}

	metric_values = {
		"integral_score": scorecard.get("integral_score") if scorecard else None,
		"risk_score_norm": _average([normalized.get(code) for code in RISK_CODES]),
		"benefit_score_norm": _average([normalized.get(code) for code in BENEFIT_CODES]),
		"cost_score_norm": _average([normalized.get(code) for code in COST_CODES]),
	}
	if metric_values["cost_score_norm"] is not None:
		metric_values["cost_score_norm_inverse"] = max(0, 1 - metric_values["cost_score_norm"])
	else:
		metric_values["cost_score_norm_inverse"] = None

	rd_cost = raw.get("RD_COST")
	mfg_cost = raw.get("MFG_COST")
	metric_values["innovation_cost_total_raw"] = (rd_cost or 0) + (mfg_cost or 0) if rd_cost is not None or mfg_cost is not None else None
	return metric_values


def _build_dynamic_metric_values(project, scorecard, scorecard_metrics, metric_catalog, link_title_cache):
	values = {}
	for definition in _iter_metric_definitions(metric_catalog):
		source_kind = definition.get("source_kind")
		if source_kind == "project_field":
			raw_value = project.get(definition.get("fieldname"))
			display_value = _display_for_field(raw_value, definition, link_title_cache)
		elif source_kind == "scorecard_field":
			raw_value = scorecard.get(definition.get("fieldname")) if scorecard else None
			display_value = _display_for_field(raw_value, definition, link_title_cache)
		elif source_kind == "criterion_raw":
			raw_value = (scorecard_metrics.get("raw") or {}).get(definition.get("criterion_code"))
			display_value = _format_metric_value(raw_value, definition.get("format"))
		elif source_kind == "criterion_normalized":
			raw_value = (scorecard_metrics.get("normalized") or {}).get(definition.get("criterion_code"))
			display_value = _format_metric_value(raw_value, definition.get("format"))
		elif source_kind == "criterion_scale":
			raw_value = (scorecard_metrics.get("scale_raw") or {}).get(definition.get("criterion_code"))
			display_value = (scorecard_metrics.get("scale_display") or {}).get(definition.get("criterion_code"))
			display_value = display_value or (raw_value if raw_value not in (None, "") else _("N/A"))
		else:
			continue

		values[definition["id"]] = {
			"metric": definition["id"],
			"label": definition.get("label") or definition["id"],
			"value": raw_value,
			"display": display_value,
			"sort_value": _get_sort_value(raw_value, definition),
		}
	return values


def _iter_metric_definitions(metric_catalog):
	seen = set()
	for entries in (metric_catalog.get("axis") or [], metric_catalog.get("size") or [], metric_catalog.get("color") or []):
		for entry in entries:
			metric_id = entry.get("id")
			if metric_id and metric_id not in seen:
				seen.add(metric_id)
				yield entry


def _display_for_field(value, definition, link_title_cache):
	if value in (None, ""):
		return _("N/A")
	if definition.get("fieldtype") == "Link" and definition.get("options"):
		return _get_link_display(definition.get("options"), value, link_title_cache)
	return _format_metric_value(value, definition.get("format"))


def _get_link_display(doctype, value, cache):
	if value in (None, ""):
		return _("N/A")
	key = (doctype, value)
	if key in cache:
		return cache[key]
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		meta = None
	title_field = getattr(meta, "title_field", None) if meta else None
	if not title_field:
		cache[key] = value
		return value
	try:
		from frappe.desk.search import get_link_title

		cache[key] = get_link_title(doctype, value) or value
	except Exception:
		cache[key] = value
	return cache[key]


def _get_metric_descriptor(row, metric_id, definition=None):
	definition = definition or {}
	descriptor = (row.get("dynamic_metric_values") or {}).get(metric_id)
	if descriptor:
		return {
			"metric": metric_id,
			"label": descriptor.get("label") or definition.get("label") or metric_id,
			"value": descriptor.get("value"),
			"display": descriptor.get("display"),
			"sort_value": descriptor.get("sort_value"),
		}
	return {
		"metric": metric_id,
		"label": definition.get("label") or metric_id,
		"value": None,
		"display": _("N/A"),
		"sort_value": None,
	}


def _build_color_key(metric_id, descriptor):
	raw_value = descriptor.get("value")
	if raw_value not in (None, ""):
		return f"{metric_id}:{raw_value}"
	display_value = descriptor.get("display")
	if display_value not in (None, ""):
		return f"{metric_id}:{_slugify(display_value)}"
	return f"{metric_id}:unknown"


def _build_color_descriptor(row, metric_id, definition):
	descriptor = _get_metric_descriptor(row, metric_id, definition)
	display_value = descriptor.get("display") or _("Unknown")
	color_key = _build_color_key(metric_id, descriptor)
	return {
		"metric": metric_id,
		"metric_label": definition.get("label") if definition else metric_id,
		"label": display_value,
		"display": display_value,
		"value": descriptor.get("value"),
		"color_key": color_key,
		"token": color_key,
	}


def _build_axis_definition(rows, metric_id, definition):
	definition = definition or {"id": metric_id, "label": metric_id, "value_type": "categorical", "axis_type": "category"}
	descriptors = [
		_resolve_axis_metric_descriptor(_get_metric_descriptor(row, metric_id, definition), definition)
		for row in rows
	]
	descriptors = [descriptor for descriptor in descriptors if _has_metric_value(descriptor)]
	axis_definition = {
		"id": metric_id,
		"label": definition.get("label") or metric_id,
		"value_type": definition.get("value_type") or "categorical",
		"axis_type": definition.get("axis_type") or "category",
	}

	if axis_definition["axis_type"] == "category":
		seen = set()
		categories = []
		for descriptor in sorted(descriptors, key=lambda item: str(item.get("display") or "")):
			label = descriptor.get("display")
			if label in seen:
				continue
			seen.add(label)
			categories.append(label)
		axis_definition["categories"] = categories
		return axis_definition

	sort_values = [descriptor.get("sort_value") for descriptor in descriptors if descriptor.get("sort_value") is not None]
	if not sort_values:
		return axis_definition
	minimum, maximum = _expand_range(sort_values, axis_definition["axis_type"])
	axis_definition["min"] = minimum
	axis_definition["max"] = maximum
	axis_definition["display_min"] = _format_metric_value(minimum, "date" if axis_definition["axis_type"] == "time" else definition.get("format"))
	axis_definition["display_max"] = _format_metric_value(maximum, "date" if axis_definition["axis_type"] == "time" else definition.get("format"))
	return axis_definition


def _build_legend(points):
	legend_items = []
	seen = set()
	for point in points:
		color = point["color"]
		color_key = color.get("color_key") or color.get("token")
		if color_key in seen:
			continue
		seen.add(color_key)
		legend_items.append(
			{
				"value": color["value"],
				"color_key": color_key,
				"token": color.get("token") or color_key,
				"label": color["display"],
			}
		)
	legend_items.sort(key=lambda item: str(item.get("label") or ""))
	return legend_items


def _expand_range(values, axis_type):
	minimum = min(values)
	maximum = max(values)
	if axis_type == "time":
		padding = (maximum - minimum) * 0.1
		if math.isclose(padding, 0):
			padding = 24 * 60 * 60 * 1000
		return minimum - padding, maximum + padding
	padding = (maximum - minimum) * 0.1
	if math.isclose(padding, 0):
		padding = abs(minimum) * 0.1 if minimum else 1
	return minimum - padding, maximum + padding


def _get_sort_value(value, definition):
	if value in (None, ""):
		return None
	if definition.get("axis_type") == "time":
		return _coerce_timestamp(value)
	return value


def _coerce_timestamp(value):
	if isinstance(value, (int, float)):
		return value
	try:
		return datetime.fromisoformat(str(value).replace(" ", "T")).timestamp() * 1000
	except ValueError:
		return value


def _format_metric_value(value, fmt):
	if value is None:
		return _("N/A")
	if fmt == "currency":
		return f"{value:,.2f}"
	if fmt == "percent":
		return f"{value:.2f}%"
	if fmt == "int":
		return str(int(value))
	if fmt == "date":
		return str(value)
	if fmt == "duration":
		return str(value)
	if fmt == "text":
		return str(value)
	return f"{value:.2f}" if isinstance(value, (int, float)) else str(value)


def _normalize_bubble_sizes(values):
	scored_values = [value for value in values if value is not None]
	if not scored_values:
		return [MISSING_BUBBLE_SYMBOL_SIZE for _ in values]

	minimum = min(scored_values)
	maximum = max(scored_values)
	if math.isclose(minimum, maximum):
		return [
			DEFAULT_SCORED_BUBBLE_SYMBOL_SIZE if value is not None else MISSING_BUBBLE_SYMBOL_SIZE
			for value in values
		]

	result = []
	for value in values:
		if value is None:
			result.append(MISSING_BUBBLE_SYMBOL_SIZE)
			continue
		scale = (value - minimum) / (maximum - minimum)
		result.append(MIN_SCORED_BUBBLE_SYMBOL_SIZE + scale * SCORED_BUBBLE_SYMBOL_SIZE_RANGE)
	return result


def _has_metric_value(descriptor):
	if descriptor is None:
		return False
	value = descriptor.get("value")
	if value not in (None, ""):
		return True
	return descriptor.get("sort_value") is not None


def _category_not_set_label():
	return _("Not Set")


def _resolve_axis_metric_descriptor(descriptor, definition):
	definition = definition or {}
	if _has_metric_value(descriptor):
		return descriptor
	if (definition.get("axis_type") or "category") != "category":
		return descriptor
	return {
		**descriptor,
		"value": CATEGORY_MISSING_VALUE,
		"display": _category_not_set_label(),
		"sort_value": CATEGORY_MISSING_SORT,
	}


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


def _slugify(value):
	return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-") or "unknown"


def _unique(values):
	seen = set()
	result = []
	for value in values:
		if value in seen:
			continue
		seen.add(value)
		result.append(value)
	return result


def _average(values):
	values = [value for value in values if value is not None]
	return sum(values) / len(values) if values else None
