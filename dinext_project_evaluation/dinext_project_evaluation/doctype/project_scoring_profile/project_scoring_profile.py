import frappe
from frappe import _
from frappe.model.document import Document

from dinext_project_evaluation.scoring.gate_fields import sanitize_profile_criterion_gate_fields
from dinext_project_evaluation.scoring.profile_stages import find_duplicate_criterion_stage_pair


class ProjectScoringProfile(Document):
	def validate(self):
		self._sanitize_criterion_gate_fields()

		duplicate = find_duplicate_criterion_stage_pair(self.criteria)
		if not duplicate:
			return

		criterion, stage = duplicate
		if stage:
			frappe.throw(
				_("Criterion {0} is already configured for stage {1}.").format(
					frappe.bold(criterion),
					frappe.bold(stage),
				)
			)
		frappe.throw(
			_("Criterion {0} is already configured without a stage.").format(
				frappe.bold(criterion),
			)
		)

	def _sanitize_criterion_gate_fields(self):
		criterion_codes = {row.criterion for row in self.criteria or [] if row.criterion}
		input_type_by_criterion = {}

		if criterion_codes:
			for row in frappe.get_all(
				"Project Scoring Criterion",
				filters={"name": ["in", list(criterion_codes)]},
				fields=["name", "input_type"],
			):
				input_type_by_criterion[row.name] = row.input_type

		for row in self.criteria or []:
			sanitize_profile_criterion_gate_fields(
				row,
				input_type_by_criterion.get(row.criterion),
			)
