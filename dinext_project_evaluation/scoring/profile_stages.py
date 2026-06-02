from __future__ import annotations

from collections import defaultdict
from typing import Any


def stages_by_criterion(profile: Any) -> dict[str, list[str]]:
	mapping: dict[str, list[str]] = defaultdict(list)
	for row in getattr(profile, "criterion_stages", None) or []:
		criterion = getattr(row, "criterion", None)
		stage = getattr(row, "stage", None)
		if criterion and stage:
			mapping[criterion].append(stage)
	return dict(mapping)
