from __future__ import annotations

import json
from pathlib import Path

from stair_agent.data.resource_audit import audit_jsonl_resources, write_audit_csvs


def test_legacy_baseline_with_decision_observation_requires_relabel(tmp_path: Path) -> None:
    source = tmp_path / "baseline_old.jsonl"
    source.write_text(
        json.dumps(
            {
                "step": 0,
                "action": 1,
                "features": [0.0] * 64,
                "decision_observation": {"player": {}},
                "terminated": False,
                "truncated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = audit_jsonl_resources(tmp_path, [source])
    row = result.inventory[0]
    assert row.classification == "needs_relabel"
    assert not row.usable_for_bc
    assert not row.usable_for_replay
    assert row.needs_relabel


def test_observation_only_data_is_invalid_and_manifests_are_row_level(tmp_path: Path) -> None:
    source = tmp_path / "observations.jsonl"
    source.write_text(
        json.dumps({"timestamp": 1.0, "player": {}}) + "\n",
        encoding="utf-8",
    )
    result = audit_jsonl_resources(tmp_path, [source])
    assert result.inventory[0].classification == "invalid"
    assert len(result.salvage_rows) == 1
    inventory = tmp_path / "artifacts" / "inventory.csv"
    salvage = tmp_path / "artifacts" / "salvage.csv"
    write_audit_csvs(result, inventory, salvage)
    assert "classification" in inventory.read_text(encoding="utf-8-sig")
    assert "row_sha256" in salvage.read_text(encoding="utf-8-sig")
