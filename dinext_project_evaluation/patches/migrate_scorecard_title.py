from __future__ import annotations

import frappe

from dinext_project_evaluation.dinext_project_evaluation.doctype.project_scorecard.project_scorecard import (
	build_scorecard_title,
)


def execute():
	if not frappe.db.table_exists("tabProject Scorecard"):
		return

	if not frappe.db.has_column("Project Scorecard", "scorecard_title"):
		return

	rows = frappe.get_all(
		"Project Scorecard",
		fields=["name", "project", "stage_at_evaluation"],
		filters={"project": ["is", "set"]},
	)

	for row in rows:
		title = build_scorecard_title(row.project, row.stage_at_evaluation)
		if title:
			frappe.db.set_value("Project Scorecard", row.name, "scorecard_title", title, update_modified=False)

	frappe.db.commit()
