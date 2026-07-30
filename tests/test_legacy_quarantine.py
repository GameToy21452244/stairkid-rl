import json
from pathlib import Path

import pytest

from stair_agent.data.migration import build_quarantine_manifest


def test_quarantine_manifest_classifies_without_migrating(tmp_path: Path) -> None:
    source = tmp_path / "logs"
    source.mkdir()
    (source / "baseline_sample.jsonl").write_text(
        json.dumps(
            {
                "step": 1,
                "action": 2,
                "features": [0.0] * 64,
                "observation": {"timestamp": 1.0},
                "decision_observation": {"timestamp": 0.9},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = build_quarantine_manifest(source)

    assert manifest["schema_version"] == "legacy-quarantine-manifest-v1"
    assert manifest["files"][0]["family"] == "baseline"
    assert manifest["files"][0]["rows"] == 1
    assert manifest["files"][0]["feature_dimensions"] == [64]
    assert not manifest["files"][0]["eligible_for_bc"]
    assert not manifest["files"][0]["eligible_for_dqn"]
    assert "source_sha256" in manifest["files"][0]


def test_quarantine_manifest_records_bad_json(tmp_path: Path) -> None:
    (tmp_path / "observations_bad.jsonl").write_text(
        "{bad json}\n", encoding="utf-8"
    )

    manifest = build_quarantine_manifest(tmp_path)

    assert manifest["files"][0]["json_errors"] == 1
    assert "invalid_json" in manifest["files"][0]["reasons"]


def test_quarantine_refuses_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_quarantine_manifest(tmp_path / "missing")
