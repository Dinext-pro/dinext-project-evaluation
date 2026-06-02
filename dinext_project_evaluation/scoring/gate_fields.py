from __future__ import annotations

from typing import Any

NUMERIC_INPUT_TYPES = frozenset({"Number", "Currency", "Percent"})
GATE_FIELD_NAMES = ("minimum_normalized_score", "minimum_raw_value", "maximum_raw_value")


def applicable_gate_fields(requirement_level: str | None, input_type: str | None) -> set[str]:
	if requirement_level != "Mandatory":
		return set()

	fields = {"minimum_normalized_score"}
	if input_type in NUMERIC_INPUT_TYPES:
		fields.update({"minimum_raw_value", "maximum_raw_value"})
	return fields


def sanitize_profile_criterion_gate_fields(row: Any, input_type: str | None) -> None:
	applicable = applicable_gate_fields(getattr(row, "requirement_level", None), input_type)
	for fieldname in GATE_FIELD_NAMES:
		if fieldname not in applicable:
			setattr(row, fieldname, None)
