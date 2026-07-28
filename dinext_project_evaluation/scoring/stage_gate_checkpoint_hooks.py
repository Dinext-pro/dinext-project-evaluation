"""Document hooks bridging Project Gate Checkpoint and Project Scorecard."""

from __future__ import annotations

from dinext_project_evaluation.scoring.stage_gate_integration import (
	apply_scorecard_requirement_to_checklist_completed,
	copy_require_agreed_scorecard_from_template,
	refresh_checkpoints_for_stage_instance,
	snapshot_require_agreed_scorecard_on_checkpoint,
	sync_checkpoint_scorecard_fields,
	validate_checkpoint_review_entry,
)

_SCORECARD_SYNC_FIELDS = (
	"docstatus",
	"status",
	"integral_score",
	"gate_pass",
	"gate_messages",
	"scorecard_title",
)


def before_insert_project_gate_checkpoint(doc, method=None):
	copy_require_agreed_scorecard_from_template(doc)


def after_insert_project_gate_checkpoint(doc, method=None):
	snapshot_require_agreed_scorecard_on_checkpoint(doc, persist=True)


def validate_project_gate_checkpoint(doc, method=None):
	"""Post-validate integration for Project Gate Checkpoint.

	Frappe runs the DocType controller ``validate()`` before ``doc_events`` handlers
	(see ``Document.hook`` / ``compose`` in ``frappe.model.document``). The base
	``ProjectGateCheckpoint.validate()`` in dinext_project_stage_gate therefore
	computes ``checklist_completed`` via ``_sync_checklist_completed()`` first; this
	hook then refreshes scorecard fields and may override that result when a linked
	scorecard is required but missing.
	"""
	sync_checkpoint_scorecard_fields(doc)
	apply_scorecard_requirement_to_checklist_completed(doc)
	validate_checkpoint_review_entry(doc)


def on_scorecard_checkpoint_sync(doc, method=None):
	stage_instance = doc.get("stage_instance_at_evaluation")
	if not stage_instance:
		return

	if method == "after_insert":
		refresh_checkpoints_for_stage_instance(stage_instance)
		return

	if method == "on_update":
		previous = doc.get_doc_before_save()
		if not previous:
			return
		if not any(doc.get(fieldname) != previous.get(fieldname) for fieldname in _SCORECARD_SYNC_FIELDS):
			return

	refresh_checkpoints_for_stage_instance(stage_instance)
