from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..baseline_policy import SafePlatformPolicy
from ..config import BaselineConfig
from ..input_controller import Action
from ..observation import GameObservation
from ..simulator.physics import ShaftSimulator


TEACHER_POLICY_VERSION = "teacher-observable-safe-platform-v2"


@dataclass(frozen=True)
class OracleDecision:
    action: Action
    target_platform_id: int | None
    candidate_action_values: tuple[float, float, float]
    target_platform_kind: str | None = None
    target_center_x: float | None = None


class OracleFull:
    """Privileged solvability oracle. Its output must never become BC labels."""

    teacher_type = "oracle_full"

    def __init__(self, *, rollout_steps: int = 2) -> None:
        if rollout_steps < 1:
            raise ValueError("rollout_steps 必須大於 0。")
        self.rollout_steps = rollout_steps

    def choose(self, simulator: ShaftSimulator) -> OracleDecision:
        candidates = [
            platform
            for platform in simulator.platforms
            if platform.floor_index > simulator.deepest_floor
            and simulator.platform_is_active(platform)
        ]
        if not candidates:
            return OracleDecision(
                Action.RELEASE_ALL, None, (0.0, 0.0, 0.0)
            )
        next_floor = min(item.floor_index for item in candidates)
        floor_candidates = [
            item for item in candidates if item.floor_index == next_floor
        ]
        normal_candidates = [
            item for item in floor_candidates if item.kind == "normal"
        ]
        safe_candidates = [
            item for item in floor_candidates if item.kind != "spikes"
        ]
        body = simulator.player.body
        target = min(
            normal_candidates or safe_candidates or floor_candidates,
            key=lambda item: abs(
                item.center_x - float(body.position.x)
            ),
        )
        x = float(body.position.x)
        vx = float(body.velocity.x)
        error = target.center_x - x
        desired_velocity = float(np.clip(error * 5.0, -180.0, 180.0))

        values = []
        for action in Action:
            projected_vx = vx
            if action is Action.LEFT:
                projected_vx -= simulator.config.horizontal_acceleration * simulator.config.dt
            elif action is Action.RIGHT:
                projected_vx += simulator.config.horizontal_acceleration * simulator.config.dt
            else:
                projected_vx *= simulator.config.release_drag
            projected_vx = float(
                np.clip(
                    projected_vx,
                    -simulator.config.max_horizontal_speed,
                    simulator.config.max_horizontal_speed,
                )
            )
            projected_x = x + projected_vx * simulator.config.dt * self.rollout_steps
            values.append(
                -abs(target.center_x - projected_x)
                - 0.12 * abs(projected_vx - desired_velocity)
            )

        # A velocity-tracking controller is more stable than pure positional
        # argmax, while values retain the required short-rollout diagnostics.
        if vx < desired_velocity - 25.0:
            action = Action.RIGHT
        elif vx > desired_velocity + 25.0:
            action = Action.LEFT
        else:
            action = Action.RELEASE_ALL
        return OracleDecision(
            action,
            target.floor_index,
            tuple(values),
            target.kind,
            target.center_x,
        )


@dataclass(frozen=True)
class TeacherDecision:
    action: Action
    action_distribution: tuple[float, float, float]
    candidate_action_values: tuple[float, float, float]
    confidence: float
    target_platform_id: int | None
    target_platform_kind: str | None
    verified: bool
    reason: str
    policy_version: str = TEACHER_POLICY_VERSION
    teacher_type: str = "teacher_observable"


class TeacherObservable:
    """BC teacher restricted to the student's structured observation."""

    teacher_type = "teacher_observable"

    def __init__(
        self,
        config: BaselineConfig | None = None,
        *,
        verified: bool = False,
    ) -> None:
        self._policy = SafePlatformPolicy(config or BaselineConfig())
        self._verified = verified

    def reset(self) -> None:
        self._policy.reset()

    def choose(self, observation: GameObservation) -> TeacherDecision:
        decision = self._policy.choose(observation)
        chosen = int(decision.action)
        player_present = bool(observation.player)
        target_present = decision.target_platform_id is not None
        confidence = 0.86 if player_present and target_present else 0.55
        if decision.action is Action.RELEASE_ALL:
            confidence -= 0.08
        residual = (1.0 - confidence) / 2.0
        probabilities = [residual, residual, residual]
        probabilities[chosen] = confidence
        values = tuple(float(np.log(max(value, 1e-6))) for value in probabilities)
        return TeacherDecision(
            action=decision.action,
            action_distribution=tuple(probabilities),
            candidate_action_values=values,
            confidence=confidence,
            target_platform_id=decision.target_platform_id,
            target_platform_kind=decision.target_platform_kind,
            verified=self._verified,
            reason=decision.reason,
        )


__all__ = [
    "OracleDecision",
    "OracleFull",
    "TeacherDecision",
    "TeacherObservable",
    "TEACHER_POLICY_VERSION",
]
