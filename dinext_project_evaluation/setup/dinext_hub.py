# Copyright (c) 2026, Dinext and contributors
# For license information, please see license.txt

"""Register this app's default Dinext Hub cards."""

from __future__ import annotations

import frappe

APP_NAME = 'dinext_project_evaluation'

HUB_ITEMS = (
	{
		"section": 'Project Management',
		"element_type": 'Workspace',
		"target": 'Скоринг проектов',
		"label": 'Project Scoring',
		"description": 'Project evaluation hub: scorecards in progress, review or approval, gate failures, scoring profiles, and portfolio reporting.',
		"icon": 'quality',
	},
)


def register_dinext_hub_items() -> None:
	if "dinext_common" not in frappe.get_installed_apps():
		return

	try:
		from dinext_common.setup.hub_catalog import register_hub_items
	except ImportError:
		return

	register_hub_items(HUB_ITEMS, source_app=APP_NAME)
