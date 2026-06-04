import frappe
from frappe import _

from dinext_project_evaluation.scoring.workflow_constants import SCORECARD_REPORT_STATUSES


PROJECT_LIMIT = 100


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	message = None
	if len(data) >= PROJECT_LIMIT:
		message = _("Showing first {0} projects. Narrow filters to reduce chart overload.").format(PROJECT_LIMIT)
	return columns, data, message, get_chart(data, filters)


def get_columns():
	return [
		{"fieldname": "project", "label": _("Project"), "fieldtype": "Link", "options": "Project", "width": 180},
		{"fieldname": "project_name", "label": _("Project Name"), "fieldtype": "Data", "width": 220},
		{"fieldname": "portfolio", "label": _("Portfolio"), "fieldtype": "Link", "options": "Project Portfolio", "width": 180},
		{
			"fieldname": "stage",
			"label": _("Stage", context="Dinext.StageGateModel"),
			"fieldtype": "Link",
			"options": "Project Stage",
			"width": 160,
		},
		{"fieldname": "scorecard", "label": _("Scorecard"), "fieldtype": "Link", "options": "Project Scorecard", "width": 180},
		{"fieldname": "profile", "label": _("Profile"), "fieldtype": "Link", "options": "Project Scoring Profile", "width": 180},
		{"fieldname": "evaluation_date", "label": _("Evaluation Date"), "fieldtype": "Datetime", "width": 170},
		{"fieldname": "integral_score", "label": _("Integral Score"), "fieldtype": "Float", "width": 120},
		{"fieldname": "gate_pass", "label": _("Gate Pass"), "fieldtype": "Check", "width": 90},
		{"fieldname": "risk_score", "label": _("Risk Score"), "fieldtype": "Float", "width": 110},
		{"fieldname": "benefit_score", "label": _("Benefit Score"), "fieldtype": "Float", "width": 110},
		{"fieldname": "cost_score", "label": _("Cost Score"), "fieldtype": "Float", "width": 110},
		{"fieldname": "bubble_size", "label": _("Bubble Size"), "fieldtype": "Float", "width": 110},
		{"fieldname": "bubble_color_token", "label": _("Bubble Color"), "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	conditions, values = _conditions(filters)
	values["report_statuses"] = SCORECARD_REPORT_STATUSES
	query = f"""
		SELECT
			p.name AS project,
			p.project_name,
			p.custom_project_portfolio AS portfolio,
			p.current_stage AS stage,
			ps.name AS scorecard,
			ps.profile,
			ps.evaluation_date,
			ps.integral_score,
			ps.gate_pass
		FROM `tabProject` p
		LEFT JOIN `tabProject Scorecard` ps
			ON ps.project = p.name
			AND ps.modified = (
				SELECT MAX(ps2.modified)
				FROM `tabProject Scorecard` ps2
				WHERE ps2.project = p.name
				AND ps2.status IN %(report_statuses)s
			)
		WHERE {conditions}
		ORDER BY ps.integral_score DESC, p.modified DESC
		LIMIT {PROJECT_LIMIT}
	"""
	rows = frappe.db.sql(query, values, as_dict=True)
	scorecard_metrics = _scorecard_metrics([row.scorecard for row in rows if row.scorecard])
	for row in rows:
		metrics = scorecard_metrics.get(row.scorecard, {})
		row.risk_score = metrics.get("risk_score")
		row.benefit_score = metrics.get("benefit_score")
		row.cost_score = metrics.get("cost_score")
		row.bubble_size = _bubble_size(row, metrics)
		row.bubble_color_token = "gate-pass" if row.gate_pass else "gate-fail"
	return rows


def get_chart(data, filters):
	x_axis = filters.get("x_axis") or "risk_score"
	y_axis = filters.get("y_axis") or "integral_score"
	return {
		"data": {
			"labels": [row.project_name or row.project for row in data],
			"datasets": [
				{
					"name": _("Project Score"),
					"values": [row.get(y_axis) or 0 for row in data],
				}
			],
		},
		"type": "bar",
		"bubble_payload": [
			{
				"project": row.project,
				"label": row.project_name or row.project,
				"x": row.get(x_axis) or 0,
				"y": row.get(y_axis) or 0,
				"size": row.bubble_size or 1,
				"color_token": row.bubble_color_token,
			}
			for row in data
		],
	}


def _conditions(filters):
	conditions = ["1 = 1"]
	values = {}
	if filters.get("project_portfolio"):
		conditions.append("p.custom_project_portfolio = %(project_portfolio)s")
		values["project_portfolio"] = filters.project_portfolio
	if filters.get("profile"):
		conditions.append("ps.profile = %(profile)s")
		values["profile"] = filters.profile
	if filters.get("stage"):
		conditions.append("p.current_stage = %(stage)s")
		values["stage"] = filters.stage
	if filters.get("gate_pass") in (0, 1, "0", "1"):
		conditions.append("ps.gate_pass = %(gate_pass)s")
		values["gate_pass"] = int(filters.gate_pass)
	if filters.get("from_date"):
		conditions.append("DATE(ps.evaluation_date) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("DATE(ps.evaluation_date) <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("project"):
		projects = filters.project if isinstance(filters.project, list) else [filters.project]
		conditions.append("p.name IN %(projects)s")
		values["projects"] = tuple(projects)
	return " AND ".join(conditions), values


def _scorecard_metrics(scorecards):
	if not scorecards:
		return {}
	rows = frappe.get_all(
		"Project Scorecard Item",
		filters={"parent": ["in", scorecards]},
		fields=["parent", "criterion_code", "normalized_score"],
		limit_page_length=1000,
	)
	metrics = {}
	for row in rows:
		target = metrics.setdefault(row.parent, {})
		code = row.criterion_code
		if code in {"RISK_IMP", "RISK_PROB"}:
			target.setdefault("risk_values", []).append(row.normalized_score or 0)
		if code in {"STR_ALIGN", "BEN_FIN", "BEN_NONFIN", "MKT_SHARE", "SALES_POT"}:
			target.setdefault("benefit_values", []).append(row.normalized_score or 0)
		if code in {"COST", "RD_COST", "MFG_COST"}:
			target.setdefault("cost_values", []).append(row.normalized_score or 0)
	for target in metrics.values():
		target["risk_score"] = _average(target.pop("risk_values", []))
		target["benefit_score"] = _average(target.pop("benefit_values", []))
		target["cost_score"] = _average(target.pop("cost_values", []))
	return metrics


def _average(values):
	return sum(values) / len(values) if values else None


def _bubble_size(row, metrics):
	if metrics.get("cost_score") is not None:
		return max(1, 1 + (1 - metrics["cost_score"]) * 20)
	return max(1, 1 + (row.integral_score or 0) * 10)
