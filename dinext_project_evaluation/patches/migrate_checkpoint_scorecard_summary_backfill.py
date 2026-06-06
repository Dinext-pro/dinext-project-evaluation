from __future__ import annotations

import frappe

from dinext_project_evaluation.scoring.stage_gate_integration import (
	backfill_checkpoint_scorecard_summaries,
)


def execute():
	if not frappe.db.table_exists("tabProject Gate Checkpoint"):
		return

	backfill_checkpoint_scorecard_summaries()
	frappe.db.commit()
