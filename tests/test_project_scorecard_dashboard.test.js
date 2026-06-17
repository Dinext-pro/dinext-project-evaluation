const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/dinext_project_evaluation/doctype/project_scorecard/project_scorecard.js";

function loadProjectScorecardScript() {
	const script = fs.readFileSync(SCRIPT_PATH, "utf8");
	const state = { handlers: {} };
	const translations = {
		"{0} normalized score {1} is below required {2}":
			"{0}: нормализованный балл {1} ниже требуемого значения {2}.",
		"{0} raw value {1} is below required {2}":
			"{0}: исходное значение {1} ниже требуемого значения {2}.",
		"{0} raw value {1} is above allowed {2}":
			"{0}: исходное значение {1} выше допустимого значения {2}.",
		"Missing mandatory value for {0}": "Отсутствует обязательное значение для {0}.",
	};
	const context = {
		__(value, args = []) {
			const template = translations[value] || value;
			if (!Array.isArray(args)) {
				return template;
			}
			return args.reduce(
				(result, arg, index) => result.replace(`{${index}}`, arg),
				template
			);
		},
		cint(value) {
			return Number.parseInt(value, 10) || 0;
		},
		console,
		flt(value, precision) {
			const numeric = Number.parseFloat(value);
			return Number.isFinite(numeric) && typeof precision === "number"
				? Number(numeric.toFixed(precision))
				: numeric;
		},
		frappe: {
			call() {
				return Promise.resolve({ message: [] });
			},
			datetime: {
				str_to_user(value) {
					return value;
				},
			},
			db: {
				get_value() {
					return Promise.resolve({ message: {} });
				},
				get_list() {
					return Promise.resolve([]);
				},
			},
			dom: {
				freeze() {},
				unfreeze() {},
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
			show_alert() {},
			ui: {
				form: {
					check_mandatory() {
						return true;
					},
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
		$: () => ({
			addClass() {},
		}),
	};

	vm.runInNewContext(script, context);
	return context.dinext_project_evaluation.project_scorecard;
}

test("parse_gate_messages localizes legacy english raw-value warnings", () => {
	const namespace = loadProjectScorecardScript();
	const messages = Array.from(
		namespace.parse_gate_messages(
			"Вероятность успешного завершения работ raw value 45.0000 is below required 50.0000"
		)
	);

	assert.deepEqual(messages, [
		"Вероятность успешного завершения работ: исходное значение 45.0000 ниже требуемого значения 50.0000.",
	]);
});

test("parse_gate_messages localizes legacy missing mandatory warnings", () => {
	const namespace = loadProjectScorecardScript();
	const messages = Array.from(namespace.parse_gate_messages("Missing mandatory value for Strategic Alignment"));

	assert.deepEqual(messages, ["Отсутствует обязательное значение для Strategic Alignment."]);
});
