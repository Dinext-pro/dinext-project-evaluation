// Copyright (c) 2026, Dinext and contributors
// For license information, please see license.txt

frappe.provide("dinext_project_evaluation.project_scorecard");

dinext_project_evaluation.project_scorecard.typed_field_by_type = {
	Scale: "scale_value",
	Boolean: "boolean_value",
	Number: "number_value",
	Currency: "currency_value",
	Percent: "percent_value",
};

dinext_project_evaluation.project_scorecard.get_items_grid = function (frm) {
	const field = frm.get_field("items");
	return field && field.grid ? field.grid : null;
};

// Frappe toggle_checkboxes() only disables inputs; row-check column stays visible.
dinext_project_evaluation.project_scorecard.hide_items_grid_checkbox_column = function (grid) {
	if (!grid || !grid.wrapper) {
		return;
	}
	grid.wrapper.find(".row-check").hide();
};

dinext_project_evaluation.project_scorecard.lock_items_grid = function (frm) {
	frm.set_df_property("items", "cannot_add_rows", true);
	frm.set_df_property("items", "cannot_delete_rows", true);
	const grid = dinext_project_evaluation.project_scorecard.get_items_grid(frm);
	if (!grid) {
		return;
	}
	grid.cannot_add_rows = true;
	grid.df.cannot_delete_rows = true;
	grid.toggle_checkboxes(false);
	dinext_project_evaluation.project_scorecard.hide_items_grid_checkbox_column(grid);
};

dinext_project_evaluation.project_scorecard.refresh_items_field = function (frm) {
	frm.refresh_field("items");
	dinext_project_evaluation.project_scorecard.lock_items_grid(frm);
};

dinext_project_evaluation.project_scorecard.ensure_value_display_column = function () {
	const df = frappe.meta.get_docfield("Project Scorecard Item", "value_display");
	if (df) {
		df.hidden = 0;
		df.in_list_view = 1;
	}
};

dinext_project_evaluation.project_scorecard.hide_row_form_field = function (gridRow, fieldname) {
	if (!gridRow || !gridRow.grid_form || !gridRow.grid_form.fields_dict[fieldname]) {
		return;
	}
	const field = gridRow.grid_form.fields_dict[fieldname];
	field.$wrapper.closest(".frappe-control").hide();
};

dinext_project_evaluation.project_scorecard.setup_grid_value_control = function (frm, gridRow, column) {
	const row = gridRow.doc;
	if (!row || !column) {
		return;
	}

	column.field_area.empty();
	const df = dinext_project_evaluation.project_scorecard.get_active_control_df(row, "value_display");
	if (!df) {
		return;
	}

	const control = frappe.ui.form.make_control({
		parent: column.field_area.get(0),
		df,
		only_input: true,
		doc: row,
		doctype: row.doctype,
		docname: row.name,
		frm,
		grid: gridRow.grid,
		grid_row: gridRow,
		value: dinext_project_evaluation.project_scorecard.get_active_control_value(row),
	});
	control.make_input();
	control.set_value(dinext_project_evaluation.project_scorecard.get_active_control_value(row));
	control.df.change = function () {
		dinext_project_evaluation.project_scorecard.apply_active_control_value(row, control.get_value());
		const displayValue = dinext_project_evaluation.project_scorecard.get_display_value(row);
		const text = displayValue == null || displayValue === "" ? "" : String(displayValue);
		if (column.static_area) {
			column.static_area.html(frappe.utils.escape_html(text));
		}
	};
	column.field = control;
	gridRow.on_grid_fields_dict.value_display = control;
	control.refresh();
};

dinext_project_evaluation.project_scorecard.bind_grid_value_column = function (frm, gridRow) {
	const row = gridRow.doc;
	const column = gridRow.columns && gridRow.columns.value_display;
	if (!row || !column) {
		return;
	}

	const displayValue = dinext_project_evaluation.project_scorecard.get_display_value(row);
	const text = displayValue == null || displayValue === "" ? "" : String(displayValue);
	if (column.static_area) {
		column.static_area.html(frappe.utils.escape_html(text));
	}

	if (!gridRow._dpe_value_make_control_bound) {
		gridRow._dpe_value_make_control_bound = true;
		const baseMakeControl = gridRow.make_control.bind(gridRow);
		gridRow.make_control = function (col) {
			if (col.df && col.df.fieldname === "value_display") {
				dinext_project_evaluation.project_scorecard.setup_grid_value_control(frm, gridRow, col);
				return;
			}
			return baseMakeControl(col);
		};
	}
};

dinext_project_evaluation.project_scorecard.setup_items_grid_lock = function (frm) {
	if (frm._dpe_items_grid_lock_bound) {
		return;
	}
	frm._dpe_items_grid_lock_bound = true;
	$(frm.wrapper).on("grid-row-render", (e, gridRow) => {
		dinext_project_evaluation.project_scorecard.bind_grid_value_column(frm, gridRow);
		dinext_project_evaluation.project_scorecard.lock_items_grid(frm);
	});
};

dinext_project_evaluation.project_scorecard.hydrate_grid_rows = function (frm) {
	const rows = frm.doc.items || [];
	if (!rows.length) {
		return Promise.resolve();
	}

	rows.forEach((row) => {
		if (!row.value_display) {
			row.value_display = dinext_project_evaluation.project_scorecard.get_display_value(row);
		}
	});

	const missingCriterionMeta = [
		...new Set(
			rows
				.filter(
					(row) =>
						row.criterion &&
						(!row.criterion_name || !row.criterion_input_type)
				)
				.map((row) => row.criterion)
		),
	];
	if (!missingCriterionMeta.length) {
		dinext_project_evaluation.project_scorecard.refresh_items_field(frm);
		return Promise.resolve();
	}

	return frappe.db
		.get_list("Project Scoring Criterion", {
			fields: ["name", "criterion_name", "input_type"],
			filters: { name: ["in", missingCriterionMeta] },
			limit: missingCriterionMeta.length,
		})
		.then((records) => {
			const metaByCriterion = Object.fromEntries(
				records.map((record) => [record.name, record])
			);
			rows.forEach((row) => {
				const meta = metaByCriterion[row.criterion];
				if (!meta) {
					return;
				}
				if (!row.criterion_name) {
					row.criterion_name = meta.criterion_name;
				}
				if (!row.criterion_input_type) {
					row.criterion_input_type = meta.input_type;
				}
				if (!row.value_display) {
					row.value_display = dinext_project_evaluation.project_scorecard.get_display_value(row);
				}
			});
			dinext_project_evaluation.project_scorecard.refresh_items_field(frm);
		});
};

dinext_project_evaluation.project_scorecard.get_display_value = function (row) {
	if (!row) {
		return null;
	}

	if (row.criterion_input_type === "Scale") {
		if (!row.scale_value) {
			return null;
		}
		try {
			const options = JSON.parse(row.scale_options_json || "[]");
			const match = options.find((option) => String(option.value) === String(row.scale_value));
			return (match && match.label) || row.scale_value;
		} catch (error) {
			return row.scale_value;
		}
	}

	if (row.criterion_input_type === "Boolean") {
		if (!row.boolean_value_set) {
			return null;
		}
		return row.boolean_value ? __("Yes") : __("No");
	}

	const numericField =
		dinext_project_evaluation.project_scorecard.typed_field_by_type[row.criterion_input_type];
	if (
		numericField &&
		row[numericField] !== undefined &&
		row[numericField] !== null &&
		row[numericField] !== ""
	) {
		return String(row[numericField]);
	}

	return row.raw_value || null;
};

dinext_project_evaluation.project_scorecard.get_active_control_df = function (row, fieldname = "active_value") {
	if (!row) {
		return null;
	}

	if (row.criterion_input_type === "Scale") {
		let options = [];
		try {
			options = JSON.parse(row.scale_options_json || "[]");
		} catch (error) {
			options = [];
		}
		return {
			fieldtype: "Select",
			fieldname,
			options: ["", ...options.map((option) => option.value)].join("\n"),
		};
	}

	if (row.criterion_input_type === "Boolean") {
		return {
			fieldtype: "Check",
			fieldname,
		};
	}

	const fieldtypeByCriterionType = {
		Number: "Float",
		Currency: "Currency",
		Percent: "Percent",
	};

	return {
		fieldtype: fieldtypeByCriterionType[row.criterion_input_type] || "Data",
		fieldname,
	};
};

dinext_project_evaluation.project_scorecard.get_active_control_value = function (row) {
	if (!row) {
		return null;
	}

	if (row.criterion_input_type === "Scale") {
		return row.scale_value || "";
	}

	if (row.criterion_input_type === "Boolean") {
		return row.boolean_value_set ? (row.boolean_value ? 1 : 0) : 0;
	}

	const numericField =
		dinext_project_evaluation.project_scorecard.typed_field_by_type[row.criterion_input_type];
	if (numericField) {
		return row[numericField];
	}

	return row.value_display || row.raw_value || null;
};

dinext_project_evaluation.project_scorecard.apply_active_control_value = function (row, value) {
	if (!row) {
		return;
	}

	if (row.criterion_input_type === "Scale") {
		row.scale_value = value || null;
	} else if (row.criterion_input_type === "Boolean") {
		row.boolean_value = value ? 1 : 0;
		row.boolean_value_set = 1;
	} else {
		const numericField =
			dinext_project_evaluation.project_scorecard.typed_field_by_type[row.criterion_input_type];
		if (numericField) {
			row[numericField] = value;
		}
	}

	row.value_display = dinext_project_evaluation.project_scorecard.get_display_value(row);
};

dinext_project_evaluation.project_scorecard.render_active_control = function (frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) {
		return;
	}

	const gridRow = frm.get_field("items").grid.get_row(cdn);
	if (!gridRow || !gridRow.grid_form || !gridRow.grid_form.fields_dict.value_editor) {
		return;
	}

	const wrapper = gridRow.grid_form.fields_dict.value_editor.$wrapper;
	if (!wrapper || !wrapper.length) {
		return;
	}

	wrapper.empty();
	const control = frappe.ui.form.make_control({
		parent: wrapper.get(0),
		df: dinext_project_evaluation.project_scorecard.get_active_control_df(row),
		render_input: true,
		value: dinext_project_evaluation.project_scorecard.get_active_control_value(row),
		only_input: true,
	});
	control.make_input();
	control.set_value(dinext_project_evaluation.project_scorecard.get_active_control_value(row));
	control.df.change = function () {
		dinext_project_evaluation.project_scorecard.apply_active_control_value(row, control.get_value());
		dinext_project_evaluation.project_scorecard.refresh_items_field(frm);
	};
};

dinext_project_evaluation.project_scorecard.render_row_editor = function (frm, cdt, cdn) {
	const gridRow = frm.get_field("items").grid.get_row(cdn);
	if (!gridRow) {
		return;
	}

	dinext_project_evaluation.project_scorecard.hide_row_form_field(gridRow, "value_display");
	dinext_project_evaluation.project_scorecard.render_active_control(frm, cdt, cdn);
};

frappe.ui.form.on("Project Scorecard", {
	refresh(frm) {
		dinext_project_evaluation.project_scorecard.ensure_value_display_column();
		dinext_project_evaluation.project_scorecard.setup_items_grid_lock(frm);
		dinext_project_evaluation.project_scorecard.lock_items_grid(frm);
		dinext_project_evaluation.project_scorecard.hydrate_grid_rows(frm);
	},
});

frappe.ui.form.on("Project Scorecard Item", {
	form_render(frm, cdt, cdn) {
		dinext_project_evaluation.project_scorecard.render_row_editor(frm, cdt, cdn);
	},
});
