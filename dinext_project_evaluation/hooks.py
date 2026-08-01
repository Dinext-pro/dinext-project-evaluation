app_name = "dinext_project_evaluation"
app_title = "Dinext Project Evaluation"
app_publisher = "Dinext"
app_description = "Dinext project evaluation."
app_email = "info@dinext.ru"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext", "dinext_project_stage_gate"]
from dinext_project_evaluation.scoring.workflow_constants import (
	SCORECARD_WORKFLOW_ACTIONS,
	SCORECARD_WORKFLOW_ROLES,
	SCORECARD_WORKFLOW_STATES,
	WORKFLOW_NAME,
)

_SCORING_GROUP_NAMES = [
	"Strategy",
	"Benefits",
	"Market",
	"Finance",
	"Risks",
	"Resources",
	"Regulatory",
	"Priority",
	"Innovation",
	"Environment",
]
_SCORING_CRITERION_NAMES = [
	"STR_ALIGN",
	"BEN_FIN",
	"BEN_NONFIN",
	"MKT_SHARE",
	"COST",
	"DEP_INT",
	"RISK_IMP",
	"RISK_PROB",
	"REG",
	"CAP_HUM_TECH",
	"URGENCY",
	"NPV",
	"IRR",
	"PP",
	"PI",
	"ECV",
	"PATENT",
	"RD_COST",
	"MFG_COST",
	"TECH_SUCCESS",
	"SALES_POT",
]
_DEFAULT_PROFILE_NAME = "Default Project Scoring Profile"

fixtures = [
	{
		"doctype": "Project Scoring Criterion Group",
		"filters": [["name", "in", _SCORING_GROUP_NAMES]],
	},
	{
		"doctype": "Project Scoring Criterion",
		"filters": [["name", "in", _SCORING_CRITERION_NAMES]],
	},
	{
		"doctype": "Project Scoring Profile",
		"filters": [["name", "=", _DEFAULT_PROFILE_NAME]],
	},
	{
		"doctype": "Client Script",
		"filters": [["module", "=", "Dinext Project Evaluation"], ["enabled", "=", 1]],
	},
	{
		"doctype": "Report",
		"filters": [["module", "=", "Dinext Project Evaluation"]],
	},
	{
		"doctype": "Custom Field",
		"filters": [["module", "=", "Dinext Project Evaluation"]],
	},
	{
		"doctype": "Role",
		"filters": [["name", "in", list(SCORECARD_WORKFLOW_ROLES)], ["disabled", "=", 0]],
	},
	{
		"doctype": "Workflow",
		"filters": [["name", "in", [WORKFLOW_NAME]]],
	},
	{
		"doctype": "Workflow State",
		"filters": [["workflow_state_name", "in", list(SCORECARD_WORKFLOW_STATES)]],
	},
	{
		"doctype": "Workflow Action Master",
		"filters": [["workflow_action_name", "in", list(SCORECARD_WORKFLOW_ACTIONS)]],
	},
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "dinext_project_evaluation",
# 		"logo": "/assets/dinext_project_evaluation/logo.png",
# 		"title": "Dinext Project Evaluation",
# 		"route": "/dinext_project_evaluation",
# 		"has_permission": "dinext_project_evaluation.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/dinext_project_evaluation/css/dinext_project_evaluation.css"
# app_include_js = "/assets/dinext_project_evaluation/js/dinext_project_evaluation.js"

# include js, css files in header of web template
# web_include_css = "/assets/dinext_project_evaluation/css/dinext_project_evaluation.css"
# web_include_js = "/assets/dinext_project_evaluation/js/dinext_project_evaluation.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dinext_project_evaluation/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Project": "public/js/project_scoring_evaluation.js",
	"Project Scorecard": "dinext_project_evaluation/doctype/project_scorecard/project_scorecard.js",
	"Project Gate Checkpoint": "public/js/project_gate_checkpoint_scorecard.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "dinext_project_evaluation/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "dinext_project_evaluation.utils.jinja_methods",
# 	"filters": "dinext_project_evaluation.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "dinext_project_evaluation.install.before_install"

# Uninstallation
# ------------

# before_uninstall = "dinext_project_evaluation.uninstall.before_uninstall"
# after_uninstall = "dinext_project_evaluation.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "dinext_project_evaluation.utils.before_app_install"
# after_app_install = "dinext_project_evaluation.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "dinext_project_evaluation.utils.before_app_uninstall"
# after_app_uninstall = "dinext_project_evaluation.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dinext_project_evaluation.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Project": {
		"validate": "dinext_project_evaluation.scoring.project_hooks.validate_project_scoring_profile_change",
		"before_save": "dinext_project_evaluation.scoring.project_hooks.before_save_project_scoring_profile_reset",
		"on_update": "dinext_project_evaluation.scoring.project_hooks.after_save_project_scoring_profile",
	},
	"Project Stage Instance": {
		"on_update": "dinext_project_evaluation.scoring.scorecard_provision.on_stage_instance_update",
	},
	"Project Gate Checkpoint": {
		"before_insert": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.before_insert_project_gate_checkpoint",
		"after_insert": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.after_insert_project_gate_checkpoint",
		"validate": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.validate_project_gate_checkpoint",
	},
	"Project Scorecard": {
		"after_insert": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.on_scorecard_checkpoint_sync",
		"on_submit": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.on_scorecard_checkpoint_sync",
		"on_cancel": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.on_scorecard_checkpoint_sync",
		"on_update": "dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks.on_scorecard_checkpoint_sync",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"dinext_project_evaluation.tasks.all"
# 	],
# 	"daily": [
# 		"dinext_project_evaluation.tasks.daily"
# 	],
# 	"hourly": [
# 		"dinext_project_evaluation.tasks.hourly"
# 	],
# 	"weekly": [
# 		"dinext_project_evaluation.tasks.weekly"
# 	],
# 	"monthly": [
# 		"dinext_project_evaluation.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "dinext_project_evaluation.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "dinext_project_evaluation.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "dinext_project_evaluation.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["dinext_project_evaluation.utils.before_request"]
# after_request = ["dinext_project_evaluation.utils.after_request"]

# Job Events
# ----------
# before_job = ["dinext_project_evaluation.utils.before_job"]
# after_job = ["dinext_project_evaluation.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"dinext_project_evaluation.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

