import json

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from dinext_project_evaluation.scoring.profile_stages import stages_by_criterion
from dinext_project_evaluation.scoring.scorecard_service import calculate_scorecard_document


class ProjectScorecard(Document):
	def before_save(self):
		self._prevent_approved_edits()
		self._hydrate_project_context()

	def validate(self):
		if self.status in {"Calculated", "Approved"}:
			self.calculate()

	def on_update(self):
		if self.status in {"Calculated", "Approved"}:
			self._update_project_last_score()

	def calculate(self):
		profile = frappe.get_doc("Project Scoring Profile", self.profile)
		criteria_by_name = _load_criteria(profile)
		result = calculate_scorecard_document(self, profile, criteria_by_name)

		for item in self.items:
			calculated_item = result.items.get(item.criterion)
			if not calculated_item:
				continue
			item.criterion_code = calculated_item.criterion_code
			item.normalized_score = calculated_item.normalized_score
			item.weighted_score = calculated_item.weighted_score
			item.weight = calculated_item.weight
			item.gate_pass = 1
			item.is_valid = 1
			item.message = calculated_item.message

		self.integral_score = result.integral_score
		self.gate_pass = 1 if result.gate_pass else 0
		self.gate_messages = "\n".join(result.messages)
		self.evaluation_date = now_datetime()
		self.profile_snapshot = json.dumps(_profile_snapshot(profile), ensure_ascii=False)

	def _hydrate_project_context(self):
		if not self.project:
			return

		project = frappe.get_cached_doc("Project", self.project)
		self.portfolio = project.get("custom_project_portfolio")
		self.stage_at_evaluation = project.get("current_stage")
		self.stage_instance_at_evaluation = project.get("current_stage_instance")

	def _prevent_approved_edits(self):
		if self.is_new() or self.status == "Approved":
			return

		previous_status = frappe.db.get_value(self.doctype, self.name, "status")
		if previous_status == "Approved":
			frappe.throw("Approved Project Scorecard cannot be edited. Create a new scorecard instead.")

	def _update_project_last_score(self):
		for fieldname, value in {
			"custom_last_scorecard": self.name,
			"custom_last_integral_score": self.integral_score,
			"custom_last_score_date": self.evaluation_date,
		}.items():
			if frappe.get_meta("Project").has_field(fieldname):
				frappe.db.set_value("Project", self.project, fieldname, value, update_modified=False)


def _load_criteria(profile):
	criteria_names = [row.criterion for row in profile.criteria]
	return {name: frappe.get_doc("Project Scoring Criterion", name) for name in criteria_names}


def _profile_snapshot(profile):
	stage_map = stages_by_criterion(profile)
	return {
		"profile": profile.name,
		"profile_version": profile.profile_version,
		"criteria": [
			{
				"criterion": row.criterion,
				"weight": row.weight,
				"requirement_level": row.requirement_level,
				"minimum_normalized_score": row.minimum_normalized_score,
				"minimum_raw_value": row.minimum_raw_value,
				"maximum_raw_value": row.maximum_raw_value,
				"applicable_stages": stage_map.get(row.criterion, []),
			}
			for row in profile.criteria
		],
		"criterion_stages": [
			{"criterion": row.criterion, "stage": row.stage}
			for row in profile.criterion_stages or []
		],
	}
