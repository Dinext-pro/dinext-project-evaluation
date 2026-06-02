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
