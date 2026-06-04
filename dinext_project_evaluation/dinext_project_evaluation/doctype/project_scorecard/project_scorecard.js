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

dinext_project_evaluation.project_scorecard.load_applicable_criteria = function (frm) {
	if (!frm.doc.project || !frm.doc.profile) {
		frm._dpe_applicable_criteria = [];
		return Promise.resolve([]);
	}

	return frappe
		.call({
			method: "dinext_project_evaluation.api.get_applicable_criteria",
			args: {
				project: frm.doc.project,
				profile: frm.doc.profile,
				stage: frm.doc.stage_at_evaluation || undefined,
			},
		})
		.then((response) => {
			frm._dpe_applicable_criteria = response.message || [];
			dinext_project_evaluation.project_scorecard.merge_item_mandatory_metadata(frm);
			return frm._dpe_applicable_criteria;
		});
};

dinext_project_evaluation.project_scorecard.merge_item_mandatory_metadata = function (frm) {
	const criteria = frm._dpe_applicable_criteria || [];
	if (!criteria.length) {
		return;
	}

	const criteriaByName = Object.fromEntries(
		criteria.map((criterion) => [criterion.criterion, criterion])
	);

	(frm.doc.items || []).forEach((row) => {
		const meta = criteriaByName[row.criterion];
		if (!meta) {
			return;
		}
		row.requirement_level = meta.requirement_level || "Desired";
		row.requires_comment = meta.requires_comment ? 1 : 0;
	});
};

dinext_project_evaluation.project_scorecard.ensure_mandatory_metadata = function (frm) {
	if (!frm.doc.project || !frm.doc.profile || !(frm.doc.items || []).length) {
		return;
	}

	if (!frm._dpe_applicable_criteria?.length) {
		frappe.call({
			method: "dinext_project_evaluation.api.get_applicable_criteria",
			args: {
				project: frm.doc.project,
				profile: frm.doc.profile,
				stage: frm.doc.stage_at_evaluation || undefined,
			},
			async: false,
			callback(response) {
				frm._dpe_applicable_criteria = response.message || [];
			},
		});
	}

	dinext_project_evaluation.project_scorecard.merge_item_mandatory_metadata(frm);
};

dinext_project_evaluation.project_scorecard.item_has_input_value = function (row) {
	if (!row) {
		return false;
	}

	const inputType = row.criterion_input_type;
	if (inputType === "Scale") {
		return !!(row.scale_value || row.raw_value);
	}
	if (inputType === "Boolean") {
		return !!row.boolean_value_set;
	}
	if (inputType === "Number") {
		return row.number_value !== undefined && row.number_value !== null && row.number_value !== "";
	}
	if (inputType === "Currency") {
		return row.currency_value !== undefined && row.currency_value !== null && row.currency_value !== "";
	}
	if (inputType === "Percent") {
		return row.percent_value !== undefined && row.percent_value !== null && row.percent_value !== "";
	}

	return !!(row.raw_value || (row.raw_numeric_value !== undefined && row.raw_numeric_value !== null && row.raw_numeric_value !== ""));
};

dinext_project_evaluation.project_scorecard.item_missing_required_comment = function (row) {
	if (!row?.requires_comment) {
		return false;
	}
	const comment = row.comment;
	return comment == null || comment === "" || !String(comment).trim();
};

dinext_project_evaluation.project_scorecard.item_missing_mandatory_value = function (row) {
	return (row.requirement_level || "Desired") === "Mandatory" &&
		!dinext_project_evaluation.project_scorecard.item_has_input_value(row);
};

dinext_project_evaluation.project_scorecard.highlight_missing_required_items = function (frm) {
	const grid = dinext_project_evaluation.project_scorecard.get_items_grid(frm);
	if (!grid) {
		return;
	}

	(frm.doc.items || []).forEach((row) => {
		if (!row?.name) {
			return;
		}

		const gridRow = grid.get_row(row.name);
		if (!gridRow) {
			return;
		}

		const valueMissing = dinext_project_evaluation.project_scorecard.item_missing_mandatory_value(row);
		const commentMissing = dinext_project_evaluation.project_scorecard.item_missing_required_comment(row);

		dinext_project_evaluation.project_scorecard.set_grid_reqd_if_changed(
			gridRow,
			"value_display",
			valueMissing || row.requirement_level === "Mandatory"
		);
		dinext_project_evaluation.project_scorecard.set_grid_reqd_if_changed(
			gridRow,
			"comment",
			commentMissing || !!row.requires_comment
		);

		const valueControl = gridRow.on_grid_fields_dict?.value_display;
		if (valueControl?.set_mandatory) {
			valueControl.set_mandatory(
				dinext_project_evaluation.project_scorecard.get_display_value(row)
			);
		}

		const commentControl = gridRow.on_grid_fields_dict?.comment;
		if (commentControl?.set_mandatory) {
			commentControl.set_mandatory(row.comment);
		}
	});
};

dinext_project_evaluation.project_scorecard.sync_item_display_values = function (frm) {
	(frm.doc.items || []).forEach((row) => {
		row.value_display = dinext_project_evaluation.project_scorecard.get_display_value(row);
	});
};

dinext_project_evaluation.project_scorecard.set_grid_reqd_if_changed = function (gridRow, fieldname, reqd) {
	const field = gridRow.on_grid_fields_dict?.[fieldname];
	const reqdInt = reqd ? 1 : 0;
	if (!field || cint(field.df.reqd) === reqdInt) {
		return;
	}
	gridRow.toggle_reqd(fieldname, reqd);
};

dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags = function (frm, cdn) {
	if (frm.doc.status === "Canceled") {
		return;
	}

	const grid = dinext_project_evaluation.project_scorecard.get_items_grid(frm);
	if (!grid) {
		return;
	}

	const rows = cdn
		? [(frm.doc.items || []).find((row) => row.name === cdn)].filter(Boolean)
		: frm.doc.items || [];

	rows.forEach((row) => {
		if (!row?.name) {
			return;
		}

		const gridRow = grid.get_row(row.name);
		if (!gridRow) {
			return;
		}

		const valueRequired = row.requirement_level === "Mandatory";
		const commentRequired = !!row.requires_comment;

		dinext_project_evaluation.project_scorecard.set_grid_reqd_if_changed(
			gridRow,
			"value_display",
			valueRequired
		);
		dinext_project_evaluation.project_scorecard.set_grid_reqd_if_changed(
			gridRow,
			"comment",
			commentRequired
		);
	});
};

dinext_project_evaluation.project_scorecard.prepare_mandatory_validation = function (frm) {
	if (frm.doc.status === "Canceled") {
		return;
	}

	dinext_project_evaluation.project_scorecard.ensure_mandatory_metadata(frm);
	dinext_project_evaluation.project_scorecard.sync_item_display_values(frm);
	dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags(frm);
	dinext_project_evaluation.project_scorecard.highlight_missing_required_items(frm);
	$(frm.wrapper).addClass("validated-form");
};

(function () {
	if (frappe.ui.form.check_mandatory.__dpe_project_scorecard_wrapped) {
		return;
	}

	const baseCheckMandatory = frappe.ui.form.check_mandatory;
	frappe.ui.form.check_mandatory = function (frm) {
		if (frm?.doc?.doctype === "Project Scorecard" && frm.doc.status !== "Canceled") {
			dinext_project_evaluation.project_scorecard.prepare_mandatory_validation(frm);
		}
		const isValid = baseCheckMandatory(frm);
		if (
			!isValid &&
			frm?.doc?.doctype === "Project Scorecard" &&
			frm.doc.status !== "Canceled"
		) {
			dinext_project_evaluation.project_scorecard.highlight_missing_required_items(frm);
		}
		return isValid;
	};
	frappe.ui.form.check_mandatory.__dpe_project_scorecard_wrapped = true;
})();

// Frappe has no API to hide row-check / row-index columns; hide them in the items grid only.
dinext_project_evaluation.project_scorecard.hide_items_grid_leading_columns = function (grid) {
	if (!grid || !grid.wrapper) {
		return;
	}
	grid.wrapper.find(".row-check, .row-index").hide();
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
	dinext_project_evaluation.project_scorecard.hide_items_grid_leading_columns(grid);
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

dinext_project_evaluation.project_scorecard.open_grid_select_control = function (control) {
	if (!control?.$input?.length) {
		return;
	}
	const input = control.$input.get(0);
	if (!input || input.tagName !== "SELECT" || input.disabled) {
		return;
	}

	input.focus();
	if (typeof input.showPicker === "function") {
		try {
			input.showPicker();
			return;
		} catch (error) {
			// fall through
		}
	}
	input.click();
};

dinext_project_evaluation.project_scorecard.autopen_grid_value_select = function (gridRow) {
	const control = gridRow.on_grid_fields_dict?.value_display;
	if (control?.df?.fieldtype === "Select") {
		dinext_project_evaluation.project_scorecard.open_grid_select_control(control);
	}
};

dinext_project_evaluation.project_scorecard.setup_grid_value_control = function (frm, gridRow, column) {
	const row = gridRow.doc;
	if (!row || !column) {
		return;
	}

	column.field_area.empty();
	const df = dinext_project_evaluation.project_scorecard.get_active_control_df(row);
	if (!df) {
		return;
	}

	const activeValue = dinext_project_evaluation.project_scorecard.get_active_control_value(row);
	const control = frappe.ui.form.make_control({
		parent: column.field_area.get(0),
		df,
		only_input: true,
		render_input: true,
		value: activeValue,
	});
	control.make_input();
	if (control.set_input) {
		control.set_input(activeValue);
	}
	control.df.change = function () {
		const nextValues = dinext_project_evaluation.project_scorecard.compute_active_control_values(
			row,
			control.get_value()
		);
		dinext_project_evaluation.project_scorecard.persist_row_value_fields(row, nextValues);
		const displayValue = nextValues?.value_display;
		const text = displayValue == null || displayValue === "" ? "" : String(displayValue);
		if (column.static_area) {
			column.static_area.html(frappe.utils.escape_html(text));
		}
		if (control.$input?.length && control.$input.get(0).tagName === "SELECT") {
			control.$input.get(0).blur();
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

	if (!column._dpe_autopen_select_bound) {
		column._dpe_autopen_select_bound = true;
		column.on("click", (event) => {
			if (column.field_area?.is(":visible") && column.field_area.has(event.target).length) {
				return;
			}
			setTimeout(() => {
				dinext_project_evaluation.project_scorecard.autopen_grid_value_select(gridRow);
			}, 0);
		});
	}
};

dinext_project_evaluation.project_scorecard.setup_items_grid_lock = function (frm) {
	if (frm._dpe_items_grid_lock_bound) {
		return;
	}
	frm._dpe_items_grid_lock_bound = true;
	$(frm.wrapper).on("grid-row-render", (e, gridRow) => {
		gridRow.row?.find(".row-check, .row-index").hide();
		dinext_project_evaluation.project_scorecard.bind_grid_value_column(frm, gridRow);
		if (gridRow.doc?.name) {
			dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags(
				frm,
				gridRow.doc.name
			);
		}
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
			const resolved = dinext_project_evaluation.project_scorecard.resolve_scale_value(
				row,
				row.scale_value
			);
			const match = options.find(
				(option) => String(option.value ?? option.score) === String(resolved)
			);
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

dinext_project_evaluation.project_scorecard.parse_scale_options = function (row) {
	try {
		return JSON.parse(row.scale_options_json || "[]");
	} catch (error) {
		return [];
	}
};

dinext_project_evaluation.project_scorecard.resolve_scale_value = function (row, scaleValue) {
	if (scaleValue == null || scaleValue === "") {
		return "";
	}

	const options = dinext_project_evaluation.project_scorecard.parse_scale_options(row);
	const normalized = String(scaleValue);

	const byValue = options.find(
		(option) => String(option.value ?? option.score) === normalized
	);
	if (byValue) {
		return String(byValue.value ?? byValue.score);
	}

	const byLabel = options.find((option) => (option.label || "") === normalized);
	if (byLabel) {
		return String(byLabel.value ?? byLabel.score);
	}

	if (normalized.includes(":")) {
		return normalized.slice(normalized.lastIndexOf(":") + 1);
	}

	return normalized;
};

dinext_project_evaluation.project_scorecard.get_scale_empty_option = function () {
	// Zero-width space: non-empty for frappe_better_select_control, visually blank in UI.
	return { label: "\u200b", value: "" };
};

dinext_project_evaluation.project_scorecard.get_scale_select_options = function (options) {
	return [
		dinext_project_evaluation.project_scorecard.get_scale_empty_option(),
		...options.map((option) => ({
			label: option.label || String(option.score ?? option.value),
			value: String(option.value ?? option.score),
		})),
	];
};

dinext_project_evaluation.project_scorecard.get_active_control_df = function (row, fieldname = "active_value") {
	if (!row) {
		return null;
	}

	if (row.criterion_input_type === "Scale") {
		const options = dinext_project_evaluation.project_scorecard.parse_scale_options(row);
		return {
			fieldtype: "Select",
			fieldname,
			options: dinext_project_evaluation.project_scorecard.get_scale_select_options(options),
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
		return (
			dinext_project_evaluation.project_scorecard.resolve_scale_value(row, row.scale_value) || ""
		);
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

dinext_project_evaluation.project_scorecard.compute_active_control_values = function (row, value) {
	if (!row) {
		return null;
	}

	const nextValues = {};
	const inputType = row.criterion_input_type;

	if (inputType === "Scale") {
		nextValues.scale_value =
			dinext_project_evaluation.project_scorecard.resolve_scale_value(row, value) || null;
	} else if (inputType === "Boolean") {
		nextValues.boolean_value = value ? 1 : 0;
		nextValues.boolean_value_set = 1;
	} else {
		const numericField =
			dinext_project_evaluation.project_scorecard.typed_field_by_type[inputType];
		if (numericField) {
			nextValues[numericField] = value;
		}
	}

	const previewRow = Object.assign({}, row, nextValues);
	nextValues.value_display =
		dinext_project_evaluation.project_scorecard.get_display_value(previewRow);

	return nextValues;
};

dinext_project_evaluation.project_scorecard.persist_row_value_fields = function (row, nextValues) {
	if (!row?.name || !nextValues) {
		return;
	}

	const cdt = row.doctype;
	const cdn = row.name;

	Object.entries(nextValues).forEach(([fieldname, value]) => {
		frappe.model.set_value(cdt, cdn, fieldname, value);
	});
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
	const activeValue = dinext_project_evaluation.project_scorecard.get_active_control_value(row);
	if (control.set_input) {
		control.set_input(activeValue);
	}
	control.df.change = function () {
		const nextValues = dinext_project_evaluation.project_scorecard.compute_active_control_values(
			row,
			control.get_value()
		);
		dinext_project_evaluation.project_scorecard.persist_row_value_fields(row, nextValues);
		if (control.$input?.length && control.$input.get(0).tagName === "SELECT") {
			control.$input.get(0).blur();
		}
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
		dinext_project_evaluation.project_scorecard.load_applicable_criteria(frm).then(() => {
			dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags(frm);
		});
	},
	validate(frm) {
		dinext_project_evaluation.project_scorecard.prepare_mandatory_validation(frm);
	},
});

frappe.ui.form.on("Project Scorecard Item", {
	comment(frm, cdt, cdn) {
		dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags(frm, cdn);
	},
	form_render(frm, cdt, cdn) {
		dinext_project_evaluation.project_scorecard.render_row_editor(frm, cdt, cdn);
		dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags(frm, cdn);
	},
});
