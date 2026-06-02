from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
from dinext_project_evaluation.scoring.profile_stages import stages_by_criterion


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
	message: str | None = None


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
	stage_map = stages_by_criterion(profile)
	profile_criteria = [_profile_criterion(row, stage_map) for row in _children(profile, "criteria")]
	applicable_criteria = filter_applicable_criteria(profile_criteria, _value(scorecard, "stage_at_evaluation"))

	inputs = {}
	item_rows_by_criterion = {item.criterion: item for item in _children(scorecard, "items") if getattr(item, "criterion", None)}
	calculated_items = {}

	for profile_criterion in applicable_criteria:
		item_row = item_rows_by_criterion.get(profile_criterion.code)
		if item_row is None:
			continue

		criterion = criteria_by_name[profile_criterion.code]
		normalized_score = normalize_item(criterion, item_row)
		inputs[profile_criterion.code] = CriterionInput(
			normalized_score=normalized_score,
			raw_value=_value(item_row, "raw_value"),
			raw_numeric_value=_value(item_row, "raw_numeric_value"),
		)
		calculated_items[profile_criterion.code] = CalculatedItem(
			criterion=profile_criterion.code,
			criterion_code=_value(criterion, "criterion_code") or profile_criterion.code,
			raw_value=_value(item_row, "raw_value"),
			raw_numeric_value=_value(item_row, "raw_numeric_value"),
			normalized_score=normalized_score,
			weighted_score=normalized_score * profile_criterion.weight,
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
	return ScorecardCalculation(
		integral_score=result.integral_score,
		gate_pass=result.gate_pass,
		messages=result.messages,
		items=calculated_items,
		applicable_criteria=applicable_criteria,
	)


def normalize_item(criterion: Any, item_row: Any) -> float:
	input_type = _value(criterion, "input_type")
	if input_type == "Scale":
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


def _profile_criterion(row: Any, stage_map: dict[str, list[str]]) -> ProfileCriterion:
	return ProfileCriterion(
		code=row.criterion,
		weight=float(row.weight or 0),
		requirement_level=row.requirement_level or "Desired",
		stages=stage_map.get(row.criterion, []),
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
