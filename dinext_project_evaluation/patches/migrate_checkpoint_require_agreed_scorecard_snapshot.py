from __future__ import annotations

import frappe

from dinext_project_evaluation.scoring.stage_gate_integration import (
	backfill_checkpoint_require_agreed_flags,
)


def execute():
	if not frappe.db.table_exists("tabProject Gate Checkpoint"):
		return

	backfill_checkpoint_require_agreed_flags()
	frappe.db.commit()
