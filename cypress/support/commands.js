Cypress.Commands.add("login", (email, password) => {
	return cy.session(email, () => {
		cy.request({
			method: "POST", url: "/api/method/login", body: { usr: email, pwd: password },
			log: false, failOnStatusCode: false,
		}).its("status").should("eq", 200);
	}, {
		cacheAcrossSpecs: false,
		validate() {
			cy.request("/api/method/frappe.auth.get_logged_user").its("body.message").should("eq", email);
		},
	});
});
