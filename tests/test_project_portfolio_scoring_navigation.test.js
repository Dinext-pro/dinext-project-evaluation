const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const HOOKS_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/hooks.py";
const CLIENT_SCRIPT_FIXTURE_PATH =
	"/home/frappe/frappe-bench/apps/dinext_project_evaluation/dinext_project_evaluation/fixtures/client_script.json";

function loadPortfolioScript() {
	assert.ok(
		fs.existsSync(CLIENT_SCRIPT_FIXTURE_PATH),
		"Expected Project Portfolio Client Script fixture to exist"
	);

	const scripts = JSON.parse(fs.readFileSync(CLIENT_SCRIPT_FIXTURE_PATH, "utf8"));
	const clientScript = scripts.find((scriptDoc) => scriptDoc.dt === "Project Portfolio");
	assert.ok(clientScript, "Expected Project Portfolio Client Script fixture");

	const script = clientScript.script;
	const state = {
		handlers: {},
		setRouteCalls: [],
	};

	const context = {
		__(value) {
			return value;
		},
		console,
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
			set_route(...args) {
				state.setRouteCalls.push(args);
			},
			route_options: null,
		},
	};

	vm.runInNewContext(script, context);

	return {
		state,
		refreshHandler: state.handlers["Project Portfolio"]?.refresh,
		context,
	};
}

function makeFormDoc({ name = "PORT-001", isNew = false } = {}) {
	const addedButtons = [];
	return {
		doc: { name },
		is_new() {
			return isNew;
		},
		add_custom_button(label, handler, group) {
			addedButtons.push({ label, handler, group });
		},
		getAddedButtons() {
			return addedButtons;
		},
	};
}

test("saved Project Portfolio form adds Project Scoring Report in View group only", () => {
	const { refreshHandler } = loadPortfolioScript();
	assert.equal(typeof refreshHandler, "function");

	const frm = makeFormDoc();
	refreshHandler(frm);

	assert.deepEqual(frm.getAddedButtons().map(({ label, group }) => ({ label, group })), [
		{ label: "Project Scoring Report", group: "View" },
	]);
});

test("unsaved Project Portfolio form does not add scoring report button", () => {
	const { refreshHandler } = loadPortfolioScript();
	const frm = makeFormDoc({ name: null, isNew: true });

	refreshHandler(frm);

	assert.equal(frm.getAddedButtons().length, 0);
});

test("scoring report button routes to query report with portfolio filter", () => {
	const { refreshHandler, state, context } = loadPortfolioScript();
	const frm = makeFormDoc({ name: "Портфель 2026" });

	refreshHandler(frm);

	const [button] = frm.getAddedButtons();
	assert.ok(button, "Expected Project Scoring Report button to be registered");

	button.handler();

	assert.equal(context.frappe.route_options.project_portfolio, "Портфель 2026");
	assert.deepEqual(state.setRouteCalls, [["query-report", "Project Scoring Report"]]);
});

test("hooks export enabled Client Scripts for this app", () => {
	const hooks = fs.readFileSync(HOOKS_PATH, "utf8");

	assert.match(hooks, /"doctype": "Client Script"/);
	assert.match(hooks, /\["module", "=", "Dinext Project Evaluation"\]/);
	assert.match(hooks, /\["enabled", "=", 1\]/);
});
