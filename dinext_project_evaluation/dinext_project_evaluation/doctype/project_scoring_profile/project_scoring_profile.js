// Copyright (c) 2026, Dinext and contributors
// For license information, please see license.txt

frappe.provide("dinext_project_evaluation.project_scoring_profile");

dinext_project_evaluation.project_scoring_profile.gate_fields = [
	"minimum_normalized_score",
	"minimum_raw_value",
	"maximum_raw_value",
];

dinext_project_evaluation.project_scoring_profile.numeric_input_types = new Set([
	"Number",
	"Currency",
	"Percent",
]);

dinext_project_evaluation.project_scoring_profile.get_gate_field_mode = function (
	requirement_level,
	input_type
) {
	if (requirement_level !== "Mandatory") {
		return {
			minimum_normalized_score: false,
			minimum_raw_value: false,
			maximum_raw_value: false,
		};
	}

	if (
		dinext_project_evaluation.project_scoring_profile.numeric_input_types.has(
			input_type
		)
	) {
		return {
			minimum_normalized_score: true,
			minimum_raw_value: true,
			maximum_raw_value: true,
		};
	}

	return {
		minimum_normalized_score: true,
		minimum_raw_value: false,
		maximum_raw_value: false,
	};
};

dinext_project_evaluation.project_scoring_profile.parse_criterion_input_type = function (value) {
	if (!value) {
		return null;
	}
	if (typeof value === "object") {
		return value.input_type || null;
	}
	return value;
};

dinext_project_evaluation.project_scoring_profile.is_blank_gate_value = function (value) {
	return value === undefined || value === null || value === "";
};

dinext_project_evaluation.project_scoring_profile.normalize_gate_field_value = function (
	fieldname,
	value
) {
	if (dinext_project_evaluation.project_scoring_profile.is_blank_gate_value(value)) {
		return null;
	}

	if (fieldname === "maximum_raw_value" && flt(value) === 0) {
		return null;
	}

	return value;
};

dinext_project_evaluation.project_scoring_profile.normalize_row_gate_values = function (
	row,
	input_type
) {
	if (!row) {
		return;
	}

	const mode = dinext_project_evaluation.project_scoring_profile.get_gate_field_mode(
		row.requirement_level,
		input_type
	);

	dinext_project_evaluation.project_scoring_profile.gate_fields.forEach((fieldname) => {
		if (!mode[fieldname]) {
			row[fieldname] = null;
			return;
		}

		row[fieldname] = dinext_project_evaluation.project_scoring_profile.normalize_gate_field_value(
			fieldname,
			row[fieldname]
		);
	});
};

dinext_project_evaluation.project_scoring_profile.apply_gate_fields = function (
	frm,
	cdt,
	cdn,
	input_type,
	clear_values = false
) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) {
		return;
	}

	const mode = dinext_project_evaluation.project_scoring_profile.get_gate_field_mode(
		row.requirement_level,
		input_type
	);
	const criteria_field = frm.get_field("criteria");
	const grid_row =
		criteria_field && criteria_field.grid ? criteria_field.grid.get_row(cdn) : null;

	dinext_project_evaluation.project_scoring_profile.gate_fields.forEach((fieldname) => {
		const visible = mode[fieldname];

		if (grid_row) {
			grid_row.toggle_display(fieldname, visible);
			grid_row.toggle_editable(fieldname, visible);
		}

		if (
			clear_values &&
			!visible &&
			!dinext_project_evaluation.project_scoring_profile.is_blank_gate_value(row[fieldname])
		) {
			frappe.model.set_value(cdt, cdn, fieldname, null);
		}
	});
};

dinext_project_evaluation.project_scoring_profile.apply_gate_fields_for_row = function (
	frm,
	cdt,
	cdn,
	clear_values = false
) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.criterion) {
		dinext_project_evaluation.project_scoring_profile.apply_gate_fields(
			frm,
			cdt,
			cdn,
			null,
			clear_values
		);
		return;
	}

	frappe.db.get_value(
		"Project Scoring Criterion",
		row.criterion,
		"input_type",
		(value) => {
			const input_type =
				dinext_project_evaluation.project_scoring_profile.parse_criterion_input_type(
					value
				);
			dinext_project_evaluation.project_scoring_profile.apply_gate_fields(
				frm,
				cdt,
				cdn,
				input_type,
				clear_values
			);
		}
	);
};

dinext_project_evaluation.project_scoring_profile.refresh_all_criteria_rows = function (
	frm,
	clear_values = false
) {
	const criteria = frm.doc.criteria || [];
	if (!criteria.length) {
		return;
	}

	const criterion_codes = [
		...new Set(criteria.map((row) => row.criterion).filter(Boolean)),
	];

	if (!criterion_codes.length) {
		criteria.forEach((row) => {
			dinext_project_evaluation.project_scoring_profile.apply_gate_fields(
				frm,
				row.doctype,
				row.name,
				null,
				clear_values
			);
		});
		return;
	}

	frappe.db
		.get_list("Project Scoring Criterion", {
			fields: ["name", "input_type"],
			filters: { name: ["in", criterion_codes] },
			limit: criterion_codes.length,
		})
		.then((records) => {
			const input_type_by_criterion = Object.fromEntries(
				records.map((record) => [record.name, record.input_type])
			);

			criteria.forEach((row) => {
				dinext_project_evaluation.project_scoring_profile.apply_gate_fields(
					frm,
					row.doctype,
					row.name,
					input_type_by_criterion[row.criterion] || null,
					clear_values
				);
			});
		});
};

dinext_project_evaluation.project_scoring_profile.normalize_all_criteria_gate_values = function (frm) {
	const criteria = frm.doc.criteria || [];
	if (!criteria.length) {
		return Promise.resolve();
	}

	const criterion_codes = [
		...new Set(criteria.map((row) => row.criterion).filter(Boolean)),
	];

	if (!criterion_codes.length) {
		criteria.forEach((row) => {
			dinext_project_evaluation.project_scoring_profile.normalize_row_gate_values(row, null);
		});
		return Promise.resolve();
	}

	return frappe.db
		.get_list("Project Scoring Criterion", {
			fields: ["name", "input_type"],
			filters: { name: ["in", criterion_codes] },
			limit: criterion_codes.length,
		})
		.then((records) => {
			const input_type_by_criterion = Object.fromEntries(
				records.map((record) => [record.name, record.input_type])
			);

			criteria.forEach((row) => {
				dinext_project_evaluation.project_scoring_profile.normalize_row_gate_values(
					row,
					input_type_by_criterion[row.criterion] || null
				);
			});
		});
};

frappe.ui.form.on("Project Scoring Profile", {
	refresh(frm) {
		dinext_project_evaluation.project_scoring_profile.refresh_all_criteria_rows(frm, false);
	},
	validate(frm) {
		return dinext_project_evaluation.project_scoring_profile.normalize_all_criteria_gate_values(
			frm
		);
	},
	criteria_add(frm, cdt, cdn) {
		dinext_project_evaluation.project_scoring_profile.apply_gate_fields(
			frm,
			cdt,
			cdn,
			null,
			true
		);
	},
});

function dpe_normalize_profile_gate_field(frm, cdt, cdn, fieldname) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) {
		return;
	}

	const normalized = dinext_project_evaluation.project_scoring_profile.normalize_gate_field_value(
		fieldname,
		row[fieldname]
	);
	if (normalized !== row[fieldname]) {
		frappe.model.set_value(cdt, cdn, fieldname, normalized);
	}
}

frappe.ui.form.on("Project Scoring Profile Criterion", {
	form_render(frm, cdt, cdn) {
		dinext_project_evaluation.project_scoring_profile.apply_gate_fields_for_row(
			frm,
			cdt,
			cdn,
			false
		);
	},
	minimum_normalized_score(frm, cdt, cdn) {
		dpe_normalize_profile_gate_field(frm, cdt, cdn, "minimum_normalized_score");
	},
	minimum_raw_value(frm, cdt, cdn) {
		dpe_normalize_profile_gate_field(frm, cdt, cdn, "minimum_raw_value");
	},
	maximum_raw_value(frm, cdt, cdn) {
		dpe_normalize_profile_gate_field(frm, cdt, cdn, "maximum_raw_value");
	},
	criterion(frm, cdt, cdn) {
		dinext_project_evaluation.project_scoring_profile.apply_gate_fields_for_row(
			frm,
			cdt,
			cdn,
			true
		);
	},
	requirement_level(frm, cdt, cdn) {
		dinext_project_evaluation.project_scoring_profile.apply_gate_fields_for_row(
			frm,
			cdt,
			cdn,
			true
		);
	},
});
