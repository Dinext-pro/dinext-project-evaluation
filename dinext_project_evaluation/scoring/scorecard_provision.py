from __future__ import annotations

from dinext_project_evaluation.scoring.scorecard_factory import ensure_scorecard_for_stage_instance


def on_stage_instance_update(doc, method=None):
	if doc.status != "Active":
		return

	before = doc.get_doc_before_save()
	if before and before.status == "Active":
		return

	ensure_scorecard_for_stage_instance(doc)
