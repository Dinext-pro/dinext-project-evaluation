from __future__ import annotations

from copy import deepcopy

from frappe import _


DEFAULT_METRIC_CONFIG = {
	"x_axis": "risk_score_norm",
	"y_axis": "integral_score",
	"size_metric": "cost_score_norm_inverse",
	"color_metric": "gate_pass",
}

LEGACY_METRIC_ALIASES = {
	"risk_score": "risk_score_norm",
	"benefit_score": "benefit_score_norm",
	"cost_score": "cost_score_norm",
}


AXIS_METRICS = [
	{
		"id": "integral_score",
		"label": _("Integral Score"),
		"kind": "axis",
		"source_kind": "scorecard_field",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "risk_score_norm",
		"label": _("Risk Score"),
		"kind": "axis",
		"source_kind": "derived",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "benefit_score_norm",
		"label": _("Benefit Score"),
		"kind": "axis",
		"source_kind": "derived",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "cost_score_norm",
		"label": _("Cost Score"),
		"kind": "axis",
		"source_kind": "derived",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "strategic_alignment_norm",
		"label": _("Strategic Alignment"),
		"kind": "axis",
		"source_kind": "criterion_normalized",
		"criterion_code": "STR_ALIGN",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "market_potential_norm",
		"label": _("Market Potential"),
		"kind": "axis",
		"source_kind": "criterion_normalized",
		"criterion_code": "SALES_POT",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "urgency_norm",
		"label": _("Urgency"),
		"kind": "axis",
		"source_kind": "criterion_normalized",
		"criterion_code": "URGENCY",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "regulatory_fit_norm",
		"label": _("Regulatory Fit"),
		"kind": "axis",
		"source_kind": "criterion_normalized",
		"criterion_code": "REG",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "capability_norm",
		"label": _("Capability"),
		"kind": "axis",
		"source_kind": "criterion_normalized",
		"criterion_code": "CAP_HUM_TECH",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "innovation_patent_norm",
		"label": _("Patent Potential"),
		"kind": "axis",
		"source_kind": "criterion_normalized",
		"criterion_code": "PATENT",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "cost_raw",
		"label": _("Cost"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "COST",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["x", "y", "size"],
	},
	{
		"id": "npv_raw",
		"label": _("NPV"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "NPV",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["x", "y", "size"],
	},
	{
		"id": "irr_raw",
		"label": _("IRR"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "IRR",
		"value_type": "numeric",
		"format": "percent",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "payback_period_raw",
		"label": _("Payback Period"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "PP",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "profitability_index_raw",
		"label": _("Profitability Index"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "PI",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["x", "y"],
	},
	{
		"id": "ecv_raw",
		"label": _("ECV"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "ECV",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["x", "y", "size"],
	},
	{
		"id": "rd_cost_raw",
		"label": _("R&D Cost"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "RD_COST",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["x", "y", "size"],
	},
	{
		"id": "mfg_cost_raw",
		"label": _("Manufacturing Cost"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "MFG_COST",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["x", "y", "size"],
	},
	{
		"id": "tech_success_pct_raw",
		"label": _("Technical Success"),
		"kind": "axis",
		"source_kind": "criterion_raw",
		"criterion_code": "TECH_SUCCESS",
		"value_type": "numeric",
		"format": "percent",
		"preferred_roles": ["x", "y"],
	},
]


SIZE_METRICS = [
	{
		"id": "cost_score_norm_inverse",
		"label": _("Inverse Cost Score"),
		"kind": "size",
		"source_kind": "derived",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["size"],
	},
	{
		"id": "cost_raw",
		"label": _("Cost"),
		"kind": "size",
		"source_kind": "criterion_raw",
		"criterion_code": "COST",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["size"],
	},
	{
		"id": "rd_cost_raw",
		"label": _("R&D Cost"),
		"kind": "size",
		"source_kind": "criterion_raw",
		"criterion_code": "RD_COST",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["size"],
	},
	{
		"id": "mfg_cost_raw",
		"label": _("Manufacturing Cost"),
		"kind": "size",
		"source_kind": "criterion_raw",
		"criterion_code": "MFG_COST",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["size"],
	},
	{
		"id": "innovation_cost_total_raw",
		"label": _("Total Innovation Cost"),
		"kind": "size",
		"source_kind": "derived",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["size"],
	},
	{
		"id": "integral_score",
		"label": _("Integral Score"),
		"kind": "size",
		"source_kind": "scorecard_field",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["size"],
	},
	{
		"id": "benefit_score_norm",
		"label": _("Benefit Score"),
		"kind": "size",
		"source_kind": "derived",
		"value_type": "numeric",
		"format": "float_2",
		"preferred_roles": ["size"],
	},
	{
		"id": "npv_raw",
		"label": _("NPV"),
		"kind": "size",
		"source_kind": "criterion_raw",
		"criterion_code": "NPV",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["size"],
	},
	{
		"id": "ecv_raw",
		"label": _("ECV"),
		"kind": "size",
		"source_kind": "criterion_raw",
		"criterion_code": "ECV",
		"value_type": "numeric",
		"format": "currency",
		"preferred_roles": ["size"],
	},
]


COLOR_METRICS = [
	{
		"id": "gate_pass",
		"label": _("Gate Pass"),
		"kind": "color",
		"source_kind": "scorecard_field",
		"value_type": "categorical",
		"preferred_roles": ["color"],
	},
	{
		"id": "risk_band",
		"label": _("Risk Band"),
		"kind": "color",
		"source_kind": "derived",
		"value_type": "categorical",
		"preferred_roles": ["color"],
	},
	{
		"id": "current_stage",
		"label": _("Current Stage", context="Dinext.StageGateModel"),
		"kind": "color",
		"source_kind": "project_field",
		"value_type": "categorical",
		"preferred_roles": ["color"],
	},
	{
		"id": "profile",
		"label": _("Profile"),
		"kind": "color",
		"source_kind": "scorecard_field",
		"value_type": "categorical",
		"preferred_roles": ["color"],
	},
	{
		"id": "portfolio",
		"label": _("Portfolio"),
		"kind": "color",
		"source_kind": "project_field",
		"value_type": "categorical",
		"preferred_roles": ["color"],
	},
]


ALL_METRICS = {entry["id"]: entry for entry in AXIS_METRICS + SIZE_METRICS + COLOR_METRICS}


def get_metric_catalog() -> dict[str, object]:
	return {
		"axis": [deepcopy(entry) for entry in AXIS_METRICS],
		"size": [deepcopy(entry) for entry in SIZE_METRICS],
		"color": [deepcopy(entry) for entry in COLOR_METRICS],
		"defaults": get_default_metric_config(),
	}


def get_default_metric_config() -> dict[str, str]:
	return dict(DEFAULT_METRIC_CONFIG)


def get_metric_definition(metric_id: str) -> dict[str, object] | None:
	entry = ALL_METRICS.get(metric_id)
	return deepcopy(entry) if entry else None


def get_numeric_metric_ids() -> set[str]:
	return {entry["id"] for entry in AXIS_METRICS + SIZE_METRICS}


def get_color_metric_ids() -> set[str]:
	return {entry["id"] for entry in COLOR_METRICS}


def resolve_metric_config(filters) -> dict[str, str]:
	defaults = get_default_metric_config()
	return {
		"x_axis": _coerce_metric(filters.get("x_axis"), get_numeric_metric_ids(), defaults["x_axis"]),
		"y_axis": _coerce_metric(filters.get("y_axis"), get_numeric_metric_ids(), defaults["y_axis"]),
		"size_metric": _coerce_metric(
			filters.get("size_metric"), {entry["id"] for entry in SIZE_METRICS}, defaults["size_metric"]
		),
		"color_metric": _coerce_metric(
			filters.get("color_metric"), get_color_metric_ids(), defaults["color_metric"]
		),
	}


def _coerce_metric(value: str | None, allowed: set[str], fallback: str) -> str:
	value = LEGACY_METRIC_ALIASES.get(value, value)
	return value if value in allowed else fallback
