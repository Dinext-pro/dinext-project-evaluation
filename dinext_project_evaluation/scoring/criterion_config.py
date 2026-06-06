from __future__ import annotations

from typing import Any

import frappe
from frappe import _

NUMERIC_INPUT_TYPES = frozenset({"Number", "Currency", "Percent"})
SUPPORTED_INPUT_TYPES = frozenset({"Scale", "Number", "Currency", "Percent", "Boolean"})
SUPPORTED_INFLUENCE_DIRECTIONS = frozenset({"higher_is_better", "lower_is_better"})
SUPPORTED_SCALE_TYPES = frozenset({"Discrete", "Interval"})

CRITERION_CONFIG_FIELDS = (
	"scale_type",
	"min_value",
	"max_value",
	"boolean_true_score",
	"boolean_false_score",
	"scale_rows",
)


def effective_scale_type(criterion: Any) -> str:
	input_type = _value(criterion, "input_type")
	if input_type != "Scale":
		return ""
	return _value(criterion, "scale_type") or "Discrete"


def get_field_visibility(criterion: Any) -> dict[str, bool]:
	input_type = _value(criterion, "input_type")
	scale_type = effective_scale_type(criterion)

	if input_type == "Scale":
		return {
			"scale_type": True,
			"scale_rows": scale_type == "Discrete",
			"min_value": scale_type == "Interval",
			"max_value": scale_type == "Interval",
			"boolean_true_score": False,
			"boolean_false_score": False,
		}
	if input_type in NUMERIC_INPUT_TYPES:
		return {
			"scale_type": False,
			"scale_rows": False,
			"min_value": True,
			"max_value": True,
			"boolean_true_score": False,
			"boolean_false_score": False,
		}
	if input_type == "Boolean":
		return {
			"scale_type": False,
			"scale_rows": False,
			"min_value": False,
			"max_value": False,
			"boolean_true_score": True,
			"boolean_false_score": True,
		}
	return {
		"scale_type": False,
		"scale_rows": False,
		"min_value": False,
		"max_value": False,
		"boolean_true_score": False,
		"boolean_false_score": False,
	}


def sanitize_criterion_config(criterion: Any) -> None:
	input_type = _value(criterion, "input_type")
	scale_type = effective_scale_type(criterion)

	if input_type != "Scale":
		_set(criterion, "scale_type", None)

	if input_type == "Scale" and scale_type == "Discrete":
		_set(criterion, "min_value", None)
		_set(criterion, "max_value", None)
	elif input_type == "Scale" and scale_type == "Interval":
		_set(criterion, "scale_rows", [])
	elif input_type in NUMERIC_INPUT_TYPES:
		_set(criterion, "scale_type", None)
		_set(criterion, "scale_rows", [])
		_set(criterion, "boolean_true_score", None)
		_set(criterion, "boolean_false_score", None)
	elif input_type == "Boolean":
		_set(criterion, "scale_type", None)
		_set(criterion, "scale_rows", [])
		_set(criterion, "min_value", None)
		_set(criterion, "max_value", None)


def validate_criterion_config(criterion: Any) -> None:
	input_type = _value(criterion, "input_type")
	if input_type not in SUPPORTED_INPUT_TYPES:
		raise frappe.ValidationError(_("Unsupported input type: {0}").format(input_type))

	influence_direction = _value(criterion, "influence_direction") or "higher_is_better"
	if influence_direction not in SUPPORTED_INFLUENCE_DIRECTIONS:
		raise frappe.ValidationError(_("Unsupported influence direction: {0}").format(influence_direction))

	if input_type == "Scale":
		_validate_scale_config(criterion)
	elif input_type in NUMERIC_INPUT_TYPES:
		_validate_numeric_config(criterion)
	elif input_type == "Boolean":
		_validate_boolean_config(criterion)


def validate_scorecard_item_value(item_row: Any, criterion: Any) -> list[str]:
	input_type = _value(criterion, "input_type")
	criterion_code = _value(criterion, "criterion_code") or _value(criterion, "name") or _("Unknown")
	errors: list[str] = []

	if input_type == "Scale":
		errors.extend(_validate_scale_item_value(item_row, criterion, criterion_code))
	elif input_type == "Boolean":
		if not item_has_input_value(item_row):
			return errors
		if not _value(item_row, "boolean_value_set"):
			errors.append(
				_("{0}: boolean value must be explicitly set").format(criterion_code)
			)
	elif input_type in NUMERIC_INPUT_TYPES:
		errors.extend(_validate_numeric_item_value(item_row, criterion, criterion_code))

	return errors


def collect_scorecard_item_validation_errors(
	items: list[Any],
	criteria_by_name: dict[str, Any],
) -> list[str]:
	errors: list[str] = []
	for item in items or []:
		criterion_name = _value(item, "criterion")
		if not criterion_name:
			continue
		criterion = criteria_by_name.get(criterion_name)
		if not criterion:
			continue
		if not item_has_input_value(item):
			continue
		errors.extend(validate_scorecard_item_value(item, criterion))
	return errors


def item_has_input_value(item_row: Any) -> bool:
	input_type = _value(item_row, "criterion_input_type")
	if input_type == "Scale":
		if _value(item_row, "criterion_scale_type") == "Interval":
			return _value(item_row, "number_value") not in (None, "")
		return _value(item_row, "scale_value") not in (None, "") or _value(item_row, "raw_value") not in (
			None,
			"",
		)
	if input_type == "Boolean":
		return bool(_value(item_row, "boolean_value_set"))
	if input_type == "Number":
		return _value(item_row, "number_value") not in (None, "")
	if input_type == "Currency":
		return _value(item_row, "currency_value") not in (None, "")
	if input_type == "Percent":
		return _value(item_row, "percent_value") not in (None, "")
	return bool(_value(item_row, "raw_value") or _value(item_row, "raw_numeric_value") not in (None, ""))


def item_missing_mandatory_value(item_row: Any) -> bool:
	return (_value(item_row, "requirement_level") or "Desired") == "Mandatory" and not item_has_input_value(
		item_row
	)


def item_missing_required_comment(item_row: Any) -> bool:
	if not int(_value(item_row, "requires_comment") or 0):
		return False
	comment = _value(item_row, "comment")
	return comment in (None, "") or not str(comment).strip()


def scorecard_has_missing_required_items(items: list[Any]) -> bool:
	for item in items or []:
		if item_missing_mandatory_value(item) or item_missing_required_comment(item):
			return True
	return False


def scorecard_validation_error_message(
	items: list[Any],
	criteria_by_name: dict[str, Any],
) -> str | None:
	missing_codes = [
		_value(item, "criterion_code") or _value(item, "criterion")
		for item in items or []
		if item_missing_mandatory_value(item)
	]
	comment_codes = [
		_value(item, "criterion_code") or _value(item, "criterion")
		for item in items or []
		if item_missing_required_comment(item)
	]
	value_errors = collect_scorecard_item_validation_errors(items, criteria_by_name)

	parts: list[str] = []
	if missing_codes:
		parts.append(
			_("Mandatory criteria require a value: {0}").format(", ".join(sorted(set(missing_codes))))
		)
	if comment_codes:
		parts.append(
			_("Comment required for criteria: {0}").format(", ".join(sorted(set(comment_codes))))
		)
	if value_errors:
		parts.extend(value_errors)

	if not parts:
		return None
	return "\n".join(parts)


def _validate_scale_config(criterion: Any) -> None:
	scale_type = effective_scale_type(criterion)
	if scale_type not in SUPPORTED_SCALE_TYPES:
		raise frappe.ValidationError(_("Unsupported scale type: {0}").format(scale_type))

	if scale_type == "Discrete":
		rows = list(_children(criterion, "scale_rows"))
		if not rows:
			raise frappe.ValidationError(
				_("Scale criteria with Discrete scale type must define at least one scale row")
			)

		seen_scores: set[str] = set()
		for row in rows:
			score = _value(row, "score")
			if score in (None, ""):
				raise frappe.ValidationError(_("Each scale row must have a numeric score"))
			try:
				score_key = str(float(score))
			except (TypeError, ValueError) as exc:
				raise frappe.ValidationError(_("Scale row score must be numeric")) from exc
			if score_key in seen_scores:
				raise frappe.ValidationError(_("Scale row scores must be unique"))
			seen_scores.add(score_key)
		return

	min_value, max_value = _require_numeric_range(criterion, _("Interval scale"))
	if min_value >= max_value:
		raise frappe.ValidationError(
			_("Minimum value must be less than maximum value for interval scale criteria")
		)


def _validate_numeric_config(criterion: Any) -> None:
	min_value, max_value = _require_numeric_range(criterion, _value(criterion, "input_type"))
	if min_value >= max_value:
		raise frappe.ValidationError(
			_("Minimum value must be less than maximum value for {0} criteria").format(
				_value(criterion, "input_type")
			)
		)


def _validate_boolean_config(criterion: Any) -> None:
	for fieldname in ("boolean_true_score", "boolean_false_score"):
		value = _value(criterion, fieldname)
		if value in (None, ""):
			raise frappe.ValidationError(_("Boolean criteria must define both true and false scores"))
		try:
			float(value)
		except (TypeError, ValueError) as exc:
			raise frappe.ValidationError(_("Boolean scores must be numeric")) from exc


def _validate_scale_item_value(item_row: Any, criterion: Any, criterion_code: str) -> list[str]:
	scale_type = effective_scale_type(criterion)
	raw_value = _value(item_row, "scale_value") or _value(item_row, "raw_value")
	if raw_value in (None, ""):
		return []

	if scale_type == "Interval":
		value = _value(item_row, "number_value")
		if value in (None, ""):
			value = _value(item_row, "raw_numeric_value")
		if value in (None, ""):
			value = raw_value
		return _numeric_range_errors(value, criterion, criterion_code)

	allowed = {str(float(row.score)) for row in _children(criterion, "scale_rows") if _value(row, "score") not in (None, "")}
	try:
		normalized = str(float(raw_value))
	except (TypeError, ValueError):
		return [_("{0}: scale value must be numeric").format(criterion_code)]

	if normalized not in allowed and raw_value not in allowed:
		return [_("{0}: value must be one of the configured scale options").format(criterion_code)]
	return []


def _validate_numeric_item_value(item_row: Any, criterion: Any, criterion_code: str) -> list[str]:
	input_type = _value(criterion, "input_type")
	if input_type == "Number":
		value = _value(item_row, "number_value")
	elif input_type == "Currency":
		value = _value(item_row, "currency_value")
	elif input_type == "Percent":
		value = _value(item_row, "percent_value")
	else:
		value = _value(item_row, "raw_numeric_value") if _value(item_row, "raw_numeric_value") not in (None, "") else _value(item_row, "raw_value")

	if value in (None, ""):
		return []
	return _numeric_range_errors(value, criterion, criterion_code)


def _numeric_range_errors(value: Any, criterion: Any, criterion_code: str) -> list[str]:
	try:
		numeric_value = float(value)
	except (TypeError, ValueError):
		return [_("{0}: value must be numeric").format(criterion_code)]

	min_value = _value(criterion, "min_value")
	max_value = _value(criterion, "max_value")
	if min_value in (None, "") or max_value in (None, ""):
		return []

	min_numeric = float(min_value)
	max_numeric = float(max_value)
	if numeric_value < min_numeric or numeric_value > max_numeric:
		return [
			_("{0}: value {1} is outside allowed range {2}..{3}").format(
				criterion_code,
				numeric_value,
				min_numeric,
				max_numeric,
			)
		]
	return []


def _require_numeric_range(criterion: Any, label: str) -> tuple[float, float]:
	min_value = _value(criterion, "min_value")
	max_value = _value(criterion, "max_value")
	if min_value in (None, "") or max_value in (None, ""):
		raise frappe.ValidationError(
			_("{0} criteria must define both minimum and maximum values").format(label)
		)
	try:
		return float(min_value), float(max_value)
	except (TypeError, ValueError) as exc:
		raise frappe.ValidationError(_("Minimum and maximum values must be numeric")) from exc


def _children(document: Any, fieldname: str) -> list[Any]:
	return list(getattr(document, fieldname, None) or [])


def _value(document: Any, fieldname: str) -> Any:
	if document is None:
		return None
	if hasattr(document, "get"):
		return document.get(fieldname)
	return getattr(document, fieldname, None)


def _set(document: Any, fieldname: str, value: Any) -> None:
	if hasattr(document, "set"):
		document.set(fieldname, value)
	else:
		setattr(document, fieldname, value)
