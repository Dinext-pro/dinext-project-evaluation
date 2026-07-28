"""Stage Gate ↔ Project Scorecard integration helpers."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from dinext_project_evaluation.scoring.scorecard_factory import (
	find_agreed_scorecard_for_stage_instance,
	has_agreed_scorecard_for_stage_instance,
)
from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_CANCELED_DOCSTATUS,
	is_agreed_scorecard,
)

REQUIRE_AGREED_SCORECARD_FIELD = "require_agreed_stage_scorecard"
TEMPLATE_REQUIRE_FIELD = REQUIRE_AGREED_SCORECARD_FIELD
CHECKPOINT_REQUIRE_FIELD = REQUIRE_AGREED_SCORECARD_FIELD

CHECKPOINT_SUMMARY_FIELDS = (
	"linked_stage_scorecard",
	"scorecard_display_title",
	"scorecard_status",
	"scorecard_integral_score",
	"scorecard_gate_pass",
	"scorecard_gate_warning",
)


def _checkpoint_has_summary_fields() -> bool:
	meta = frappe.get_meta("Project Gate Checkpoint")
	return meta.has_field("linked_stage_scorecard")


def _template_has_require_field() -> bool:
	meta = frappe.get_meta("Stage Gate Template")
	return meta.has_field(TEMPLATE_REQUIRE_FIELD)


def _checkpoint_has_require_field() -> bool:
	meta = frappe.get_meta("Project Gate Checkpoint")
	return meta.has_field(CHECKPOINT_REQUIRE_FIELD)


def get_template_require_agreed_scorecard_value(gate_template: str | None) -> int:
	if not gate_template or not _template_has_require_field():
		return 0
	return cint(frappe.db.get_value("Stage Gate Template", gate_template, TEMPLATE_REQUIRE_FIELD))


def template_requires_agreed_scorecard(gate_template: str | None) -> bool:
	return bool(get_template_require_agreed_scorecard_value(gate_template))


def checkpoint_requires_agreed_scorecard(checkpoint) -> bool:
	if not _checkpoint_has_require_field():
		return False
	return bool(cint(checkpoint.get(CHECKPOINT_REQUIRE_FIELD)))


def snapshot_require_agreed_scorecard_on_checkpoint(checkpoint, *, persist: bool = False) -> None:
	"""Copy template requirement flag onto checkpoint at creation time."""
	if not _checkpoint_has_require_field() or not checkpoint.gate_template:
		return

	value = get_template_require_agreed_scorecard_value(checkpoint.gate_template)
	checkpoint.set(CHECKPOINT_REQUIRE_FIELD, value)
	if persist and checkpoint.name:
		frappe.db.set_value(
			checkpoint.doctype,
			checkpoint.name,
			CHECKPOINT_REQUIRE_FIELD,
			value,
			update_modified=False,
		)


def copy_require_agreed_scorecard_from_template(checkpoint) -> None:
	if not checkpoint.is_new():
		return
	snapshot_require_agreed_scorecard_on_checkpoint(checkpoint)


def backfill_checkpoint_require_agreed_flags() -> None:
	if not _checkpoint_has_require_field() or not _template_has_require_field():
		return

	checkpoints = frappe.get_all(
		"Project Gate Checkpoint",
		filters={"gate_template": ["is", "set"]},
		fields=["name", "gate_template"],
	)
	for row in checkpoints:
		frappe.db.set_value(
			"Project Gate Checkpoint",
			row.name,
			CHECKPOINT_REQUIRE_FIELD,
			get_template_require_agreed_scorecard_value(row.gate_template),
			update_modified=False,
		)


def find_latest_scorecard_for_stage_instance(stage_instance: str) -> str | None:
	if not stage_instance:
		return None
	rows = frappe.get_all(
		"Project Scorecard",
		filters={
			"stage_instance_at_evaluation": stage_instance,
			"docstatus": ["!=", SCORECARD_CANCELED_DOCSTATUS],
		},
		fields=["name"],
		order_by="modified desc",
		limit=1,
	)
	return rows[0].name if rows else None


def build_scorecard_summary(scorecard_name: str | None) -> dict[str, Any]:
	empty = {
		"scorecard": None,
		"scorecard_title": "",
		"docstatus": 0,
		"status": "",
		"integral_score": None,
		"gate_pass": 1,
		"gate_warning": "",
		"is_agreed": False,
	}
	if not scorecard_name:
		return empty

	values = frappe.db.get_value(
		"Project Scorecard",
		scorecard_name,
		[
			"name",
			"scorecard_title",
			"docstatus",
			"status",
			"integral_score",
			"gate_pass",
			"gate_messages",
		],
		as_dict=True,
	)
	if not values:
		return empty

	gate_pass = cint(values.gate_pass)
	gate_warning = ""
	if not gate_pass:
		gate_warning = (values.gate_messages or "").strip()

	return {
		"scorecard": values.name,
		"scorecard_title": values.scorecard_title or values.name,
		"docstatus": cint(values.docstatus),
		"status": values.status or "",
		"integral_score": values.integral_score,
		"gate_pass": gate_pass,
		"gate_warning": gate_warning,
		"is_agreed": is_agreed_scorecard(values.docstatus),
	}


def resolve_checkpoint_scorecard_summary(stage_instance: str | None) -> dict[str, Any]:
	"""Return UI summary for the latest non-canceled scorecard on a stage instance."""
	display_name = find_latest_scorecard_for_stage_instance(stage_instance or "")
	summary = build_scorecard_summary(display_name)
	agreed_name = find_agreed_scorecard_for_stage_instance(stage_instance or "")
	summary["agreed_scorecard"] = agreed_name
	summary["has_agreed_scorecard"] = bool(agreed_name)
	return summary


def summary_to_checkpoint_fields(summary: dict[str, Any]) -> dict[str, Any]:
	return {
		"linked_stage_scorecard": summary.get("scorecard"),
		"scorecard_display_title": summary.get("scorecard_title") or "",
		"scorecard_status": summary.get("status") or "",
		"scorecard_integral_score": flt(summary.get("integral_score")),
		"scorecard_gate_pass": cint(summary.get("gate_pass", 1)),
		"scorecard_gate_warning": summary.get("gate_warning") or "",
	}


def apply_checkpoint_scorecard_summary(checkpoint, summary: dict[str, Any]) -> None:
	if not _checkpoint_has_summary_fields():
		return
	for fieldname, value in summary_to_checkpoint_fields(summary).items():
		checkpoint.set(fieldname, value)


def sync_checkpoint_scorecard_fields(checkpoint) -> None:
	if not checkpoint.stage_instance:
		apply_checkpoint_scorecard_summary(checkpoint, build_scorecard_summary(None))
		return
	summary = resolve_checkpoint_scorecard_summary(checkpoint.stage_instance)
	apply_checkpoint_scorecard_summary(checkpoint, summary)


def apply_scorecard_requirement_to_checklist_completed(checkpoint) -> None:
	"""Force checklist_completed off when an agreed scorecard is required but missing.

	Call only from the ``validate`` doc_event hook, after the base controller has
	already run ``_sync_checklist_completed()``. This function adjusts the
	already-computed value; it does not replace standard checklist logic.
	"""
	if not checkpoint_requires_agreed_scorecard(checkpoint):
		return
	if not _checkpoint_has_summary_fields():
		return
	if checkpoint.get("linked_stage_scorecard"):
		return
	checkpoint.checklist_completed = 0


def refresh_checkpoints_for_stage_instance(stage_instance: str | None) -> None:
	if not stage_instance or not frappe.db.exists("DocType", "Project Gate Checkpoint"):
		return
	if not _checkpoint_has_summary_fields():
		return

	summary = resolve_checkpoint_scorecard_summary(stage_instance)
	field_values = summary_to_checkpoint_fields(summary)
	checkpoint_names = frappe.get_all(
		"Project Gate Checkpoint",
		filters={"stage_instance": stage_instance},
		pluck="name",
	)
	for name in checkpoint_names:
		frappe.db.set_value(
			"Project Gate Checkpoint",
			name,
			field_values,
			update_modified=True,
		)


def _transitioning_to_in_review(checkpoint) -> bool:
	if checkpoint.status != "In Review":
		return False
	previous = checkpoint.get_doc_before_save()
	if previous and previous.status == "In Review":
		return False
	return True


def validate_checkpoint_review_entry(checkpoint) -> None:
	if not _transitioning_to_in_review(checkpoint):
		return
	if not checkpoint_requires_agreed_scorecard(checkpoint):
		return
	if not checkpoint.stage_instance:
		frappe.throw(
			_("Stage Instance is required before submitting the checkpoint for review."),
			frappe.ValidationError,
		)
	if has_agreed_scorecard_for_stage_instance(checkpoint.stage_instance):
		return
	frappe.throw(
		_(
			"This checkpoint requires a submitted Project Scorecard for stage instance {0} "
			"before it can enter review."
		).format(checkpoint.stage_instance),
		frappe.ValidationError,
	)


def get_checkpoint_scorecard_summary_for_api(checkpoint_name: str) -> dict[str, Any]:
	checkpoint = frappe.get_doc("Project Gate Checkpoint", checkpoint_name)
	summary = resolve_checkpoint_scorecard_summary(checkpoint.stage_instance)
	summary["requires_agreed_scorecard"] = checkpoint_requires_agreed_scorecard(checkpoint)
	summary["checkpoint_fields"] = summary_to_checkpoint_fields(summary)
	return summary


def backfill_checkpoint_scorecard_summaries() -> None:
	"""Refresh denormalized scorecard summary fields on all checkpoints."""
	if not _checkpoint_has_summary_fields():
		return

	stage_instances = frappe.get_all(
		"Project Gate Checkpoint",
		filters={"stage_instance": ["is", "set"]},
		pluck="stage_instance",
		distinct=True,
	)
	for stage_instance in stage_instances:
		refresh_checkpoints_for_stage_instance(stage_instance)
