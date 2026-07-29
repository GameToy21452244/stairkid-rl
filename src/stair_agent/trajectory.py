from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import EnvironmentConfig
from .game_state import GamePhase
from .gym_env import RewardCalculator
from .observation import GameObservation


@dataclass(frozen=True)
class AuditResult:
    reward: float
    terminated: bool
    truncated: bool
    event_types: list[str]


class RewardAuditor:
    """逐筆重算 reward，並彙總事件與回合終止原因。"""

    TERMINAL_PHASES = {
        GamePhase.MENU.value,
        GamePhase.DIALOG.value,
        GamePhase.NAME_ENTRY.value,
        GamePhase.GAME_OVER.value,
    }

    def __init__(self, config: EnvironmentConfig) -> None:
        self.calculator = RewardCalculator(
            floor_reward=config.floor_reward,
            damage_penalty_per_segment=config.damage_penalty_per_segment,
            death_penalty=config.death_penalty,
        )
        self.steps = 0
        self.total_reward = 0.0
        self.event_counts: Counter[str] = Counter()
        self.end_reason: str | None = None

    def evaluate(self, observation: GameObservation) -> AuditResult:
        terminated = observation.phase in self.TERMINAL_PHASES
        truncated = observation.phase == GamePhase.UNKNOWN.value
        reward = self.calculator.calculate(
            observation,
            terminated=terminated,
        )
        event_types = [
            str(event.get("type", "unknown"))
            for event in observation.events
        ]
        self.steps += 1
        self.total_reward += reward
        self.event_counts.update(event_types)
        if terminated or truncated:
            self.end_reason = observation.phase
        return AuditResult(
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            event_types=event_types,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "steps": self.steps,
            "total_reward": self.total_reward,
            "event_counts": dict(sorted(self.event_counts.items())),
            "end_reason": self.end_reason,
        }

    def finish(self, reason: str) -> None:
        if self.end_reason is None:
            self.end_reason = reason


class TrajectoryJsonlWriter:
    """以新檔寫入逐步軌跡，結束時另存精簡摘要。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.summary_path = self.path.with_suffix(".summary.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() or self.summary_path.exists():
            existing = self.path if self.path.exists() else self.summary_path
            raise FileExistsError(f"拒絕覆寫既有軌跡檔：{existing}")
        self._file = self.path.open("x", encoding="utf-8")
        self._closed = False

    def write(
        self,
        *,
        step: int,
        action: int | str,
        observation: GameObservation,
        features: np.ndarray,
        result: AuditResult,
        cumulative_reward: float,
        policy_decision: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "step": step,
            "action": action,
            "reward": result.reward,
            "cumulative_reward": cumulative_reward,
            "terminated": result.terminated,
            "truncated": result.truncated,
            "events": result.event_types,
            "features": features.astype(float).tolist(),
            "observation": observation.to_dict(),
        }
        if policy_decision is not None:
            payload["policy_decision"] = policy_decision
        self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self, summary: dict[str, Any] | None = None) -> None:
        if self._closed:
            return
        self._closed = True
        self._file.close()
        if summary is not None:
            self.summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def __enter__(self) -> "TrajectoryJsonlWriter":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()
