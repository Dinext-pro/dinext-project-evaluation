frappe.provide("dinext_project_evaluation.project_scoring");

frappe.ui.form.on("Project", {
	refresh(frm) {
		frm._dpe_prev_scoring_profile = frm.doc.custom_project_scoring_profile;
		frm._dpe_prev_governance_model = frm.doc.governance_model;
		dinext_project_evaluation.project_scoring.setup_profile_field(frm);
		dinext_project_evaluation.project_scoring.refresh(frm);
	},
	after_save(frm) {
		frm._dpe_prev_scoring_profile = frm.doc.custom_project_scoring_profile;
		frm._dpe_prev_governance_model = frm.doc.governance_model;
		frm._dpe_stashed_scoring_profile = null;
		frm._dpe_governance_before_attempt = null;
	},
	governance_model(frm) {
		dinext_project_evaluation.project_scoring.on_governance_change(frm);
	},
	custom_project_scoring_profile(frm) {
		dinext_project_evaluation.project_scoring.on_profile_change(frm);
	},
});

dinext_project_evaluation.project_scoring.build_profile_filters = function (frm) {
	const filters = { status: "Active" };

	if (frm.doc.custom_project_portfolio) {
		filters.portfolio = ["in", [frm.doc.custom_project_portfolio, ""]];
	}
	if (frm.doc.company) {
		filters.company = ["in", [frm.doc.company, ""]];
	}
	if (frm.doc.project_type) {
		filters.project_type = ["in", [frm.doc.project_type, ""]];
	}

	return filters;
};

dinext_project_evaluation.project_scoring.setup_profile_field = function (frm) {
	if (!frm.fields_dict.custom_project_scoring_profile) {
		return;
	}

	const has_governance = !!frm.doc.governance_model;
	frm.toggle_display("custom_project_scoring_profile", has_governance);
	frm.toggle_enable("custom_project_scoring_profile", has_governance);

	frm.set_query("custom_project_scoring_profile", () => ({
		filters: dinext_project_evaluation.project_scoring.build_profile_filters(frm),
	}));
};

dinext_project_evaluation.project_scoring.on_governance_change = function (frm) {
	if (frm.is_new()) {
		frm._dpe_prev_governance_model = frm.doc.governance_model;
		dinext_project_evaluation.project_scoring.setup_profile_field(frm);
		return;
	}

	const previous = frm._dpe_prev_governance_model;
	const next_value = frm.doc.governance_model;
	if (previous === next_value) {
		return;
	}

	if (
		frm._dpe_stashed_scoring_profile &&
		next_value === frm._dpe_governance_before_attempt
	) {
		dinext_project_evaluation.project_scoring.clear_profile_silently(
			frm,
			frm._dpe_stashed_scoring_profile
		);
		frm._dpe_stashed_scoring_profile = null;
		frm._dpe_governance_before_attempt = null;
		frm._dpe_prev_governance_model = next_value;
		dinext_project_evaluation.project_scoring.setup_profile_field(frm);
		return;
	}

	frm._dpe_prev_governance_model = next_value;
	dinext_project_evaluation.project_scoring.setup_profile_field(frm);

	if (!frm.doc.custom_project_scoring_profile) {
		frm._dpe_prev_scoring_profile = null;
		return;
	}

	frm._dpe_governance_before_attempt = previous;
	frm._dpe_stashed_scoring_profile = frm.doc.custom_project_scoring_profile;
	dinext_project_evaluation.project_scoring.clear_profile_silently(frm, null);
};

dinext_project_evaluation.project_scoring.clear_profile_silently = function (frm, value) {
	frm._dpe_suppress_profile_confirm = true;
	frm._dpe_prev_scoring_profile = value;
	return frm.set_value("custom_project_scoring_profile", value).finally(() => {
		frm._dpe_prev_scoring_profile = value;
		frm._dpe_suppress_profile_confirm = false;
	});
};

dinext_project_evaluation.project_scoring.on_profile_change = function (frm) {
	if (frm.is_new()) {
		frm._dpe_prev_scoring_profile = frm.doc.custom_project_scoring_profile;
		return;
	}

	const previous = frm._dpe_prev_scoring_profile;
	const next_value = frm.doc.custom_project_scoring_profile;
	if (previous === next_value) {
		return;
	}

	if (frm._dpe_suppress_profile_confirm) {
		frm._dpe_prev_scoring_profile = next_value;
		return;
	}

	if (!previous) {
		frm._dpe_prev_scoring_profile = next_value;
		return;
	}

	const message = __(
		"Changing or clearing Project Scoring Profile will cancel all Project Scorecards for this project. Continue?"
	);

	frappe.confirm(
		message,
		() => {
			frm.set_value("confirm_scoring_profile_reset", 1).then(() => {
				frm._dpe_prev_scoring_profile = next_value;
			});
		},
		() => {
			frm.set_value("custom_project_scoring_profile", previous).then(() => {
				frm._dpe_prev_scoring_profile = previous;
			});
		}
	);
};

dinext_project_evaluation.project_scoring.refresh = function (frm) {
	if (frm.is_new() || !frm.doc.custom_project_scoring_profile) {
		return;
	}

	frm.add_custom_button(
		__("Open Scorecards"),
		() => {
			frappe.set_route("List", "Project Scorecard", { project: frm.doc.name });
		},
		__("Evaluation")
	);

	frm.add_custom_button(
		__("Open Scoring Report"),
		() => {
			frappe.route_options = {
				project_portfolio: frm.doc.custom_project_portfolio,
				project: [frm.doc.name],
			};
			frappe.set_route("query-report", "Project Scoring Report");
		},
		__("Evaluation")
	);

	dinext_project_evaluation.project_scoring.render_history(frm);
};

dinext_project_evaluation.project_scoring.render_history = function (frm) {
	frappe.call({
		method: "dinext_project_evaluation.api.get_scorecard_history",
		args: { project: frm.doc.name, limit: 5 },
		callback(r) {
			const rows = r.message || [];
			if (!rows.length) {
				return;
			}

			const html = rows
				.map((row) => {
					const score =
						row.integral_score === null || row.integral_score === undefined
							? "-"
							: flt(row.integral_score, 4);
					const gate = row.gate_pass ? __("Gate passed") : __("Gate failed");
					return `<li><a href="/app/project-scorecard/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a>: ${score} (${gate})</li>`;
				})
				.join("");

			frm.dashboard.add_section(
				`<div class="project-scoring-history"><h5>${__("Project Evaluation")}</h5><ul>${html}</ul></div>`
			);
		},
	});
};
