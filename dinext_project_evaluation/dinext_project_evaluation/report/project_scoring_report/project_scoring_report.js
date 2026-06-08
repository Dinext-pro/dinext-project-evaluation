frappe.provide("dinext_project_evaluation.project_scoring_report");

const PROJECT_SCORING_REPORT_NAME = "Project Scoring Report";
const PROJECT_SCORECARD_DOCTYPE = "Project Scorecard";
const PROJECT_SCORING_AXIS_DEFAULTS = {
	x_axis: "risk_score_norm",
	y_axis: "integral_score",
	size_metric: "cost_score_norm_inverse",
	color_metric: "gate_pass",
};
const PROJECT_SCORING_AXIS_OPTIONS = [
	"integral_score",
	"risk_score_norm",
	"benefit_score_norm",
	"cost_score_norm",
	"strategic_alignment_norm",
	"market_potential_norm",
	"urgency_norm",
	"regulatory_fit_norm",
	"capability_norm",
	"innovation_patent_norm",
	"cost_raw",
	"npv_raw",
	"irr_raw",
	"payback_period_raw",
	"profitability_index_raw",
	"ecv_raw",
	"rd_cost_raw",
	"mfg_cost_raw",
	"tech_success_pct_raw",
];
const PROJECT_SCORING_SIZE_OPTIONS = [
	"cost_score_norm_inverse",
	"cost_raw",
	"rd_cost_raw",
	"mfg_cost_raw",
	"innovation_cost_total_raw",
	"integral_score",
	"benefit_score_norm",
	"npv_raw",
	"ecv_raw",
];
const PROJECT_SCORING_COLOR_OPTIONS = [
	"gate_pass",
	"risk_band",
	"current_stage",
	"profile",
	"portfolio",
];

frappe.query_reports[PROJECT_SCORING_REPORT_NAME] = {
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
			fieldname: "project_stage",
			label: __("Current Stage", null, "Dinext.StageGateModel"),
			fieldtype: "Link",
			options: "Project Stage",
		},
		{
			fieldname: "evaluated_stage",
			label: __("Evaluated Stage", null, "Dinext.StageGateModel"),
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
			options: PROJECT_SCORING_AXIS_OPTIONS.join("\n"),
			default: PROJECT_SCORING_AXIS_DEFAULTS.x_axis,
		},
		{
			fieldname: "y_axis",
			label: __("Y Axis"),
			fieldtype: "Select",
			options: PROJECT_SCORING_AXIS_OPTIONS.join("\n"),
			default: PROJECT_SCORING_AXIS_DEFAULTS.y_axis,
		},
		{
			fieldname: "size_metric",
			label: __("Bubble Size"),
			fieldtype: "Select",
			options: PROJECT_SCORING_SIZE_OPTIONS.join("\n"),
			default: PROJECT_SCORING_AXIS_DEFAULTS.size_metric,
		},
		{
			fieldname: "color_metric",
			label: __("Bubble Color"),
			fieldtype: "Select",
			options: PROJECT_SCORING_COLOR_OPTIONS.join("\n"),
			default: PROJECT_SCORING_AXIS_DEFAULTS.color_metric,
		},
	],

	onload(report) {
		dinext_project_evaluation.project_scoring_report.wrapReportRefresh(report);
		dinext_project_evaluation.project_scoring_report.ensureChartMount(report);
		dinext_project_evaluation.project_scoring_report.ensureThemeObserver(report);
		dinext_project_evaluation.project_scoring_report.ensureResizeHandler(report);
	},

	after_datatable_render(_datatable) {
		const report = frappe.query_report;
		if (!dinext_project_evaluation.project_scoring_report.isScoringReport(report)) {
			return;
		}
		if (report._dinextProjectScoringSkipNextDatatableRender) {
			report._dinextProjectScoringSkipNextDatatableRender = false;
			return;
		}
		dinext_project_evaluation.project_scoring_report.render(report);
	},
};

dinext_project_evaluation.project_scoring_report.isScoringReport = function (report) {
	return (report?.report_name || "") === PROJECT_SCORING_REPORT_NAME;
};

dinext_project_evaluation.project_scoring_report.wrapReportRefresh = function (report) {
	if (!report || typeof report.refresh !== "function" || report._dinextProjectScoringRefreshWrapped) {
		return;
	}

	const baseRefresh = report.refresh.bind(report);
	report.refresh = function (...args) {
		if (!dinext_project_evaluation.project_scoring_report.isScoringReport(report)) {
			dinext_project_evaluation.project_scoring_report.teardownScoringSession(report);
			return baseRefresh(...args);
		}

		report._dinextProjectScoringSkipNextDatatableRender = true;
		const renderAfterRefresh = () => {
			report._dinextProjectScoringSkipNextDatatableRender = false;
			if (!dinext_project_evaluation.project_scoring_report.isScoringReport(report)) {
				dinext_project_evaluation.project_scoring_report.teardownScoringSession(report);
				return Promise.resolve();
			}
			dinext_project_evaluation.project_scoring_report.normalizeReportPayload(report);
			return Promise.resolve(dinext_project_evaluation.project_scoring_report.render(report));
		};

		const refreshResult = baseRefresh(...args);
		if (refreshResult && typeof refreshResult.then === "function") {
			return refreshResult.then(
				(value) => renderAfterRefresh().then(() => value),
				(error) => {
					report._dinextProjectScoringSkipNextDatatableRender = false;
					throw error;
				}
			);
		}
		renderAfterRefresh();
		return refreshResult;
	};
	report._dinextProjectScoringRefreshWrapped = true;
};

dinext_project_evaluation.project_scoring_report.getEmptyPayload = function () {
	return {
		summary: {
			total_rows: 0,
			displayed_rows: 0,
			plotted_points: 0,
			notice: null,
		},
		metric_catalog: {
			axis: [],
			size: [],
			color: [],
			defaults: { ...PROJECT_SCORING_AXIS_DEFAULTS },
		},
		bubble_chart: {
			config: { ...PROJECT_SCORING_AXIS_DEFAULTS },
			legend: { metric: PROJECT_SCORING_AXIS_DEFAULTS.color_metric, items: [] },
			points: [],
		},
	};
};

dinext_project_evaluation.project_scoring_report.normalizeReportPayload = function (report) {
	if (report?.raw_data?.message?.bubble_chart) {
		return report.raw_data.message;
	}
	if (report?.raw_data?.chart?.bubble_payload) {
		const legacyMetricConfig =
			report.raw_data?.message?.metric_config || PROJECT_SCORING_AXIS_DEFAULTS;
		const points = report.raw_data.chart.bubble_payload.map((point) => ({
			project: point.project,
			label: point.label,
			portfolio: point.portfolio || null,
			project_stage: point.project_stage || point.stage || null,
			evaluated_stage: point.evaluated_stage || null,
			scorecard: point.scorecard || null,
			profile: point.profile || null,
			gate_pass: point.gate_pass,
			x: {
				metric: legacyMetricConfig.x_axis,
				label: legacyMetricConfig.x_axis,
				value: point.x,
				display: point.x == null ? __("N/A") : String(point.x),
			},
			y: {
				metric: legacyMetricConfig.y_axis,
				label: legacyMetricConfig.y_axis,
				value: point.y,
				display: point.y == null ? __("N/A") : String(point.y),
			},
			size: {
				metric: legacyMetricConfig.size_metric,
				label: legacyMetricConfig.size_metric,
				value: point.size,
				display: point.size == null ? __("N/A") : String(point.size),
				normalized: Number(point.size || 18),
			},
			color: {
				value: point.color_token,
				token: point.color_token,
				label: point.color_token,
			},
			meta: {},
		}));
		report.raw_data.message = {
			summary: {
				total_rows: Array.isArray(report.raw_data.result) ? report.raw_data.result.length : points.length,
				displayed_rows: Array.isArray(report.raw_data.result) ? report.raw_data.result.length : points.length,
				plotted_points: points.length,
				notice: null,
			},
			metric_catalog: {
				axis: [],
				size: [],
				color: [],
				defaults: { ...PROJECT_SCORING_AXIS_DEFAULTS },
			},
			bubble_chart: {
				config: { ...PROJECT_SCORING_AXIS_DEFAULTS, ...legacyMetricConfig },
				legend: {
					metric: legacyMetricConfig.color_metric || PROJECT_SCORING_AXIS_DEFAULTS.color_metric,
					items: dinext_project_evaluation.project_scoring_report.buildLegacyLegend(points),
				},
				points,
			},
		};
		return report.raw_data.message;
	}
	report.raw_data = {
		...(report.raw_data || {}),
		result: report?.data || [],
		message: dinext_project_evaluation.project_scoring_report.getEmptyPayload(),
	};
	return report.raw_data.message;
};

dinext_project_evaluation.project_scoring_report.buildLegacyLegend = function (points) {
	const seen = new Set();
	return points
		.map((point) => point.color)
		.filter((color) => {
			const key = `${color.value}:${color.token}`;
			if (seen.has(key)) {
				return false;
			}
			seen.add(key);
			return true;
		})
		.map((color) => ({
			value: color.value,
			token: color.token,
			label: color.label,
		}));
};

dinext_project_evaluation.project_scoring_report.ensureAssets = function () {
	if (dinext_project_evaluation.project_scoring_report._assetsPromise) {
		return dinext_project_evaluation.project_scoring_report._assetsPromise;
	}
	dinext_project_evaluation.project_scoring_report._assetsPromise = new Promise((resolve, reject) => {
		if (window.echarts) {
			resolve();
			return;
		}
		frappe.require(
			[
				"/assets/dinext_common/js/echarts.min.js",
				"/assets/dinext_project_evaluation/css/project_scoring_report.css",
			],
			() => {
				if (window.echarts) {
					resolve();
					return;
				}
				reject(new Error("Failed to load ECharts"));
			}
		);
	});
	return dinext_project_evaluation.project_scoring_report._assetsPromise;
};

dinext_project_evaluation.project_scoring_report.ensureChartMount = function (report) {
	if (!report?.page?.main || typeof report.page.main.find !== "function") {
		return null;
	}
	dinext_project_evaluation.project_scoring_report.hideBuiltInChart(report);
	let mount = report.page.main.find(".project-scoring-report-shell");
	if (!mount?.length) {
		mount = $(
			'<div class="project-scoring-report-shell"><div class="project-scoring-report-card frappe-card"><div class="project-scoring-report-card-body frappe-card-body"><div class="project-scoring-report-legend"></div><div class="project-scoring-report-chart"></div><div class="project-scoring-report-empty-state"></div></div></div></div>'
		).prependTo(report.page.main);
	}
	return mount;
};

dinext_project_evaluation.project_scoring_report.hideBuiltInChart = function (report) {
	const chartWrapper = report?.page?.main?.find?.(".chart-wrapper");
	if (chartWrapper?.length) {
		chartWrapper.remove();
	}
};

dinext_project_evaluation.project_scoring_report.teardownScoringMount = function (report) {
	if (!report?.page?.main || typeof report.page.main.find !== "function") {
		return;
	}
	const mount = report.page.main.find(".project-scoring-report-shell");
	const dom = mount?.find?.(".project-scoring-report-chart")?.get?.(0);
	const chart =
		(typeof window.echarts?.getInstanceByDom === "function" && dom && window.echarts.getInstanceByDom(dom)) ||
		dom?._dinextProjectScoringChart ||
		null;
	if (chart && typeof chart.dispose === "function") {
		chart.dispose();
	}
	if (mount?.remove) {
		mount.remove();
	}
};

dinext_project_evaluation.project_scoring_report.teardownScoringSession = function (report) {
	dinext_project_evaluation.project_scoring_report.teardownScoringMount(report);
	if (report) {
		report._dinextProjectScoringSkipNextDatatableRender = false;
	}
};

dinext_project_evaluation.project_scoring_report.ensureThemeObserver = function (report) {
	if (
		!report ||
		dinext_project_evaluation.project_scoring_report._themeObserver ||
		typeof MutationObserver === "undefined"
	) {
		return;
	}
	const root = document.documentElement;
	if (!root) {
		return;
	}
	let theme = root.getAttribute("data-theme");
	const observer = new MutationObserver(() => {
		const nextTheme = root.getAttribute("data-theme");
		if (nextTheme === theme) {
			return;
		}
		theme = nextTheme;
		const activeReport = frappe.query_report;
		if (!dinext_project_evaluation.project_scoring_report.isScoringReport(activeReport)) {
			return;
		}
		dinext_project_evaluation.project_scoring_report.render(activeReport);
	});
	observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
	dinext_project_evaluation.project_scoring_report._themeObserver = observer;
};

dinext_project_evaluation.project_scoring_report.ensureResizeHandler = function () {
	if (dinext_project_evaluation.project_scoring_report._resizeHandler) {
		return;
	}
	const handler = () => {
		const report = frappe.query_report;
		if (!dinext_project_evaluation.project_scoring_report.isScoringReport(report)) {
			return;
		}
		const mount = report?.page?.main?.find?.(".project-scoring-report-shell");
		const dom = mount?.find?.(".project-scoring-report-chart")?.get?.(0);
		const chart =
			(typeof window.echarts?.getInstanceByDom === "function" && dom && window.echarts.getInstanceByDom(dom)) ||
			dom?._dinextProjectScoringChart ||
			null;
		if (chart && typeof chart.resize === "function") {
			chart.resize();
		}
	};
	window.addEventListener("resize", handler);
	dinext_project_evaluation.project_scoring_report._resizeHandler = handler;
};

dinext_project_evaluation.project_scoring_report.render = async function (report) {
	if (!report?.page?.main) {
		return;
	}
	if (!dinext_project_evaluation.project_scoring_report.isScoringReport(report)) {
		dinext_project_evaluation.project_scoring_report.teardownScoringSession(report);
		return;
	}

	const message = dinext_project_evaluation.project_scoring_report.normalizeReportPayload(report);
	await dinext_project_evaluation.project_scoring_report.ensureAssets();
	const mount = dinext_project_evaluation.project_scoring_report.ensureChartMount(report);
	if (!mount?.length) {
		return;
	}
	const chartDom = mount.find(".project-scoring-report-chart").get(0);
	const legendDom = mount.find(".project-scoring-report-legend").get(0);
	const emptyDom = mount.find(".project-scoring-report-empty-state").get(0);
	const bubbleChart = message.bubble_chart || dinext_project_evaluation.project_scoring_report.getEmptyPayload().bubble_chart;
	const points = Array.isArray(bubbleChart.points) ? bubbleChart.points : [];

	dinext_project_evaluation.project_scoring_report.renderLegend(legendDom, bubbleChart.legend);
	dinext_project_evaluation.project_scoring_report.syncMetricFilterOptions(report, message.metric_catalog);

	const existing =
		(typeof window.echarts?.getInstanceByDom === "function" && chartDom && window.echarts.getInstanceByDom(chartDom)) ||
		chartDom?._dinextProjectScoringChart ||
		null;
	if (existing && typeof existing.dispose === "function") {
		existing.dispose();
	}

	if (!points.length) {
		chartDom.innerHTML = "";
		emptyDom.textContent = message.summary?.notice || __("No projects match the selected filters.");
		emptyDom.classList.add("is-visible");
		return;
	}

	emptyDom.textContent = "";
	emptyDom.classList.remove("is-visible");
	const chart = window.echarts.init(chartDom, dinext_project_evaluation.project_scoring_report.getThemeName());
	chartDom._dinextProjectScoringChart = chart;
	chart.setOption(dinext_project_evaluation.project_scoring_report.buildChartOptions(points, bubbleChart));
	dinext_project_evaluation.project_scoring_report.bindBubbleChartNavigation(chart);
};

dinext_project_evaluation.project_scoring_report.openScorecard = function (scorecardName) {
	const name = String(scorecardName || "").trim();
	if (!name) {
		return;
	}
	frappe.set_route("Form", PROJECT_SCORECARD_DOCTYPE, name);
};

dinext_project_evaluation.project_scoring_report.handleBubbleChartClick = function (params) {
	const scorecardName = params?.data?.point?.scorecard;
	dinext_project_evaluation.project_scoring_report.openScorecard(scorecardName);
};

dinext_project_evaluation.project_scoring_report.bindBubbleChartNavigation = function (chart) {
	if (!chart || typeof chart.off !== "function" || typeof chart.on !== "function") {
		return;
	}
	chart.off("click");
	chart.on("click", (params) => {
		dinext_project_evaluation.project_scoring_report.handleBubbleChartClick(params);
	});
};

dinext_project_evaluation.project_scoring_report.renderLegend = function (dom, legend) {
	if (!dom) {
		return;
	}
	const items = Array.isArray(legend?.items) ? legend.items : [];
	if (!items.length) {
		dom.innerHTML = "";
		return;
	}
	dom.innerHTML = items
		.map((item) => {
			const color = dinext_project_evaluation.project_scoring_report.resolveColorToken(item.token);
			return `<span class="project-scoring-report-legend-item"><span class="project-scoring-report-legend-swatch" style="background:${color};"></span>${frappe.utils.escape_html(item.label)}</span>`;
		})
		.join("");
};

dinext_project_evaluation.project_scoring_report.syncMetricFilterOptions = function (report, catalog) {
	if (!report || !catalog) {
		return;
	}
	const updateSelect = (fieldname, entries, fallbackOptions) => {
		const filter = report.get_filter?.(fieldname);
		if (!filter?.df) {
			return;
		}
		const options = Array.isArray(entries) && entries.length ? entries.map((entry) => entry.id).join("\n") : fallbackOptions.join("\n");
		filter.df.options = options;
	};
	updateSelect("x_axis", catalog.axis, PROJECT_SCORING_AXIS_OPTIONS);
	updateSelect("y_axis", catalog.axis, PROJECT_SCORING_AXIS_OPTIONS);
	updateSelect("size_metric", catalog.size, PROJECT_SCORING_SIZE_OPTIONS);
	updateSelect("color_metric", catalog.color, PROJECT_SCORING_COLOR_OPTIONS);
};

dinext_project_evaluation.project_scoring_report.buildChartOptions = function (points, bubbleChart) {
	const xLabel = points[0]?.x?.label || bubbleChart?.config?.x_axis || __("X Axis");
	const yLabel = points[0]?.y?.label || bubbleChart?.config?.y_axis || __("Y Axis");
	return {
		animation: false,
		backgroundColor: "transparent",
		grid: {
			left: 60,
			right: 24,
			top: 40,
			bottom: 56,
		},
		tooltip: {
			trigger: "item",
			confine: true,
			formatter(params) {
				const point = params.data?.point || {};
				const fields = [
					`<strong>${frappe.utils.escape_html(point.label || "")}</strong>`,
					point.portfolio ? `${__("Portfolio")}: ${frappe.utils.escape_html(point.portfolio)}` : "",
					point.project_stage
						? `${__("Current Stage")}: ${frappe.utils.escape_html(point.project_stage)}`
						: "",
					point.evaluated_stage
						? `${__("Evaluated Stage")}: ${frappe.utils.escape_html(point.evaluated_stage)}`
						: "",
					point.profile ? `${__("Profile")}: ${frappe.utils.escape_html(point.profile)}` : "",
					point.meta?.evaluation_date
						? `${__("Evaluation Date")}: ${frappe.utils.escape_html(point.meta.evaluation_date)}`
						: "",
					point.x ? `${frappe.utils.escape_html(point.x.label)}: ${frappe.utils.escape_html(point.x.display)}` : "",
					point.y ? `${frappe.utils.escape_html(point.y.label)}: ${frappe.utils.escape_html(point.y.display)}` : "",
					point.size ? `${frappe.utils.escape_html(point.size.label)}: ${frappe.utils.escape_html(point.size.display)}` : "",
					point.color ? `${__("Color")}: ${frappe.utils.escape_html(point.color.label)}` : "",
				].filter(Boolean);
				return fields.join("<br>");
			},
		},
		xAxis: {
			name: xLabel,
			nameLocation: "middle",
			nameGap: 32,
			type: "value",
			scale: true,
		},
		yAxis: {
			name: yLabel,
			nameLocation: "middle",
			nameGap: 46,
			type: "value",
			scale: true,
		},
		series: [
			{
				type: "scatter",
				data: points.map((point) => ({
					value: [Number(point.x?.value || 0), Number(point.y?.value || 0), Number(point.size?.normalized || 18)],
					point,
					symbolSize: Number(point.size?.normalized || 18),
					itemStyle: {
						color: dinext_project_evaluation.project_scoring_report.resolveColorToken(point.color?.token),
						opacity: 0.78,
					},
				})),
				emphasis: {
					scale: true,
				},
			},
		],
	};
};

dinext_project_evaluation.project_scoring_report.resolveColorToken = function (token) {
	const palette = dinext_project_evaluation.project_scoring_report.getPalette();
	if (palette[token]) {
		return palette[token];
	}
	const fallbackColors = [
		"#4f6fa8",
		"#4e7d5c",
		"#a86f4f",
		"#8f5ca8",
		"#5a8a9e",
		"#b38b4d",
	];
	let hash = 0;
	for (const char of String(token || "unknown")) {
		hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
	}
	return fallbackColors[hash % fallbackColors.length];
};

dinext_project_evaluation.project_scoring_report.getPalette = function () {
	const isDark = dinext_project_evaluation.project_scoring_report.getThemeName() === "dark";
	return isDark
		? {
				"gate-pass": "#4e7d5c",
				"gate-fail": "#a85c5c",
				"gate-unknown": "#6a7d92",
				"risk-low": "#4e7d5c",
				"risk-medium": "#a88e5c",
				"risk-high": "#a85c5c",
				"risk-unknown": "#6a7d92",
		  }
		: {
				"gate-pass": "#739b7f",
				"gate-fail": "#c08b8b",
				"gate-unknown": "#8f9aa8",
				"risk-low": "#739b7f",
				"risk-medium": "#c6a45c",
				"risk-high": "#c08b8b",
				"risk-unknown": "#8f9aa8",
		  };
};

dinext_project_evaluation.project_scoring_report.getThemeName = function () {
	const root = document.documentElement;
	return root && root.getAttribute("data-theme") === "dark" ? "dark" : undefined;
};
