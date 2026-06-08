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
	dinext_project_evaluation.project_scoring_report.renderMetricControls(
		report,
		mount,
		message.metric_catalog,
		bubbleChart.config
	);

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

dinext_project_evaluation.project_scoring_report.openProject = function (projectName) {
	const name = String(projectName || "").trim();
	if (!name) {
		return;
	}
	frappe.set_route("Form", PROJECT_DOCTYPE, name);
};

dinext_project_evaluation.project_scoring_report.handleBubbleChartClick = function (params) {
	const point = params?.data?.point || {};
	const scorecardName = String(point.scorecard || "").trim();
	if (scorecardName) {
		dinext_project_evaluation.project_scoring_report.openScorecard(scorecardName);
		return;
	}
	const projectName = String(point.project || "").trim();
	if (projectName) {
		dinext_project_evaluation.project_scoring_report.openProject(projectName);
	}
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
	const updateSelect = (fieldname, entries) => {
		const filter = report.get_filter?.(fieldname);
		if (!filter?.df) {
			return;
		}
		const options = Array.isArray(entries) && entries.length ? entries.map((entry) => entry.id).join("\n") : "";
		filter.df.options = options;
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
	return [];
};

dinext_project_evaluation.project_scoring_report.getMetricDropdownSourcePrefix = function (entry) {
	if (entry?.source_kind === "project_field") {
		return __("Project");
	}
	if (entry?.source_kind === "scorecard_field") {
		return __("Project Evaluation");
	}
	return null;
};

dinext_project_evaluation.project_scoring_report.disambiguateMetricDropdownLabels = function (catalogEntries) {
	const labelCounts = {};
	if (Array.isArray(catalogEntries)) {
		for (const entry of catalogEntries) {
			if (!entry?.id) {
				continue;
			}
			const baseLabel = entry.label || entry.id;
			labelCounts[baseLabel] = (labelCounts[baseLabel] || 0) + 1;
		}
	}

	const disambiguated = {};
	if (Array.isArray(catalogEntries)) {
		for (const entry of catalogEntries) {
			if (!entry?.id) {
				continue;
			}
			const baseLabel = entry.label || entry.id;
			if ((labelCounts[baseLabel] || 0) <= 1) {
				disambiguated[entry.id] = baseLabel;
				continue;
			}
			const prefix = dinext_project_evaluation.project_scoring_report.getMetricDropdownSourcePrefix(entry);
			disambiguated[entry.id] = prefix ? `${prefix} - ${baseLabel}` : baseLabel;
		}
	}
	return disambiguated;
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
	const labelMap = dinext_project_evaluation.project_scoring_report.buildMetricOptionLabelMap(
		catalogEntries,
		optionIds
	);
	return optionIds.map((optionId) => ({
		value: optionId,
		label: labelMap[optionId] || optionId,
	}));
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

dinext_project_evaluation.project_scoring_report.buildChartOptions = function (points, bubbleChart) {
	const xAxis = bubbleChart?.axes?.x || { axis_type: "value", label: __("X Axis") };
	const yAxis = bubbleChart?.axes?.y || { axis_type: "value", label: __("Y Axis") };
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
