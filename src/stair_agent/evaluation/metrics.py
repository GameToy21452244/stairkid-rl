"""Generic metrics with no experiment-round or promotion policy."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping

import numpy as np


def floor_metrics(floors: Iterable[int], *, low_floor_threshold: int = 4) -> dict[str, Any]:
    values = [int(value) for value in floors]
    if not values:
        raise ValueError("FLOOR_METRICS_REQUIRE_AT_LEAST_ONE_EPISODE")
    return {
        "episodes": len(values),
        "mean": float(mean(values)),
        "median": float(median(values)),
        "q25": float(np.quantile(values, 0.25)),
        "q75": float(np.quantile(values, 0.75)),
        "min": min(values),
        "max": max(values),
        "floor_le_threshold": int(low_floor_threshold),
        "floor_le_threshold_rate": sum(value <= low_floor_threshold for value in values)
        / len(values),
    }


def write_json_report(path: Path, payload: Mapping[str, Any]) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
