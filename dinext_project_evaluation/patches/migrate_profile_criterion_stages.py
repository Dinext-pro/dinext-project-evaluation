from __future__ import annotations

from collections import defaultdict

import frappe


def execute():
	if not frappe.db.table_exists("tabProject Scoring Profile Criterion Stage"):
		return

	stage_rows = frappe.get_all(
		"Project Scoring Profile Criterion Stage",
		fields=["name", "parent", "stage", "idx"],
		order_by="parent asc, idx asc",
	)
	if not stage_rows:
		_delete_legacy_doctype()
		return

	stages_by_criterion = defaultdict(list)
	for row in stage_rows:
		if row.stage:
			stages_by_criterion[row.parent].append(row.stage)

	for criterion_name, stages in stages_by_criterion.items():
		if not frappe.db.exists("Project Scoring Profile Criterion", criterion_name):
			continue

		criterion_row = frappe.db.get_value(
			"Project Scoring Profile Criterion",
			criterion_name,
			[
				"parent",
				"criterion",
				"weight",
				"requirement_level",
				"minimum_normalized_score",
				"minimum_raw_value",
				"maximum_raw_value",
			],
			as_dict=True,
		)
		if not criterion_row or not criterion_row.parent:
			continue

		unique_stages = list(dict.fromkeys(stages))
		frappe.db.set_value("Project Scoring Profile Criterion", criterion_name, "stage", unique_stages[0])

		if len(unique_stages) <= 1:
			continue

		profile = frappe.get_doc("Project Scoring Profile", criterion_row.parent)
		for stage in unique_stages[1:]:
			profile.append(
				"criteria",
				{
					"criterion": criterion_row.criterion,
					"stage": stage,
					"weight": criterion_row.weight,
					"requirement_level": criterion_row.requirement_level,
					"minimum_normalized_score": criterion_row.minimum_normalized_score,
					"minimum_raw_value": criterion_row.minimum_raw_value,
					"maximum_raw_value": criterion_row.maximum_raw_value,
				},
			)
		profile.save(ignore_permissions=True)

	_delete_legacy_doctype()
	frappe.db.commit()


def _delete_legacy_doctype():
	frappe.db.delete("Project Scoring Profile Criterion Stage")
	if frappe.db.exists("DocType", "Project Scoring Profile Criterion Stage"):
		frappe.delete_doc("DocType", "Project Scoring Profile Criterion Stage", force=1, ignore_permissions=True)
