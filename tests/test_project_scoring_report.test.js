const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const REPORT_SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/dinext_project_evaluation/report/project_scoring_report/project_scoring_report.js";
const REPORT_PYTHON_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/dinext_project_evaluation/report/project_scoring_report/project_scoring_report.py";

function jqueryGet(nodes) {
	return function get(index) {
		if (index === undefined) {
			return nodes;
		}
		return nodes[index];
	};
}

function loadReportScript() {
	const script = fs.readFileSync(REPORT_SCRIPT_PATH, "utf8");
	const state = {
		requiredAssets: [],
		windowListeners: {},
		setRouteCalls: [],
		makeControlCalls: [],
	};

	const context = {
		__(value) {
			return value;
		},
		console,
		window: {
			addEventListener(event, handler) {
				state.windowListeners[event] = handler;
			},
			removeEventListener(event, handler) {
				if (state.windowListeners[event] === handler) {
					delete state.windowListeners[event];
				}
			},
		},
		document: {
			documentElement: {
				getAttribute() {
					return null;
				},
			},
			createElement(tag) {
				return {
					tagName: tag,
					className: "",
					children: [],
					appendChild(node) {
						this.children.push(node);
					},
				};
			},
		},
		MutationObserver: function MutationObserver(callback) {
			this.callback = callback;
			this.observe = () => {};
			this.disconnect = () => {};
		},
		frappe: {
			query_reports: {},
			query_report: null,
			provide(path) {
				const segments = path.split(".");
				let pointer = context;
				for (const segment of segments) {
					pointer[segment] = pointer[segment] || {};
					pointer = pointer[segment];
				}
			},
			ui: {
				form: {
					make_control(config) {
						state.makeControlCalls.push(config);
						const control = {
							df: config.df,
							_value: config.value,
							get_value() {
								return this._value;
							},
							set_value(value) {
								this._value = value;
							},
							refresh() {},
						};
						if (config.df?.change) {
							control.triggerChange = function triggerChange() {
								config.df.change.call(control);
							};
						}
						return control;
					},
				},
			},
			db: {
				get_link_options() {
					return [];
				},
			},
			require(files, callback) {
				state.requiredAssets.push(...files);
				if (callback) {
					callback();
				}
			},
			utils: {
				escape_html(value) {
					return value;
				},
			},
			set_route(...args) {
				state.setRouteCalls.push(args);
			},
		},
		dinext_project_evaluation: {},
		$: (value) => {
			if (value && typeof value === "object") {
				return value;
			}
			return {
				length: 0,
				remove() {},
				prependTo() {
					return {
						length: 1,
						find() {
							return { length: 0, get: jqueryGet([]) };
						},
						get: jqueryGet([{ innerHTML: "" }]),
					};
				},
				find() {
					return { length: 0, remove() {} };
				},
				get: jqueryGet([{ innerHTML: "" }]),
			};
		},
	};

	vm.runInNewContext(script, context);

	return {
		context,
		state,
		report: context.frappe.query_reports["Project Scoring Report"],
		namespace: context.dinext_project_evaluation.project_scoring_report,
	};
}

function createMetricControlsMount() {
	const controlsDom = {
		innerHTML: "",
		children: [],
		appendChild(node) {
			this.children.push(node);
		},
	};
	const mount = {
		length: 1,
		find(selector) {
			if (selector === ".project-scoring-report-controls") {
				return {
					length: 1,
					get: jqueryGet([controlsDom]),
				};
			}
			return { length: 0, get: jqueryGet([]) };
		},
	};
	return { mount, controlsDom };
}

test("project scoring report defines evaluated stage, size metric and color metric filters", () => {
	const { report } = loadReportScript();

	assert.ok(report);
	assert.ok(Array.isArray(report.filters));

	const filterNames = report.filters.map((filter) => filter.fieldname);
	assert.ok(filterNames.includes("evaluated_stage"));
	assert.ok(filterNames.includes("size_metric"));
	assert.ok(filterNames.includes("color_metric"));
});

test("project scoring report defines project governance and activity filters", () => {
	const { report } = loadReportScript();
	const filterNames = report.filters.map((filter) => filter.fieldname);

	assert.ok(filterNames.includes("project_type"));
	assert.ok(filterNames.includes("project_status"));
	assert.ok(filterNames.includes("governance_model"));
	assert.ok(filterNames.includes("only_active_projects"));

	const profileFilter = report.filters.find((filter) => filter.fieldname === "profile");
	assert.equal(profileFilter.label, "Project Scoring Profile");
	assert.equal(profileFilter.options, "Project Scoring Profile");

	const governanceFilter = report.filters.find((filter) => filter.fieldname === "governance_model");
	assert.equal(governanceFilter.options, "Project Governance Model");

	const activeFilter = report.filters.find((filter) => filter.fieldname === "only_active_projects");
	assert.equal(activeFilter.fieldtype, "Check");
	assert.equal(activeFilter.default, 0);
});

test("project scoring report table columns align with row-level filters", () => {
	const pythonSource = fs.readFileSync(REPORT_PYTHON_PATH, "utf8");
	const columnsBlockMatch = pythonSource.match(/def get_columns\(\):[\s\S]*?^\t\]/m);
	assert.ok(columnsBlockMatch, "expected get_columns() definition in report python module");

	const columnsBlock = columnsBlockMatch[0];
	const requiredColumns = [
		"project",
		"portfolio",
		"project_type",
		"project_status",
		"governance_model",
		"project_stage",
		"evaluated_stage",
		"profile",
		"gate_pass",
	];

	for (const fieldname of requiredColumns) {
		assert.match(columnsBlock, new RegExp(`"fieldname": "${fieldname}"`));
	}

	for (const fieldname of ["risk_score_norm", "benefit_score_norm", "cost_score_norm"]) {
		assert.doesNotMatch(columnsBlock, new RegExp(`"fieldname": "${fieldname}"`));
	}
});

test("project scoring report uses roadmap-safe namespace and onload hook", () => {
	const { report, namespace } = loadReportScript();

	assert.equal(typeof report.onload, "function");
	assert.ok(namespace);
	assert.equal(typeof namespace.isScoringReport, "function");
	assert.equal(typeof namespace.wrapReportRefresh, "function");
});

test("after_datatable_render renders against frappe.query_report instead of datatable argument", () => {
	const { context, report, namespace } = loadReportScript();
	const renderCalls = [];
	namespace.render = (activeReport) => {
		renderCalls.push(activeReport);
	};

	context.frappe.query_report = {
		report_name: "Project Scoring Report",
	};

	report.after_datatable_render({ not: "the report instance" });

	assert.deepEqual(renderCalls, [context.frappe.query_report]);
});

test("ensureChartMount shell includes metric controls above chart", () => {
	const { namespace } = loadReportScript();
	const script = fs.readFileSync(REPORT_SCRIPT_PATH, "utf8");

	assert.doesNotMatch(script, /project-scoring-report-card-head/);
	assert.doesNotMatch(script, /project-scoring-report-summary/);
	assert.doesNotMatch(script, /renderSummary/);
	assert.match(script, /project-scoring-report-controls/);
	assert.match(script, /frappe\.ui\.form\.make_control/);
	assert.match(script, /project-scoring-report-legend/);
	assert.match(script, /project-scoring-report-chart/);
	assert.match(script, /project-scoring-report-empty-state/);
	assert.equal(typeof namespace.renderLegend, "function");
	assert.equal(typeof namespace.renderMetricControls, "function");
	assert.equal(typeof namespace.ensureMetricControlInstances, "function");
});

test("metric axis filters are hidden from standard report filter bar", () => {
	const { report } = loadReportScript();
	const metricFilters = report.filters.filter((filter) =>
		["x_axis", "y_axis", "size_metric", "color_metric"].includes(filter.fieldname)
	);

	assert.equal(metricFilters.length, 4);
	for (const filter of metricFilters) {
		assert.equal(filter.hidden, 1);
	}
});

test("getMetricControlOptionIds reads filter options with fallback", () => {
	const { namespace } = loadReportScript();

	assert.equal(
		namespace.getMetricControlOptionIds({ df: { options: "a\nb" } }).join(","),
		"a,b"
	);
	assert.equal(
		namespace
			.getMetricControlOptionIds({
				df: {
					options: [
						{ value: "c", label: "C" },
						{ value: "d", label: "D" },
					],
				},
			})
			.join(","),
		"c,d"
	);
	assert.equal(namespace.getMetricControlOptionIds(null).join(","), "");
});

test("buildMetricOptionLabelMap prefers catalog labels", () => {
	const { namespace } = loadReportScript();

	const labelMap = namespace.buildMetricOptionLabelMap(
		[{ id: "integral_score", label: "Integral Score" }],
		["integral_score", "risk_score_norm"]
	);

	assert.equal(labelMap.integral_score, "Integral Score");
	assert.equal(labelMap.risk_score_norm, "risk_score_norm");
});

test("buildMetricOptionLabelMap keeps plain catalog labels for duplicate Project and Scorecard names", () => {
	const { namespace } = loadReportScript();
	const catalogEntries = [
		{
			id: "project:status",
			label: "Status",
			source_kind: "project_field",
			source_doctype: "Project",
		},
		{
			id: "scorecard:status",
			label: "Status",
			source_kind: "scorecard_field",
			source_doctype: "Project Scorecard",
		},
		{ id: "project:priority", label: "Priority", source_kind: "project_field" },
	];

	const labelMap = namespace.buildMetricOptionLabelMap(catalogEntries, [
		"project:status",
		"scorecard:status",
		"project:priority",
	]);

	assert.equal(labelMap["project:status"], "Status");
	assert.equal(labelMap["scorecard:status"], "Status");
	assert.equal(labelMap["project:priority"], "Priority");
});

test("buildMetricSelectOptions returns value/label pairs for make_control", () => {
	const { namespace } = loadReportScript();

	const options = namespace.buildMetricSelectOptions(
		[{ id: "integral_score", label: "Integral Score" }],
		["integral_score", "risk_score_norm"]
	);

	assert.equal(JSON.stringify(options), JSON.stringify([
		{ value: "integral_score", label: "Integral Score" },
		{ value: "risk_score_norm", label: "risk_score_norm" },
	]));
});

test("buildMetricSelectOptions groups Project fields before Project Evaluation fields", () => {
	const { namespace } = loadReportScript();
	const catalogEntries = [
		{ id: "scorecard:integral_score", label: "Integral Score", source_kind: "scorecard_field" },
		{ id: "project:priority", label: "Priority", source_kind: "project_field" },
		{ id: "project:status", label: "Status", source_kind: "project_field" },
		{ id: "scorecard:status", label: "Status", source_kind: "scorecard_field" },
	];

	const options = namespace.buildMetricSelectOptions(catalogEntries, [
		"scorecard:integral_score",
		"project:priority",
		"project:status",
		"scorecard:status",
	]);

	assert.equal(JSON.stringify(options), JSON.stringify([
		{ label: "#Project", value: "" },
		{ value: "project:priority", label: "Priority" },
		{ value: "project:status", label: "Status" },
		{ label: "#Project Evaluation", value: "" },
		{ value: "scorecard:integral_score", label: "Integral Score" },
		{ value: "scorecard:status", label: "Status" },
	]));
});

test("buildGroupedMetricOptionIds matches grouped select option order without optgroup markers", () => {
	const { namespace } = loadReportScript();
	const catalogEntries = [
		{ id: "scorecard:integral_score", label: "Integral Score", source_kind: "scorecard_field" },
		{ id: "project:priority", label: "Priority", source_kind: "project_field" },
		{ id: "project:status", label: "Status", source_kind: "project_field" },
		{ id: "scorecard:status", label: "Status", source_kind: "scorecard_field" },
	];

	const optionIds = namespace.buildGroupedMetricOptionIds(catalogEntries);
	const selectOptions = namespace.buildMetricSelectOptions(catalogEntries, optionIds);
	const selectValues = selectOptions
		.filter((option) => option.value)
		.map((option) => option.value);

	assert.equal(JSON.stringify(selectValues), JSON.stringify(optionIds));
	assert.equal(JSON.stringify(optionIds), JSON.stringify([
		"project:priority",
		"project:status",
		"scorecard:integral_score",
		"scorecard:status",
	]));
});

test("buildMetricSelectOptions sorts labels inside each group using locale collator", () => {
	const { namespace } = loadReportScript();
	const catalogEntries = [
		{ id: "project:zebra", label: "Zebra", source_kind: "project_field" },
		{ id: "project:alpha", label: "Alpha", source_kind: "project_field" },
		{ id: "scorecard:beta", label: "Beta", source_kind: "scorecard_field" },
		{ id: "scorecard:gamma", label: "Gamma", source_kind: "scorecard_field" },
	];

	const options = namespace.buildMetricSelectOptions(catalogEntries, [
		"project:zebra",
		"project:alpha",
		"scorecard:beta",
		"scorecard:gamma",
	]);

	assert.equal(
		JSON.stringify(
			options
				.filter((option) => option.value?.startsWith("project:"))
				.map((option) => option.value)
		),
		JSON.stringify(["project:alpha", "project:zebra"])
	);
	assert.equal(
		JSON.stringify(
			options
				.filter((option) => option.value?.startsWith("scorecard:"))
				.map((option) => option.value)
		),
		JSON.stringify(["scorecard:beta", "scorecard:gamma"])
	);
});

test("buildMetricSelectOptions keeps plain labels for duplicate names in grouped select options", () => {
	const { namespace } = loadReportScript();
	const catalogEntries = [
		{ id: "project:status", label: "Status", source_kind: "project_field" },
		{ id: "scorecard:status", label: "Status", source_kind: "scorecard_field" },
	];

	const options = namespace.buildMetricSelectOptions(catalogEntries, [
		"project:status",
		"scorecard:status",
	]);

	assert.equal(JSON.stringify(options), JSON.stringify([
		{ label: "#Project", value: "" },
		{ value: "project:status", label: "Status" },
		{ label: "#Project Evaluation", value: "" },
		{ value: "scorecard:status", label: "Status" },
	]));
});

test("ensureMetricControlInstances creates make_control selects once", () => {
	const { namespace, state } = loadReportScript();
	const { mount } = createMetricControlsMount();
	const report = {};

	const first = namespace.ensureMetricControlInstances(report, mount);
	const second = namespace.ensureMetricControlInstances(report, mount);

	assert.equal(first, second);
	assert.equal(state.makeControlCalls.length, 4);
	assert.equal(Object.keys(report._dinextProjectScoringMetricControls).length, 4);
	assert.equal(first.x_axis.df.fieldtype, "Select");
	assert.equal(first.x_axis.df.label, "X Axis");
});

test("syncMetricControlValues uses catalog defaults on clean open when hidden filters are empty", () => {
	const { namespace } = loadReportScript();
	const emptyFilter = {
		value: "",
		df: { options: "project:priority\nproject:estimated_costing" },
		get_value() {
			return this.value;
		},
		set_value(value) {
			this.value = value;
		},
	};
	const report = {
		get_filter(fieldname) {
			return fieldname === "x_axis" ? emptyFilter : null;
		},
	};
	const controls = {
		x_axis: {
			df: { options: [] },
			_value: "",
			get_value() {
				return this._value;
			},
			set_value(value) {
				this._value = value;
			},
			refresh() {},
		},
	};
	const catalog = {
		axis: [
			{ id: "project:priority", label: "Priority" },
			{ id: "project:estimated_costing", label: "Estimated Cost" },
		],
		defaults: { x_axis: "project:estimated_costing" },
	};
	const currentConfig = { x_axis: "project:estimated_costing" };

	namespace.syncMetricControlValues(report, catalog, controls, currentConfig);

	assert.equal(controls.x_axis._value, "project:estimated_costing");
	assert.equal(emptyFilter.value, "project:estimated_costing");
});

test("syncMetricControlValues updates make_control options and values from hidden filters", () => {
	const { namespace } = loadReportScript();
	const filterState = {
		value: "risk_score_norm",
		df: { options: "integral_score\nrisk_score_norm" },
		get_value() {
			return this.value;
		},
		set_value(value) {
			this.value = value;
		},
	};
	const report = {
		get_filter(fieldname) {
			return fieldname === "x_axis" ? filterState : null;
		},
	};
	const controls = {
		x_axis: {
			df: { options: [] },
			_value: "integral_score",
			get_value() {
				return this._value;
			},
			set_value(value) {
				this._value = value;
			},
			refresh() {},
		},
	};

	namespace.syncMetricControlValues(
		report,
		{
			axis: [{ id: "integral_score", label: "Integral Score" }],
		},
		controls
	);

	assert.equal(controls.x_axis._value, "risk_score_norm");
	assert.equal(
		JSON.stringify(controls.x_axis.df.options),
		JSON.stringify([
			{ value: "integral_score", label: "Integral Score" },
			{ value: "risk_score_norm", label: "risk_score_norm" },
		])
	);
});

test("make_control change handler updates hidden filter and refreshes report", () => {
	const { namespace, state } = loadReportScript();
	const refreshCalls = [];
	const filterState = {
		value: "risk_score_norm",
		get_value() {
			return this.value;
		},
		set_value(value) {
			this.value = value;
		},
	};
	const report = {
		refresh(haveFiltersChanged) {
			refreshCalls.push(haveFiltersChanged);
		},
		get_filter(fieldname) {
			return fieldname === "x_axis" ? filterState : null;
		},
	};
	const { mount } = createMetricControlsMount();
	const controls = namespace.ensureMetricControlInstances(report, mount);

	controls.x_axis.set_value("integral_score");
	controls.x_axis.triggerChange();

	assert.equal(filterState.value, "integral_score");
	assert.deepEqual(refreshCalls, [true]);
	assert.equal(state.makeControlCalls.length, 4);
});

test("handleMetricControlChange waits for async set_value before refresh(true)", async () => {
	const { namespace } = loadReportScript();
	const refreshCalls = [];
	const events = [];
	const filterState = {
		value: "risk_score_norm",
		get_value() {
			return this.value;
		},
		set_value(value) {
			return Promise.resolve().then(() => {
				events.push("settled");
				this.value = value;
			});
		},
	};
	const report = {
		refresh(haveFiltersChanged) {
			events.push("refresh");
			refreshCalls.push(haveFiltersChanged);
		},
		get_filter(fieldname) {
			return fieldname === "x_axis" ? filterState : null;
		},
	};

	await namespace.handleMetricControlChange(report, "x_axis", "integral_score");

	assert.equal(filterState.value, "integral_score");
	assert.deepEqual(events, ["settled", "refresh"]);
	assert.deepEqual(refreshCalls, [true]);
});

test("handleMetricControlChange is no-op while syncing controls", () => {
	const { namespace } = loadReportScript();
	const refreshCalls = [];
	const report = {
		_dinextProjectScoringSyncingControls: true,
		refresh(haveFiltersChanged) {
			refreshCalls.push(haveFiltersChanged);
		},
		get_filter() {
			return {
				get_value() {
					return "risk_score_norm";
				},
				set_value() {
					throw new Error("should not set value during sync");
				},
			};
		},
	};

	namespace.handleMetricControlChange(report, "x_axis", "integral_score");

	assert.equal(refreshCalls.length, 0);
});

test("syncMetricControlValues does not trigger refresh loop during programmatic sync", () => {
	const { namespace } = loadReportScript();
	const refreshCalls = [];
	const filterState = {
		value: "integral_score",
		df: { options: "integral_score\nrisk_score_norm" },
		get_value() {
			return this.value;
		},
		set_value(value) {
			this.value = value;
		},
	};
	const report = {
		refresh() {
			refreshCalls.push(true);
		},
		get_filter(fieldname) {
			return fieldname === "x_axis" ? filterState : null;
		},
	};
	const controls = {
		x_axis: {
			df: { options: [] },
			_value: "integral_score",
			get_value() {
				return this._value;
			},
			set_value(value) {
				this._value = value;
			},
			refresh() {},
			triggerChange() {
				namespace.handleMetricControlChange(report, "x_axis", this.get_value());
			},
		},
	};

	namespace.syncMetricControlValues(report, { axis: [] }, controls);

	assert.equal(refreshCalls.length, 0);
	assert.notEqual(report._no_refresh, true);
});

test("handleMetricControlChange updates filter and refreshes report", () => {
	const { namespace } = loadReportScript();
	const refreshCalls = [];
	const filterState = {
		value: "risk_score_norm",
		get_value() {
			return this.value;
		},
		set_value(value) {
			this.value = value;
		},
	};
	const report = {
		refresh(haveFiltersChanged) {
			refreshCalls.push(haveFiltersChanged);
		},
		get_filter(fieldname) {
			return fieldname === "x_axis" ? filterState : null;
		},
	};

	namespace.handleMetricControlChange(report, "x_axis", "integral_score");

	assert.equal(filterState.value, "integral_score");
	assert.deepEqual(refreshCalls, [true]);
});

test("handleMetricControlChange is no-op when value is unchanged", () => {
	const { namespace } = loadReportScript();
	const refreshCalls = [];
	const report = {
		refresh() {
			refreshCalls.push(true);
		},
		get_filter() {
			return {
				get_value() {
					return "integral_score";
				},
				set_value() {
					throw new Error("should not set unchanged value");
				},
			};
		},
	};

	namespace.handleMetricControlChange(report, "x_axis", "integral_score");

	assert.equal(refreshCalls.length, 0);
});

test("buildChartOptions uses transparent chart background", () => {
	const { namespace } = loadReportScript();
	const points = [
		{
			x: { label: "Risk", value: 0.4, display: "0.4" },
			y: { label: "Score", value: 0.8, display: "0.8" },
			size: { normalized: 18 },
			color: { token: "gate-pass" },
		},
	];

	const options = namespace.buildChartOptions(points, { config: {} });

	assert.equal(options.backgroundColor, "transparent");
});

test("buildChartOptions keeps transparent background in dark theme", () => {
	const { context, namespace } = loadReportScript();
	context.document.documentElement.getAttribute = () => "dark";

	const points = [
		{
			x: { label: "Risk", value: 0.4, display: "0.4" },
			y: { label: "Score", value: 0.8, display: "0.8" },
			size: { normalized: 18 },
			color: { token: "gate-pass" },
		},
	];

	const options = namespace.buildChartOptions(points, { config: {} });

	assert.equal(namespace.getThemeName(), "dark");
	assert.equal(options.backgroundColor, "transparent");
});

test("buildChartOptions adds minimal toolbox with saveAsImage export", () => {
	const { namespace } = loadReportScript();
	const points = [
		{
			x: { label: "Risk", value: 0.4, display: "0.4" },
			y: { label: "Score", value: 0.8, display: "0.8" },
			size: { normalized: 18 },
			color: { token: "gate-pass" },
		},
	];

	const options = namespace.buildChartOptions(points, { config: {} });

	assert.ok(options.toolbox);
	assert.equal(options.toolbox.right, 8);
	assert.equal(options.toolbox.top, 4);
	assert.equal(options.toolbox.itemSize, 16);
	assert.ok(options.toolbox.feature.saveAsImage);
	assert.equal(options.toolbox.feature.saveAsImage.title, "Save as Image");
	assert.equal(options.toolbox.feature.saveAsImage.name, "project-scoring-report");
	assert.equal(options.toolbox.feature.saveAsImage.pixelRatio, 2);
	assert.equal(options.toolbox.feature.saveAsImage.backgroundColor, "#ffffff");
	assert.equal(options.backgroundColor, "transparent");
});

test("buildChartOptions toolbox saveAsImage uses theme card background when available", () => {
	const { context, namespace } = loadReportScript();
	context.getComputedStyle = () => ({
		getPropertyValue(name) {
			return name === "--card-bg" ? "#1b1c1f" : "";
		},
	});

	const points = [
		{
			x: { label: "Risk", value: 0.4, display: "0.4" },
			y: { label: "Score", value: 0.8, display: "0.8" },
			size: { normalized: 18 },
			color: { token: "gate-pass" },
		},
	];

	const options = namespace.buildChartOptions(points, { config: {} });

	assert.equal(options.toolbox.feature.saveAsImage.backgroundColor, "#1b1c1f");
});

test("getBubbleSizeLabel returns formatted display when size value is present", () => {
	const { namespace } = loadReportScript();
	const point = {
		size: {
			label: "Financial Value (Raw)",
			value: 150000,
			display: "150000.00",
			normalized: 24,
		},
	};

	assert.equal(namespace.getBubbleSizeLabel(point), "150000.00");
});

test("getBubbleSizeLabel returns empty string when size value is missing", () => {
	const { namespace } = loadReportScript();
	const point = {
		size: {
			label: "Financial Value (Raw)",
			value: null,
			display: "N/A",
			normalized: 6,
		},
	};

	assert.equal(namespace.getBubbleSizeLabel(point), "");
});

test("buildChartOptions series label formatter shows bubble size display for populated values", () => {
	const { namespace } = loadReportScript();
	const points = [
		{
			x: { label: "Risk", value: 0.4, display: "0.4" },
			y: { label: "Score", value: 0.8, display: "0.8" },
			size: { label: "Financial Value (Raw)", value: 150000, display: "150000.00", normalized: 24 },
			color: { token: "gate-pass" },
		},
	];

	const options = namespace.buildChartOptions(points, { config: {} });
	const labelFormatter = options.series[0].label.formatter;

	assert.equal(labelFormatter({ data: { point: points[0] } }), "150000.00");
	assert.equal(options.series[0].label.show, true);
	assert.equal(options.series[0].label.position, "top");
	assert.equal(options.series[0].label.hideOverlap, true);
});

test("buildChartOptions series label formatter hides label when bubble size is missing", () => {
	const { namespace } = loadReportScript();
	const point = {
		x: { label: "Risk", value: 0.4, display: "0.4" },
		y: { label: "Score", value: 0.8, display: "0.8" },
		size: { label: "Financial Value (Raw)", value: null, display: "N/A", normalized: 6 },
		color: { token: "gate-pass" },
	};
	const points = [point];

	const options = namespace.buildChartOptions(points, { config: {} });
	const labelFormatter = options.series[0].label.formatter;

	assert.equal(labelFormatter({ data: { point } }), "");
});

test("buildChartOptions series label uses theme text color in dark theme", () => {
	const { context, namespace } = loadReportScript();
	context.document.documentElement.getAttribute = () => "dark";
	context.getComputedStyle = () => ({
		getPropertyValue(name) {
			return name === "--text-color" ? "#e4e4e7" : "";
		},
	});

	const points = [
		{
			x: { label: "Risk", value: 0.4, display: "0.4" },
			y: { label: "Score", value: 0.8, display: "0.8" },
			size: { label: "Financial Value (Raw)", value: 150000, display: "150000.00", normalized: 24 },
			color: { token: "gate-pass" },
		},
	];

	const options = namespace.buildChartOptions(points, { config: {} });

	assert.equal(options.series[0].label.color, "#e4e4e7");
});

test("normalizeReportPayload converts legacy bubble_payload into custom message payload", () => {
	const { namespace } = loadReportScript();
	const report = {
		raw_data: {
			result: [{ project: "PRJ-001" }],
			chart: {
				bubble_payload: [
					{
						project: "PRJ-001",
						label: "Alpha",
						x: 0.4,
						y: 0.8,
						size: 12,
						color_token: "gate-pass",
					},
				],
			},
		},
	};

	const payload = namespace.normalizeReportPayload(report);

	assert.equal(payload.bubble_chart.points.length, 1);
	assert.equal(payload.bubble_chart.points[0].x.value, 0.4);
	assert.equal(payload.bubble_chart.points[0].color.token, "gate-pass");
	assert.equal(payload.summary.plotted_points, 1);
});

test("openScorecard routes to Project Scorecard form", () => {
	const { namespace, state } = loadReportScript();

	namespace.openScorecard("PSC-001");

	assert.deepEqual(state.setRouteCalls, [["Form", "Project Scorecard", "PSC-001"]]);
});

test("openScorecard ignores empty scorecard name", () => {
	const { namespace, state } = loadReportScript();

	namespace.openScorecard("");
	namespace.openScorecard(null);

	assert.equal(state.setRouteCalls.length, 0);
});

test("openProject routes to Project form", () => {
	const { namespace, state } = loadReportScript();

	namespace.openProject("PRJ-001");

	assert.deepEqual(state.setRouteCalls, [["Form", "Project", "PRJ-001"]]);
});

test("openProject ignores empty project name", () => {
	const { namespace, state } = loadReportScript();

	namespace.openProject("");
	namespace.openProject(null);

	assert.equal(state.setRouteCalls.length, 0);
});

test("handleBubbleChartClick opens linked scorecard from bubble payload", () => {
	const { namespace, state } = loadReportScript();

	namespace.handleBubbleChartClick({
		data: {
			point: {
				project: "PRJ-001",
				scorecard: "PSC-042",
			},
		},
	});

	assert.deepEqual(state.setRouteCalls, [["Form", "Project Scorecard", "PSC-042"]]);
});

test("handleBubbleChartClick opens project form when bubble has no scorecard", () => {
	const { namespace, state } = loadReportScript();

	namespace.handleBubbleChartClick({
		data: {
			point: {
				project: "PRJ-001",
				scorecard: null,
			},
		},
	});

	assert.deepEqual(state.setRouteCalls, [["Form", "Project", "PRJ-001"]]);
});

test("handleBubbleChartClick is no-op when bubble has neither scorecard nor project", () => {
	const { namespace, state } = loadReportScript();

	namespace.handleBubbleChartClick({
		data: {
			point: {
				project: null,
				scorecard: null,
			},
		},
	});

	assert.equal(state.setRouteCalls.length, 0);
});

test("syncBubbleNavContext stores size metric source kind on report", () => {
	const { namespace } = loadReportScript();
	const report = {};

	namespace.syncBubbleNavContext(report, {
		metric_catalog: {
			size: [{ id: "project:percent_complete", source_kind: "project_field" }],
		},
		bubble_chart: {
			config: { size_metric: "project:percent_complete" },
		},
	});

	assert.equal(report._dinextProjectScoringBubbleNavContext.size_metric, "project:percent_complete");
	assert.equal(report._dinextProjectScoringBubbleNavContext.size_source_kind, "project_field");
});

test("handleBubbleChartClick opens project when bubble size metric is a project field", () => {
	const { namespace, state } = loadReportScript();
	const report = {};

	namespace.syncBubbleNavContext(report, {
		metric_catalog: {
			size: [{ id: "project:percent_complete", source_kind: "project_field" }],
		},
		bubble_chart: {
			config: { size_metric: "project:percent_complete" },
		},
	});

	namespace.handleBubbleChartClick(
		{
			data: {
				point: {
					project: "PRJ-001",
					scorecard: "PSC-042",
				},
			},
		},
		report
	);

	assert.deepEqual(state.setRouteCalls, [["Form", "Project", "PRJ-001"]]);
});

test("handleBubbleChartClick keeps scorecard-first routing for scorecard size metric", () => {
	const { namespace, state } = loadReportScript();
	const report = {};

	namespace.syncBubbleNavContext(report, {
		metric_catalog: {
			size: [{ id: "scorecard:integral_score", source_kind: "scorecard_field" }],
		},
		bubble_chart: {
			config: { size_metric: "scorecard:integral_score" },
		},
	});

	namespace.handleBubbleChartClick(
		{
			data: {
				point: {
					project: "PRJ-001",
					scorecard: "PSC-042",
				},
			},
		},
		report
	);

	assert.deepEqual(state.setRouteCalls, [["Form", "Project Scorecard", "PSC-042"]]);
});

test("handleBubbleChartClick keeps scorecard-first routing for criterion size metric", () => {
	const { namespace, state } = loadReportScript();
	const report = {};

	namespace.syncBubbleNavContext(report, {
		metric_catalog: {
			size: [
				{
					id: "criterion:number:normalized:RISK_IMP",
					source_kind: "criterion_normalized",
				},
			],
		},
		bubble_chart: {
			config: { size_metric: "criterion:number:normalized:RISK_IMP" },
		},
	});

	namespace.handleBubbleChartClick(
		{
			data: {
				point: {
					project: "PRJ-001",
					scorecard: "PSC-042",
				},
			},
		},
		report
	);

	assert.deepEqual(state.setRouteCalls, [["Form", "Project Scorecard", "PSC-042"]]);
});

test("bindBubbleChartNavigation registers click handler without duplicate routes", () => {
	const { namespace, state } = loadReportScript();
	const handlers = {};
	const chart = {
		off(event) {
			delete handlers[event];
		},
		on(event, handler) {
			handlers[event] = handler;
		},
	};

	namespace.bindBubbleChartNavigation(chart);
	assert.equal(typeof handlers.click, "function");

	handlers.click({
		data: {
			point: {
				scorecard: "PSC-007",
			},
		},
	});
	assert.deepEqual(state.setRouteCalls, [["Form", "Project Scorecard", "PSC-007"]]);

	state.setRouteCalls.length = 0;
	namespace.bindBubbleChartNavigation(chart);
	handlers.click({
		data: {
			point: {
				scorecard: "PSC-008",
			},
		},
	});
	assert.deepEqual(state.setRouteCalls, [["Form", "Project Scorecard", "PSC-008"]]);
});

test("buildUniqueColorMap assigns distinct colors for distinct identities", () => {
	const { namespace } = loadReportScript();
	const identities = [
		"project:customer:CUST-001",
		"project:customer:CUST-002",
		"project:customer:CUST-003",
		"project:customer:CUST-004",
		"project:customer:CUST-005",
		"project:customer:CUST-006",
	];
	const colorMap = namespace.buildUniqueColorMap(identities);
	const colors = identities.map((identity) => colorMap[identity]);

	assert.equal(new Set(colors).size, identities.length);
});

test("buildUniqueColorMap assigns distinct colors for 24 identities in dark theme", () => {
	const { context, namespace } = loadReportScript();
	context.document.documentElement.getAttribute = () => "dark";
	const identities = Array.from({ length: 24 }, (_, index) => `project:customer:CUST-${index}`);
	const colorMap = namespace.buildUniqueColorMap(identities);
	const colors = identities.map((identity) => colorMap[identity]);

	assert.equal(new Set(colors).size, identities.length);
});

test("resolveColor uses the same generated color for legend item and point", () => {
	const { namespace } = loadReportScript();
	const identities = ["project:customer:CUST-001", "project:customer:CUST-002"];
	const colorMap = namespace.buildUniqueColorMap(identities);
	const legendItem = { color_key: "project:customer:CUST-001", token: "project:customer:CUST-001" };
	const pointColor = { color_key: "project:customer:CUST-001", token: "project:customer:CUST-001" };

	assert.equal(namespace.resolveColor(legendItem, colorMap), namespace.resolveColor(pointColor, colorMap));
});

test("resolveColor prefers color_key over token when both are present", () => {
	const { namespace } = loadReportScript();
	const colorMap = namespace.buildUniqueColorMap(["project:customer:CUST-001"]);

	assert.equal(
		namespace.resolveColor(
			{ color_key: "project:customer:CUST-001", token: "project:customer:legacy-token" },
			colorMap
		),
		colorMap["project:customer:CUST-001"]
	);
});

test("resolveColor regenerates theme-specific colors while keeping one identity per color", () => {
	const { context, namespace } = loadReportScript();
	const identities = ["project:customer:CUST-001", "project:customer:CUST-002"];
	const lightMap = namespace.buildUniqueColorMap(identities);

	context.document.documentElement.getAttribute = () => "dark";
	const darkMap = namespace.buildUniqueColorMap(identities);

	assert.notEqual(lightMap[identities[0]], darkMap[identities[0]]);
	assert.equal(new Set(Object.values(lightMap)).size, identities.length);
	assert.equal(new Set(Object.values(darkMap)).size, identities.length);
});

test("resolveColor honors semantic palette overrides", () => {
	const { namespace } = loadReportScript();

	assert.equal(namespace.resolveColor("gate-pass"), "#739b7f");
	assert.equal(namespace.resolveColor("gate-fail"), "#c08b8b");
});

test("filterPointsByHiddenLegend excludes points with hidden color identities", () => {
	const { namespace } = loadReportScript();
	const report = {};
	const points = [
		{ color: { color_key: "gate-pass", token: "gate-pass" } },
		{ color: { color_key: "gate-fail", token: "gate-fail" } },
		{ color: { color_key: "gate-unknown", token: "gate-unknown" } },
	];

	namespace.toggleHiddenLegendColorKey(report, "gate-fail");

	assert.equal(namespace.filterPointsByHiddenLegend(report, points).length, 2);
	assert.equal(
		namespace.filterPointsByHiddenLegend(report, points)[0].color.color_key,
		"gate-pass"
	);
});

test("toggleHiddenLegendColorKey toggles hidden state for legend identity", () => {
	const { namespace } = loadReportScript();
	const report = {};

	namespace.toggleHiddenLegendColorKey(report, "project:priority:High");
	assert.ok(namespace.getHiddenLegendColorKeys(report).has("project:priority:High"));

	namespace.toggleHiddenLegendColorKey(report, "project:priority:High");
	assert.equal(namespace.getHiddenLegendColorKeys(report).has("project:priority:High"), false);
});

test("resetHiddenLegendColorKeys clears hidden legend state", () => {
	const { namespace } = loadReportScript();
	const report = {};

	namespace.toggleHiddenLegendColorKey(report, "gate-pass");
	namespace.toggleHiddenLegendColorKey(report, "gate-fail");
	namespace.resetHiddenLegendColorKeys(report);

	assert.equal(namespace.getHiddenLegendColorKeys(report).size, 0);
});

test("renderLegend renders interactive legend items with color keys and hidden state", () => {
	const { namespace } = loadReportScript();
	const legendDom = { innerHTML: "" };
	const colorMap = namespace.buildUniqueColorMap(["gate-pass", "gate-fail"]);
	const hiddenKeys = new Set(["gate-fail"]);

	namespace.renderLegend(
		legendDom,
		{
			items: [
				{ color_key: "gate-pass", token: "gate-pass", label: "Pass" },
				{ color_key: "gate-fail", token: "gate-fail", label: "Fail" },
			],
		},
		colorMap,
		hiddenKeys
	);

	assert.match(legendDom.innerHTML, /data-color-key="gate-pass"/);
	assert.match(legendDom.innerHTML, /data-color-key="gate-fail"/);
	assert.match(legendDom.innerHTML, /project-scoring-report-legend-item is-hidden/);
	assert.match(legendDom.innerHTML, /aria-pressed="false"/);
	assert.match(legendDom.innerHTML, /<button type="button"/);
});

test("ensureLegendClickHandler toggles legend visibility through handleLegendItemClick", () => {
	const { namespace } = loadReportScript();
	const { mount, legendDom, chartDom, emptyDom } = createLegendToggleMount();
	const report = {
		page: {
			main: {
				find(selector) {
					if (selector === ".project-scoring-report-shell") {
						return mount;
					}
					return { length: 0 };
				},
			},
		},
		raw_data: {
			message: {
				summary: { notice: null },
				bubble_chart: {
					config: {},
					axes: {
						x: { axis_type: "value", label: "X" },
						y: { axis_type: "value", label: "Y" },
					},
					legend: {
						items: [
							{ color_key: "gate-pass", token: "gate-pass", label: "Pass" },
							{ color_key: "gate-fail", token: "gate-fail", label: "Fail" },
						],
					},
					points: [
						{
							x: { label: "Risk", value: 0.4, display: "0.4" },
							y: { label: "Score", value: 0.8, display: "0.8" },
							size: { normalized: 18 },
							color: { color_key: "gate-pass", token: "gate-pass", label: "Pass" },
						},
						{
							x: { label: "Risk", value: 0.2, display: "0.2" },
							y: { label: "Score", value: 0.5, display: "0.5" },
							size: { normalized: 18 },
							color: { color_key: "gate-fail", token: "gate-fail", label: "Fail" },
						},
					],
				},
			},
		},
	};
	const setOptionCalls = [];
	const chart = {
		setOption(options, replace) {
			setOptionCalls.push({ options, replace });
		},
		resize() {},
	};
	chartDom._dinextProjectScoringChart = chart;

	namespace.ensureLegendClickHandler(report, legendDom);
	namespace.renderLegend(
		legendDom,
		report.raw_data.message.bubble_chart.legend,
		namespace.buildUniqueColorMap(["gate-pass", "gate-fail"]),
		namespace.getHiddenLegendColorKeys(report)
	);

	const passButton = {
		getAttribute(name) {
			return name === "data-color-key" ? "gate-pass" : null;
		},
	};
	namespace.handleLegendItemClick(report, passButton.getAttribute("data-color-key"));

	assert.ok(namespace.getHiddenLegendColorKeys(report).has("gate-pass"));
	assert.equal(setOptionCalls.length, 1);
	assert.equal(setOptionCalls[0].options.series[0].data.length, 1);
	assert.equal(setOptionCalls[0].options.series[0].data[0].point.color.color_key, "gate-fail");
	assert.match(legendDom.innerHTML, /project-scoring-report-legend-item is-hidden/);
	assert.equal(emptyDom.classList.contains("is-visible"), false);
});

test("updateLegendChartView shows empty state when all legend categories are hidden", () => {
	const { namespace } = loadReportScript();
	const report = {};
	const message = {
		summary: { notice: null },
		bubble_chart: {
			config: {},
			axes: {
				x: { axis_type: "value", label: "X" },
				y: { axis_type: "value", label: "Y" },
			},
			legend: {
				items: [{ color_key: "gate-pass", token: "gate-pass", label: "Pass" }],
			},
			points: [
				{
					x: { label: "Risk", value: 0.4, display: "0.4" },
					y: { label: "Score", value: 0.8, display: "0.8" },
					size: { normalized: 18 },
					color: { color_key: "gate-pass", token: "gate-pass", label: "Pass" },
				},
			],
		},
	};
	const { mount, chartDom, emptyDom } = createLegendToggleMount();
	const disposeCalls = [];
	chartDom._dinextProjectScoringChart = {
		dispose() {
			disposeCalls.push(true);
		},
	};

	namespace.toggleHiddenLegendColorKey(report, "gate-pass");
	namespace.updateLegendChartView(report, mount, message);

	assert.equal(disposeCalls.length, 1);
	assert.equal(emptyDom.textContent, "All legend categories are hidden.");
	assert.equal(emptyDom.classList.contains("is-visible"), true);
	assert.equal(chartDom.innerHTML, "");
});

test("wrapReportRefresh resets hidden legend state before render", async () => {
	const { namespace } = loadReportScript();
	const renderCalls = [];
	const report = {
		report_name: "Project Scoring Report",
		refresh() {
			return Promise.resolve();
		},
	};
	namespace.wrapReportRefresh(report);
	namespace.toggleHiddenLegendColorKey(report, "gate-pass");
	namespace.render = async () => {
		renderCalls.push(Array.from(namespace.getHiddenLegendColorKeys(report)));
	};

	await report.refresh();

	assert.deepEqual(renderCalls, [[]]);
});

function createLegendToggleMount() {
	const legendDom = {
		innerHTML: "",
		_dinextProjectScoringLegendBound: false,
		addEventListener(event, handler) {
			this._clickHandler = handler;
		},
	};
	const chartDom = {
		innerHTML: "chart",
		_dinextProjectScoringChart: null,
	};
	const emptyDom = {
		textContent: "",
		classList: {
			classes: new Set(),
			add(name) {
				this.classes.add(name);
			},
			remove(name) {
				this.classes.delete(name);
			},
			contains(name) {
				return this.classes.has(name);
			},
		},
	};
	const mount = {
		length: 1,
		find(selector) {
			if (selector === ".project-scoring-report-legend") {
				return { length: 1, get: jqueryGet([legendDom]) };
			}
			if (selector === ".project-scoring-report-chart") {
				return { length: 1, get: jqueryGet([chartDom]) };
			}
			if (selector === ".project-scoring-report-empty-state") {
				return { length: 1, get: jqueryGet([emptyDom]) };
			}
			return { length: 0, get: jqueryGet([]) };
		},
	};
	return { mount, legendDom, chartDom, emptyDom };
}

