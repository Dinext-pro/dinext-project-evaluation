frappe.query_reports["Project Scoring Report"] = {
	filters: [
		{
			fieldname: "project_portfolio",
			label: __("Project Portfolio"),
			fieldtype: "Link",
			options: "Project Portfolio",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				return frappe.db.get_link_options("Project", txt);
			},
		},
		{
			fieldname: "profile",
			label: __("Profile"),
			fieldtype: "Link",
			options: "Project Scoring Profile",
		},
		{
			fieldname: "stage",
			label: __("Stage", null, "Dinext.StageGateModel"),
			fieldtype: "Link",
			options: "Project Stage",
		},
		{
			fieldname: "gate_pass",
			label: __("Gate Pass"),
			fieldtype: "Select",
			options: "\n1\n0",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "x_axis",
			label: __("X Axis"),
			fieldtype: "Select",
			options: "risk_score\nbenefit_score\ncost_score\nintegral_score",
			default: "risk_score",
		},
		{
			fieldname: "y_axis",
			label: __("Y Axis"),
			fieldtype: "Select",
			options: "integral_score\nbenefit_score\nrisk_score\ncost_score",
			default: "integral_score",
		},
	],

	after_datatable_render(report) {
		const payload = report.raw_data && report.raw_data.chart && report.raw_data.chart.bubble_payload;
		if (!payload || !payload.length) return;

		let wrapper = report.page.main.find(".project-scoring-bubble-chart");
		if (!wrapper.length) {
			wrapper = $('<div class="project-scoring-bubble-chart" style="margin: 16px 0;"></div>').prependTo(report.page.main);
		}
		render_project_scoring_bubbles(wrapper.get(0), payload);
	},
};

function render_project_scoring_bubbles(container, points) {
	const width = 760;
	const height = 360;
	const padding = 40;
	const maxSize = Math.max(...points.map((point) => flt(point.size) || 1), 1);
	const maxX = Math.max(...points.map((point) => flt(point.x) || 0), 1);
	const maxY = Math.max(...points.map((point) => flt(point.y) || 0), 1);
	const circles = points
		.map((point) => {
			const x = padding + ((flt(point.x) || 0) / maxX) * (width - padding * 2);
			const y = height - padding - ((flt(point.y) || 0) / maxY) * (height - padding * 2);
			const radius = 6 + ((flt(point.size) || 1) / maxSize) * 18;
			const fill = point.color_token === "gate-pass" ? "var(--green-500)" : "var(--red-500)";
			return `<g><circle cx="${x}" cy="${y}" r="${radius}" fill="${fill}" opacity="0.72"></circle><title>${frappe.utils.escape_html(point.label)}</title></g>`;
		})
		.join("");

	container.innerHTML = `
		<div class="frappe-card">
			<div class="frappe-card-head"><strong>${__("Bubble Chart")}</strong></div>
			<div class="frappe-card-body">
				<svg viewBox="0 0 ${width} ${height}" style="width: 100%; max-height: ${height}px;">
					<line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="currentColor"></line>
					<line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" stroke="currentColor"></line>
					${circles}
				</svg>
			</div>
		</div>`;
}
