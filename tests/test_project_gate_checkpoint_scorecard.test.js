const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/public/js/project_gate_checkpoint_scorecard.js";

function loadCheckpointScript() {
	const script = fs.readFileSync(SCRIPT_PATH, "utf8");
	const state = {
		handlers: {},
		routeCalls: [],
	};
	const context = {
		__(value, args = []) {
			if (!Array.isArray(args)) {
				return value;
			}
			return args.reduce((result, arg, index) => result.replace(`{${index}}`, arg), value);
		},
		cint(value) {
			return Number.parseInt(value, 10) || 0;
		},
		console,
		flt(value) {
			return Number.parseFloat(value);
		},
		frappe: {
			get_indicator() {
				return null;
			},
			model: {
				with_doctype() {
					return Promise.resolve();
				},
			},
			provide(path) {
				const segments = path.split(".");
				let pointer = context;
				for (const segment of segments) {
					pointer[segment] = pointer[segment] || {};
					pointer = pointer[segment];
				}
			},
			require(_files, callback) {
				callback();
			},
			set_route(...args) {
				state.routeCalls.push(args);
			},
			ui: {
				form: {
					on(doctype, handlers) {
						state.handlers[doctype] = handlers;
					},
				},
			},
			utils: {
				escape_html(value) {
					return String(value);
				},
			},
		},
		dinext_project_evaluation: {},
		$: (value) => value,
	};

	vm.runInNewContext(script, context);
	return {
		namespace: context.dinext_project_evaluation.stage_gate_checkpoint,
		state,
	};
}

test("format_gate_warning falls back to translated threshold warning for failed linked scorecard", () => {
	const { namespace } = loadCheckpointScript();
	const message = namespace.format_gate_warning({
		doc: {
			linked_stage_scorecard: "PSC-001",
			scorecard_gate_warning: "",
			scorecard_gate_pass: 0,
		},
	});

	assert.equal(message, "Scorecard gate thresholds were not met.");
});

test("parse_gate_messages localizes legacy english gate warnings", () => {
	const { namespace } = loadCheckpointScript();
	const messages = Array.from(
		namespace.parse_gate_messages(
			"Вероятность успешного завершения работ raw value 45.0000 is below required 50.0000"
		)
	);

	assert.deepEqual(messages, [
		"Вероятность успешного завершения работ: исходное значение 45.0000 ниже требуемого значения 50.0000.",
	]);
});

test("build_scorecard_widget_html includes linked scorecard navigation label", () => {
	const { namespace } = loadCheckpointScript();
	const html = namespace.build_scorecard_widget_html({
		doc: {
			linked_stage_scorecard: "PSC-001",
			scorecard_integral_score: 3.4,
			scorecard_gate_pass: 1,
			scorecard_gate_warning: "",
			scorecard_status: "Approved",
		},
	});

	assert.match(html, /Open linked Project Scorecard PSC-001/);
	assert.match(html, /Approved/);
	assert.match(html, /Integral Score/);
});

test("open_linked_scorecard routes to Project Scorecard form", () => {
	const { namespace, state } = loadCheckpointScript();

	namespace.open_linked_scorecard("PSC-009");

	assert.deepEqual(state.routeCalls, [["Form", "Project Scorecard", "PSC-009"]]);
});
