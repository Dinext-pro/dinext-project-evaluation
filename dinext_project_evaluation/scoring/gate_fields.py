from __future__ import annotations

from typing import Any

NUMERIC_INPUT_TYPES = frozenset({"Number", "Currency", "Percent"})
GATE_FIELD_NAMES = ("minimum_normalized_score", "minimum_raw_value", "maximum_raw_value")
# Frappe Float grids often serialize cleared optional fields as 0. For maximum_raw_value,
# 0 is treated as unset because blank fields are the common case and explicit max=0 is rare.
ZERO_AS_UNSET_GATE_FIELDS = frozenset({"maximum_raw_value"})


def applicable_gate_fields(requirement_level: str | None, input_type: str | None) -> set[str]:
	if requirement_level != "Mandatory":
		return set()

	fields = {"minimum_normalized_score"}
	if input_type in NUMERIC_INPUT_TYPES:
		fields.update({"minimum_raw_value", "maximum_raw_value"})
	return fields


def is_blank_gate_threshold(value: Any) -> bool:
	return value is None or value == "" or (isinstance(value, str) and not value.strip())


def coerce_gate_threshold_value(value: Any, fieldname: str | None = None) -> float | None:
	if is_blank_gate_threshold(value):
		return None

	try:
		numeric = float(value)
	except (TypeError, ValueError):
		return None

	if fieldname in ZERO_AS_UNSET_GATE_FIELDS and numeric == 0:
		return None

	return numeric


def build_gate_rule_values(row: Any, input_type: str | None) -> dict[str, float | None]:
	applicable = applicable_gate_fields(getattr(row, "requirement_level", None), input_type)
	return {
		fieldname: (
			coerce_gate_threshold_value(getattr(row, fieldname, None), fieldname)
			if fieldname in applicable
			else None
		)
		for fieldname in GATE_FIELD_NAMES
	}


def sanitize_profile_criterion_gate_fields(row: Any, input_type: str | None) -> None:
	gate_values = build_gate_rule_values(row, input_type)
	for fieldname, value in gate_values.items():
		setattr(row, fieldname, value)
