# Copyright (c) 2026, Dinext and Contributors
# See license.txt

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from dinext_project_evaluation.scoring import stage_gate_integration
from dinext_project_evaluation.scoring.stage_gate_checkpoint_hooks import (
	on_scorecard_checkpoint_sync,
	validate_project_gate_checkpoint,
)
from dinext_project_evaluation.scoring.workflow_constants import SCORECARD_AGREED_DOCSTATUS


class TestStageGateIntegrationService(unittest.TestCase):
	@patch("dinext_project_evaluation.scoring.stage_gate_integration.frappe.db.get_value")
	def test_template_requires_agreed_scorecard_reads_template_flag(self, get_value):
		get_value.return_value = 1
		with patch.object(stage_gate_integration, "_template_has_require_field", return_value=True):
			self.assertTrue(stage_gate_integration.template_requires_agreed_scorecard("TPL-001"))

	def test_checkpoint_requires_agreed_scorecard_reads_snapshot_field(self):
		checkpoint = frappe._dict(require_agreed_stage_scorecard=1)
		with patch.object(stage_gate_integration, "_checkpoint_has_require_field", return_value=True):
			self.assertTrue(stage_gate_integration.checkpoint_requires_agreed_scorecard(checkpoint))

	def test_copy_require_flag_from_template_sets_snapshot_on_new_checkpoint(self):
		checkpoint = SimpleNamespace(
			is_new=lambda: True,
			gate_template="TPL-001",
			require_agreed_stage_scorecard=None,
		)
		checkpoint.set = lambda fieldname, value: setattr(checkpoint, fieldname, value)
		with patch.object(stage_gate_integration, "_checkpoint_has_require_field", return_value=True):
			with patch.object(
				stage_gate_integration,
				"get_template_require_agreed_scorecard_value",
				return_value=1,
			):
				stage_gate_integration.copy_require_agreed_scorecard_from_template(checkpoint)
		self.assertEqual(checkpoint.require_agreed_stage_scorecard, 1)

	@patch("dinext_project_evaluation.scoring.stage_gate_integration.frappe.db.get_value")
	def test_build_scorecard_summary_surfaces_gate_warning(self, get_value):
		get_value.return_value = frappe._dict(
			name="PSC-001",
			scorecard_title="Project A: Idea",
			docstatus=1,
			status="Approved",
			integral_score=3.5,
			gate_pass=0,
			gate_messages="STR_ALIGN normalized score 0.5000 is below required 0.7000",
		)
		summary = stage_gate_integration.build_scorecard_summary("PSC-001")
		self.assertEqual(summary["scorecard"], "PSC-001")
		self.assertEqual(summary["scorecard_title"], "Project A: Idea")
		self.assertTrue(summary["is_agreed"])
		self.assertIn("STR_ALIGN", summary["gate_warning"])

	@patch("dinext_project_evaluation.scoring.stage_gate_integration.frappe.db.get_value")
	def test_build_scorecard_summary_clears_warning_when_gate_passes(self, get_value):
		get_value.return_value = frappe._dict(
			name="PSC-002",
			scorecard_title="Project A: Idea",
			docstatus=0,
			status="Draft",
			integral_score=4.0,
			gate_pass=1,
			gate_messages="",
		)
		summary = stage_gate_integration.build_scorecard_summary("PSC-002")
		self.assertEqual(summary["gate_warning"], "")
		self.assertFalse(summary["is_agreed"])

	@patch(
		"dinext_project_evaluation.scoring.stage_gate_integration.find_agreed_scorecard_for_stage_instance",
		return_value="PSC-AGREED",
	)
	@patch(
		"dinext_project_evaluation.scoring.stage_gate_integration.find_latest_scorecard_for_stage_instance",
		return_value="PSC-LATEST",
	)
	@patch.object(stage_gate_integration, "build_scorecard_summary")
	def test_resolve_checkpoint_summary_uses_latest_for_display(
		self, build_summary, _latest, _agreed
	):
		build_summary.return_value = {"scorecard": "PSC-LATEST"}
		summary = stage_gate_integration.resolve_checkpoint_scorecard_summary("STAGE-001")
		build_summary.assert_called_once_with("PSC-LATEST")
		self.assertEqual(summary["agreed_scorecard"], "PSC-AGREED")
		self.assertTrue(summary["has_agreed_scorecard"])

	def test_summary_to_checkpoint_fields_maps_display_values(self):
		fields = stage_gate_integration.summary_to_checkpoint_fields(
			{
				"scorecard": "PSC-001",
				"scorecard_title": "Title",
				"status": "Approved",
				"integral_score": 2.5,
				"gate_pass": 0,
				"gate_warning": "Gate failed",
			}
		)
		self.assertEqual(fields["linked_stage_scorecard"], "PSC-001")
		self.assertEqual(fields["scorecard_display_title"], "Title")
		self.assertEqual(fields["scorecard_gate_warning"], "Gate failed")
		self.assertEqual(fields["scorecard_gate_pass"], 0)


@unittest.skipUnless(
	frappe.db.exists("DocType", "Project Gate Checkpoint"),
	"Stage Gate app is not installed",
)
class TestStageGateScorecardIntegration(FrappeTestCase):
	def setUp(self):
		self.original_flags = getattr(frappe.local, "flags", None)
		flags = frappe._dict(getattr(frappe.local, "flags", {}) or {})
		flags.in_test = True
		flags.mute_messages = True
		frappe.local.flags = flags

	def tearDown(self):
		if self.original_flags is None:
			try:
				del frappe.local.flags
			except AttributeError:
				pass
		else:
			frappe.local.flags = self.original_flags

	def test_checkpoint_review_blocked_without_agreed_scorecard(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field(
			stage_gate_integration.CHECKPOINT_REQUIRE_FIELD
		):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, template = self._create_checkpoint_fixture(require_scorecard=True)
		self.assertEqual(int(checkpoint.require_agreed_stage_scorecard or 0), 1)
		checkpoint.status = "In Review"
		with self.assertRaises(frappe.ValidationError):
			validate_project_gate_checkpoint(checkpoint)

		scorecard = self._create_submitted_scorecard(checkpoint)
		self.assertEqual(scorecard.docstatus, SCORECARD_AGREED_DOCSTATUS)

		checkpoint = frappe.get_doc("Project Gate Checkpoint", checkpoint.name)
		checkpoint.status = "In Review"
		validate_project_gate_checkpoint(checkpoint)
		self.assertEqual(checkpoint.linked_stage_scorecard, scorecard.name)

	def test_checkpoint_review_allowed_when_template_flag_disabled(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field(
			stage_gate_integration.CHECKPOINT_REQUIRE_FIELD
		):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, _template = self._create_checkpoint_fixture(require_scorecard=False)
		self.assertEqual(int(checkpoint.require_agreed_stage_scorecard or 0), 0)
		checkpoint.status = "In Review"
		validate_project_gate_checkpoint(checkpoint)

	def test_template_change_after_creation_does_not_change_checkpoint_requirement(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field(
			stage_gate_integration.CHECKPOINT_REQUIRE_FIELD
		):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, template = self._create_checkpoint_fixture(require_scorecard=True)
		frappe.db.set_value(
			"Stage Gate Template",
			template.name,
			stage_gate_integration.TEMPLATE_REQUIRE_FIELD,
			0,
		)
		checkpoint.reload()
		self.assertEqual(int(checkpoint.require_agreed_stage_scorecard or 0), 1)
		checkpoint.status = "In Review"
		with self.assertRaises(frappe.ValidationError):
			validate_project_gate_checkpoint(checkpoint)

	def test_backfill_copies_require_flag_from_template(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field(
			stage_gate_integration.CHECKPOINT_REQUIRE_FIELD
		):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, template = self._create_checkpoint_fixture(require_scorecard=False)
		frappe.db.set_value(
			"Stage Gate Template",
			template.name,
			stage_gate_integration.TEMPLATE_REQUIRE_FIELD,
			1,
		)
		frappe.db.set_value(
			"Project Gate Checkpoint",
			checkpoint.name,
			stage_gate_integration.CHECKPOINT_REQUIRE_FIELD,
			0,
			update_modified=False,
		)
		stage_gate_integration.backfill_checkpoint_require_agreed_flags()
		checkpoint.reload()
		self.assertEqual(int(checkpoint.require_agreed_stage_scorecard or 0), 1)

	def test_checkpoint_summary_reflects_failed_gate_as_warning_only(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field("linked_stage_scorecard"):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, _template = self._create_checkpoint_fixture(require_scorecard=False)
		scorecard = self._create_submitted_scorecard(
			checkpoint,
			gate_pass=0,
			gate_messages="STR_ALIGN normalized score 0.5000 is below required 0.7000",
		)
		checkpoint.reload()
		self.assertEqual(checkpoint.linked_stage_scorecard, scorecard.name)
		self.assertEqual(checkpoint.scorecard_gate_pass, 0)
		self.assertIn("STR_ALIGN", checkpoint.scorecard_gate_warning or "")

		checkpoint.status = "In Review"
		validate_project_gate_checkpoint(checkpoint)

	def test_scorecard_after_insert_refreshes_checkpoint_without_manual_save(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field("linked_stage_scorecard"):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, _template = self._create_checkpoint_fixture(require_scorecard=False)
		self._clear_checkpoint_scorecard_summary(checkpoint.name)
		scorecard = self._insert_scorecard_for_checkpoint(
			checkpoint,
			gate_pass=0,
			gate_messages="Gate failed",
			integral_score=2.5,
		)
		on_scorecard_checkpoint_sync(scorecard, "after_insert")
		checkpoint.reload()
		self.assertEqual(checkpoint.linked_stage_scorecard, scorecard.name)
		self.assertEqual(checkpoint.scorecard_integral_score, 2.5)
		self.assertEqual(checkpoint.scorecard_gate_pass, 0)

	def test_backfill_checkpoint_scorecard_summaries_restores_stale_checkpoint(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field("linked_stage_scorecard"):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, _template = self._create_checkpoint_fixture(require_scorecard=False)
		scorecard = self._insert_scorecard_for_checkpoint(checkpoint, integral_score=3.1)
		self._clear_checkpoint_scorecard_summary(checkpoint.name)
		stage_gate_integration.backfill_checkpoint_scorecard_summaries()
		checkpoint.reload()
		self.assertEqual(checkpoint.linked_stage_scorecard, scorecard.name)
		self.assertEqual(checkpoint.scorecard_integral_score, 3.1)

	def test_api_summary_includes_checkpoint_fields(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field("linked_stage_scorecard"):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, _template = self._create_checkpoint_fixture(require_scorecard=False)
		scorecard = self._insert_scorecard_for_checkpoint(
			checkpoint,
			gate_pass=0,
			gate_messages="Gate failed",
		)
		on_scorecard_checkpoint_sync(scorecard, "after_insert")
		summary = stage_gate_integration.get_checkpoint_scorecard_summary_for_api(checkpoint.name)
		self.assertEqual(summary["checkpoint_fields"]["linked_stage_scorecard"], scorecard.name)
		self.assertEqual(summary["checkpoint_fields"]["scorecard_gate_pass"], 0)
		self.assertEqual(summary["checkpoint_fields"]["scorecard_gate_warning"], "Gate failed")

	def test_refresh_after_recalculate_updates_checkpoint_summary(self):
		if not frappe.get_meta("Project Gate Checkpoint").has_field("linked_stage_scorecard"):
			self.skipTest("Stage Gate scorecard custom fields are not installed")

		checkpoint, _template = self._create_checkpoint_fixture(require_scorecard=False)
		scorecard = frappe.get_doc(
			"Project Scorecard",
			self._create_submitted_scorecard(checkpoint, gate_pass=1, integral_score=2.0).name,
		)
		frappe.db.set_value(
			"Project Scorecard",
			scorecard.name,
			{"integral_score": 1.0, "gate_pass": 0, "gate_messages": "Gate failed"},
			update_modified=True,
		)
		stage_gate_integration.refresh_checkpoints_for_stage_instance(checkpoint.stage_instance)
		checkpoint.reload()
		self.assertEqual(checkpoint.scorecard_integral_score, 1.0)
		self.assertEqual(checkpoint.scorecard_gate_pass, 0)
		self.assertEqual(checkpoint.scorecard_gate_warning, "Gate failed")

	def _create_checkpoint_fixture(self, *, require_scorecard: bool):
		company = frappe.get_all("Company", pluck="name", limit=1)[0]
		suffix = frappe.generate_hash(length=6)
		level = frappe.get_doc(
			{
				"doctype": "Project Gate Checkpoint Level",
				"name": f"CP Level {suffix}",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		template_data = {
			"doctype": "Stage Gate Template",
			"name": f"Gate Tpl {suffix}",
			"checkpoint_level": level.name,
			"enabled": 1,
			"items": [{"title": "Criterion", "is_mandatory": 1, "is_evidence_mandatory": 0}],
		}
		if frappe.get_meta("Stage Gate Template").has_field(stage_gate_integration.TEMPLATE_REQUIRE_FIELD):
			template_data[stage_gate_integration.TEMPLATE_REQUIRE_FIELD] = 1 if require_scorecard else 0
		template = frappe.get_doc(template_data).insert(ignore_permissions=True)
		stage = frappe.get_doc(
			{
				"doctype": "Project Stage",
				"name": f"Idea {suffix}",
				"stage_code": f"IDEA-{suffix}",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		governance_model = frappe.get_doc(
			{
				"doctype": "Project Governance Model",
				"name": f"Model {suffix}",
				"company": company,
				"enabled": 1,
				"stages": [
					{
						"stage": stage.name,
						"sequence": 1,
						"checkpoint_template": template.name,
					}
				],
			}
		).insert(ignore_permissions=True)
		project = frappe.get_doc(
			{
				"doctype": "Project",
				"name": f"TEST-PROJ-{suffix}",
				"project_name": f"Checkpoint scorecard test {suffix}",
				"naming_series": "PROJ-.####",
				"company": company,
				"governance_model": governance_model.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		checkpoint_name = frappe.get_all(
			"Project Gate Checkpoint",
			filters={"project": project.name},
			pluck="name",
			limit=1,
		)[0]
		checkpoint = frappe.get_doc("Project Gate Checkpoint", checkpoint_name)
		return checkpoint, template

	def _clear_checkpoint_scorecard_summary(self, checkpoint_name: str) -> None:
		frappe.db.set_value(
			"Project Gate Checkpoint",
			checkpoint_name,
			{
				"linked_stage_scorecard": None,
				"scorecard_display_title": "",
				"scorecard_status": "",
				"scorecard_integral_score": 0,
				"scorecard_gate_pass": 1,
				"scorecard_gate_warning": "",
			},
			update_modified=False,
		)

	def _insert_scorecard_for_checkpoint(
		self,
		checkpoint,
		*,
		gate_pass=1,
		gate_messages="",
		integral_score=3.0,
	):
		profile = frappe.db.get_value(
			"Project Scoring Profile", {"name": "Default Project Scoring Profile"}, "name"
		)
		if not profile:
			profile = frappe.get_all("Project Scoring Profile", pluck="name", limit=1)[0]
		frappe.db.set_value("Project", checkpoint.project, "custom_project_scoring_profile", profile)

		scorecard = frappe.get_doc(
			{
				"doctype": "Project Scorecard",
				"project": checkpoint.project,
				"profile": profile,
				"stage_instance_at_evaluation": checkpoint.stage_instance,
				"integral_score": integral_score,
				"gate_pass": gate_pass,
				"gate_messages": gate_messages,
			}
		)
		scorecard.insert(ignore_permissions=True)
		return scorecard

	def _create_submitted_scorecard(self, checkpoint, *, gate_pass=1, gate_messages="", integral_score=3.0):
		profile = frappe.db.get_value(
			"Project Scoring Profile", {"name": "Default Project Scoring Profile"}, "name"
		)
		if not profile:
			profile = frappe.get_all("Project Scoring Profile", pluck="name", limit=1)[0]
		frappe.db.set_value("Project", checkpoint.project, "custom_project_scoring_profile", profile)

		scorecard = frappe.get_doc(
			{
				"doctype": "Project Scorecard",
				"project": checkpoint.project,
				"profile": profile,
				"stage_instance_at_evaluation": checkpoint.stage_instance,
				"integral_score": integral_score,
				"gate_pass": gate_pass,
				"gate_messages": gate_messages,
			}
		)
		scorecard.insert(ignore_permissions=True)
		frappe.db.set_value(
			"Project Scorecard",
			scorecard.name,
			{"docstatus": SCORECARD_AGREED_DOCSTATUS, "status": "Approved"},
			update_modified=True,
		)
		stage_gate_integration.refresh_checkpoints_for_stage_instance(checkpoint.stage_instance)
		return frappe.get_doc("Project Scorecard", scorecard.name)
