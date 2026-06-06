// Copyright (c) 2026, Dinext and contributors
// For license information, please see license.txt

frappe.provide("dinext_project_evaluation.project_scorecard");

dinext_project_evaluation.project_scorecard.form_styles = `
.dpe-project-scorecard-form .grid-row.dpe-project-scorecard-mandatory-row {
	border-radius: var(--border-radius-md, 8px);
	box-shadow: inset 0 0 0 1px var(--red-500, #dc2626);
}
.dpe-project-scorecard-form .grid-form .dpe-scale-key-phrases-hint {
	font-size: var(--text-xs, 11px);
	color: var(--text-muted, #6b7280);
	margin-top: 4px;
	line-height: 1.35;
	white-space: normal;
}
.dpe-project-scorecard-form .dpe-criterion-description-hint {
	margin-left: 4px;
	color: var(--text-muted, #6b7280);
	cursor: help;
	vertical-align: middle;
}
`;

dinext_project_evaluation.project_scorecard.typed_field_by_type = {
	Scale: "scale_value",
	Boolean: "boolean_value",
	Number: "number_value",
	Currency: "currency_value",
	Percent: "percent_value",
};

dinext_project_evaluation.project_scorecard.normalize_criterion_description = function (value) {
	if (value == null) {
		return "";
	}
	return String(value).trim();
};

dinext_project_evaluation.project_scorecard.get_criterion_description = function (row) {
	return dinext_project_evaluation.project_scorecard.normalize_criterion_description(
		row?.criterion_description
	);
};

dinext_project_evaluation.project_scorecard.get_items_grid = function (frm) {
	const field = frm.get_field("items");
	return field && field.grid ? field.grid : null;
};

dinext_project_evaluation.project_scorecard.is_content_editable = function (frm) {
	return frm?.doc?.status === "Draft";
};

dinext_project_evaluation.project_scorecard.apply_content_editability = function (frm) {
	const editable = dinext_project_evaluation.project_scorecard.is_content_editable(frm);
	frm.set_df_property("items", "read_only", editable ? 0 : 1);

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
		gridRow.toggle_editable("comment", editable);
		const commentControl = gridRow.on_grid_fields_dict?.comment;
		if (commentControl?.set_read_only) {
			commentControl.set_read_only(!editable);
		}
		if (commentControl?.$input?.length) {
			commentControl.$input.prop("disabled", !editable);
		}
	});
};

dinext_project_evaluation.project_scorecard.ensure_styles = function () {
	if (dinext_project_evaluation.project_scorecard._styles_injected) {
		return;
	}

	frappe.dom.set_style(dinext_project_evaluation.project_scorecard.form_styles);
	dinext_project_evaluation.project_scorecard._styles_injected = true;
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
		row.criterion_min_value = meta.min_value ?? row.criterion_min_value;
		row.criterion_max_value = meta.max_value ?? row.criterion_max_value;
		row.criterion_description = dinext_project_evaluation.project_scorecard.normalize_criterion_description(
			meta.description
		);
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

dinext_project_evaluation.project_scorecard.item_value_out_of_range = function (row) {
	if (!row || row.criterion_min_value == null || row.criterion_max_value == null) {
		return false;
	}

	let value = null;
	if (row.criterion_input_type === "Number") {
		value = row.number_value;
	} else if (row.criterion_input_type === "Currency") {
		value = row.currency_value;
	} else if (row.criterion_input_type === "Percent") {
		value = row.percent_value;
	}

	if (value === undefined || value === null || value === "") {
		return false;
	}

	const numericValue = Number(value);
	if (Number.isNaN(numericValue)) {
		return true;
	}

	return numericValue < Number(row.criterion_min_value) || numericValue > Number(row.criterion_max_value);
};

dinext_project_evaluation.project_scorecard.item_has_validation_issue = function (row) {
	return (
		dinext_project_evaluation.project_scorecard.item_missing_mandatory_value(row) ||
		dinext_project_evaluation.project_scorecard.item_missing_required_comment(row) ||
		dinext_project_evaluation.project_scorecard.item_value_out_of_range(row)
	);
};

dinext_project_evaluation.project_scorecard.item_missing_mandatory_value = function (row) {
	return (row.requirement_level || "Desired") === "Mandatory" &&
		!dinext_project_evaluation.project_scorecard.item_has_input_value(row);
};

dinext_project_evaluation.project_scorecard.decorate_criterion_description_hint = function (
	parentEl,
	description
) {
	if (!parentEl?.length) {
		return;
	}

	const hintClass = "dpe-criterion-description-hint";
	parentEl.find(`.${hintClass}`).remove();
	if (!description) {
		parentEl.removeAttr("title");
		return;
	}

	parentEl.attr("title", description);
	const hint = $(
		`<span class="${hintClass}" title="${frappe.utils.escape_html(description)}">` +
			`<svg class="icon icon-xs" aria-hidden="true"><use href="#icon-help"></use></svg>` +
			`</span>`
	);
	parentEl.append(hint);
};

dinext_project_evaluation.project_scorecard.apply_criterion_row_tooltip = function (gridRow) {
	if (!gridRow?.doc) {
		return;
	}

	const description = dinext_project_evaluation.project_scorecard.get_criterion_description(
		gridRow.doc
	);
	const column = gridRow.columns?.criterion_name;
	if (column?.static_area?.length) {
		dinext_project_evaluation.project_scorecard.decorate_criterion_description_hint(
			column.static_area,
			description
		);
	}

	const criterionField = gridRow.grid_form?.fields_dict?.criterion_name;
	if (criterionField?.$wrapper?.length) {
		const labelArea = criterionField.$wrapper.find(".control-label, .grid-label");
		const target = labelArea.length ? labelArea.first() : criterionField.$wrapper;
		dinext_project_evaluation.project_scorecard.decorate_criterion_description_hint(
			target,
			description
		);
	}
};

dinext_project_evaluation.project_scorecard.apply_all_criterion_row_tooltips = function (frm) {
	const grid = dinext_project_evaluation.project_scorecard.get_items_grid(frm);
	if (!grid) {
		return;
	}

	(frm.doc.items || []).forEach((row) => {
		if (!row?.name) {
			return;
		}
		const gridRow = grid.get_row(row.name);
		if (gridRow) {
			dinext_project_evaluation.project_scorecard.apply_criterion_row_tooltip(gridRow);
		}
	});
};

dinext_project_evaluation.project_scorecard.get_grid_row_element = function (gridRow) {
	// Frappe: wrapper is `.grid-row`, inner `.row` is `.data-row` — styles target wrapper.
	return gridRow?.wrapper?.length ? gridRow.wrapper : gridRow?.row;
};

dinext_project_evaluation.project_scorecard.apply_item_row_state = function (frm, gridRow) {
	if (!gridRow?.doc) {
		return;
	}

	const rowEl = dinext_project_evaluation.project_scorecard.get_grid_row_element(gridRow);
	if (!rowEl?.length) {
		return;
	}

	const row = gridRow.doc;
	const showMandatoryOutline =
		dinext_project_evaluation.project_scorecard.item_has_validation_issue(row);

	$(frm.wrapper).addClass("dpe-project-scorecard-form");
	rowEl.toggleClass("dpe-project-scorecard-mandatory-row", showMandatoryOutline);
};

dinext_project_evaluation.project_scorecard.apply_all_item_row_states = function (frm) {
	const grid = dinext_project_evaluation.project_scorecard.get_items_grid(frm);
	if (!grid) {
		return;
	}

	(frm.doc.items || []).forEach((row) => {
		if (!row?.name) {
			return;
		}
		const gridRow = grid.get_row(row.name);
		if (gridRow) {
			dinext_project_evaluation.project_scorecard.apply_item_row_state(frm, gridRow);
		}
	});
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

		dinext_project_evaluation.project_scorecard.apply_item_row_state(frm, gridRow);

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

		dinext_project_evaluation.project_scorecard.apply_item_row_state(frm, gridRow);

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
	setTimeout(() => {
		dinext_project_evaluation.project_scorecard.lock_items_grid(frm);
		dinext_project_evaluation.project_scorecard.apply_all_item_row_states(frm);
		dinext_project_evaluation.project_scorecard.apply_all_criterion_row_tooltips(frm);
	}, 0);
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

	if (!dinext_project_evaluation.project_scorecard.is_content_editable(frm)) {
		const displayValue = dinext_project_evaluation.project_scorecard.get_display_value(row);
		const text = displayValue == null || displayValue === "" ? "" : String(displayValue);
		if (column.static_area) {
			column.static_area.html(frappe.utils.escape_html(text));
			dinext_project_evaluation.project_scorecard.apply_scale_static_tooltip(row, column.static_area);
		}
		return;
	}

	column.field_area.empty();
	column.field_area.find(".dpe-scale-key-phrases-hint").remove();
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
			dinext_project_evaluation.project_scorecard.apply_scale_static_tooltip(row, column.static_area);
		}
		dinext_project_evaluation.project_scorecard.decorate_scale_select_control(
			row,
			control,
			column.field_area,
			{ showInlineHint: false }
		);
		if (control.$input?.length && control.$input.get(0).tagName === "SELECT") {
			control.$input.get(0).blur();
		}
	};
	column.field = control;
	gridRow.on_grid_fields_dict.value_display = control;
	control.refresh();
	dinext_project_evaluation.project_scorecard.decorate_scale_select_control(row, control, column.field_area, {
		showInlineHint: false,
	});
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
		dinext_project_evaluation.project_scorecard.apply_scale_static_tooltip(row, column.static_area);
	}
	column.field_area?.find(".dpe-scale-key-phrases-hint").remove();

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

	if (
		dinext_project_evaluation.project_scorecard.is_content_editable(frm) &&
		!column._dpe_autopen_select_bound
	) {
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
		dinext_project_evaluation.project_scorecard.apply_criterion_row_tooltip(gridRow);
		dinext_project_evaluation.project_scorecard.apply_item_row_state(frm, gridRow);
		if (!dinext_project_evaluation.project_scorecard.is_content_editable(frm)) {
			gridRow.toggle_editable("comment", false);
		}
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
						(!row.criterion_name ||
							!row.criterion_input_type ||
							!dinext_project_evaluation.project_scorecard.get_criterion_description(row))
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
			fields: ["name", "criterion_name", "input_type", "description"],
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
				if (!dinext_project_evaluation.project_scorecard.get_criterion_description(row)) {
					row.criterion_description =
						dinext_project_evaluation.project_scorecard.normalize_criterion_description(
							meta.description
						);
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
		const raw = JSON.parse(row.scale_options_json || "[]");
		return dinext_project_evaluation.project_scorecard.normalize_scale_options(raw);
	} catch (error) {
		return [];
	}
};

dinext_project_evaluation.project_scorecard.normalize_scale_options = function (options) {
	return (options || []).map((option) => ({
		label: option.label || String(option.score ?? option.value ?? ""),
		value: String(option.value ?? option.score ?? ""),
		score: option.score ?? option.value,
		sort_order: option.sort_order ?? null,
		key_phrases: option.key_phrases || "",
	}));
};

dinext_project_evaluation.project_scorecard.find_scale_option = function (row, scaleValue) {
	if (scaleValue == null || scaleValue === "") {
		return null;
	}
	const options = dinext_project_evaluation.project_scorecard.parse_scale_options(row);
	const resolved = dinext_project_evaluation.project_scorecard.resolve_scale_value(row, scaleValue);
	return options.find(
		(option) => String(option.value ?? option.score) === String(resolved)
	);
};

dinext_project_evaluation.project_scorecard.get_selected_scale_key_phrases = function (row) {
	const activeValue = dinext_project_evaluation.project_scorecard.get_active_control_value(row);
	if (!activeValue) {
		return "";
	}
	const option = dinext_project_evaluation.project_scorecard.find_scale_option(row, activeValue);
	return option?.key_phrases ? String(option.key_phrases).trim() : "";
};

dinext_project_evaluation.project_scorecard.apply_scale_select_tooltips = function (row, control) {
	if (!control?.$input?.length || row?.criterion_input_type !== "Scale") {
		return;
	}

	const select = control.$input.get(0);
	if (!select || select.tagName !== "SELECT") {
		return;
	}

	const options = dinext_project_evaluation.project_scorecard.parse_scale_options(row);
	const optionByValue = Object.fromEntries(
		options.map((option) => [String(option.value ?? option.score), option])
	);
	const currentValue = dinext_project_evaluation.project_scorecard.get_active_control_value(row);
	const currentOption = optionByValue[currentValue];
	select.title = currentOption?.key_phrases ? String(currentOption.key_phrases).trim() : "";

	Array.from(select.options).forEach((optionElement) => {
		const meta = optionByValue[optionElement.value];
		optionElement.title = meta?.key_phrases ? String(meta.key_phrases).trim() : "";
	});
};

dinext_project_evaluation.project_scorecard.apply_scale_static_tooltip = function (row, staticArea) {
	if (!staticArea?.length || row?.criterion_input_type !== "Scale") {
		return;
	}

	const phrases = dinext_project_evaluation.project_scorecard.get_selected_scale_key_phrases(row);
	staticArea.attr("title", phrases || null);
};

dinext_project_evaluation.project_scorecard.remove_scale_key_phrases_hint = function (parentEl) {
	if (!parentEl?.length) {
		return;
	}
	parentEl.find(".dpe-scale-key-phrases-hint").remove();
};

dinext_project_evaluation.project_scorecard.ensure_scale_key_phrases_hint = function (row, parentEl) {
	if (!parentEl?.length || row?.criterion_input_type !== "Scale") {
		return;
	}

	const hintClass = "dpe-scale-key-phrases-hint";
	let hint = parentEl.find(`.${hintClass}`);
	if (!hint.length) {
		hint = $(`<div class="${hintClass}"></div>`);
		parentEl.append(hint);
	}

	const phrases = dinext_project_evaluation.project_scorecard.get_selected_scale_key_phrases(row);
	if (!phrases) {
		hint.hide().empty();
		return;
	}

	hint.text(phrases).show();
};

dinext_project_evaluation.project_scorecard.decorate_scale_select_control = function (
	row,
	control,
	parentEl,
	options = {}
) {
	const showInlineHint = !!options.showInlineHint;
	dinext_project_evaluation.project_scorecard.apply_scale_select_tooltips(row, control);
	if (showInlineHint) {
		dinext_project_evaluation.project_scorecard.ensure_scale_key_phrases_hint(row, parentEl);
		return;
	}
	dinext_project_evaluation.project_scorecard.remove_scale_key_phrases_hint(parentEl);
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

	const parent = locals[row.parenttype] && locals[row.parenttype][row.parent];
	if (parent && parent.status !== "Draft") {
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

	if (!dinext_project_evaluation.project_scorecard.is_content_editable(frm)) {
		const gridRow = frm.get_field("items").grid.get_row(cdn);
		if (!gridRow?.grid_form?.fields_dict?.value_editor?.$wrapper?.length) {
			return;
		}
		const displayValue = dinext_project_evaluation.project_scorecard.get_display_value(row);
		const text = displayValue == null || displayValue === "" ? "" : String(displayValue);
		gridRow.grid_form.fields_dict.value_editor.$wrapper.html(frappe.utils.escape_html(text));
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
		dinext_project_evaluation.project_scorecard.decorate_scale_select_control(row, control, wrapper, {
			showInlineHint: true,
		});
		if (control.$input?.length && control.$input.get(0).tagName === "SELECT") {
			control.$input.get(0).blur();
		}
		dinext_project_evaluation.project_scorecard.refresh_items_field(frm);
	};
	dinext_project_evaluation.project_scorecard.decorate_scale_select_control(row, control, wrapper, {
		showInlineHint: true,
	});
};

dinext_project_evaluation.project_scorecard.render_row_editor = function (frm, cdt, cdn) {
	const gridRow = frm.get_field("items").grid.get_row(cdn);
	if (!gridRow) {
		return;
	}

	dinext_project_evaluation.project_scorecard.hide_row_form_field(gridRow, "value_display");
	dinext_project_evaluation.project_scorecard.apply_criterion_row_tooltip(gridRow);
	dinext_project_evaluation.project_scorecard.render_active_control(frm, cdt, cdn);
};

dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT = "Project Scorecard.KPI";

dinext_project_evaluation.project_scorecard.ensure_dashboard_styles = function () {
	if (dinext_project_evaluation.project_scorecard._dashboard_styles_loaded) {
		return Promise.resolve();
	}

	return new Promise((resolve) => {
		frappe.require(
			["/assets/dinext_project_evaluation/css/project_scorecard_dashboard.css"],
			() => {
				dinext_project_evaluation.project_scorecard._dashboard_styles_loaded = true;
				resolve();
			}
		);
	});
};

dinext_project_evaluation.project_scorecard.is_score_computed = function (doc) {
	if (!doc?.evaluation_date) {
		return false;
	}
	const score = doc.integral_score;
	return score !== null && score !== undefined && score !== "";
};

dinext_project_evaluation.project_scorecard.format_integral_score = function (doc) {
	if (!dinext_project_evaluation.project_scorecard.is_score_computed(doc)) {
		return null;
	}
	return flt(doc.integral_score, 2);
};

dinext_project_evaluation.project_scorecard.parse_gate_messages = function (gate_messages) {
	if (!gate_messages) {
		return [];
	}
	return String(gate_messages)
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean);
};

dinext_project_evaluation.project_scorecard.get_gate_kpi_state = function (doc) {
	if (cint(doc.gate_pass)) {
		return {
			modifier: "gate-pass",
			label: __("Passed", null, dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT),
		};
	}
	return {
		modifier: "gate-fail",
		label: __("Failed", null, dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT),
	};
};

dinext_project_evaluation.project_scorecard.build_gate_messages_html = function (doc) {
	if (
		!dinext_project_evaluation.project_scorecard.is_score_computed(doc) ||
		cint(doc.gate_pass)
	) {
		return "";
	}

	const messages = dinext_project_evaluation.project_scorecard.parse_gate_messages(
		doc.gate_messages
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
				dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT
			)}</div>
			<ul class="dpe-scorecard-gate-messages-list">${items}</ul>
		</div>`;
};

dinext_project_evaluation.project_scorecard.build_dashboard_kpi_html = function (frm) {
	const doc = frm.doc;
	const integralScore = dinext_project_evaluation.project_scorecard.format_integral_score(doc);
	const gateState = dinext_project_evaluation.project_scorecard.get_gate_kpi_state(doc);

	const gateMessagesHtml =
		dinext_project_evaluation.project_scorecard.build_gate_messages_html(doc);

	return `
		<div class="dpe-scorecard-dashboard-kpis">
			<div class="dpe-scorecard-kpi-grid">
				<div class="dpe-scorecard-kpi-card dpe-scorecard-kpi-card--score">
					<div class="dpe-scorecard-kpi-label">${__(
						"Integral Score",
						null,
						dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT
					)}</div>
					<div class="dpe-scorecard-kpi-value">${frappe.utils.escape_html(String(integralScore))}</div>
				</div>
				<div class="dpe-scorecard-kpi-card dpe-scorecard-kpi-card--gate dpe-scorecard-kpi-card--${gateState.modifier}">
					<div class="dpe-scorecard-kpi-label">${__(
						"Gate Pass",
						null,
						dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT
					)}</div>
					<div class="dpe-scorecard-kpi-status">
						<span class="dpe-scorecard-kpi-indicator" aria-hidden="true"></span>
						<span class="dpe-scorecard-kpi-status-text">${frappe.utils.escape_html(
							gateState.label
						)}</span>
					</div>
				</div>
			</div>
			${gateMessagesHtml}
		</div>`;
};

dinext_project_evaluation.project_scorecard.clear_dashboard_kpis = function (frm) {
	if (!frm.dashboard?.parent?.length) {
		return;
	}
	frm.dashboard.parent.find(".dpe-scorecard-kpi-dashboard").remove();
};

dinext_project_evaluation.project_scorecard.render_dashboard_kpis = function (frm) {
	if (!frm.dashboard) {
		return;
	}

	const renderToken = (frm._dpe_dashboard_kpi_render_token =
		(frm._dpe_dashboard_kpi_render_token || 0) + 1);

	dinext_project_evaluation.project_scorecard.clear_dashboard_kpis(frm);

	if (!dinext_project_evaluation.project_scorecard.is_score_computed(frm.doc)) {
		return;
	}

	dinext_project_evaluation.project_scorecard.ensure_dashboard_styles().then(() => {
		if (renderToken !== frm._dpe_dashboard_kpi_render_token) {
			return;
		}

		dinext_project_evaluation.project_scorecard.clear_dashboard_kpis(frm);

		if (!dinext_project_evaluation.project_scorecard.is_score_computed(frm.doc)) {
			return;
		}

		const html = dinext_project_evaluation.project_scorecard.build_dashboard_kpi_html(frm);
		frm.dashboard.add_section(
			html,
			__("Evaluation Summary", null, dinext_project_evaluation.project_scorecard.KPI_TRANSLATION_CONTEXT),
			"custom dpe-scorecard-kpi-dashboard"
		);
		frm.dashboard.show();
	});
};

frappe.ui.form.on("Project Scorecard", {
	refresh(frm) {
		dinext_project_evaluation.project_scorecard.ensure_value_display_column();
		dinext_project_evaluation.project_scorecard.ensure_styles();
		dinext_project_evaluation.project_scorecard.render_dashboard_kpis(frm);
		$(frm.wrapper).addClass("dpe-project-scorecard-form");
		dinext_project_evaluation.project_scorecard.setup_items_grid_lock(frm);
		dinext_project_evaluation.project_scorecard.lock_items_grid(frm);
		dinext_project_evaluation.project_scorecard.hydrate_grid_rows(frm);
		dinext_project_evaluation.project_scorecard.apply_content_editability(frm);
		dinext_project_evaluation.project_scorecard.load_applicable_criteria(frm).then(() => {
			dinext_project_evaluation.project_scorecard.apply_item_mandatory_flags(frm);
			dinext_project_evaluation.project_scorecard.apply_all_item_row_states(frm);
			dinext_project_evaluation.project_scorecard.apply_all_criterion_row_tooltips(frm);
			dinext_project_evaluation.project_scorecard.apply_content_editability(frm);
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
