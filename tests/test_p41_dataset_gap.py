from __future__ import annotations

import json

from stair_agent.data.p41_dataset_gap import (
    analyze_teacher_dataset,
    compare_same_seed_datasets,
    evaluate_v2_same_seed_readiness,
    evaluate_v2_readiness,
)


def _episode(
    episode_id: str,
    *,
    seed: int,
    outcome: str,
    version: str = "teacher-v2",
) -> list[dict[str, object]]:
    length = 10 if outcome == "target_reached" else 3
    rows = []
    for step in range(length):
        bottom = outcome == "bottom" and step == length - 1
        rows.append(
            {
                "episode_id": episode_id,
                "seed": seed,
                "split": "train",
                "step": step,
                "action": (1, 0, 2)[step % 3],
                "events": ["floor_descended"] if outcome == "target_reached" else [],
                "terminated": bottom,
                "truncated": False,
                "failure_reason": "bottom_death" if bottom else None,
                "teacher_reason": (
                    "direction_change_brake" if step == 1 else "move_toward_recovery_platform"
                ),
                "target_platform_kind": "spikes" if step == 0 else "normal",
                "visible_platform_kinds": ["normal", "spikes"],
                "teacher_policy_version": version,
                "environment_version": "sim-test-v1",
                "health_segments": 12,
            }
        )
    return rows


def _write(path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_dataset_gap_counts_branches_outcomes_and_release_bridged_reversals(tmp_path) -> None:
    path = tmp_path / "teacher.jsonl"
    _write(path, _episode("target", seed=1, outcome="target_reached"))

    result = analyze_teacher_dataset(path)

    assert result["outcomes"]["target_reached"] == 1
    assert result["branches"]["direction_brake"]["rows"] > 0
    assert result["branches"]["recovery"]["episodes"] == 1
    assert result["branches"]["spike_target"]["rows"] == 1
    assert result["release_bridged_reversals_per_100_steps"] > 0


def test_same_seed_comparison_detects_target_to_bottom_regression(tmp_path) -> None:
    frozen_path = tmp_path / "frozen.jsonl"
    current_path = tmp_path / "current.jsonl"
    _write(frozen_path, _episode("frozen", seed=7, outcome="target_reached"))
    current_rows = _episode("current", seed=7, outcome="bottom")
    current_rows[0]["action"] = 0
    _write(current_path, current_rows)
    frozen = analyze_teacher_dataset(frozen_path)
    current = analyze_teacher_dataset(current_path)

    comparison = compare_same_seed_datasets(frozen, current)

    assert comparison["common_seeds"] == 1
    assert comparison["outcome_transitions"]["target_reached->bottom"] == 1
    assert comparison["regressed_seeds"] == [7]
    assert comparison["first_action_transitions"]["1->0"] == 1


def test_v2_readiness_rejects_same_version_and_reliability_regression(tmp_path) -> None:
    frozen_path = tmp_path / "frozen.jsonl"
    current_path = tmp_path / "current.jsonl"
    _write(frozen_path, _episode("frozen", seed=7, outcome="target_reached"))
    _write(current_path, _episode("current", seed=7, outcome="bottom"))
    frozen = analyze_teacher_dataset(frozen_path)
    current = analyze_teacher_dataset(current_path)
    comparison = compare_same_seed_datasets(frozen, current)

    gate = evaluate_v2_readiness(
        frozen,
        current,
        comparison,
        source_fingerprint_embedded=False,
        fresh_reliability_evaluated=False,
    )

    assert not gate["passed"]
    assert not gate["checks"]["policy_version_bumped"]
    assert not gate["checks"]["same_seed_target_reliability"]
    assert not gate["checks"]["fresh_reliability_evaluated"]


def test_same_seed_gate_requires_config_fingerprint(tmp_path) -> None:
    frozen_path = tmp_path / "frozen.jsonl"
    current_path = tmp_path / "current.jsonl"
    rows = []
    for seed in range(30):
        rows.extend(_episode(f"frozen-{seed}", seed=seed, outcome="target_reached"))
    _write(frozen_path, rows)
    current_rows = []
    for row in rows:
        updated = dict(row)
        updated["episode_id"] = "current-" + str(row["episode_id"])
        updated["teacher_policy_version"] = "teacher-v3"
        split_index = int(row["seed"]) % 3
        updated["split"] = ("train", "validation", "test")[split_index]
        current_rows.append(updated)
    _write(current_path, current_rows)
    frozen = analyze_teacher_dataset(frozen_path)
    current = analyze_teacher_dataset(current_path)
    comparison = compare_same_seed_datasets(frozen, current)

    gate = evaluate_v2_same_seed_readiness(
        frozen,
        current,
        comparison,
        source_fingerprint_embedded=True,
        config_fingerprint_embedded=False,
    )

    assert not gate["passed"]
    assert gate["checks"]["source_fingerprint_embedded"]
    assert not gate["checks"]["config_fingerprint_embedded"]
