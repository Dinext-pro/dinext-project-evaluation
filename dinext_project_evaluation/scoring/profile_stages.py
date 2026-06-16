from __future__ import annotations

from typing import Any


def get_applicable_stages(criterion_row: Any) -> list[str]:
	"""Return stage restriction for a profile criterion row.

	Empty list means the criterion applies to all stages.
	"""
	stage = getattr(criterion_row, "stage", None)
	if stage:
		return [stage]
	return []


def is_profile_row_applicable_to_stage(criterion_row: Any, current_stage: str | None) -> bool:
	stages = get_applicable_stages(criterion_row)
	if not stages:
		return True
	return bool(current_stage and current_stage in stages)


def is_global_profile_row(criterion_row: Any) -> bool:
	return not get_applicable_stages(criterion_row)


def is_stage_specific_profile_row(criterion_row: Any, current_stage: str | None) -> bool:
	stage = getattr(criterion_row, "stage", None)
	return bool(stage and current_stage and stage == current_stage)


def resolve_stage_overridden_profile_rows(criteria: list[Any], current_stage: str | None) -> list[Any]:
	"""Return profile rows applicable to the stage, with stage-specific rows overriding global ones."""
	applicable = [
		row for row in criteria or [] if is_profile_row_applicable_to_stage(row, current_stage)
	]
	selected = _resolve_stage_overridden_rows(
		applicable,
		current_stage,
		get_criterion=lambda row: getattr(row, "criterion", None),
		is_global_row=is_global_profile_row,
		is_stage_specific_row=is_stage_specific_profile_row,
	)
	selected_ids = {id(row) for row in selected}
	return [row for row in criteria or [] if id(row) in selected_ids]


def _resolve_stage_overridden_rows(
	rows: list[Any],
	current_stage: str | None,
	*,
	get_criterion,
	is_global_row,
	is_stage_specific_row,
) -> list[Any]:
	by_criterion: dict[str, list[Any]] = {}
	for row in rows:
		criterion = get_criterion(row)
		if not criterion:
			continue
		by_criterion.setdefault(criterion, []).append(row)

	selected: list[Any] = []
	for grouped_rows in by_criterion.values():
		stage_specific = [row for row in grouped_rows if is_stage_specific_row(row, current_stage)]
		if stage_specific:
			selected.extend(stage_specific)
			continue
		selected.extend([row for row in grouped_rows if is_global_row(row)])
	return selected


def find_duplicate_criterion_stage_pair(criteria: list[Any]) -> tuple[str, str | None] | None:
	seen: set[tuple[str, str]] = set()

	for row in criteria or []:
		criterion = getattr(row, "criterion", None)
		if not criterion:
			continue

		stage_key = getattr(row, "stage", None) or ""
		pair = (criterion, stage_key)
		if pair in seen:
			stage = getattr(row, "stage", None) or None
			return criterion, stage

		seen.add(pair)

	return None
