const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const REPORT_SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/dinext_project_evaluation/report/project_scoring_report/project_scoring_report.js";

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
		namespace.getMetricControlOptionIds({ df: { options: "a\nb" } }, ["c"]).join(","),
		"a,b"
	);
	assert.equal(namespace.getMetricControlOptionIds(null, ["c", "d"]).join(","), "c,d");
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

