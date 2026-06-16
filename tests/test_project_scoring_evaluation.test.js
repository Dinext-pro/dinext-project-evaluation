const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const SCRIPT_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/public/js/project_scoring_evaluation.js";

function loadProjectScoringScript() {
	const script = fs.readFileSync(SCRIPT_PATH, "utf8");
	const state = {
		confirmCalls: [],
		handlers: {},
		routeCalls: [],
	};
	const context = {
		__(value) {
			return value;
		},
		console,
		frappe: {
			confirm(message, onYes, onNo) {
				state.confirmCalls.push({ message, onYes, onNo });
			},
			provide(path) {
				const segments = path.split(".");
				let pointer = context;
				for (const segment of segments) {
					pointer[segment] = pointer[segment] || {};
					pointer = pointer[segment];
				}
			},
			route_options: null,
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
		},
		dinext_project_evaluation: {},
	};

	vm.runInNewContext(script, context);

	return {
		context,
		namespace: context.dinext_project_evaluation.project_scoring,
		projectHandlers: state.handlers.Project,
		state,
	};
}

test("build_profile_filters applies active, portfolio, company and project type filters", () => {
	const { namespace } = loadProjectScoringScript();
	const filters = namespace.build_profile_filters({
		doc: {
			custom_project_portfolio: "PORT-001",
			company: "DINEXT",
			project_type: "R&D",
		},
	});

	assert.deepEqual(JSON.parse(JSON.stringify(filters)), {
		status: "Active",
		portfolio: ["in", ["PORT-001", ""]],
		company: ["in", ["DINEXT", ""]],
		project_type: ["in", ["R&D", ""]],
	});
});

test("on_profile_change reverts profile when user cancels confirmation", async () => {
	const { namespace, state } = loadProjectScoringScript();
	const setValueCalls = [];
	const frm = {
		doc: { custom_project_scoring_profile: "PROFILE-NEW" },
		_dpe_prev_scoring_profile: "PROFILE-OLD",
		_dpe_suppress_profile_confirm: false,
		is_new() {
			return false;
		},
		set_value(fieldname, value) {
			setValueCalls.push([fieldname, value]);
			return Promise.resolve();
		},
	};

	namespace.on_profile_change(frm);
	assert.equal(state.confirmCalls.length, 1);

	await state.confirmCalls[0].onNo();

	assert.deepEqual(setValueCalls, [["custom_project_scoring_profile", "PROFILE-OLD"]]);
	assert.equal(frm._dpe_prev_scoring_profile, "PROFILE-OLD");
});

test("refresh adds scorecard and report buttons in Evaluation group", () => {
	const { projectHandlers, state, context } = loadProjectScoringScript();
	const buttons = [];
	const frm = {
		doc: {
			name: "PRJ-001",
			custom_project_scoring_profile: "PROFILE-001",
			custom_project_portfolio: "PORT-001",
		},
		_dpe_prev_scoring_profile: null,
		_dpe_prev_governance_model: null,
		is_new() {
			return false;
		},
		add_custom_button(label, handler, group) {
			buttons.push({ label, handler, group });
		},
		fields_dict: { custom_project_scoring_profile: {} },
		toggle_display() {},
		toggle_enable() {},
		set_query() {},
	};

	// `refresh` internally calls `setup_profile_field` and `refresh`.
	projectHandlers.refresh(frm);

	assert.deepEqual(
		buttons.map(({ label, group }) => ({ label, group })),
		[
			{ label: "Open Scorecards", group: "Evaluation" },
			{ label: "Open Scoring Report", group: "Evaluation" },
		]
	);

	buttons[1].handler();
	assert.deepEqual(state.routeCalls, [["query-report", "Project Scoring Report"]]);
	assert.deepEqual(JSON.parse(JSON.stringify(context.frappe.route_options)), {
		project_portfolio: "PORT-001",
		project: ["PRJ-001"],
	});
});
