frappe.provide("dinext_project_evaluation.project_scoring_report");

const PROJECT_SCORING_REPORT_NAME = "Project Scoring Report";
const PROJECT_SCORECARD_DOCTYPE = "Project Scorecard";
const PROJECT_DOCTYPE = "Project";
const PROJECT_SCORING_EMPTY_CONFIG = {
	x_axis: "",
	y_axis: "",
	size_metric: "",
	color_metric: "",
};
const PROJECT_SCORING_METRIC_GROUP_ORDER = [
	{ key: "project", label: __("Project") },
	{ key: "scorecard", label: __("Project Evaluation") },
];
const PROJECT_SCORING_METRIC_CONTROLS = [
	{
		fieldname: "x_axis",
		label: __("X Axis"),
		catalogKey: "axis",
	},
	{
		fieldname: "y_axis",
		label: __("Y Axis"),
		catalogKey: "axis",
	},
	{
		fieldname: "size_metric",
		label: __("Bubble Size"),
		catalogKey: "size",
	},
	{
		fieldname: "color_metric",
		label: __("Bubble Color"),
		catalogKey: "color",
	},
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
			fieldname: "project_type",
			label: __("Project Type"),
			fieldtype: "Link",
			options: "Project Type",
		},
		{
			fieldname: "project_status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nCompleted\nCancelled",
		},
		{
			fieldname: "governance_model",
			label: __("Governance Model"),
			fieldtype: "Link",
			options: "Project Governance Model",
		},
		{
			fieldname: "profile",
			label: __("Project Scoring Profile"),
			fieldtype: "Link",
			options: "Project Scoring Profile",
		},
		{
			fieldname: "only_active_projects",
			label: __("Only Active Projects"),
			fieldtype: "Check",
			default: 0,
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
			options: "",
			hidden: 1,
		},
		{
			fieldname: "y_axis",
			label: __("Y Axis"),
			fieldtype: "Select",
			options: "",
			hidden: 1,
		},
		{
			fieldname: "size_metric",
			label: __("Bubble Size"),
			fieldtype: "Select",
			options: "",
			hidden: 1,
		},
		{
			fieldname: "color_metric",
			label: __("Bubble Color"),
			fieldtype: "Select",
			options: "",
			hidden: 1,
		},
	],

	onload(report) {
		dinext_project_evaluation.project_scoring_report.suppressSetChartToolbarActions(report);
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
			dinext_project_evaluation.project_scoring_report.resetHiddenLegendColorKeys(report);
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
			defaults: { ...PROJECT_SCORING_EMPTY_CONFIG },
		},
		bubble_chart: {
			config: { ...PROJECT_SCORING_EMPTY_CONFIG },
			axes: {
				x: { axis_type: "value", label: __("X Axis") },
				y: { axis_type: "value", label: __("Y Axis") },
			},
			legend: { metric: "", metric_label: __("Bubble Color"), items: [] },
			points: [],
		},
	};
};

dinext_project_evaluation.project_scoring_report.normalizeReportPayload = function (report) {
	if (report?.raw_data?.message?.bubble_chart) {
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
			'<div class="project-scoring-report-shell"><div class="project-scoring-report-card frappe-card"><div class="project-scoring-report-card-body frappe-card-body"><div class="project-scoring-report-controls"></div><div class="project-scoring-report-legend"></div><div class="project-scoring-report-chart"></div><div class="project-scoring-report-empty-state"></div></div></div></div>'
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

dinext_project_evaluation.project_scoring_report.removeSetChartToolbarButtons = function (report) {
	if (!report) {
		return;
	}
	report.create_chart_button?.remove?.();
	report.create_chart_button = null;
	report.add_to_dashboard_button?.remove?.();
	report.add_to_dashboard_button = null;
	if (report.page?.remove_inner_button) {
		report.page.remove_inner_button(__("Set Chart"), __("Actions"));
		report.page.remove_inner_button(__("Add Chart to Dashboard"), __("Actions"));
	}
};

dinext_project_evaluation.project_scoring_report.suppressSetChartToolbarActions = function (report) {
	if (!dinext_project_evaluation.project_scoring_report.isScoringReport(report)) {
		return;
	}
	if (report._dinextProjectScoringSetChartSuppressed) {
		dinext_project_evaluation.project_scoring_report.removeSetChartToolbarButtons(report);
		return;
	}

	const queryReportProto = frappe.views?.QueryReport?.prototype;
	if (!queryReportProto || typeof queryReportProto.add_chart_buttons_to_toolbar !== "function") {
		return;
	}

	report._dinextProjectScoringBaseAddChartButtons =
		report._dinextProjectScoringBaseAddChartButtons ||
		queryReportProto.add_chart_buttons_to_toolbar.bind(report);
	report.add_chart_buttons_to_toolbar = function () {
		dinext_project_evaluation.project_scoring_report.removeSetChartToolbarButtons(report);
	};
	report._dinextProjectScoringSetChartSuppressed = true;
	dinext_project_evaluation.project_scoring_report.removeSetChartToolbarButtons(report);
};

dinext_project_evaluation.project_scoring_report.restoreSetChartToolbarActions = function (report) {
	if (!report?._dinextProjectScoringSetChartSuppressed) {
		return;
	}
	if (report._dinextProjectScoringBaseAddChartButtons) {
		report.add_chart_buttons_to_toolbar = report._dinextProjectScoringBaseAddChartButtons;
	}
	delete report._dinextProjectScoringBaseAddChartButtons;
	delete report._dinextProjectScoringSetChartSuppressed;
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
	if (report) {
		delete report._dinextProjectScoringMetricControls;
		delete report._dinextProjectScoringBubbleNavContext;
	}
};

dinext_project_evaluation.project_scoring_report.teardownScoringSession = function (report) {
	dinext_project_evaluation.project_scoring_report.restoreSetChartToolbarActions(report);
	dinext_project_evaluation.project_scoring_report.teardownScoringMount(report);
	if (report) {
		report._dinextProjectScoringSkipNextDatatableRender = false;
		dinext_project_evaluation.project_scoring_report.resetHiddenLegendColorKeys(report);
	}
};

dinext_project_evaluation.project_scoring_report.resetHiddenLegendColorKeys = function (report) {
	if (!report) {
		return;
	}
	report._dinextProjectScoringHiddenColorKeys = new Set();
};

dinext_project_evaluation.project_scoring_report.getHiddenLegendColorKeys = function (report) {
	if (!report) {
		return new Set();
	}
	if (!report._dinextProjectScoringHiddenColorKeys) {
		report._dinextProjectScoringHiddenColorKeys = new Set();
	}
	return report._dinextProjectScoringHiddenColorKeys;
};

dinext_project_evaluation.project_scoring_report.toggleHiddenLegendColorKey = function (report, colorKey) {
	const key = String(colorKey || "").trim();
	if (!key || !report) {
		return;
	}
	const hiddenKeys = dinext_project_evaluation.project_scoring_report.getHiddenLegendColorKeys(report);
	if (hiddenKeys.has(key)) {
		hiddenKeys.delete(key);
		return;
	}
	hiddenKeys.add(key);
};

dinext_project_evaluation.project_scoring_report.filterPointsByHiddenLegend = function (report, points) {
	const hiddenKeys = dinext_project_evaluation.project_scoring_report.getHiddenLegendColorKeys(report);
	if (!hiddenKeys.size) {
		return Array.isArray(points) ? points : [];
	}
	return (Array.isArray(points) ? points : []).filter((point) => {
		const identity = dinext_project_evaluation.project_scoring_report.getColorIdentity(point?.color);
		return identity && !hiddenKeys.has(identity);
	});
};

dinext_project_evaluation.project_scoring_report.getChartInstance = function (chartDom) {
	return (
		(typeof window.echarts?.getInstanceByDom === "function" && chartDom && window.echarts.getInstanceByDom(chartDom)) ||
		chartDom?._dinextProjectScoringChart ||
		null
	);
};

dinext_project_evaluation.project_scoring_report.disposeChartInstance = function (chartDom) {
	const chart = dinext_project_evaluation.project_scoring_report.getChartInstance(chartDom);
	if (chart && typeof chart.dispose === "function") {
		chart.dispose();
	}
	if (chartDom) {
		chartDom.innerHTML = "";
		delete chartDom._dinextProjectScoringChart;
	}
};

dinext_project_evaluation.project_scoring_report.updateLegendChartView = function (report, mount, message) {
	const namespace = dinext_project_evaluation.project_scoring_report;
	if (!mount?.length) {
		return;
	}
	const chartDom = mount.find(".project-scoring-report-chart").get(0);
	const legendDom = mount.find(".project-scoring-report-legend").get(0);
	const emptyDom = mount.find(".project-scoring-report-empty-state").get(0);
	const bubbleChart = message?.bubble_chart || namespace.getEmptyPayload().bubble_chart;
	namespace.syncBubbleNavContext(report, message);
	const allPoints = Array.isArray(bubbleChart.points) ? bubbleChart.points : [];
	const visiblePoints = namespace.filterPointsByHiddenLegend(report, allPoints);
	const hiddenKeys = namespace.getHiddenLegendColorKeys(report);
	const colorMap = namespace.buildUniqueColorMap(
		namespace.collectColorIdentities(allPoints, bubbleChart.legend)
	);

	namespace.renderLegend(legendDom, bubbleChart.legend, colorMap, hiddenKeys);
	namespace.ensureLegendClickHandler(report, legendDom);

	if (!allPoints.length) {
		namespace.disposeChartInstance(chartDom);
		if (emptyDom) {
			emptyDom.textContent = message?.summary?.notice || __("No projects match the selected filters.");
			emptyDom.classList.add("is-visible");
		}
		return;
	}

	if (!visiblePoints.length) {
		namespace.disposeChartInstance(chartDom);
		if (emptyDom) {
			emptyDom.textContent = __("All legend categories are hidden.");
			emptyDom.classList.add("is-visible");
		}
		return;
	}

	if (emptyDom) {
		emptyDom.textContent = "";
		emptyDom.classList.remove("is-visible");
	}

	let chart = namespace.getChartInstance(chartDom);
	if (!chart || typeof chart.setOption !== "function") {
		namespace.disposeChartInstance(chartDom);
		chart = window.echarts.init(chartDom, namespace.getThemeName());
		chartDom._dinextProjectScoringChart = chart;
		namespace.bindBubbleChartNavigation(chart, report);
	}
	chart.setOption(namespace.buildChartOptions(visiblePoints, bubbleChart, colorMap), true);
	if (typeof chart.resize === "function") {
		chart.resize();
	}
};

dinext_project_evaluation.project_scoring_report.handleLegendItemClick = function (report, colorKey) {
	if (!report || !colorKey) {
		return;
	}
	dinext_project_evaluation.project_scoring_report.toggleHiddenLegendColorKey(report, colorKey);
	const message = dinext_project_evaluation.project_scoring_report.normalizeReportPayload(report);
	const mount = report.page?.main?.find?.(".project-scoring-report-shell");
	dinext_project_evaluation.project_scoring_report.updateLegendChartView(report, mount, message);
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
	const bubbleChart = message.bubble_chart || dinext_project_evaluation.project_scoring_report.getEmptyPayload().bubble_chart;

	dinext_project_evaluation.project_scoring_report.syncMetricFilterOptions(report, message.metric_catalog);
	dinext_project_evaluation.project_scoring_report.renderMetricControls(
		report,
		mount,
		message.metric_catalog,
		bubbleChart.config
	);

	dinext_project_evaluation.project_scoring_report.updateLegendChartView(report, mount, message);
};

dinext_project_evaluation.project_scoring_report.openScorecard = function (scorecardName) {
	const name = String(scorecardName || "").trim();
	if (!name) {
		return;
	}
	frappe.set_route("Form", PROJECT_SCORECARD_DOCTYPE, name);
};

dinext_project_evaluation.project_scoring_report.openProject = function (projectName) {
	const name = String(projectName || "").trim();
	if (!name) {
		return;
	}
	frappe.set_route("Form", PROJECT_DOCTYPE, name);
};

dinext_project_evaluation.project_scoring_report.getMetricCatalogEntry = function (catalog, metricId, catalogKey) {
	const entries = catalog?.[catalogKey] || [];
	const id = String(metricId || "").trim();
	if (!id) {
		return null;
	}
	return entries.find((entry) => entry?.id === id) || null;
};

dinext_project_evaluation.project_scoring_report.syncBubbleNavContext = function (report, message) {
	if (!report) {
		return;
	}
	const bubbleChart = message?.bubble_chart || {};
	const sizeMetricId = bubbleChart?.config?.size_metric || "";
	const sizeEntry = dinext_project_evaluation.project_scoring_report.getMetricCatalogEntry(
		message?.metric_catalog,
		sizeMetricId,
		"size"
	);
	report._dinextProjectScoringBubbleNavContext = {
		size_metric: sizeMetricId,
		size_source_kind: sizeEntry?.source_kind || null,
	};
};

dinext_project_evaluation.project_scoring_report.shouldOpenProjectOnBubbleClick = function (report) {
	return report?._dinextProjectScoringBubbleNavContext?.size_source_kind === "project_field";
};

dinext_project_evaluation.project_scoring_report.handleBubbleChartClick = function (params, report) {
	const activeReport = report || frappe.query_report;
	const point = params?.data?.point || {};
	const projectName = String(point.project || "").trim();

	if (dinext_project_evaluation.project_scoring_report.shouldOpenProjectOnBubbleClick(activeReport)) {
		if (projectName) {
			dinext_project_evaluation.project_scoring_report.openProject(projectName);
		}
		return;
	}

	const scorecardName = String(point.scorecard || "").trim();
	if (scorecardName) {
		dinext_project_evaluation.project_scoring_report.openScorecard(scorecardName);
		return;
	}
	if (projectName) {
		dinext_project_evaluation.project_scoring_report.openProject(projectName);
	}
};

dinext_project_evaluation.project_scoring_report.bindBubbleChartNavigation = function (chart, report) {
	if (!chart || typeof chart.off !== "function" || typeof chart.on !== "function") {
		return;
	}
	chart.off("click");
	chart.on("click", (params) => {
		dinext_project_evaluation.project_scoring_report.handleBubbleChartClick(params, report);
	});
};

dinext_project_evaluation.project_scoring_report.renderLegend = function (dom, legend, colorMap, hiddenKeys) {
	if (!dom) {
		return;
	}
	const items = Array.isArray(legend?.items) ? legend.items : [];
	if (!items.length) {
		dom.innerHTML = "";
		return;
	}
	const hiddenSet =
		hiddenKeys && typeof hiddenKeys.has === "function"
			? hiddenKeys
			: new Set(Array.isArray(hiddenKeys) ? hiddenKeys : []);
	dom.innerHTML = items
		.map((item) => {
			const colorKey = dinext_project_evaluation.project_scoring_report.getColorIdentity(item);
			const color = dinext_project_evaluation.project_scoring_report.resolveColor(item, colorMap);
			const isHidden = hiddenSet.has(colorKey);
			const hiddenClass = isHidden ? " is-hidden" : "";
			return `<button type="button" class="project-scoring-report-legend-item${hiddenClass}" data-color-key="${frappe.utils.escape_html(colorKey)}" aria-pressed="${isHidden ? "false" : "true"}"><span class="project-scoring-report-legend-swatch" style="background:${color};"></span>${frappe.utils.escape_html(item.label)}</button>`;
		})
		.join("");
};

dinext_project_evaluation.project_scoring_report.ensureLegendClickHandler = function (report, legendDom) {
	if (!report || !legendDom || legendDom._dinextProjectScoringLegendBound) {
		return;
	}
	legendDom._dinextProjectScoringLegendBound = true;
	legendDom.addEventListener("click", (event) => {
		const item = event.target.closest(".project-scoring-report-legend-item");
		if (!item) {
			return;
		}
		const colorKey = item.getAttribute("data-color-key");
		if (!colorKey) {
			return;
		}
		event.preventDefault();
		dinext_project_evaluation.project_scoring_report.handleLegendItemClick(report, colorKey);
	});
};

dinext_project_evaluation.project_scoring_report.syncMetricFilterOptions = function (report, catalog) {
	if (!report || !catalog) {
		return;
	}
	const namespace = dinext_project_evaluation.project_scoring_report;
	const updateSelect = (fieldname, entries) => {
		const filter = report.get_filter?.(fieldname);
		if (!filter?.df) {
			return;
		}
		const optionIds = namespace.buildGroupedMetricOptionIds(entries);
		filter.df.options = optionIds.length ? optionIds.join("\n") : "";
	};
	updateSelect("x_axis", catalog.axis);
	updateSelect("y_axis", catalog.axis);
	updateSelect("size_metric", catalog.size);
	updateSelect("color_metric", catalog.color);
};

dinext_project_evaluation.project_scoring_report.getMetricControlOptionIds = function (filter) {
	const rawOptions = filter?.df?.options;
	if (typeof rawOptions === "string" && rawOptions.trim()) {
		return rawOptions
			.split("\n")
			.map((option) => option.trim())
			.filter(Boolean);
	}
	if (Array.isArray(rawOptions)) {
		return rawOptions
			.map((option) => {
				if (option && typeof option === "object") {
					return String(option.value ?? "").trim();
				}
				return String(option ?? "").trim();
			})
			.filter(Boolean);
	}
	return [];
};

dinext_project_evaluation.project_scoring_report.getMetricEntryGroupKey = function (entry) {
	if (entry?.source_kind === "project_field") {
		return "project";
	}
	if (entry?.source_kind === "scorecard_field") {
		return "scorecard";
	}
	return "criterion";
};

dinext_project_evaluation.project_scoring_report.getMetricLocaleCollator = function () {
	const locale = frappe.boot?.lang || document?.documentElement?.lang || undefined;
	return new Intl.Collator(locale, { sensitivity: "base", numeric: true });
};

dinext_project_evaluation.project_scoring_report.partitionMetricEntriesByGroup = function (catalogEntries, optionIds) {
	const allowedIds = new Set(optionIds || []);
	const entries = (catalogEntries || []).filter((entry) => entry?.id && allowedIds.has(entry.id));
	const grouped = {
		project: [],
		scorecard: [],
		criterion: [],
	};
	for (const entry of entries) {
		const groupKey = dinext_project_evaluation.project_scoring_report.getMetricEntryGroupKey(entry);
		grouped[groupKey].push(entry);
	}
	return grouped;
};

dinext_project_evaluation.project_scoring_report.sortMetricEntriesByDisplayLabel = function (entries, labelMap) {
	const collator = dinext_project_evaluation.project_scoring_report.getMetricLocaleCollator();
	return [...entries].sort((left, right) => {
		const leftLabel = labelMap[left.id] || left.id;
		const rightLabel = labelMap[right.id] || right.id;
		const comparison = collator.compare(leftLabel, rightLabel);
		if (comparison !== 0) {
			return comparison;
		}
		return String(left.id).localeCompare(String(right.id));
	});
};

dinext_project_evaluation.project_scoring_report.buildGroupedMetricOptionIds = function (catalogEntries, optionIds) {
	const namespace = dinext_project_evaluation.project_scoring_report;
	const resolvedOptionIds =
		optionIds ||
		(catalogEntries || []).map((entry) => entry?.id).filter(Boolean);
	const labelMap = namespace.buildMetricOptionLabelMap(catalogEntries, resolvedOptionIds);
	const grouped = namespace.partitionMetricEntriesByGroup(catalogEntries, resolvedOptionIds);
	const orderedIds = [];

	for (const groupSpec of PROJECT_SCORING_METRIC_GROUP_ORDER) {
		const sortedEntries = namespace.sortMetricEntriesByDisplayLabel(
			grouped[groupSpec.key],
			labelMap
		);
		for (const entry of sortedEntries) {
			orderedIds.push(entry.id);
		}
	}

	const criterionEntries = namespace.sortMetricEntriesByDisplayLabel(grouped.criterion, labelMap);
	for (const entry of criterionEntries) {
		orderedIds.push(entry.id);
	}

	const knownIds = new Set(orderedIds);
	const orphanIds = resolvedOptionIds.filter((optionId) => !knownIds.has(optionId));
	const orphanEntries = orphanIds.map((optionId) => ({ id: optionId, label: labelMap[optionId] || optionId }));
	const sortedOrphans = namespace.sortMetricEntriesByDisplayLabel(orphanEntries, labelMap);
	for (const entry of sortedOrphans) {
		orderedIds.push(entry.id);
	}

	return orderedIds;
};

dinext_project_evaluation.project_scoring_report.disambiguateMetricDropdownLabels = function (catalogEntries) {
	const labelMap = {};
	if (Array.isArray(catalogEntries)) {
		for (const entry of catalogEntries) {
			if (!entry?.id) {
				continue;
			}
			labelMap[entry.id] = entry.label || entry.id;
		}
	}
	return labelMap;
};

dinext_project_evaluation.project_scoring_report.buildMetricOptionLabelMap = function (catalogEntries, optionIds) {
	const labelMap = dinext_project_evaluation.project_scoring_report.disambiguateMetricDropdownLabels(
		catalogEntries
	);
	for (const optionId of optionIds) {
		if (!labelMap[optionId]) {
			labelMap[optionId] = optionId;
		}
	}
	return labelMap;
};

dinext_project_evaluation.project_scoring_report.buildMetricSelectOptions = function (catalogEntries, optionIds) {
	const namespace = dinext_project_evaluation.project_scoring_report;
	const labelMap = namespace.buildMetricOptionLabelMap(catalogEntries, optionIds);
	const grouped = namespace.partitionMetricEntriesByGroup(catalogEntries, optionIds);
	const selectOptions = [];

	for (const groupSpec of PROJECT_SCORING_METRIC_GROUP_ORDER) {
		const sortedEntries = namespace.sortMetricEntriesByDisplayLabel(
			grouped[groupSpec.key],
			labelMap
		);
		if (!sortedEntries.length) {
			continue;
		}
		selectOptions.push({
			label: `#${groupSpec.label}`,
			value: "",
		});
		for (const entry of sortedEntries) {
			selectOptions.push({
				value: entry.id,
				label: labelMap[entry.id] || entry.id,
			});
		}
	}

	const criterionEntries = namespace.sortMetricEntriesByDisplayLabel(grouped.criterion, labelMap);
	for (const entry of criterionEntries) {
		selectOptions.push({
			value: entry.id,
			label: labelMap[entry.id] || entry.id,
		});
	}

	const knownIds = new Set(
		selectOptions.map((option) => option.value).filter((value) => value != null && value !== "")
	);
	const orphanIds = (optionIds || []).filter((optionId) => !knownIds.has(optionId));
	const orphanEntries = orphanIds.map((optionId) => ({
		id: optionId,
		label: labelMap[optionId] || optionId,
	}));
	const sortedOrphans = namespace.sortMetricEntriesByDisplayLabel(orphanEntries, labelMap);
	for (const entry of sortedOrphans) {
		selectOptions.push({
			value: entry.id,
			label: labelMap[entry.id] || entry.id,
		});
	}

	return selectOptions;
};

dinext_project_evaluation.project_scoring_report.handleMetricControlChange = function (report, fieldname, value) {
	if (report?._dinextProjectScoringSyncingControls) {
		return;
	}
	const filter = report?.get_filter?.(fieldname);
	const nextValue = String(value ?? "").trim();
	if (!filter || String(filter.get_value?.() ?? "").trim() === nextValue) {
		return;
	}

	const refreshReport = () => {
		if (typeof report?.refresh === "function") {
			return report.refresh(true);
		}
	};
	const previousNoRefresh = report?._no_refresh;
	if (report) {
		report._no_refresh = true;
	}
	const setResult = filter.set_value?.(nextValue);
	const finish = () => {
		if (report) {
			report._no_refresh = previousNoRefresh;
		}
		return refreshReport();
	};
	if (setResult && typeof setResult.then === "function") {
		return setResult.then(finish);
	}
	return finish();
};

dinext_project_evaluation.project_scoring_report.ensureMetricControlInstances = function (report, mount) {
	if (report?._dinextProjectScoringMetricControls) {
		return report._dinextProjectScoringMetricControls;
	}
	const controlsDom = mount.find(".project-scoring-report-controls").get(0);
	if (!controlsDom || typeof frappe.ui?.form?.make_control !== "function") {
		return null;
	}
	const namespace = dinext_project_evaluation.project_scoring_report;
	const controls = {};
	controlsDom.innerHTML = "";
	for (const spec of PROJECT_SCORING_METRIC_CONTROLS) {
		const wrapper = document.createElement("div");
		wrapper.className = "project-scoring-report-control";
		controlsDom.appendChild(wrapper);
		const control = frappe.ui.form.make_control({
			parent: $(wrapper),
			df: {
				label: spec.label,
				fieldname: spec.fieldname,
				fieldtype: "Select",
				options: "",
				input_class: "input-sm",
				change() {
					if (report._dinextProjectScoringSyncingControls) {
						return;
					}
					namespace.handleMetricControlChange(report, spec.fieldname, this.get_value());
				},
			},
			value: "",
			render_input: true,
		});
		controls[spec.fieldname] = control;
	}
	report._dinextProjectScoringMetricControls = controls;
	return controls;
};

dinext_project_evaluation.project_scoring_report.syncMetricControlValues = function (
	report,
	catalog,
	controls,
	currentConfig
) {
	if (!report || !controls) {
		return;
	}
	const namespace = dinext_project_evaluation.project_scoring_report;
	const defaults = catalog?.defaults || {};
	const previousNoRefresh = report._no_refresh;
	report._dinextProjectScoringSyncingControls = true;
	report._no_refresh = true;
	try {
		for (const spec of PROJECT_SCORING_METRIC_CONTROLS) {
			const control = controls[spec.fieldname];
			if (!control) {
				continue;
			}
			const filter = report.get_filter?.(spec.fieldname);
			const optionIds = namespace.getMetricControlOptionIds(filter);
			const selectOptions = namespace.buildMetricSelectOptions(catalog?.[spec.catalogKey], optionIds);
			const currentValue =
				filter?.get_value?.() || currentConfig?.[spec.fieldname] || defaults[spec.fieldname] || optionIds[0] || "";
			const resolvedValue = optionIds.includes(currentValue) ? currentValue : optionIds[0] || "";

			control.df.options = selectOptions;
			if (typeof control.refresh === "function") {
				control.refresh();
			}
			if (filter && filter.get_value?.() !== resolvedValue && typeof filter.set_value === "function") {
				filter.set_value(resolvedValue);
			}
			if (control.get_value?.() !== resolvedValue && typeof control.set_value === "function") {
				control.set_value(resolvedValue);
			}
		}
	} finally {
		report._no_refresh = previousNoRefresh;
		report._dinextProjectScoringSyncingControls = false;
	}
};

dinext_project_evaluation.project_scoring_report.renderMetricControls = function (
	report,
	mount,
	catalog,
	currentConfig
) {
	if (!report || !mount?.length) {
		return;
	}
	const controls = dinext_project_evaluation.project_scoring_report.ensureMetricControlInstances(report, mount);
	if (!controls) {
		return;
	}
	dinext_project_evaluation.project_scoring_report.syncMetricControlValues(
		report,
		catalog,
		controls,
		currentConfig
	);
};

dinext_project_evaluation.project_scoring_report.getBubbleSizeLabel = function (point) {
	const size = point?.size;
	if (!size) {
		return "";
	}
	const value = size.value;
	if (value == null || value === "") {
		return "";
	}
	const display = String(size.display || "").trim();
	return display && display !== "N/A" ? display : "";
};

dinext_project_evaluation.project_scoring_report.buildChartOptions = function (points, bubbleChart, colorMap) {
	const xAxis = bubbleChart?.axes?.x || { axis_type: "value", label: __("X Axis") };
	const yAxis = bubbleChart?.axes?.y || { axis_type: "value", label: __("Y Axis") };
	const labelColor = dinext_project_evaluation.project_scoring_report.getThemeVariableColor(
		"--text-color",
		dinext_project_evaluation.project_scoring_report.getFallbackColor()
	);
	return {
		animation: false,
		backgroundColor: "transparent",
		grid: {
			left: 60,
			right: 24,
			top: 40,
			bottom: 56,
		},
		toolbox: {
			right: 8,
			top: 4,
			itemSize: 16,
			iconStyle: {
				borderColor: dinext_project_evaluation.project_scoring_report.getThemeVariableColor(
					"--text-muted",
					dinext_project_evaluation.project_scoring_report.getFallbackColor()
				),
			},
			feature: {
				saveAsImage: {
					title: __("Save as Image"),
					name: "project-scoring-report",
					pixelRatio: 2,
					backgroundColor: dinext_project_evaluation.project_scoring_report.getThemeVariableColor(
						"--card-bg",
						"#ffffff"
					),
				},
			},
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
					point.color
						? `${frappe.utils.escape_html(point.color.metric_label || __("Color"))}: ${frappe.utils.escape_html(point.color.display || point.color.label || "")}`
						: "",
				].filter(Boolean);
				return fields.join("<br>");
			},
		},
		xAxis: dinext_project_evaluation.project_scoring_report.buildAxisOption(xAxis, 32),
		yAxis: dinext_project_evaluation.project_scoring_report.buildAxisOption(yAxis, 46),
		series: [
			{
				type: "scatter",
				data: points.map((point) => ({
					value: [
						dinext_project_evaluation.project_scoring_report.getPointAxisValue(point.x, xAxis),
						dinext_project_evaluation.project_scoring_report.getPointAxisValue(point.y, yAxis),
						Number(point.size?.normalized ?? 18),
					],
					point,
					symbolSize: Number(point.size?.normalized ?? 18),
					itemStyle: {
						color: dinext_project_evaluation.project_scoring_report.resolveColor(point.color, colorMap),
						opacity: 0.78,
					},
				})),
				label: {
					show: true,
					position: "top",
					distance: 4,
					fontSize: 11,
					color: labelColor,
					hideOverlap: true,
					formatter(params) {
						return dinext_project_evaluation.project_scoring_report.getBubbleSizeLabel(params.data?.point);
					},
				},
				labelLayout: {
					hideOverlap: true,
				},
				emphasis: {
					scale: true,
				},
			},
		],
	};
};

dinext_project_evaluation.project_scoring_report.buildAxisOption = function (axis, nameGap) {
	const axisType = axis?.axis_type || "value";
	const option = {
		name: axis?.label || "",
		nameLocation: "middle",
		nameGap,
		type: axisType,
		scale: axisType !== "category",
	};
	if (axisType === "category") {
		option.data = Array.isArray(axis?.categories) ? axis.categories : [];
		option.axisLabel = { interval: 0, hideOverlap: true };
	}
	if (axisType !== "category") {
		if (axis?.min != null) {
			option.min = axis.min;
		}
		if (axis?.max != null) {
			option.max = axis.max;
		}
	}
	return option;
};

dinext_project_evaluation.project_scoring_report.getPointAxisValue = function (metricPoint, axis) {
	if (!metricPoint) {
		return null;
	}
	const axisType = axis?.axis_type || "value";
	if (axisType === "category") {
		return metricPoint.display || metricPoint.value || "";
	}
	if (axisType === "time") {
		return metricPoint.sort_value ?? metricPoint.value ?? null;
	}
	return Number(metricPoint.value ?? 0);
};

dinext_project_evaluation.project_scoring_report.getColorIdentity = function (colorLike) {
	if (!colorLike) {
		return "";
	}
	if (typeof colorLike === "string") {
		return colorLike;
	}
	return colorLike.color_key || colorLike.token || "";
};

dinext_project_evaluation.project_scoring_report.collectColorIdentities = function (points, legend) {
	const identities = [];
	const legendItems = Array.isArray(legend?.items) ? legend.items : [];
	for (const item of legendItems) {
		identities.push(dinext_project_evaluation.project_scoring_report.getColorIdentity(item));
	}
	for (const point of Array.isArray(points) ? points : []) {
		identities.push(dinext_project_evaluation.project_scoring_report.getColorIdentity(point.color));
	}
	return identities.filter(Boolean);
};

dinext_project_evaluation.project_scoring_report.generateDistinctColor = function (index, total) {
	const isDark = dinext_project_evaluation.project_scoring_report.getThemeName() === "dark";
	const safeTotal = Math.max(Number(total) || 1, 1);
	const hue = (index * (360 / safeTotal)) % 360;
	const lightnessCycle = isDark ? [62, 55, 68] : [48, 42, 54];
	const saturationCycle = isDark ? [70, 62, 78] : [60, 52, 68];
	const lightness = lightnessCycle[index % lightnessCycle.length];
	const saturation = saturationCycle[index % saturationCycle.length];
	return `hsl(${hue.toFixed(2)}, ${saturation}%, ${lightness}%)`;
};

dinext_project_evaluation.project_scoring_report.buildUniqueColorMap = function (identities) {
	const uniqueIdentities = [...new Set((identities || []).filter(Boolean))].sort();
	const colorMap = {};
	uniqueIdentities.forEach((identity, index) => {
		colorMap[identity] = dinext_project_evaluation.project_scoring_report.generateDistinctColor(
			index,
			uniqueIdentities.length
		);
	});
	return colorMap;
};

dinext_project_evaluation.project_scoring_report.resolveColor = function (colorLike, colorMap) {
	const identity = dinext_project_evaluation.project_scoring_report.getColorIdentity(colorLike);
	if (!identity) {
		return dinext_project_evaluation.project_scoring_report.getFallbackColor();
	}
	const semanticPalette = dinext_project_evaluation.project_scoring_report.getPalette();
	if (semanticPalette[identity]) {
		return semanticPalette[identity];
	}
	if (colorMap?.[identity]) {
		return colorMap[identity];
	}
	return dinext_project_evaluation.project_scoring_report.getFallbackColor();
};

dinext_project_evaluation.project_scoring_report.getFallbackColor = function () {
	return dinext_project_evaluation.project_scoring_report.getThemeName() === "dark" ? "#8f9aa8" : "#6a7d92";
};

dinext_project_evaluation.project_scoring_report.resolveColorToken = function (token, colorMap) {
	return dinext_project_evaluation.project_scoring_report.resolveColor(token, colorMap);
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

dinext_project_evaluation.project_scoring_report.getThemeVariableColor = function (variableName, fallback) {
	if (
		typeof getComputedStyle !== "function" ||
		!document ||
		!document.documentElement ||
		!variableName
	) {
		return fallback;
	}
	const value = getComputedStyle(document.documentElement).getPropertyValue(variableName).trim();
	return value || fallback;
};
