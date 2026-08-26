from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from .schema import (
    OBSERVATION_SCHEMA_VERSION,
    REWARD_VERSION,
    SCHEMA_VERSION,
    PolicySource,
    TransitionRecord,
)

REWARD_TERM_KEYS = {
    "step_penalty",
    "floor_reward",
    "landing_reward",
    "damage_penalty",
    "death_penalty",
    "direction_change_penalty",
    "spike_dwell_penalty",
    "idle_action_penalty",
    "platform_dwell_penalty",
    "top_danger_penalty",
    "wall_push_penalty",
    "platform_alignment_reward",
    "platform_target_action_reward",
}


def extract_reward_terms(components: dict) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in components.items()
        if key in REWARD_TERM_KEYS
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    }


@dataclass(frozen=True)
class ActionTiming:
    action_command_timestamp: float
    action_effective_timestamp: float
    next_observation_timestamp: float
    held_action: bool
    action_duration_ms: float
    action_applied: bool = True


class TransitionJsonlWriter:
    """Write one validated episode without appending or guessing timing."""

    def __init__(
        self,
        path: str | Path,
        *,
        policy_source: PolicySource | str,
        episode_id: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"拒絕覆寫既有 transition：{self.path}")
        self.policy_source = PolicySource(policy_source)
        self.episode_id = episode_id or f"episode-{uuid4()}"
        self._file = self.path.open("x", encoding="utf-8")
        self._observation: list[float] | None = None
        self._observation_timestamp: float | None = None
        self._step = 0
        self._finished = False

    def begin(
        self,
        observation: np.ndarray | list[float],
        *,
        observation_timestamp: float,
    ) -> None:
        if self._observation is not None:
            raise RuntimeError("writer 已開始。")
        self._observation = np.asarray(
            observation, dtype=np.float32
        ).astype(float).tolist()
        self._observation_timestamp = float(observation_timestamp)

    def write_step(
        self,
        *,
        action: int,
        reward: float,
        reward_components: dict[str, float],
        next_observation: np.ndarray | list[float],
        terminated: bool,
        truncated: bool,
        events: list[dict],
        timing: ActionTiming,
        target_platform_id: int | None = None,
        target_platform_kind: str | None = None,
        target_signed_offset: float | None = None,
    ) -> TransitionRecord:
        if self._finished:
            raise RuntimeError("episode 已結束，拒絕再寫 transition。")
        if self._observation is None or self._observation_timestamp is None:
            raise RuntimeError("寫入前必須 begin。")
        component_total = float(sum(reward_components.values()))
        if not math.isclose(
            float(reward), component_total, rel_tol=1e-6, abs_tol=1e-6
        ):
            raise ValueError(
                "reward_components 加總與 reward 不一致："
                f"{component_total} != {reward}"
            )
        next_values = np.asarray(
            next_observation, dtype=np.float32
        ).astype(float).tolist()
        record = TransitionRecord(
            schema_version=SCHEMA_VERSION,
            episode_id=self.episode_id,
            step=self._step,
            observation=self._observation,
            action=int(action),
            reward=float(reward),
            reward_components={
                str(key): float(value)
                for key, value in reward_components.items()
            },
            next_observation=next_values,
            terminated=bool(terminated),
            truncated=bool(truncated),
            events=[dict(event) for event in events],
            policy_source=self.policy_source,
            target_platform_id=target_platform_id,
            target_platform_kind=target_platform_kind,
            target_signed_offset=target_signed_offset,
            observation_timestamp=self._observation_timestamp,
            action_command_timestamp=timing.action_command_timestamp,
            action_effective_timestamp=timing.action_effective_timestamp,
            next_observation_timestamp=timing.next_observation_timestamp,
            held_action=timing.held_action,
            action_duration_ms=timing.action_duration_ms,
            observation_schema_version=OBSERVATION_SCHEMA_VERSION,
            reward_version=REWARD_VERSION,
            timestamp=datetime.now(timezone.utc).astimezone().isoformat(),
        )
        # The schema constructor performs strict type checks.
        TransitionRecord.from_dict(record.to_dict())
        self._file.write(
            json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
        )
        self._file.flush()
        self._step += 1
        self._observation = next_values
        self._observation_timestamp = timing.next_observation_timestamp
        self._finished = bool(terminated or truncated)
        return record

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "TransitionJsonlWriter":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()
