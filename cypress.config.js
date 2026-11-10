module.exports = {
	includeShadowDom: true,
	defaultCommandTimeout: 30000,
	pageLoadTimeout: 120000,
	requestTimeout: 30000,
	responseTimeout: 120000,
	viewportWidth: 1440,
	viewportHeight: 1000,
	video: false,
	e2e: {
		baseUrl: "http://localhost:8000",
		specPattern: "cypress/integration/**/*.js",
		supportFile: "cypress/support/e2e.js",
		setupNodeEvents(on, config) {
			const { execFileSync } = require("node:child_process");
			const path = require("node:path");
			const bench = path.resolve(__dirname, "../..");
			const site = process.env.FRAPPE_SITE || "localhost";
			function execute(method) {
				const output = execFileSync("bench", ["--site", site, "execute", method], {
					cwd: bench, encoding: "utf8", timeout: 120000,
				});
				return JSON.parse(output.trim().split("\n").at(-1));
			}
			const siteUrl = execute("frappe.utils.get_url");
			if (new URL(siteUrl).origin !== new URL(config.baseUrl).origin) {
				throw new Error("FRAPPE_SITE must select the same site as the Cypress base URL.");
			}
			on("task", {
				scoringSeed: () => execute("dinext_project_evaluation.tests.ui_test_helpers.seed"),
				scoringCleanup: () => execute("dinext_project_evaluation.tests.ui_test_helpers.cleanup"),
			});
		},
	},
};
