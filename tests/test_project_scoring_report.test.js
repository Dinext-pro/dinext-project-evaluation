const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const REPORT_SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/dinext_project_evaluation/report/project_scoring_report/project_scoring_report.js";

function loadReportScript() {
	const script = fs.readFileSync(REPORT_SCRIPT_PATH, "utf8");
	const state = {
		requiredAssets: [],
		windowListeners: {},
		setRouteCalls: [],
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
		$: () => ({
			length: 0,
			remove() {},
			prependTo() {
				return {
					length: 1,
					get() {
						return [{ innerHTML: "" }];
					},
				};
			},
			find() {
				return { length: 0, remove() {} };
			},
			get() {
				return [{ innerHTML: "" }];
			},
		}),
	};

	vm.runInNewContext(script, context);

	return {
		context,
		state,
		report: context.frappe.query_reports["Project Scoring Report"],
		namespace: context.dinext_project_evaluation.project_scoring_report,
	};
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

test("ensureChartMount shell omits bubble chart header and metric summary", () => {
	const { namespace } = loadReportScript();
	const script = fs.readFileSync(REPORT_SCRIPT_PATH, "utf8");

	assert.doesNotMatch(script, /project-scoring-report-card-head/);
	assert.doesNotMatch(script, /project-scoring-report-summary/);
	assert.doesNotMatch(script, /renderSummary/);
	assert.match(script, /project-scoring-report-legend/);
	assert.match(script, /project-scoring-report-chart/);
	assert.match(script, /project-scoring-report-empty-state/);
	assert.equal(typeof namespace.renderLegend, "function");
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

test("handleBubbleChartClick is no-op when bubble has no scorecard", () => {
	const { namespace, state } = loadReportScript();

	namespace.handleBubbleChartClick({
		data: {
			point: {
				project: "PRJ-001",
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

