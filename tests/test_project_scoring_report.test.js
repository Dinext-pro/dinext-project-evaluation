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

