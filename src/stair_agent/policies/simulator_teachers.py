from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..baseline_policy import SafePlatformPolicy
from ..config import BaselineConfig
from ..input_controller import Action
from ..observation import GameObservation
from ..simulator.physics import ShaftSimulator
from .simulator_route_planner import (
    BoundedRoutePlanner,
    BranchPreservedSearch,
    RoutePlan,
)


@dataclass(frozen=True)
class SimulatorTeacherProfile:
    name: str
    policy_version: str
    departure_enabled: bool
    departure_delay_steps: int
    support_aware_launch_handoff_enabled: bool = False

    def __post_init__(self) -> None:
        if self.departure_delay_steps < 0:
            raise ValueError("departure_delay_steps 不可小於 0。")


SIMULATOR_TEACHER_PROFILES = {
    "current": SimulatorTeacherProfile(
        name="current",
        policy_version="teacher-observable-simulator-v3-current",
        departure_enabled=True,
        departure_delay_steps=0,
    ),
    "departure_delayed": SimulatorTeacherProfile(
        name="departure_delayed",
        policy_version="teacher-observable-simulator-v3-departure-delay2",
        departure_enabled=True,
        departure_delay_steps=2,
    ),
    "departure_disabled": SimulatorTeacherProfile(
        name="departure_disabled",
        policy_version="teacher-observable-simulator-v3-departure-disabled",
        departure_enabled=False,
        departure_delay_steps=0,
    ),
    "departure_delayed_launch_handoff": SimulatorTeacherProfile(
        name="departure_delayed_launch_handoff",
        policy_version=(
            "teacher-observable-simulator-v4-delay2-launch-handoff"
        ),
        departure_enabled=True,
        departure_delay_steps=2,
        support_aware_launch_handoff_enabled=True,
    ),
}

# Historical default retained for legacy scripts and frozen Dataset v1.
# New experiments must pass an explicit SimulatorTeacherProfile.
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
    policy_version = "oracle-full-v5-committed-edge-top-pressure"

    def __init__(
        self,
        *,
        rollout_steps: int = 2,
        enable_spring_escape: bool = True,
        spring_clearance: float = 2.0,
        support_position_gain: float = 2.5,
        top_pressure_screen_y: float = 140.0,
        top_pressure_lookahead: int = 3,
        enable_route_planner: bool = False,
        route_plan_execution: str = "cached",
    ) -> None:
        if rollout_steps < 1:
            raise ValueError("rollout_steps 必須大於 0。")
        if spring_clearance < 0:
            raise ValueError("spring_clearance 不可小於 0。")
        if support_position_gain <= 0:
            raise ValueError("support_position_gain 必須大於 0。")
        if top_pressure_screen_y < 0:
            raise ValueError("top_pressure_screen_y 不可小於 0。")
        if top_pressure_lookahead < 1:
            raise ValueError("top_pressure_lookahead 必須至少為 1。")
        if route_plan_execution not in {
            "cached",
            "branch_preserved",
            "receding",
            "terminal_guarded",
        }:
            raise ValueError(
                "route_plan_execution 必須是 cached、branch_preserved、"
                "receding 或 terminal_guarded。"
            )
        self.rollout_steps = rollout_steps
        self.enable_spring_escape = bool(enable_spring_escape)
        self.spring_clearance = float(spring_clearance)
        self.support_position_gain = float(support_position_gain)
        self.top_pressure_screen_y = float(top_pressure_screen_y)
        self.top_pressure_lookahead = int(top_pressure_lookahead)
        self.enable_route_planner = bool(enable_route_planner)
        self.route_plan_execution = route_plan_execution
        if self.enable_route_planner:
            if self.route_plan_execution == "terminal_guarded":
                self.policy_version = "oracle-full-v8-terminal-risk-guard"
            elif self.route_plan_execution == "branch_preserved":
                self.policy_version = (
                    "oracle-full-v9-terminal-branch-preserving"
                )
            elif self.route_plan_execution == "receding":
                self.policy_version = (
                    "oracle-full-v7-receding-route-planner"
                )
            else:
                self.policy_version = (
                    "oracle-full-v6-bounded-route-planner"
                )
        else:
            self.policy_version = type(self).policy_version
        self._route_planner = BoundedRoutePlanner()
        self._route_actions: tuple[Action, ...] = ()
        self._route_plan_simulator_id: int | None = None
        self._route_plan_floor: int | None = None
        self._route_terminal_risk = False
        self.last_route_plan: RoutePlan | None = None
        self.last_branch_search: BranchPreservedSearch | None = None
        self.route_planning_count = 0
        self.branch_preserved_search_count = 0
        self.branch_selected_lane_counts = {
            action.name: 0 for action in Action
        }
        self._support_departure_key: tuple[int, int] | None = None
        self._support_departure_direction: Action | None = None

    def _clear_route_plan(self) -> None:
        self._route_actions = ()
        self._route_plan_simulator_id = None
        self._route_plan_floor = None
        self._route_terminal_risk = False

    def _route_planner_action(
        self, simulator: ShaftSimulator
    ) -> Action | None:
        if not self.enable_route_planner:
            return None
        if self.route_plan_execution == "receding":
            self._clear_route_plan()
            if not self._route_planner.should_plan(simulator):
                return None
            plan = self._route_planner.plan(simulator)
            self.last_route_plan = plan
            self.route_planning_count += 1
            if not plan.actions:
                return None
            return plan.actions[0]
        if (
            self._route_plan_simulator_id != id(simulator)
            or self._route_plan_floor != simulator.deepest_floor
        ):
            self._clear_route_plan()
        if (
            self.route_plan_execution == "terminal_guarded"
            and self._route_terminal_risk
        ):
            if not self._route_planner.should_plan(simulator):
                self._clear_route_plan()
                return None
            plan = self._route_planner.plan(simulator)
            self.last_route_plan = plan
            self.route_planning_count += 1
            self._route_plan_simulator_id = id(simulator)
            self._route_plan_floor = simulator.deepest_floor
            if not plan.actions:
                return None
            if plan.predicted_terminal is not None:
                return plan.actions[0]
            self._route_terminal_risk = False
            self._route_actions = plan.actions[1:]
            return plan.actions[0]
        if self._route_actions:
            action = self._route_actions[0]
            self._route_actions = self._route_actions[1:]
            return action
        if not self._route_planner.should_plan(simulator):
            return None
        plan = self._route_planner.plan(simulator)
        self.last_route_plan = plan
        self.route_planning_count += 1
        self._route_plan_simulator_id = id(simulator)
        self._route_plan_floor = simulator.deepest_floor
        if (
            self.route_plan_execution == "branch_preserved"
            and plan.predicted_terminal is not None
        ):
            branch_search = self._route_planner.plan_first_action_lanes(
                simulator
            )
            plan = branch_search.selected
            self.last_branch_search = branch_search
            self.last_route_plan = plan
            self.branch_preserved_search_count += 1
            if plan.actions:
                self.branch_selected_lane_counts[plan.actions[0].name] += 1
        if (
            self.route_plan_execution == "terminal_guarded"
            and plan.predicted_terminal is not None
        ):
            self._route_terminal_risk = True
            self._route_actions = ()
            if not plan.actions:
                return None
            return plan.actions[0]
        self._route_actions = plan.actions
        if not self._route_actions:
            return None
        action = self._route_actions[0]
        self._route_actions = self._route_actions[1:]
        return action

    def _clear_support_departure_commitment(self) -> None:
        self._support_departure_key = None
        self._support_departure_direction = None

    def _clearance_direction(
        self,
        simulator: ShaftSimulator,
        source,
        target,
    ) -> Action | None:
        player_half = simulator.player.width / 2
        left_clear_x = source.left - player_half - self.spring_clearance
        right_clear_x = source.right + player_half + self.spring_clearance
        minimum_x = (
            simulator.config.effective_playfield_left + player_half
        )
        maximum_x = (
            simulator.config.effective_playfield_right - player_half
        )
        exits = []
        if left_clear_x >= minimum_x:
            exits.append((abs(target.center_x - left_clear_x), Action.LEFT))
        if right_clear_x <= maximum_x:
            exits.append((abs(target.center_x - right_clear_x), Action.RIGHT))
        if not exits:
            return None
        return min(
            exits,
            key=lambda item: (
                item[0],
                0 if item[1] is Action.LEFT else 1,
            ),
        )[1]

    def _source_clearance_action(
        self,
        simulator: ShaftSimulator,
        source,
        target,
        *,
        preferred_direction: Action | None = None,
    ) -> Action | None:
        player_half = simulator.player.width / 2
        left_clear_x = source.left - player_half - self.spring_clearance
        right_clear_x = source.right + player_half + self.spring_clearance
        minimum_x = (
            simulator.config.effective_playfield_left + player_half
        )
        maximum_x = (
            simulator.config.effective_playfield_right - player_half
        )
        preferred = preferred_direction or self._clearance_direction(
            simulator,
            source,
            target,
        )
        if preferred is None:
            return None
        if preferred is Action.LEFT and left_clear_x < minimum_x:
            return None
        if preferred is Action.RIGHT and right_clear_x > maximum_x:
            return None
        player_x = float(simulator.player.body.position.x)
        velocity_x = float(simulator.player.body.velocity.x)
        cleared = (
            preferred is Action.LEFT and player_x <= left_clear_x
        ) or (
            preferred is Action.RIGHT and player_x >= right_clear_x
        )
        if cleared:
            return Action.RELEASE_ALL
        if not simulator.config.enable_support_ownership:
            return preferred

        # Start braking on the final supported control step when the opposite
        # input still carries the full player AABB beyond the source edge.
        # Without this handoff, the old position-only oracle exits at maximum
        # speed and cannot steer back onto a nearby overlapping lower platform.
        acceleration_step = (
            simulator.config.horizontal_acceleration * simulator.config.dt
        )
        if preferred is Action.RIGHT and velocity_x > 0.0:
            braking_velocity = max(0.0, velocity_x - acceleration_step)
            if (
                player_x + braking_velocity * simulator.config.dt
                >= right_clear_x
            ):
                return Action.LEFT
        elif preferred is Action.LEFT and velocity_x < 0.0:
            braking_velocity = min(0.0, velocity_x + acceleration_step)
            if (
                player_x + braking_velocity * simulator.config.dt
                <= left_clear_x
            ):
                return Action.RIGHT
        return preferred

    def _support_departure_action(
        self,
        simulator: ShaftSimulator,
        target,
    ) -> Action | None:
        source = simulator.supported_platform
        if source is None:
            self._clear_support_departure_commitment()
            return None
        if source.floor_index >= target.floor_index:
            self._clear_support_departure_commitment()
            return None
        key = (id(simulator), source.floor_index)
        if self._support_departure_key != key:
            self._support_departure_key = key
            self._support_departure_direction = self._clearance_direction(
                simulator,
                source,
                target,
            )
        return self._source_clearance_action(
            simulator,
            source,
            target,
            preferred_direction=self._support_departure_direction,
        )

    def _spring_escape_action(
        self,
        simulator: ShaftSimulator,
        target,
    ) -> Action | None:
        if not self.enable_spring_escape:
            return None
        source_floor = simulator.last_landed_floor
        if source_floor is None:
            return None
        source = next(
            (
                platform
                for platform in simulator.platforms
                if platform.floor_index == source_floor
            ),
            None,
        )
        if source is None or source.kind != "spring":
            return None
        body = simulator.player.body
        player_bottom = float(body.position.y) - simulator.player.height / 2
        if player_bottom < source.top - 1.5:
            return None

        return self._source_clearance_action(simulator, source, target)

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
        candidate_floors = sorted(
            {item.floor_index for item in candidates}
        )
        next_floor = candidate_floors[0]
        player_screen_y = (
            simulator.config.height - float(simulator.player.body.position.y)
        )
        if (
            simulator.config.enable_support_ownership
            and player_screen_y <= self.top_pressure_screen_y
        ):
            floor_offset = min(
                self.top_pressure_lookahead - 1,
                len(candidate_floors) - 1,
            )
            next_floor = candidate_floors[floor_offset]
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
        spring_escape_action = self._spring_escape_action(
            simulator,
            target,
        )
        support_departure_action = self._support_departure_action(
            simulator,
            target,
        )
        route_planner_action = self._route_planner_action(simulator)
        x = float(body.position.x)
        vx = float(body.velocity.x)
        error = target.center_x - x
        position_gain = (
            self.support_position_gain
            if simulator.config.enable_support_ownership
            else 5.0
        )
        desired_velocity = float(
            np.clip(error * position_gain, -180.0, 180.0)
        )

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
        if route_planner_action is not None:
            action = route_planner_action
        elif support_departure_action is not None:
            action = support_departure_action
        elif spring_escape_action is not None:
            action = spring_escape_action
        elif vx < desired_velocity - 25.0:
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
    target_signed_offset: float | None = None
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
        profile: SimulatorTeacherProfile | None = None,
    ) -> None:
        self._profile = profile
        departure_enabled = True if profile is None else profile.departure_enabled
        departure_delay_steps = 0 if profile is None else profile.departure_delay_steps
        self._policy = SafePlatformPolicy(
            config or BaselineConfig(),
            normal_support_departure_enabled=departure_enabled,
            normal_support_departure_delay_steps=departure_delay_steps,
            support_aware_launch_handoff_enabled=(
                False
                if profile is None
                else profile.support_aware_launch_handoff_enabled
            ),
        )
        self._verified = verified
        self._policy_version = (
            TEACHER_POLICY_VERSION
            if profile is None
            else profile.policy_version
        )

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
            target_signed_offset=decision.horizontal_delta,
            policy_version=self._policy_version,
        )


__all__ = [
    "OracleDecision",
    "OracleFull",
    "TeacherDecision",
    "TeacherObservable",
    "SimulatorTeacherProfile",
    "SIMULATOR_TEACHER_PROFILES",
    "TEACHER_POLICY_VERSION",
]
