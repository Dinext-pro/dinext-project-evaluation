from frappe.model.document import Document

from dinext_project_evaluation.scoring.criterion_config import (
	sanitize_criterion_config,
	validate_criterion_config,
)


class ProjectScoringCriterion(Document):
	def validate(self):
		sanitize_criterion_config(self)
		validate_criterion_config(self)
