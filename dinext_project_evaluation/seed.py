import frappe


LIKERT_SCALE = [
	("0 - нет соответствия", 0, "Критерий не выполняется или данных нет"),
	("1 - очень низко", 1, "Минимальное соответствие"),
	("2 - низко", 2, "Слабое соответствие"),
	("3 - средне", 3, "Приемлемое соответствие"),
	("4 - высоко", 4, "Хорошее соответствие"),
	("5 - отлично", 5, "Полное соответствие"),
]


DEFAULT_GROUPS = [
	("Strategy", "Strategy"),
	("Benefits", "Benefits"),
	("Market", "Market"),
	("Finance", "Finance"),
	("Risks", "Risks"),
	("Resources", "Resources"),
	("Regulatory", "Regulatory"),
	("Priority", "Priority"),
	("Innovation", "Innovation"),
	("Environment", "Environment"),
]


DEFAULT_CRITERIA = [
	("STR_ALIGN", "Соответствие стратегии и целям компании", "Strategy", "Scale", "higher_is_better"),
	("BEN_FIN", "Финансовые выгоды", "Benefits", "Scale", "higher_is_better"),
	("BEN_NONFIN", "Нефинансовые выгоды", "Benefits", "Scale", "higher_is_better"),
	("MKT_SHARE", "Доля рынка / новые рынки", "Market", "Scale", "higher_is_better"),
	("COST", "Стоимость / инвестиции", "Resources", "Currency", "lower_is_better"),
	("DEP_INT", "Внутренние и внешние зависимости", "Environment", "Scale", "lower_is_better"),
	("RISK_IMP", "Воздействие риска", "Risks", "Scale", "lower_is_better"),
	("RISK_PROB", "Вероятность риска", "Risks", "Scale", "lower_is_better"),
	("REG", "Соответствие нормативным требованиям", "Regulatory", "Scale", "higher_is_better"),
	("CAP_HUM_TECH", "Человеческие и технические возможности", "Resources", "Scale", "higher_is_better"),
	("URGENCY", "Срочность", "Priority", "Scale", "higher_is_better"),
	("NPV", "Чистый дисконтированный доход (NPV)", "Finance", "Currency", "higher_is_better"),
	("IRR", "Внутренняя норма доходности (IRR)", "Finance", "Percent", "higher_is_better"),
	("PP", "Период окупаемости (PP)", "Finance", "Number", "lower_is_better"),
	("PI", "Индекс рентабельности (PI)", "Finance", "Number", "higher_is_better"),
	("ECV", "Ожидаемая коммерческая стоимость (ECV)", "Finance", "Currency", "higher_is_better"),
	("PATENT", "Патентоспособность", "Innovation", "Scale", "higher_is_better"),
	("RD_COST", "Затраты на НИОКР", "Innovation", "Currency", "lower_is_better"),
	("MFG_COST", "Затраты на производство", "Innovation", "Currency", "lower_is_better"),
	("TECH_SUCCESS", "Вероятность успешного завершения работ", "Innovation", "Percent", "higher_is_better"),
	("SALES_POT", "Возможность сбыта", "Innovation", "Scale", "higher_is_better"),
]


DEFAULT_PROFILE_WEIGHTS = {
	"STR_ALIGN": 3,
	"BEN_FIN": 2,
	"BEN_NONFIN": 1,
	"MKT_SHARE": 1,
	"COST": 1,
	"DEP_INT": 1,
	"RISK_IMP": 2,
	"RISK_PROB": 2,
	"REG": 2,
	"CAP_HUM_TECH": 1,
	"URGENCY": 1,
	"NPV": 2,
	"IRR": 1,
	"PP": 1,
	"PI": 1,
	"ECV": 2,
	"PATENT": 1,
	"RD_COST": 1,
	"MFG_COST": 1,
	"TECH_SUCCESS": 2,
	"SALES_POT": 2,
}


def seed_default_scoring_model():
	for group_code, group_name in DEFAULT_GROUPS:
		_upsert_criterion_group(group_code, group_name)
	for code, title, group, input_type, direction in DEFAULT_CRITERIA:
		_upsert_criterion(code, title, group, input_type, direction)
	_upsert_default_profile()
	frappe.db.commit()


def _upsert_criterion_group(group_code, group_name):
	if frappe.db.exists("Project Scoring Criterion Group", group_code):
		doc = frappe.get_doc("Project Scoring Criterion Group", group_code)
	else:
		doc = frappe.new_doc("Project Scoring Criterion Group")
		doc.group_code = group_code
	doc.group_name = group_name
	doc.enabled = 1
	doc.save(ignore_permissions=True)


def _upsert_criterion(code, title, group, input_type, direction):
	doc = frappe.get_doc("Project Scoring Criterion", code) if frappe.db.exists("Project Scoring Criterion", code) else frappe.new_doc("Project Scoring Criterion")
	doc.criterion_code = code
	doc.criterion_name = title
	doc.criterion_group = group
	doc.input_type = input_type
	doc.influence_direction = direction
	doc.enabled = 1
	doc.min_value = 0
	doc.max_value = 100 if input_type in {"Percent", "Currency", "Number"} else 5
	doc.set("scale_rows", [])
	if input_type == "Scale":
		for label, score, phrases in LIKERT_SCALE:
			doc.append("scale_rows", {"scale_label": label, "score": score, "sort_order": score, "key_phrases": phrases})
	doc.save(ignore_permissions=True)


def _upsert_default_profile():
	profile_name = "Default Project Scoring Profile"
	doc = frappe.get_doc("Project Scoring Profile", profile_name) if frappe.db.exists("Project Scoring Profile", profile_name) else frappe.new_doc("Project Scoring Profile")
	if doc.is_new():
		doc.name = profile_name
	doc.profile_name = profile_name
	doc.status = "Active"
	doc.description = "Типовой профиль скоринга проектов Dinext на основе стартового каталога критериев."
	doc.set("criteria", [])
	for code, weight in DEFAULT_PROFILE_WEIGHTS.items():
		is_mandatory_gate = code in {"STR_ALIGN", "REG"}
		doc.append(
			"criteria",
			{
				"criterion": code,
				"weight": weight,
				"requirement_level": "Mandatory" if is_mandatory_gate else "Desired",
				"minimum_normalized_score": 0.4 if is_mandatory_gate else None,
				"minimum_raw_value": None,
				"maximum_raw_value": None,
			},
		)
	doc.save(ignore_permissions=True)
