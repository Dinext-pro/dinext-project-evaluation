from __future__ import annotations

from dataclasses import dataclass, field


class ScoringConfigurationError(ValueError):
	pass


@dataclass(frozen=True)
class ScaleCriterion:
	scores: list[float]
	influence_direction: str = "higher_is_better"


@dataclass(frozen=True)
class NumericCriterion:
	min_value: float
	max_value: float
	influence_direction: str = "higher_is_better"


@dataclass(frozen=True)
class BoolCriterion:
	true_score: float = 1
	false_score: float = 0
	influence_direction: str = "higher_is_better"


@dataclass(frozen=True)
class GateRule:
	minimum_normalized_score: float | None = None
	minimum_raw_value: float | None = None
	maximum_raw_value: float | None = None


@dataclass(frozen=True)
class ProfileCriterion:
	code: str
	weight: float
	requirement_level: str = "Desired"
	stages: list[str] = field(default_factory=list)
	gate_rule: GateRule | None = None


@dataclass(frozen=True)
class CriterionInput:
	normalized_score: float
	raw_value: str | None = None
	raw_numeric_value: float | None = None


@dataclass(frozen=True)
class ScorecardResult:
	integral_score: float
	gate_pass: bool
	messages: list[str]


def normalize_scale(criterion: ScaleCriterion, score: float) -> float:
	if not criterion.scores:
		raise ScoringConfigurationError("Scale criterion must define at least one score")

	return _apply_direction(_normalize_between(score, min(criterion.scores), max(criterion.scores)), criterion.influence_direction)


def normalize_numeric(criterion: NumericCriterion, value: float) -> float:
	return _apply_direction(
		_normalize_between(value, criterion.min_value, criterion.max_value),
		criterion.influence_direction,
	)


def normalize_bool(criterion: BoolCriterion, value: bool) -> float:
	score = criterion.true_score if value else criterion.false_score
	return _apply_direction(
		_normalize_between(score, min(criterion.true_score, criterion.false_score), max(criterion.true_score, criterion.false_score)),
		criterion.influence_direction,
	)


def filter_applicable_criteria(criteria: list[ProfileCriterion], current_stage: str | None) -> list[ProfileCriterion]:
	applicable = [
		criterion for criterion in criteria if not criterion.stages or current_stage in criterion.stages
	]
	return _resolve_stage_overridden_profile_criteria(applicable, current_stage)


def _resolve_stage_overridden_profile_criteria(
	criteria: list[ProfileCriterion],
	current_stage: str | None,
) -> list[ProfileCriterion]:
	by_code: dict[str, list[ProfileCriterion]] = {}
	for criterion in criteria:
		by_code.setdefault(criterion.code, []).append(criterion)

	selected: list[ProfileCriterion] = []
	for grouped_criteria in by_code.values():
		stage_specific = [
			criterion
			for criterion in grouped_criteria
			if criterion.stages and current_stage and criterion.stages == [current_stage]
		]
		if stage_specific:
			selected.extend(stage_specific)
			continue
		selected.extend([criterion for criterion in grouped_criteria if not criterion.stages])
	return selected


def calculate_scorecard(criteria: list[ProfileCriterion], inputs: dict[str, CriterionInput]) -> ScorecardResult:
	total_weight = sum(criterion.weight for criterion in criteria if criterion.weight > 0)
	if total_weight <= 0:
		raise ScoringConfigurationError("Applicable profile criteria must have a positive weight sum")

	weighted_sum = 0.0
	messages = []

	for criterion in criteria:
		criterion_input = inputs.get(criterion.code)
		if criterion_input is None:
			if _is_mandatory(criterion):
				messages.append(f"Missing mandatory value for {criterion.code}")
			continue

		normalized_score = _clip(criterion_input.normalized_score)
		weighted_sum += normalized_score * criterion.weight
		messages.extend(_gate_messages(criterion, criterion_input, normalized_score))

	return ScorecardResult(
		integral_score=weighted_sum / total_weight,
		gate_pass=not messages,
		messages=messages,
	)


def _normalize_between(value: float, min_value: float, max_value: float) -> float:
	if max_value == min_value:
		raise ScoringConfigurationError("Normalization range must not be empty")

	return _clip((value - min_value) / (max_value - min_value))


def _apply_direction(normalized_score: float, influence_direction: str) -> float:
	if influence_direction == "higher_is_better":
		return normalized_score
	if influence_direction == "lower_is_better":
		return 1 - normalized_score
	raise ScoringConfigurationError(f"Unsupported influence direction: {influence_direction}")


def _clip(value: float) -> float:
	return min(1.0, max(0.0, value))


def _is_mandatory(criterion: ProfileCriterion) -> bool:
	return criterion.requirement_level == "Mandatory"


def _gate_messages(criterion: ProfileCriterion, criterion_input: CriterionInput, normalized_score: float) -> list[str]:
	if not _is_mandatory(criterion) or criterion.gate_rule is None:
		return []

	messages = []
	if (
		criterion.gate_rule.minimum_normalized_score is not None
		and normalized_score < criterion.gate_rule.minimum_normalized_score
	):
		messages.append(
			f"{criterion.code} normalized score {normalized_score:.4f} is below required "
			f"{criterion.gate_rule.minimum_normalized_score:.4f}"
		)
	if (
		criterion.gate_rule.minimum_raw_value is not None
		and criterion_input.raw_numeric_value is not None
		and criterion_input.raw_numeric_value < criterion.gate_rule.minimum_raw_value
	):
		messages.append(
			f"{criterion.code} raw value {criterion_input.raw_numeric_value:.4f} is below required "
			f"{criterion.gate_rule.minimum_raw_value:.4f}"
		)
	if (
		criterion.gate_rule.maximum_raw_value is not None
		and criterion_input.raw_numeric_value is not None
		and criterion_input.raw_numeric_value > criterion.gate_rule.maximum_raw_value
	):
		messages.append(
			f"{criterion.code} raw value {criterion_input.raw_numeric_value:.4f} is above allowed "
			f"{criterion.gate_rule.maximum_raw_value:.4f}"
		)

	return messages
