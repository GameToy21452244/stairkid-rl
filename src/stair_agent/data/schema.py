from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any


SCHEMA_VERSION = "ns-shaft-transition-v1"
OBSERVATION_SCHEMA_VERSION = "stair-observation-v3-268"
REWARD_VERSION = "stair-reward-v2"
OBSERVATION_DIM = 268


class PolicySource(str, Enum):
    HUMAN = "human"
    BASELINE = "baseline"
    BASELINE_VERIFIED = "baseline_verified"
    OLD_PPO = "old_ppo"
    MODEL = "model"
    CORRECTED = "corrected"
    INVALID = "invalid"


@dataclass(frozen=True)
class TransitionRecord:
    """Canonical one-action transition used by future offline training."""

    schema_version: str
    episode_id: str
    step: int
    observation: list[float]
    action: int
    reward: float
    reward_components: dict[str, float]
    next_observation: list[float]
    terminated: bool
    truncated: bool
    events: list[dict[str, Any]]
    policy_source: PolicySource
    target_platform_id: int | None
    target_platform_kind: str | None
    target_signed_offset: float | None
    observation_timestamp: float
    action_command_timestamp: float
    action_effective_timestamp: float
    next_observation_timestamp: float
    held_action: bool
    action_duration_ms: float
    observation_schema_version: str
    reward_version: str
    timestamp: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransitionRecord":
        if not isinstance(payload, dict):
            raise ValueError("transition 必須是 JSON object。")
        expected = {field.name for field in fields(cls)}
        actual = set(payload)
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        if missing:
            raise ValueError(f"缺少欄位：{', '.join(missing)}")
        if unknown:
            raise ValueError(f"未知欄位：{', '.join(unknown)}")
        values = dict(payload)
        try:
            values["policy_source"] = PolicySource(values["policy_source"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"未知 policy_source：{values.get('policy_source')!r}"
            ) from exc
        cls._validate_types(values)
        return cls(**values)

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @classmethod
    def _validate_types(cls, values: dict[str, Any]) -> None:
        for name in (
            "schema_version",
            "observation_schema_version",
            "reward_version",
        ):
            if not isinstance(values[name], str) or not values[name]:
                raise ValueError(f"{name} 必須是非空字串。")
        if not isinstance(values["episode_id"], str) or not values["episode_id"]:
            raise ValueError("episode_id 必須是非空字串。")
        if (
            not isinstance(values["step"], int)
            or isinstance(values["step"], bool)
            or values["step"] < 0
        ):
            raise ValueError("step 必須是大於等於 0 的整數。")
        for name in ("observation", "next_observation"):
            value = values[name]
            if not isinstance(value, list) or not all(
                cls._is_number(item) for item in value
            ):
                raise ValueError(f"{name} 必須是數值陣列。")
        if (
            not isinstance(values["action"], int)
            or isinstance(values["action"], bool)
        ):
            raise ValueError("action 必須是整數。")
        if not cls._is_number(values["reward"]):
            raise ValueError("reward 必須是數值。")
        components = values["reward_components"]
        if not isinstance(components, dict) or not all(
            isinstance(name, str) and cls._is_number(value)
            for name, value in components.items()
        ):
            raise ValueError("reward_components 必須是 string 到數值的 object。")
        for name in ("terminated", "truncated", "held_action"):
            if not isinstance(values[name], bool):
                raise ValueError(f"{name} 必須是 boolean。")
        if not isinstance(values["events"], list) or not all(
            isinstance(event, dict) for event in values["events"]
        ):
            raise ValueError("events 必須是 object 陣列。")
        target_id = values["target_platform_id"]
        if target_id is not None and (
            not isinstance(target_id, int) or isinstance(target_id, bool)
        ):
            raise ValueError("target_platform_id 必須是整數或 null。")
        target_kind = values["target_platform_kind"]
        if target_kind is not None and not isinstance(target_kind, str):
            raise ValueError("target_platform_kind 必須是字串或 null。")
        target_offset = values["target_signed_offset"]
        if target_offset is not None and not cls._is_number(target_offset):
            raise ValueError("target_signed_offset 必須是數值或 null。")
        for name in (
            "observation_timestamp",
            "action_command_timestamp",
            "action_effective_timestamp",
            "next_observation_timestamp",
            "action_duration_ms",
        ):
            if not cls._is_number(values[name]):
                raise ValueError(f"{name} 必須是數值。")
        if values["action_duration_ms"] < 0:
            raise ValueError("action_duration_ms 不可小於 0。")
        if not isinstance(values["timestamp"], str):
            raise ValueError("timestamp 必須是 ISO-8601 字串。")
        try:
            datetime.fromisoformat(values["timestamp"])
        except ValueError as exc:
            raise ValueError("timestamp 必須是有效 ISO-8601 字串。") from exc

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["policy_source"] = self.policy_source.value
        return payload
