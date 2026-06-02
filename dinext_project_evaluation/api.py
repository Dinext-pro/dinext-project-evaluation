import frappe

from dinext_project_evaluation.scoring.profile_stages import stages_by_criterion


@frappe.whitelist()
def get_applicable_criteria(project: str, profile: str):
	project_doc = frappe.get_doc("Project", project)
	profile_doc = frappe.get_doc("Project Scoring Profile", profile)
	current_stage = project_doc.get("current_stage")
	stage_map = stages_by_criterion(profile_doc)
	rows = []

	for profile_row in profile_doc.criteria:
		stages = stage_map.get(profile_row.criterion, [])
		if stages and current_stage not in stages:
			continue

		criterion = frappe.get_doc("Project Scoring Criterion", profile_row.criterion)
		rows.append(
			{
				"criterion": criterion.name,
				"criterion_code": criterion.criterion_code,
				"criterion_name": criterion.criterion_name,
				"criterion_group": criterion.criterion_group,
				"input_type": criterion.input_type,
				"influence_direction": criterion.influence_direction,
				"weight": profile_row.weight,
				"requirement_level": profile_row.requirement_level,
				"scale_rows": [
					{
						"scale_label": scale.scale_label,
						"score": scale.score,
						"sort_order": scale.sort_order,
						"key_phrases": scale.key_phrases,
					}
					for scale in criterion.scale_rows
				],
			}
		)

	return rows


@frappe.whitelist()
def create_scorecard(project: str, profile: str):
	scorecard = frappe.new_doc("Project Scorecard")
	scorecard.project = project
	scorecard.profile = profile
	scorecard.status = "Draft"

	for criterion in get_applicable_criteria(project, profile):
		scorecard.append(
			"items",
			{
				"criterion": criterion["criterion"],
				"criterion_code": criterion["criterion_code"],
				"weight": criterion["weight"],
			},
		)

	scorecard.insert()
	return scorecard.as_dict()


@frappe.whitelist()
def calculate_scorecard(scorecard: str):
	doc = frappe.get_doc("Project Scorecard", scorecard)
	doc.status = "Calculated"
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def approve_scorecard(scorecard: str):
	doc = frappe.get_doc("Project Scorecard", scorecard)
	doc.status = "Approved"
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def get_scorecard_history(project: str, limit: int = 10):
	return frappe.get_all(
		"Project Scorecard",
		filters={"project": project},
		fields=["name", "profile", "status", "evaluation_date", "integral_score", "gate_pass", "modified"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)
