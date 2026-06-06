from __future__ import annotations

from typing import Any

NUMERIC_INPUT_TYPES = frozenset({"Number", "Currency", "Percent"})
GATE_FIELD_NAMES = ("minimum_normalized_score", "minimum_raw_value", "maximum_raw_value")
GATE_FIELD_LABELS = {
	"minimum_normalized_score": "Minimum Normalized Score",
	"minimum_raw_value": "Minimum Raw Value",
	"maximum_raw_value": "Maximum Raw Value",
}


def applicable_gate_fields(requirement_level: str | None, input_type: str | None) -> set[str]:
	if requirement_level != "Mandatory":
		return set()

	fields = {"minimum_normalized_score"}
	if input_type in NUMERIC_INPUT_TYPES:
		fields.update({"minimum_raw_value", "maximum_raw_value"})
	return fields


def is_blank_gate_threshold(value: Any) -> bool:
	return value is None or value == "" or (isinstance(value, str) and not value.strip())


def format_gate_threshold_storage_value(numeric: float) -> str:
	if numeric == int(numeric):
		return str(int(numeric))
	return format(numeric, "f").rstrip("0").rstrip(".")


def coerce_gate_threshold_value(value: Any, fieldname: str | None = None, row: Any = None) -> float | None:
	if is_blank_gate_threshold(value):
		return None

	try:
		return float(str(value).strip())
	except (TypeError, ValueError):
		return None


def validate_profile_criterion_gate_fields(row: Any, input_type: str | None) -> list[str]:
	applicable = applicable_gate_fields(getattr(row, "requirement_level", None), input_type)
	errors: list[str] = []
	criterion = getattr(row, "criterion", None) or "row"

	for fieldname in GATE_FIELD_NAMES:
		if fieldname not in applicable:
			continue

		value = getattr(row, fieldname, None)
		if is_blank_gate_threshold(value):
			continue

		if coerce_gate_threshold_value(value, fieldname, row) is None:
			label = GATE_FIELD_LABELS[fieldname]
			errors.append(f"Criterion {criterion}: {label} must be numeric.")

	return errors


def build_gate_rule_values(row: Any, input_type: str | None) -> dict[str, float | None]:
	applicable = applicable_gate_fields(getattr(row, "requirement_level", None), input_type)
	return {
		fieldname: (
			coerce_gate_threshold_value(getattr(row, fieldname, None), fieldname, row)
			if fieldname in applicable
			else None
		)
		for fieldname in GATE_FIELD_NAMES
	}


def sanitize_profile_criterion_gate_fields(row: Any, input_type: str | None) -> None:
	applicable = applicable_gate_fields(getattr(row, "requirement_level", None), input_type)

	for fieldname in GATE_FIELD_NAMES:
		if fieldname not in applicable:
			setattr(row, fieldname, None)
			continue

		value = getattr(row, fieldname, None)
		if is_blank_gate_threshold(value):
			setattr(row, fieldname, None)
			continue

		coerced = coerce_gate_threshold_value(value, fieldname, row)
		if coerced is None:
			setattr(row, fieldname, None)
		else:
			setattr(row, fieldname, format_gate_threshold_storage_value(coerced))
