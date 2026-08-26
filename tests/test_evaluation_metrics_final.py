from __future__ import annotations

import json
from pathlib import Path

import pytest

from stair_agent.evaluation import floor_metrics, write_json_report


def test_generic_floor_metrics_have_no_round_or_gate_policy() -> None:
    result = floor_metrics([1, 3, 5, 9])
    assert result == {
        "episodes": 4,
        "mean": 4.5,
        "median": 4.0,
        "q25": 2.5,
        "q75": 6.0,
        "min": 1,
        "max": 9,
        "floor_le_threshold": 4,
        "floor_le_threshold_rate": 0.5,
    }


def test_floor_metrics_reject_empty_sample() -> None:
    with pytest.raises(ValueError, match="AT_LEAST_ONE_EPISODE"):
        floor_metrics([])


def test_json_report_is_machine_readable(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    write_json_report(path, {"status": "PASS", "episodes": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "status": "PASS",
        "episodes": 2,
    }
    assert not path.with_suffix(".json.tmp").exists()
