from __future__ import annotations

import pytest

from stair_agent.data.schema import (
    OBSERVATION_DIM,
    OBSERVATION_SCHEMA_VERSION,
    REWARD_VERSION,
    SCHEMA_VERSION,
    PolicySource,
    TransitionRecord,
)


def valid_payload() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": "episode-001",
        "step": 0,
        "observation": [0.0] * OBSERVATION_DIM,
        "action": 2,
        "reward": 1.0,
        "reward_components": {"floor_reward": 1.0},
        "next_observation": [0.1] * OBSERVATION_DIM,
        "terminated": False,
        "truncated": False,
        "events": [{"type": "floor_descended"}],
        "policy_source": "baseline_verified",
        "target_platform_id": 7,
        "target_platform_kind": "normal",
        "target_signed_offset": 12.5,
        "observation_timestamp": 10.0,
        "action_command_timestamp": 10.01,
        "action_effective_timestamp": 10.02,
        "next_observation_timestamp": 10.10,
        "held_action": False,
        "action_duration_ms": 50.0,
        "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
        "reward_version": REWARD_VERSION,
        "timestamp": "2026-07-30T10:00:00+08:00",
    }


def test_transition_round_trip_preserves_contract() -> None:
    record = TransitionRecord.from_dict(valid_payload())

    assert record.policy_source is PolicySource.BASELINE_VERIFIED
    assert record.to_dict() == valid_payload()


def test_transition_rejects_unknown_fields() -> None:
    payload = valid_payload()
    payload["mystery"] = True

    with pytest.raises(ValueError, match="未知欄位"):
        TransitionRecord.from_dict(payload)


def test_transition_requires_all_contract_fields() -> None:
    payload = valid_payload()
    del payload["next_observation_timestamp"]

    with pytest.raises(ValueError, match="缺少欄位"):
        TransitionRecord.from_dict(payload)


def test_policy_sources_include_invalid_for_quarantine() -> None:
    assert {source.value for source in PolicySource} == {
        "human",
        "baseline",
        "baseline_verified",
        "old_ppo",
        "model",
        "corrected",
        "invalid",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("episode_id", ""),
        ("step", "0"),
        ("reward", "1.0"),
        ("terminated", 0),
        ("events", ["landed"]),
        ("action_duration_ms", -1),
        ("timestamp", 123),
    ],
)
def test_transition_rejects_wrong_field_types(field: str, value) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValueError, match=field):
        TransitionRecord.from_dict(payload)
