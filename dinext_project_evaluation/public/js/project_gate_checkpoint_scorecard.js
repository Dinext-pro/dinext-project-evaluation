frappe.provide("dinext_project_evaluation.stage_gate_checkpoint");

const SCORECARD_SUMMARY_FIELDS = [
	"linked_stage_scorecard",
	"scorecard_display_title",
	"scorecard_status",
	"scorecard_integral_score",
	"scorecard_gate_pass",
	"scorecard_gate_warning",
];

const CHECKPOINT_SCORECARD_WIDGET_CLASS = "dpe-checkpoint-scorecard-widget";
const CHECKPOINT_SCORECARD_KPI_CONTEXT = "Project Gate Checkpoint.StageScorecard";

dinext_project_evaluation.stage_gate_checkpoint.ensure_dashboard_styles = function () {
	if (dinext_project_evaluation.stage_gate_checkpoint._dashboard_styles_loaded) {
		return Promise.resolve();
	}

	return new Promise((resolve) => {
		frappe.require(
			["/assets/dinext_project_evaluation/css/project_scorecard_dashboard.css"],
			() => {
				dinext_project_evaluation.stage_gate_checkpoint._dashboard_styles_loaded = true;
				resolve();
			}
		);
	});
};

dinext_project_evaluation.stage_gate_checkpoint.apply_checkpoint_fields = function (frm, fields) {
	if (!fields) {
		return;
	}
	for (const fieldname of SCORECARD_SUMMARY_FIELDS) {
		if (!Object.prototype.hasOwnProperty.call(fields, fieldname)) {
			continue;
		}
		frm.doc[fieldname] = fields[fieldname];
		if (frm.fields_dict[fieldname]) {
			frm.refresh_field(fieldname);
		}
	}
};

dinext_project_evaluation.stage_gate_checkpoint.ensure_scorecard_summary = function (frm) {
	if (frm.is_new() || !frm.doc.name || frm.doc.linked_stage_scorecard) {
		return Promise.resolve();
	}
	if (!frm.doc.stage_instance) {
		return Promise.resolve();
	}

	return frappe
		.call({
			method: "dinext_project_evaluation.api.get_checkpoint_scorecard_summary",
			args: { checkpoint: frm.doc.name },
		})
		.then((response) => {
			const summary = response.message;
			if (!summary) {
				return;
			}
			const fields = summary.checkpoint_fields || {};
			if (!fields.linked_stage_scorecard && summary.scorecard) {
				fields.linked_stage_scorecard = summary.scorecard;
				fields.scorecard_display_title = summary.scorecard_title || "";
				fields.scorecard_status = summary.status || "";
				fields.scorecard_integral_score = summary.integral_score;
				fields.scorecard_gate_pass = summary.gate_pass;
				fields.scorecard_gate_warning = summary.gate_warning || "";
			}
			dinext_project_evaluation.stage_gate_checkpoint.apply_checkpoint_fields(frm, fields);
		});
};

dinext_project_evaluation.stage_gate_checkpoint.has_linked_scorecard = function (frm) {
	return Boolean((frm.doc.linked_stage_scorecard || "").trim());
};

dinext_project_evaluation.stage_gate_checkpoint.format_integral_score = function (frm) {
	const score = frm.doc.scorecard_integral_score;
	if (score === null || score === undefined || score === "") {
		return null;
	}
	return flt(score, 2);
};

dinext_project_evaluation.stage_gate_checkpoint.get_gate_kpi_state = function (frm) {
	if (cint(frm.doc.scorecard_gate_pass)) {
		return {
			modifier: "gate-pass",
			label: __("Passed", null, CHECKPOINT_SCORECARD_KPI_CONTEXT),
		};
	}
	return {
		modifier: "gate-fail",
		label: __("Failed", null, CHECKPOINT_SCORECARD_KPI_CONTEXT),
	};
};

dinext_project_evaluation.stage_gate_checkpoint.parse_gate_messages = function (gate_warning) {
	if (!gate_warning) {
		return [];
	}
	return String(gate_warning)
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean);
};

dinext_project_evaluation.stage_gate_checkpoint.format_gate_warning = function (frm) {
	const warning = (frm.doc.scorecard_gate_warning || "").trim();
	if (warning) {
		return warning;
	}
	if (!dinext_project_evaluation.stage_gate_checkpoint.has_linked_scorecard(frm)) {
		return "";
	}
	if (cint(frm.doc.scorecard_gate_pass)) {
		return "";
	}
	return __("Scorecard gate thresholds were not met.", null, CHECKPOINT_SCORECARD_KPI_CONTEXT);
};

dinext_project_evaluation.stage_gate_checkpoint.build_gate_messages_html = function (frm) {
	if (cint(frm.doc.scorecard_gate_pass)) {
		return "";
	}

	const messages = dinext_project_evaluation.stage_gate_checkpoint.parse_gate_messages(
		dinext_project_evaluation.stage_gate_checkpoint.format_gate_warning(frm)
	);
	if (!messages.length) {
		return "";
	}

	const items = messages
		.map((message) => `<li>${frappe.utils.escape_html(message)}</li>`)
		.join("");

	return `
		<div class="dpe-scorecard-gate-messages">
			<div class="dpe-scorecard-gate-messages-title">${__(
				"Gate failure reasons",
				null,
				CHECKPOINT_SCORECARD_KPI_CONTEXT
			)}</div>
			<ul class="dpe-scorecard-gate-messages-list">${items}</ul>
		</div>`;
};

dinext_project_evaluation.stage_gate_checkpoint.build_scorecard_widget_html = function (frm) {
	const integralScore = dinext_project_evaluation.stage_gate_checkpoint.format_integral_score(frm);
	const gateState = dinext_project_evaluation.stage_gate_checkpoint.get_gate_kpi_state(frm);
	const statusLabel =
		(frm.doc.scorecard_status || "").trim() ||
		__("Not available", null, CHECKPOINT_SCORECARD_KPI_CONTEXT);
	const title =
		(frm.doc.scorecard_display_title || "").trim() || frm.doc.linked_stage_scorecard;
	const scorecardName = frm.doc.linked_stage_scorecard;
	const integralScoreLabel =
		integralScore === null
			? __("Not calculated", null, CHECKPOINT_SCORECARD_KPI_CONTEXT)
			: frappe.utils.escape_html(String(integralScore));
	const gateMessagesHtml =
		dinext_project_evaluation.stage_gate_checkpoint.build_gate_messages_html(frm);

	return `
		<div class="dpe-scorecard-dashboard-kpis dpe-checkpoint-scorecard-dashboard-kpis"
			data-scorecard="${frappe.utils.escape_html(scorecardName)}"
			role="link"
			tabindex="0"
			aria-label="${__(
				"Open linked Project Scorecard {0}",
				[scorecardName],
				CHECKPOINT_SCORECARD_KPI_CONTEXT
			)}">			
			<div class="dpe-scorecard-kpi-grid">
				<div class="dpe-scorecard-kpi-card dpe-scorecard-kpi-card--score">
					<div class="dpe-scorecard-kpi-label">${__(
						"Integral Score",
						null,
						CHECKPOINT_SCORECARD_KPI_CONTEXT
					)}</div>
					<div class="dpe-scorecard-kpi-value${
						integralScore === null ? " dpe-scorecard-kpi-value--pending" : ""
					}">${integralScoreLabel}</div>
				</div>
				<div class="dpe-scorecard-kpi-card dpe-scorecard-kpi-card--gate dpe-scorecard-kpi-card--${
					gateState.modifier
				}">
					<div class="dpe-scorecard-kpi-label">${__(
						"Gate Pass",
						null,
						CHECKPOINT_SCORECARD_KPI_CONTEXT
					)}</div>
					<div class="dpe-scorecard-kpi-status">
						<span class="dpe-scorecard-kpi-indicator" aria-hidden="true"></span>
						<span class="dpe-scorecard-kpi-status-text">${frappe.utils.escape_html(
							gateState.label
						)}</span>
					</div>
				</div>
				<div class="dpe-scorecard-kpi-card dpe-scorecard-kpi-card--recalculated">
					<div class="dpe-scorecard-kpi-label">${__(
						"Scorecard Status",
						null,
						CHECKPOINT_SCORECARD_KPI_CONTEXT
					)}</div>
					<div class="dpe-scorecard-kpi-value dpe-scorecard-kpi-value--datetime">${frappe.utils.escape_html(
						statusLabel
					)}</div>
				</div>
			</div>
			${gateMessagesHtml}
		</div>`;
};

dinext_project_evaluation.stage_gate_checkpoint.clear_scorecard_widget = function (frm) {
	if (!frm.dashboard?.parent?.length) {
		return;
	}
	frm.dashboard.parent.find(`.${CHECKPOINT_SCORECARD_WIDGET_CLASS}`).remove();
};

dinext_project_evaluation.stage_gate_checkpoint.open_linked_scorecard = function (scorecardName) {
	if (!scorecardName) {
		return;
	}
	frappe.set_route("Form", "Project Scorecard", scorecardName);
};

dinext_project_evaluation.stage_gate_checkpoint.bind_scorecard_widget_navigation = function (frm) {
	if (!frm.dashboard?.parent?.length) {
		return;
	}

	const $widget = frm.dashboard.parent.find(".dpe-checkpoint-scorecard-dashboard-kpis");
	$widget.off("click.dpeCheckpointScorecard keydown.dpeCheckpointScorecard");
	$widget.on("click.dpeCheckpointScorecard", function () {
		const scorecardName = $(this).attr("data-scorecard");
		dinext_project_evaluation.stage_gate_checkpoint.open_linked_scorecard(scorecardName);
	});
	$widget.on("keydown.dpeCheckpointScorecard", function (event) {
		if (event.key !== "Enter" && event.key !== " ") {
			return;
		}
		event.preventDefault();
		const scorecardName = $(this).attr("data-scorecard");
		dinext_project_evaluation.stage_gate_checkpoint.open_linked_scorecard(scorecardName);
	});
};

dinext_project_evaluation.stage_gate_checkpoint.render_scorecard_widget = function (frm) {
	if (!frm.dashboard) {
		return;
	}

	const renderToken = (frm._dpe_checkpoint_scorecard_widget_token =
		(frm._dpe_checkpoint_scorecard_widget_token || 0) + 1);

	dinext_project_evaluation.stage_gate_checkpoint.clear_scorecard_widget(frm);

	if (!dinext_project_evaluation.stage_gate_checkpoint.has_linked_scorecard(frm)) {
		return;
	}

	dinext_project_evaluation.stage_gate_checkpoint.ensure_dashboard_styles().then(() => {
		if (renderToken !== frm._dpe_checkpoint_scorecard_widget_token) {
			return;
		}

		dinext_project_evaluation.stage_gate_checkpoint.clear_scorecard_widget(frm);

		if (!dinext_project_evaluation.stage_gate_checkpoint.has_linked_scorecard(frm)) {
			return;
		}

		const html = dinext_project_evaluation.stage_gate_checkpoint.build_scorecard_widget_html(frm);
		frm.dashboard.add_section(
			html,
			__("Stage Scorecard", null, CHECKPOINT_SCORECARD_KPI_CONTEXT),
			`custom ${CHECKPOINT_SCORECARD_WIDGET_CLASS}`
		);
		dinext_project_evaluation.stage_gate_checkpoint.bind_scorecard_widget_navigation(frm);
		frm.dashboard.show();
	});
};

frappe.ui.form.on("Project Gate Checkpoint", {
	refresh(frm) {
		dinext_project_evaluation.stage_gate_checkpoint
			.ensure_scorecard_summary(frm)
			.then(() => {
				dinext_project_evaluation.stage_gate_checkpoint.render_scorecard_widget(frm);
			});
	},
});
