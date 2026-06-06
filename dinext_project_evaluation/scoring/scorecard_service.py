from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from frappe.utils import cint

from dinext_project_evaluation.scoring.criterion_config import (
	effective_scale_type,
	item_has_input_value,
	item_missing_mandatory_value,
	item_missing_required_comment,
	scorecard_has_missing_required_items,
	scorecard_validation_error_message,
)
from dinext_project_evaluation.scoring.engine import (
	BoolCriterion,
	CriterionInput,
	GateRule,
	NumericCriterion,
	ProfileCriterion,
	ScaleCriterion,
	calculate_scorecard,
	filter_applicable_criteria,
	normalize_bool,
	normalize_numeric,
	normalize_scale,
)
from dinext_project_evaluation.scoring.profile_stages import get_applicable_stages


@dataclass(frozen=True)
class CalculatedItem:
	criterion: str
	criterion_code: str
	raw_value: str | None
	raw_numeric_value: float | None
	normalized_score: float
	weighted_score: float
	weight: float
	gate_pass: bool


@dataclass(frozen=True)
class ScorecardCalculation:
	integral_score: float
	gate_pass: bool
	messages: list[str]
	items: dict[str, CalculatedItem]
	applicable_criteria: list[ProfileCriterion]


def calculate_scorecard_document(
	scorecard: Any,
	profile: Any,
	criteria_by_name: dict[str, Any],
) -> ScorecardCalculation:
	profile_criteria = [_profile_criterion(row) for row in _children(profile, "criteria")]
	applicable_criteria = filter_applicable_criteria(profile_criteria, _value(scorecard, "stage_at_evaluation"))

	inputs = {}
	item_rows_by_criterion = {item.criterion: item for item in _children(scorecard, "items") if getattr(item, "criterion", None)}
	calculated_items = {}

	for profile_criterion in applicable_criteria:
		item_row = item_rows_by_criterion.get(profile_criterion.code)
		criterion = criteria_by_name[profile_criterion.code]
		item_input = _build_item_input(criterion, item_row)
		if item_input:
			inputs[profile_criterion.code] = item_input
		calculated_items[profile_criterion.code] = CalculatedItem(
			criterion=profile_criterion.code,
			criterion_code=_value(criterion, "criterion_code") or profile_criterion.code,
			raw_value=_value(item_row, "raw_value"),
			raw_numeric_value=_coerce_float(_value(item_row, "raw_numeric_value")),
			normalized_score=item_input.normalized_score if item_input else 0,
			weighted_score=(item_input.normalized_score * profile_criterion.weight) if item_input else 0,
			weight=profile_criterion.weight,
			gate_pass=True,
		)

	if not applicable_criteria:
		return ScorecardCalculation(
			integral_score=0,
			gate_pass=False,
			messages=["No applicable scoring criteria for current stage"],
			items={},
			applicable_criteria=[],
		)

	result = calculate_scorecard(applicable_criteria, inputs)
	message_map = _messages_by_criterion(result.messages)
	return ScorecardCalculation(
		integral_score=result.integral_score,
		gate_pass=result.gate_pass,
		messages=result.messages,
		items={
			code: CalculatedItem(
				criterion=item.criterion,
				criterion_code=item.criterion_code,
				raw_value=item.raw_value,
				raw_numeric_value=item.raw_numeric_value,
				normalized_score=item.normalized_score,
				weighted_score=item.weighted_score,
				weight=item.weight,
				gate_pass=not bool(message_map.get(code)),
			)
			for code, item in calculated_items.items()
		},
		applicable_criteria=applicable_criteria,
	)


def normalize_item(criterion: Any, item_row: Any) -> float:
	input_type = _value(criterion, "input_type")
	if input_type == "Scale":
		if effective_scale_type(criterion) == "Interval":
			value = _value(item_row, "raw_numeric_value")
			if value in (None, ""):
				value = _value(item_row, "raw_value")
			return normalize_numeric(
				NumericCriterion(
					min_value=float(_value(criterion, "min_value") or 0),
					max_value=float(_value(criterion, "max_value") or 0),
					influence_direction=_value(criterion, "influence_direction") or "higher_is_better",
				),
				float(value),
			)
		return normalize_scale(
			ScaleCriterion(
				scores=[float(row.score) for row in _children(criterion, "scale_rows")],
				influence_direction=_value(criterion, "influence_direction") or "higher_is_better",
			),
			float(_value(item_row, "raw_value")),
		)
	if input_type in {"Number", "Currency", "Percent"}:
		return normalize_numeric(
			NumericCriterion(
				min_value=float(_value(criterion, "min_value") or 0),
				max_value=float(_value(criterion, "max_value") or 0),
				influence_direction=_value(criterion, "influence_direction") or "higher_is_better",
			),
			float(_value(item_row, "raw_numeric_value") if _value(item_row, "raw_numeric_value") is not None else _value(item_row, "raw_value")),
		)
	if input_type == "Boolean":
		return normalize_bool(
			BoolCriterion(
				true_score=float(_value(criterion, "boolean_true_score") or 1),
				false_score=float(_value(criterion, "boolean_false_score") or 0),
				influence_direction=_value(criterion, "influence_direction") or "higher_is_better",
			),
			str(_value(item_row, "raw_value")).lower() in {"1", "true", "yes", "да"},
		)
	raise ValueError(f"Unsupported criterion input type: {input_type}")


def _build_item_input(criterion: Any, item_row: Any) -> CriterionInput | None:
	if item_row is None:
		return None

	input_type = _value(criterion, "input_type")
	raw_value = _value(item_row, "raw_value")
	raw_numeric_value = _value(item_row, "raw_numeric_value")

	if input_type == "Scale":
		if effective_scale_type(criterion) == "Interval":
			value = raw_numeric_value if raw_numeric_value not in (None, "") else raw_value
			if value in (None, ""):
				return None
			numeric_value = float(value)
			item_row.raw_numeric_value = numeric_value
			return CriterionInput(
				normalized_score=normalize_item(criterion, item_row),
				raw_value=str(raw_value) if raw_value not in (None, "") else str(numeric_value),
				raw_numeric_value=numeric_value,
			)

		if raw_value in (None, ""):
			return None
		return CriterionInput(
			normalized_score=normalize_item(criterion, item_row),
			raw_value=raw_value,
			raw_numeric_value=None,
		)

	if input_type in {"Number", "Currency", "Percent"}:
		value = raw_numeric_value if raw_numeric_value not in (None, "") else raw_value
		if value in (None, ""):
			return None
		numeric_value = float(value)
		item_row.raw_numeric_value = numeric_value
		return CriterionInput(
			normalized_score=normalize_item(criterion, item_row),
			raw_value=raw_value,
			raw_numeric_value=numeric_value,
		)

	if input_type == "Boolean":
		if raw_value in (None, ""):
			return None
		return CriterionInput(
			normalized_score=normalize_item(criterion, item_row),
			raw_value=str(raw_value),
			raw_numeric_value=None,
		)

	raise ValueError(f"Unsupported criterion input type: {input_type}")


def _profile_criterion(row: Any) -> ProfileCriterion:
	return ProfileCriterion(
		code=row.criterion,
		weight=float(row.weight or 0),
		requirement_level=row.requirement_level or "Desired",
		stages=get_applicable_stages(row),
		gate_rule=GateRule(
			minimum_normalized_score=_value(row, "minimum_normalized_score"),
			minimum_raw_value=_value(row, "minimum_raw_value"),
			maximum_raw_value=_value(row, "maximum_raw_value"),
		),
	)


def _children(document: Any, fieldname: str) -> list[Any]:
	return list(getattr(document, fieldname, None) or [])


def _value(document: Any, fieldname: str) -> Any:
	return getattr(document, fieldname, None)


def _messages_by_criterion(messages: list[str]) -> dict[str, list[str]]:
	result: dict[str, list[str]] = {}
	for message in messages:
		code = _criterion_code_from_message(message)
		if not code:
			continue
		result.setdefault(code, []).append(message)
	return result


def _coerce_float(value: Any) -> float | None:
	if value in (None, ""):
		return None
	return float(value)


MANDATORY_MISSING_PREFIX = "Missing mandatory value for "


def missing_mandatory_criterion_codes(messages: list[str]) -> list[str]:
	codes = []
	for message in messages:
		code = _criterion_code_from_message(message)
		if code and message.startswith(MANDATORY_MISSING_PREFIX):
			codes.append(code)
	return codes


def _criterion_code_from_message(message: str) -> str | None:
	if message.startswith(MANDATORY_MISSING_PREFIX):
		return message[len(MANDATORY_MISSING_PREFIX) :].strip() or None

	parts = message.split(" ", 1)
	return parts[0] if parts else None
