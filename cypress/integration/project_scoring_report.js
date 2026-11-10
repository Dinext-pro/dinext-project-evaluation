describe("Project Scoring Report with missing project dates", () => {
	let fixture;
	before(() => cy.task("scoringSeed", null, { log: false }).then((value) => { fixture = value; }));
	after(() => cy.task("scoringCleanup", null, { log: false }));
	beforeEach(() => {
		cy.login(fixture.user, fixture.password);
		cy.intercept("**/api/method/frappe.desk.query_report.run*").as("report");
		cy.visit("/app/query-report/Project%20Scoring%20Report");
	});

	function assertReport() {
		cy.wait("@report").then(({ response }) => {
			expect(response.statusCode).to.eq(200);
			const payload = response.body.message;
			const names = payload.result.map((row) => row.project);
			expect(names).to.include(fixture.missing_project).and.include(fixture.dated_project);
			expect(names.indexOf(fixture.missing_project)).to.be.lessThan(names.indexOf(fixture.dated_project));
			expect(payload.columns).to.have.length.greaterThan(0);
			expect(payload.message.bubble_chart.points).to.have.length.greaterThan(0);
		});
		cy.get(".datatable").should("contain.text", fixture.missing_project).and("contain.text", fixture.dated_project);
		cy.get(".project-scoring-report-chart canvas").should("be.visible");
		cy.window().should((win) => {
			expect(win.frappe.query_report.get_filter_value("from_date")).to.be.oneOf([null, undefined, ""]);
			expect(win.frappe.query_report.get_filter_value("to_date")).to.be.oneOf([null, undefined, ""]);
		});
	}

	it("opens and refreshes without dates, rendering the table and chart in both themes", () => {
		assertReport();
		cy.window().then((win) => {
			const report = win.frappe.query_report;
			return cy.wrap(report.refresh_button || report.page.btn_secondary).should("be.visible").click();
		});
		assertReport();
		for (const theme of ["dark", "light"]) {
			cy.window().then((win) => {
				const switcher = new win.frappe.ui.ThemeSwitcher();
				switcher.toggle_theme(theme);
			});
			cy.get("html").should("have.attr", "data-theme", theme);
			cy.get(".project-scoring-report-chart canvas").should("be.visible");
			cy.screenshot(`scoring-date-sort-${theme}`);
		}
	});

	it("retains the evaluation period filter and excludes projects without matching scorecards", () => {
		assertReport();
		cy.window().then((win) => win.frappe.query_report.set_filter_value("x_axis", "project:expected_start_date"));
		cy.wait("@report").its("response.statusCode").should("eq", 200);
		cy.window().then((win) => win.frappe.query_report.set_filter_value("from_date", "2099-01-01"));
		cy.wait("@report").then(({ response }) => {
			expect(response.statusCode).to.eq(200);
			expect(response.body.message.result).to.deep.eq([]);
		});
		cy.get(".project-scoring-report-empty-state").should("be.visible");
		cy.window().should((win) => {
			expect(win.frappe.query_report.get_filter_value("x_axis")).to.eq("project:expected_start_date");
		});
		cy.window().then((win) => win.frappe.query_report.set_filter_value("from_date", ""));
		assertReport();
		cy.window().should((win) => {
			expect(win.frappe.query_report.get_filter_value("x_axis")).to.eq("project:expected_start_date");
		});
	});
});
