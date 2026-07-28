const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/dinext_project_evaluation/doctype/project_scoring_profile/project_scoring_profile.js";

function loadProjectScoringProfileScript() {
	const script = fs.readFileSync(SCRIPT_PATH, "utf8");
	const state = { handlers: {} };
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
			if (typeof value === "number") {
				return value;
			}
			return Number.parseFloat(String(value).trim());
		},
		frappe: {
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
					on(doctype, handlers) {
						state.handlers[doctype] = handlers;
					},
				},
			},
		},
		dinext_project_evaluation: {},
		locals: {},
	};

	vm.runInNewContext(script, context);
	return context.dinext_project_evaluation.project_scoring_profile;
}

test("get_gate_field_mode enables raw thresholds only for mandatory numeric criteria", () => {
	const namespace = loadProjectScoringProfileScript();

	assert.deepEqual(JSON.parse(JSON.stringify(namespace.get_gate_field_mode("Mandatory", "Number"))), {
		minimum_normalized_score: true,
		minimum_raw_value: true,
		maximum_raw_value: true,
	});
	assert.deepEqual(JSON.parse(JSON.stringify(namespace.get_gate_field_mode("Mandatory", "Scale"))), {
		minimum_normalized_score: true,
		minimum_raw_value: false,
		maximum_raw_value: false,
	});
	assert.deepEqual(JSON.parse(JSON.stringify(namespace.get_gate_field_mode("Desired", "Number"))), {
		minimum_normalized_score: false,
		minimum_raw_value: false,
		maximum_raw_value: false,
	});
});

test("validate_row_gate_values reports criterion-specific numeric errors", () => {
	const namespace = loadProjectScoringProfileScript();
	const errors = Array.from(
		namespace.validate_row_gate_values(
		{
			criterion: "REG",
			requirement_level: "Mandatory",
			minimum_normalized_score: "abc",
			minimum_raw_value: "5",
			maximum_raw_value: "",
		},
		"Scale"
		)
	);

	assert.deepEqual(errors, ["Criterion REG: Minimum Normalized Score must be numeric."]);
});

test("normalize_row_gate_values clears raw thresholds for non-numeric mandatory criteria", () => {
	const namespace = loadProjectScoringProfileScript();
	const row = {
		requirement_level: "Mandatory",
		minimum_normalized_score: " 0.4 ",
		minimum_raw_value: "3",
		maximum_raw_value: "5",
	};

	namespace.normalize_row_gate_values(row, "Scale");

	assert.deepEqual(row, {
		requirement_level: "Mandatory",
		minimum_normalized_score: "0.4",
		minimum_raw_value: null,
		maximum_raw_value: null,
	});
});
