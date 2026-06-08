from __future__ import annotations

from copy import deepcopy

import frappe
from frappe import _

PROJECT_DOCTYPE = "Project"
SCORECARD_DOCTYPE = "Project Scorecard"
CRITERION_DOCTYPE = "Project Scoring Criterion"

EXCLUDED_FIELDTYPES = {
	"Attach",
	"Attach Image",
	"Barcode",
	"Button",
	"Check",
	"Code",
	"Column Break",
	"Geolocation",
	"HTML",
	"Image",
	"Long Text",
	"Markdown Editor",
	"Password",
	"Section Break",
	"Signature",
	"Small Text",
	"Table",
	"Table MultiSelect",
	"Text Editor",
}
NUMERIC_FIELDTYPES = {"Currency", "Duration", "Float", "Int", "Percent", "Rating"}
DATE_FIELDTYPES = {"Date", "Datetime"}
NUMERIC_CRITERION_TYPES = {"Currency", "Number", "Percent"}


def get_metric_catalog() -> dict[str, object]:
	project_metrics = _build_field_metrics(PROJECT_DOCTYPE, "project")
	scorecard_metrics = _build_field_metrics(SCORECARD_DOCTYPE, "scorecard")
	criteria = _load_criteria()

	axis = [deepcopy(entry) for entry in project_metrics["axis"] + scorecard_metrics["axis"]]
	size = [deepcopy(entry) for entry in project_metrics["size"] + scorecard_metrics["size"]]
	size.extend(_build_numeric_criterion_metrics(criteria))
	color = [deepcopy(entry) for entry in project_metrics["color"] + scorecard_metrics["color"]]
	color.extend(_build_scale_criterion_metrics(criteria))

	catalog = {"axis": axis, "size": size, "color": color}
	catalog["defaults"] = get_default_metric_config(catalog)
	return catalog


def get_default_metric_config(catalog: dict[str, object] | None = None) -> dict[str, str]:
	catalog = catalog or get_metric_catalog()
	axis_entries = list(catalog.get("axis") or [])
	size_entries = list(catalog.get("size") or [])
	color_entries = list(catalog.get("color") or [])

	x_axis = _pick_metric_id(axis_entries, preferred_value_types=("date", "numeric", "categorical"))
	y_axis = _pick_metric_id(
		axis_entries,
		preferred_value_types=("numeric", "date", "categorical"),
		exclude_ids={x_axis} if x_axis else set(),
	) or x_axis
	size_metric = _pick_metric_id(
		size_entries,
		preferred_ids=("scorecard:integral_score", "project:percent_complete", "project:custom_budget"),
		preferred_value_types=("numeric",),
	)
	color_metric = _pick_metric_id(
		color_entries,
		preferred_ids=("scorecard:status", "project:custom_project_portfolio", "scorecard:profile"),
		preferred_value_types=("categorical", "date", "numeric"),
	)

	return {
		"x_axis": x_axis or "",
		"y_axis": y_axis or "",
		"size_metric": size_metric or "",
		"color_metric": color_metric or "",
	}


def get_metric_definition(metric_id: str, catalog: dict[str, object] | None = None) -> dict[str, object] | None:
	catalog = catalog or get_metric_catalog()
	for entries in (catalog.get("axis") or [], catalog.get("size") or [], catalog.get("color") or []):
		for entry in entries:
			if entry.get("id") == metric_id:
				return deepcopy(entry)
	return None


def get_numeric_metric_ids(catalog: dict[str, object] | None = None) -> set[str]:
	catalog = catalog or get_metric_catalog()
	return {
		entry["id"]
		for entry in list(catalog.get("axis") or []) + list(catalog.get("size") or [])
		if entry.get("value_type") == "numeric"
	}


def get_color_metric_ids(catalog: dict[str, object] | None = None) -> set[str]:
	catalog = catalog or get_metric_catalog()
	return {entry["id"] for entry in catalog.get("color") or []}


def resolve_metric_config(filters, catalog: dict[str, object] | None = None) -> dict[str, str]:
	catalog = catalog or get_metric_catalog()
	defaults = catalog.get("defaults") or get_default_metric_config(catalog)
	return {
		"x_axis": _coerce_metric(filters.get("x_axis") if filters else None, catalog.get("axis") or [], defaults["x_axis"]),
		"y_axis": _coerce_metric(filters.get("y_axis") if filters else None, catalog.get("axis") or [], defaults["y_axis"]),
		"size_metric": _coerce_metric(
			filters.get("size_metric") if filters else None,
			catalog.get("size") or [],
			defaults["size_metric"],
		),
		"color_metric": _coerce_metric(
			filters.get("color_metric") if filters else None,
			catalog.get("color") or [],
			defaults["color_metric"],
		),
	}


def get_field_metric_fieldnames(catalog: dict[str, object], doctype: str) -> list[str]:
	fieldnames = []
	for entries in (catalog.get("axis") or [], catalog.get("size") or [], catalog.get("color") or []):
		for entry in entries:
			if entry.get("source_doctype") != doctype:
				continue
			fieldname = entry.get("fieldname")
			if fieldname and fieldname not in fieldnames and field_exists_in_db(doctype, fieldname):
				fieldnames.append(fieldname)
	return fieldnames


def field_exists_in_db(doctype: str, fieldname: str) -> bool:
	if not doctype or not fieldname:
		return False
	try:
		if not frappe.db.table_exists(doctype):
			return False
		return frappe.db.has_column(doctype, fieldname)
	except Exception:
		return False


def _build_field_metrics(doctype: str, namespace: str) -> dict[str, list[dict[str, object]]]:
	meta = frappe.get_meta(doctype)
	axis: list[dict[str, object]] = []
	size: list[dict[str, object]] = []
	color: list[dict[str, object]] = []

	for docfield in _iter_meta_fields(meta):
		fieldname = getattr(docfield, "fieldname", None)
		fieldtype = getattr(docfield, "fieldtype", None)
		if not fieldname or not fieldtype or fieldtype in EXCLUDED_FIELDTYPES:
			continue
		if not field_exists_in_db(doctype, fieldname):
			continue

		label = _((getattr(docfield, "label", None) or fieldname).strip())
		base_entry = {
			"id": f"{namespace}:{fieldname}",
			"label": label,
			"fieldname": fieldname,
			"fieldtype": fieldtype,
			"source_doctype": doctype,
			"source_kind": f"{namespace}_field",
			"options": getattr(docfield, "options", None),
			"value_type": _get_value_type(fieldtype),
			"axis_type": _get_axis_type(fieldtype),
			"format": _get_format(fieldtype),
		}

		axis.append(deepcopy(base_entry))
		color.append(deepcopy(base_entry))
		if fieldtype in NUMERIC_FIELDTYPES:
			size.append(deepcopy(base_entry))

	return {"axis": axis, "size": size, "color": color}


def _build_numeric_criterion_metrics(criteria: list[dict[str, object]]) -> list[dict[str, object]]:
	entries = []
	for criterion in criteria:
		input_type = criterion.get("input_type")
		if input_type not in NUMERIC_CRITERION_TYPES:
			continue
		criterion_code = criterion.get("criterion_code")
		criterion_name = criterion.get("criterion_name") or criterion_code
		metric_format = _criterion_format(input_type)
		entries.extend(
			[
				{
					"id": f"criterion:number:raw:{criterion_code}",
					"label": _("{0} (Raw)").format(criterion_name),
					"criterion_code": criterion_code,
					"criterion_name": criterion_name,
					"criterion_input_type": input_type,
					"source_doctype": CRITERION_DOCTYPE,
					"source_kind": "criterion_raw",
					"value_type": "numeric",
					"axis_type": "value",
					"format": metric_format,
				},
				{
					"id": f"criterion:number:normalized:{criterion_code}",
					"label": _("{0} (Normalized)").format(criterion_name),
					"criterion_code": criterion_code,
					"criterion_name": criterion_name,
					"criterion_input_type": input_type,
					"source_doctype": CRITERION_DOCTYPE,
					"source_kind": "criterion_normalized",
					"value_type": "numeric",
					"axis_type": "value",
					"format": "float_2",
				},
			]
		)
	return entries


def _iter_meta_fields(meta):
	seen = set()
	for collection_name in ("default_fields", "fields"):
		for docfield in getattr(meta, collection_name, []) or []:
			fieldname = getattr(docfield, "fieldname", None)
			if not fieldname or fieldname in seen:
				continue
			seen.add(fieldname)
			yield docfield


def _build_scale_criterion_metrics(criteria: list[dict[str, object]]) -> list[dict[str, object]]:
	entries = []
	for criterion in criteria:
		if criterion.get("input_type") != "Scale":
			continue
		criterion_code = criterion.get("criterion_code")
		criterion_name = criterion.get("criterion_name") or criterion_code
		entries.append(
			{
				"id": f"criterion:scale:{criterion_code}",
				"label": criterion_name,
				"criterion_code": criterion_code,
				"criterion_name": criterion_name,
				"criterion_input_type": "Scale",
				"source_doctype": CRITERION_DOCTYPE,
				"source_kind": "criterion_scale",
				"value_type": "categorical",
				"axis_type": "category",
				"format": "text",
			}
		)
	return entries


def _load_criteria() -> list[dict[str, object]]:
	return frappe.db.get_all(
		CRITERION_DOCTYPE,
		filters={"enabled": 1},
		fields=["criterion_code", "criterion_name", "input_type"],
		order_by="criterion_name asc",
	)


def _pick_metric_id(
	entries: list[dict[str, object]],
	preferred_ids: tuple[str, ...] = (),
	preferred_value_types: tuple[str, ...] = (),
	exclude_ids: set[str] | None = None,
) -> str | None:
	exclude_ids = exclude_ids or set()
	for preferred_id in preferred_ids:
		if preferred_id and any(entry.get("id") == preferred_id for entry in entries if entry.get("id") not in exclude_ids):
			return preferred_id

	for preferred_value_type in preferred_value_types:
		for entry in entries:
			if entry.get("id") in exclude_ids:
				continue
			if entry.get("value_type") == preferred_value_type:
				return entry.get("id")

	for entry in entries:
		if entry.get("id") not in exclude_ids:
			return entry.get("id")
	return None


def _coerce_metric(value: str | None, entries: list[dict[str, object]], fallback: str) -> str:
	allowed = {entry.get("id") for entry in entries}
	if value in allowed:
		return value
	if fallback in allowed:
		return fallback
	return next(iter(allowed), "")


def _get_value_type(fieldtype: str) -> str:
	if fieldtype in NUMERIC_FIELDTYPES:
		return "numeric"
	if fieldtype in DATE_FIELDTYPES:
		return "date"
	return "categorical"


def _get_axis_type(fieldtype: str) -> str:
	if fieldtype in NUMERIC_FIELDTYPES:
		return "value"
	if fieldtype in DATE_FIELDTYPES:
		return "time"
	return "category"


def _get_format(fieldtype: str) -> str:
	if fieldtype == "Currency":
		return "currency"
	if fieldtype == "Percent":
		return "percent"
	if fieldtype in DATE_FIELDTYPES:
		return "date"
	if fieldtype in {"Int", "Rating"}:
		return "int"
	if fieldtype == "Duration":
		return "duration"
	if fieldtype in {"Link", "Select", "Data"}:
		return "text"
	return "float_2"


def _criterion_format(input_type: str) -> str:
	if input_type == "Currency":
		return "currency"
	if input_type == "Percent":
		return "percent"
	return "float_2"
