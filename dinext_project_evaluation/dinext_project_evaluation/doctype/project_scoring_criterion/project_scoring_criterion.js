// Copyright (c) 2026, Dinext and contributors
// For license information, please see license.txt

frappe.provide("dinext_project_evaluation.project_scoring_criterion");

dinext_project_evaluation.project_scoring_criterion.numeric_input_types = new Set([
	"Number",
	"Currency",
	"Percent",
]);

dinext_project_evaluation.project_scoring_criterion.get_field_visibility = function (doc) {
	const inputType = doc?.input_type;

	if (inputType === "Scale") {
		return {
			scale_rows: true,
			min_value: false,
			max_value: false,
			boolean_true_score: false,
			boolean_false_score: false,
		};
	}

	if (dinext_project_evaluation.project_scoring_criterion.numeric_input_types.has(inputType)) {
		return {
			scale_rows: false,
			min_value: true,
			max_value: true,
			boolean_true_score: false,
			boolean_false_score: false,
		};
	}

	if (inputType === "Boolean") {
		return {
			scale_rows: false,
			min_value: false,
			max_value: false,
			boolean_true_score: true,
			boolean_false_score: true,
		};
	}

	return {
		scale_rows: false,
		min_value: false,
		max_value: false,
		boolean_true_score: false,
		boolean_false_score: false,
	};
};

dinext_project_evaluation.project_scoring_criterion.apply_field_visibility = function (frm) {
	const visibility = dinext_project_evaluation.project_scoring_criterion.get_field_visibility(
		frm.doc
	);

	Object.entries(visibility).forEach(([fieldname, visible]) => {
		frm.toggle_display(fieldname, visible);
	});
};

frappe.ui.form.on("Project Scoring Criterion", {
	refresh(frm) {
		dinext_project_evaluation.project_scoring_criterion.apply_field_visibility(frm);
	},
	input_type(frm) {
		dinext_project_evaluation.project_scoring_criterion.apply_field_visibility(frm);
	},
});
