from __future__ import annotations

import json
from pathlib import Path

from stair_agent.data.schema import OBSERVATION_DIM
from stair_agent.data.validator import DatasetValidator

from test_data_schema import valid_payload


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_validator_accepts_clean_episode(tmp_path: Path) -> None:
    first = valid_payload()
    second = valid_payload()
    second.update(
        {
            "step": 1,
            "observation": first["next_observation"],
            "next_observation": [0.2] * OBSERVATION_DIM,
            "observation_timestamp": 10.10,
            "action_command_timestamp": 10.11,
            "action_effective_timestamp": 10.12,
            "next_observation_timestamp": 10.20,
            "terminated": True,
        }
    )
    path = tmp_path / "clean.jsonl"
    write_jsonl(path, [first, second])

    report = DatasetValidator().validate_file(path)

    assert report.valid
    assert report.records == 2
    assert report.episodes == 1
    assert report.error_count == 0


def test_validator_detects_schema_dimension_action_and_nonfinite(
    tmp_path: Path,
) -> None:
    malformed = valid_payload()
    malformed["observation"] = [0.0, float("nan")]
    malformed["action"] = 9
    path = tmp_path / "bad.jsonl"
    write_jsonl(path, [malformed])

    report = DatasetValidator().validate_file(path)

    assert not report.valid
    assert {"observation_dimension", "nonfinite", "invalid_action"} <= (
        issue_codes(report)
    )


def test_validator_reports_type_error_without_crashing(tmp_path: Path) -> None:
    malformed = valid_payload()
    malformed["step"] = "zero"
    malformed["observation_timestamp"] = "late"
    path = tmp_path / "types.jsonl"
    write_jsonl(path, [malformed])

    report = DatasetValidator().validate_file(path)

    assert not report.valid
    assert "schema_error" in issue_codes(report)


def test_validator_rejects_reward_component_mismatch(tmp_path: Path) -> None:
    malformed = valid_payload()
    malformed["reward"] = 9.0
    path = tmp_path / "reward.jsonl"
    write_jsonl(path, [malformed])

    report = DatasetValidator().validate_file(path)

    assert not report.valid
    assert "reward_component_mismatch" in issue_codes(report)


def test_validator_detects_time_regression_and_transition_after_terminal(
    tmp_path: Path,
) -> None:
    first = valid_payload()
    first["terminated"] = True
    second = valid_payload()
    second["step"] = 1
    second["observation_timestamp"] = 9.0
    second["action_command_timestamp"] = 8.0
    path = tmp_path / "continuity.jsonl"
    write_jsonl(path, [first, second])

    report = DatasetValidator().validate_file(path)

    assert {
        "transition_after_terminal",
        "timestamp_regression",
        "timestamp_order",
    } <= issue_codes(report)


def test_validator_detects_reappearing_episode_and_step_gap(
    tmp_path: Path,
) -> None:
    first = valid_payload()
    second = valid_payload()
    second.update({"episode_id": "episode-002", "step": 0})
    third = valid_payload()
    third.update({"step": 3})
    fourth = valid_payload()
    fourth.update({"step": 5})
    path = tmp_path / "crossed.jsonl"
    write_jsonl(path, [first, second, third, fourth])

    report = DatasetValidator().validate_file(path)

    assert {
        "episode_reappeared",
        "episode_start_step",
        "step_discontinuity",
    } <= issue_codes(report)


def test_validator_warns_on_action_collapse_and_duplicates(
    tmp_path: Path,
) -> None:
    records = []
    for step in range(60):
        record = valid_payload()
        record.update(
            {
                "step": step,
                "observation_timestamp": 10.0 + step,
                "action_command_timestamp": 10.01 + step,
                "action_effective_timestamp": 10.02 + step,
                "next_observation_timestamp": 10.1 + step,
            }
        )
        records.append(record)
    path = tmp_path / "collapsed.jsonl"
    write_jsonl(path, records)

    report = DatasetValidator().validate_file(path)

    assert {"action_collapse", "duplicate_transitions"} <= issue_codes(report)
    assert report.error_count == 0
    assert report.warning_count >= 2
