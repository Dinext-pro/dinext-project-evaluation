import frappe
from frappe import _
from frappe.model.document import Document

from dinext_project_evaluation.scoring.profile_stages import find_duplicate_criterion_stage_pair


class ProjectScoringProfile(Document):
	def validate(self):
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
