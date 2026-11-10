"""Owned synthetic records for the project scoring report browser regression."""

from datetime import datetime

import frappe
from frappe.tests.ui_test_helpers import whitelist_for_tests
from frappe.utils.password import update_password


USER = "scoring-date-sort@example.com"
MISSING_PROJECT = "_Test Scoring Date Sort Missing"
DATED_PROJECT = "_Test Scoring Date Sort Dated"
ROLE = "Scoring Report Date Sort Test"
READ_DOCTYPES = (
	"Report", "Project", "Project Scorecard", "Project Type", "Project Portfolio",
	"Project Governance Model", "Project Stage", "Project Scoring Profile", "Kanban Board",
)


def _check_test_site():
	if not frappe.conf.get("allow_tests"):
		frappe.throw("Scoring report fixtures require a test site.")
	frappe.only_for("System Manager")


@whitelist_for_tests
def cleanup():
	_check_test_site()
	frappe.db.delete("Project", {"name": ["in", [MISSING_PROJECT, DATED_PROJECT]]})
	if frappe.db.exists("User", USER):
		frappe.delete_doc("User", USER, force=True, ignore_permissions=True)
	for doctype in READ_DOCTYPES:
		for permission_doctype in ("DocPerm", "Custom DocPerm"):
			frappe.db.delete(permission_doctype, {"parent": doctype, "role": ROLE})
		frappe.clear_cache(doctype=doctype)
	if frappe.db.exists("Role", ROLE):
		frappe.delete_doc("Role", ROLE, force=True, ignore_permissions=True)
	frappe.db.commit()
	return {"cleaned": True}


@whitelist_for_tests
def seed():
	_check_test_site()
	cleanup()
	frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)
	for doctype in READ_DOCTYPES:
		permission_doctype = "Custom DocPerm" if frappe.db.exists("Custom DocPerm", {"parent": doctype}) else "DocPerm"
		frappe.get_doc({
			"doctype": permission_doctype, "parent": doctype, "parenttype": "DocType",
			"parentfield": "permissions", "role": ROLE, "read": 1, "select": 1,
			"report": int(doctype == "Project"),
		}).db_insert()
		frappe.clear_cache(doctype=doctype)
	user = frappe.get_doc({
		"doctype": "User", "email": USER, "first_name": "Scoring Date Sort", "enabled": 1,
		"send_welcome_email": 0, "user_type": "System User",
		"roles": [{"role": role} for role in ["System Manager", "Project Governance Admin", "Dinext_Projects_Admin", ROLE]],
	})
	user.insert(ignore_permissions=True)
	password = frappe.generate_hash(length=32)
	update_password(USER, password)
	frappe.db.bulk_insert(
		"Project",
		fields=["name", "project_name", "status", "is_active", "creation", "modified", "owner", "modified_by", "expected_start_date", "estimated_costing", "percent_complete"],
		values=[
			[name, name, "Open", "Yes", datetime(1900, 1, 1), modified, USER, USER, "2026-06-01", budget, 0]
			for name, modified, budget in [
				(MISSING_PROJECT, None, 100), (DATED_PROJECT, datetime(1900, 1, 2), 200)
			]
		],
	)
	frappe.db.commit()
	return {"user": USER, "password": password, "missing_project": MISSING_PROJECT, "dated_project": DATED_PROJECT}
