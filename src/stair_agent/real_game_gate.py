from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
from math import ceil
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from .game_state import GamePhase
from .diagnostics import save_image
from .input_controller import Action
from .observation import GameObservation


FAILURE_TAXONOMY = {
    "unreachable_sequence",
    "wrong_target",
    "brake_too_late",
    "wall_collision",
    "platform_not_visible_in_time",
    "missed_platform",
    "top",
    "bottom",
    "health_depleted",
    "timeout",
    "unknown",
}

REAL_GAME_GATE_VERSION = 11
SPECIAL_CONTACT_ABSOLUTE_MAX_STEPS = 16
PRE_SPECIAL_DROPOUT_MAX_STEPS = 2


class DropoutForensicRecorder:
    """Persist a small, lossless evidence set for live player dropouts."""

    def __init__(
        self,
        output_dir: str | Path,
        *,
        diagnose_player: Callable[[np.ndarray], tuple[dict[str, object], np.ndarray]],
        milestones: Iterable[int] = (1, 3, 8, 16, 24),
        max_snapshots: int = 6,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.diagnose_player = diagnose_player
        self.milestones = {max(1, int(value)) for value in milestones}
        self.max_snapshots = max(1, int(max_snapshots))
        self.snapshots: list[dict[str, Any]] = []
        self.dropped_snapshot_count = 0
        self._dropout_active = False
        self._last_missing_streak = 0
        self._finalized = False

    def observe(
        self,
        *,
        step: int,
        detection_source: str,
        missing_streak: int,
        frame: np.ndarray,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._finalized:
            raise RuntimeError("DropoutForensicRecorder 已 finalize。")
        source = str(detection_source)
        streak = max(0, int(missing_streak))
        if source == "raw":
            capture_event = self._dropout_active
            event = "recovered"
            event_streak = self._last_missing_streak
            self._dropout_active = False
            self._last_missing_streak = 0
        else:
            streak = max(1, streak)
            self._dropout_active = True
            self._last_missing_streak = max(self._last_missing_streak, streak)
            capture_event = streak in self.milestones
            event = "missing"
            event_streak = streak
        if not capture_event:
            return
        if len(self.snapshots) >= self.max_snapshots:
            self.dropped_snapshot_count += 1
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"step_{int(step):04d}_{event}_{event_streak:03d}"
        raw_name = f"{stem}.raw.png"
        mask_name = f"{stem}.player-mask.png"
        diagnostics: dict[str, object]
        try:
            diagnostics, mask = self.diagnose_player(frame)
            save_image(self.output_dir / mask_name, mask)
        except Exception as exc:  # forensics must never break input safety
            diagnostics = {"diagnostics_error": str(exc)}
            mask_name = ""
        save_image(self.output_dir / raw_name, frame)
        self.snapshots.append(
            {
                "step": int(step),
                "event": event,
                "detection_source": source,
                "missing_streak": event_streak,
                "raw_frame": raw_name,
                "player_mask": mask_name or None,
                "player_color_diagnostics": diagnostics,
                "metadata": dict(metadata or {}),
            }
        )

    def finalize(self) -> dict[str, Any]:
        if self._finalized:
            return {
                "snapshot_count": len(self.snapshots),
                "dropped_snapshot_count": self.dropped_snapshot_count,
                "snapshots": self.snapshots,
            }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "snapshot_count": len(self.snapshots),
            "dropped_snapshot_count": self.dropped_snapshot_count,
            "milestones": sorted(self.milestones),
            "max_snapshots": self.max_snapshots,
            "snapshots": self.snapshots,
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._finalized = True
        return payload


@dataclass(frozen=True)
class RealGameMicroLimits:
    episodes: int = 3
    max_steps_per_episode: int = 300
    max_seconds_per_episode: float = 60.0
    max_total_steps: int = 900
    max_total_seconds: float = 180.0

    def validate(self) -> None:
        if self.episodes not in {3, 5, 10}:
            raise ValueError("Teacher real Gate 只允許 3、5 或 10 回合。")
        if not 1 <= self.max_steps_per_episode <= 500:
            raise ValueError("每回合步數上限必須介於 1–500。")
        if not 0 < self.max_seconds_per_episode <= 120:
            raise ValueError("每回合時間上限必須大於 0 且不超過 120 秒。")
        if not self.episodes <= self.max_total_steps <= 5000:
            raise ValueError("總步數上限必須介於回合數與 5000。")
        if not 0 < self.max_total_seconds <= 600:
            raise ValueError("總時間上限必須大於 0 且不超過 600 秒。")

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


class DirectionOscillationTracker:
    """Count rapid LEFT/RIGHT reversals while ignoring explicit brake frames."""

    def __init__(self, *, max_step_gap: int = 3) -> None:
        self.max_step_gap = max(1, int(max_step_gap))
        self._last_direction: Action | None = None
        self._last_direction_step: int | None = None
        self._current_burst = 0
        self.reversal_count = 0
        self.max_burst = 0

    def reset_burst(self) -> None:
        self._last_direction = None
        self._last_direction_step = None
        self._current_burst = 0

    def update(
        self,
        action: Action,
        *,
        step: int,
        eligible: bool = True,
    ) -> None:
        if not eligible:
            self.reset_burst()
            return
        if action not in {Action.LEFT, Action.RIGHT}:
            return
        if (
            self._last_direction is not None
            and self._last_direction is not action
            and self._last_direction_step is not None
        ):
            gap = int(step) - self._last_direction_step
            if gap <= self.max_step_gap:
                self._current_burst += 1
                self.reversal_count += 1
                self.max_burst = max(self.max_burst, self._current_burst)
            else:
                self._current_burst = 0
        elif self._last_direction is action:
            # A sustained direction ends an alternating burst once it has
            # lasted beyond the short correction window.
            if (
                self._last_direction_step is not None
                and int(step) - self._last_direction_step > self.max_step_gap
            ):
                self._current_burst = 0
        self._last_direction = action
        self._last_direction_step = int(step)


class ObservationDropoutTracker:
    """Classify safe, recovered perception gaps separately from blind control."""

    def __init__(self, *, max_recoverable_steps: int = 20) -> None:
        self.max_recoverable_steps = max(1, int(max_recoverable_steps))
        self.invalid_step_count = 0
        self.recovered_count = 0
        self.unrecovered_count = 0
        self.terminal_count = 0
        self.blind_directional_action_count = 0
        self.approved_directional_action_count = 0
        self.max_approved_directional_streak = 0
        self.max_recovered_streak = 0
        self.recovery_samples: list[dict[str, Any]] = []
        self._current_streak = 0
        self._entry_phase: str | None = None
        self._start_floor: int | None = None
        self._last_valid_phase: str | None = None
        self._approved_directional_streak = 0
        self._finalized = False

    @staticmethod
    def _floor_value(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def update(
        self,
        *,
        confidence: float,
        action: Action,
        controller_phase: str | None,
        floor: Any,
        approved_directional: bool = False,
    ) -> None:
        if self._finalized:
            raise RuntimeError("ObservationDropoutTracker 已 finalize。")
        phase = None if controller_phase is None else str(controller_phase)
        floor_value = self._floor_value(floor)
        if float(confidence) <= 0.0:
            if self._current_streak == 0:
                self._entry_phase = self._last_valid_phase or phase
                self._start_floor = floor_value
            self._current_streak += 1
            self.invalid_step_count += 1
            if action in {Action.LEFT, Action.RIGHT}:
                if approved_directional:
                    self.approved_directional_action_count += 1
                    self._approved_directional_streak += 1
                    self.max_approved_directional_streak = max(
                        self.max_approved_directional_streak,
                        self._approved_directional_streak,
                    )
                else:
                    self.blind_directional_action_count += 1
                    self._approved_directional_streak = 0
            else:
                self._approved_directional_streak = 0
            return

        if self._current_streak:
            progressed = (
                self._start_floor is not None
                and floor_value is not None
                and floor_value > self._start_floor
            )
            if progressed:
                context = "scroll_progress"
            elif self._entry_phase in {
                "launch",
                "special_escape",
                "support_departure",
            }:
                context = "dynamic_transition"
            else:
                context = "ordinary_recovered"
            self.recovery_samples.append(
                {
                    "steps": self._current_streak,
                    "context": context,
                    "entry_phase": self._entry_phase,
                    "floor_start": self._start_floor,
                    "floor_recovery": floor_value,
                }
            )
            self.recovered_count += 1
            self.max_recovered_streak = max(
                self.max_recovered_streak,
                self._current_streak,
            )
            self._current_streak = 0
            self._entry_phase = None
            self._start_floor = None
        self._last_valid_phase = phase
        self._approved_directional_streak = 0

    def finalize(self, *, terminal: bool) -> None:
        if self._finalized:
            return
        if self._current_streak:
            sample = {
                "steps": self._current_streak,
                "context": "terminal" if terminal else "unrecovered",
                "entry_phase": self._entry_phase,
                "floor_start": self._start_floor,
                "floor_recovery": None,
            }
            self.recovery_samples.append(sample)
            if terminal:
                self.terminal_count += 1
            else:
                self.unrecovered_count += 1
            self._current_streak = 0
        self._finalized = True


class SupportAlignedStallTracker:
    """Only flag RELEASE when a distinct departure target is actionable."""

    def __init__(self) -> None:
        self.support_settle_release_count = 0
        self.actionable_support_release_count = 0
        self.max_actionable_release_streak = 0
        self._current_actionable_streak = 0
        self._support_id: int | None = None
        self._target_id: int | None = None

    def update(
        self,
        memory: dict[str, Any],
        *,
        action: Action,
        reason: str,
    ) -> None:
        support_active = bool(memory.get("support_contact_active"))
        support_raw = memory.get("support_platform_id")
        target_raw = memory.get("target_platform_id")
        support_id = None if support_raw is None else int(support_raw)
        target_id = None if target_raw is None else int(target_raw)
        aligned_release = (
            support_active
            and action is Action.RELEASE_ALL
            and str(reason).startswith("aligned")
        )
        actionable = (
            aligned_release
            and support_id is not None
            and target_id is not None
            and target_id != support_id
        )
        if aligned_release and target_id == support_id:
            self.support_settle_release_count += 1
        if actionable:
            self.actionable_support_release_count += 1
            if (
                self._support_id == support_id
                and self._target_id == target_id
            ):
                self._current_actionable_streak += 1
            else:
                self._current_actionable_streak = 1
            self.max_actionable_release_streak = max(
                self.max_actionable_release_streak,
                self._current_actionable_streak,
            )
            self._support_id = support_id
            self._target_id = target_id
        else:
            self._current_actionable_streak = 0
            self._support_id = None
            self._target_id = None


class SupportDepartureTracker:
    """Measure repeated departure attempts while one support remains active."""

    def __init__(self, *, edge_threshold_pixels: float = 20.0) -> None:
        self.edge_threshold_pixels = max(0.0, float(edge_threshold_pixels))
        self.same_support_departure_cycle_count = 0
        self.support_departure_target_switch_count = 0
        self.support_departure_timeout_count = 0
        # Gate-facing counters only include an actual departure decision.
        self.support_edge_release_count = 0
        self.support_edge_opportunity_count = 0
        # Generic edge occupancy remains useful diagnostics, but same-support
        # settle and special-contact braking must not fail the departure Gate.
        self.generic_support_edge_release_count = 0
        self.generic_support_edge_opportunity_count = 0
        self.support_departure_exit_samples: list[int] = []
        self.max_support_departure_steps = 0
        self._support_id: int | None = None
        self._departure_starts_on_support = 0
        self._departure_active = False
        self._departure_destination_id: int | None = None
        self._departure_steps = 0
        self._last_reason: str | None = None

    def update(
        self,
        memory: dict[str, Any],
        *,
        action: Action,
        reason: str,
    ) -> None:
        support_active = bool(memory.get("support_contact_active"))
        support_id_raw = memory.get("support_platform_id")
        support_id = (
            None if support_id_raw is None else int(support_id_raw)
        )
        same_support = support_active and support_id == self._support_id
        if not same_support:
            if self._departure_active and (
                not support_active or support_id != self._support_id
            ):
                self.support_departure_exit_samples.append(
                    self._departure_steps
                )
            self._support_id = support_id if support_active else None
            self._departure_starts_on_support = 0

        departure_active = bool(memory.get("support_departure_active"))
        destination_raw = memory.get("support_departure_destination_id")
        destination_id = (
            None if destination_raw is None else int(destination_raw)
        )
        target_raw = memory.get("target_platform_id")
        target_id = None if target_raw is None else int(target_raw)
        edge_raw = memory.get("support_edge_distance")
        in_edge_zone = (
            support_active
            and edge_raw is not None
            and float(edge_raw) <= self.edge_threshold_pixels
        )
        if in_edge_zone:
            self.generic_support_edge_opportunity_count += 1
            if action is Action.RELEASE_ALL:
                self.generic_support_edge_release_count += 1

        actionable_edge = in_edge_zone and (
            departure_active
            or (
                target_id is not None
                and support_id is not None
                and target_id != support_id
            )
        )
        if actionable_edge:
            self.support_edge_opportunity_count += 1
            if action is Action.RELEASE_ALL:
                self.support_edge_release_count += 1

        steps = int(memory.get("support_departure_steps", 0) or 0)
        self.max_support_departure_steps = max(
            self.max_support_departure_steps,
            steps,
        )
        if departure_active and not self._departure_active:
            if same_support and self._departure_starts_on_support > 0:
                self.same_support_departure_cycle_count += 1
            self._departure_starts_on_support += 1
        elif (
            departure_active
            and self._departure_active
            and same_support
            and destination_id != self._departure_destination_id
        ):
            self.support_departure_target_switch_count += 1
        if departure_active and not same_support:
            self._departure_starts_on_support = 1
        if (
            reason == "support_departure_safety_abort"
            and self._last_reason != reason
        ):
            self.support_departure_timeout_count += 1

        self._departure_active = departure_active
        self._departure_destination_id = destination_id
        self._departure_steps = steps
        self._last_reason = reason


@dataclass(frozen=True)
class PhysicalResponseUpdate:
    direction: str | None
    latency_ms: float | None
    pending: bool
    timed_out: bool = False
    preexisting_motion: bool = False


class PhysicalResponseLatencyTracker:
    """量測方向命令到可見水平速度 onset；不把 backend return 當物理反應。"""

    def __init__(
        self,
        *,
        velocity_threshold: float = 10.0,
        max_wait_seconds: float = 0.5,
    ) -> None:
        self.velocity_threshold = max(0.0, float(velocity_threshold))
        self.max_wait_seconds = max(0.01, float(max_wait_seconds))
        self.reset()

    def reset(self) -> None:
        self._last_action = Action.RELEASE_ALL
        self._pending_action: Action | None = None
        self._pending_timestamp: float | None = None

    def update(
        self,
        action: Action,
        *,
        command_timestamp: float,
        observation: GameObservation,
        prior_observation: GameObservation | None = None,
    ) -> PhysicalResponseUpdate:
        if action is Action.RELEASE_ALL:
            self._last_action = action
            self._pending_action = None
            self._pending_timestamp = None
            return PhysicalResponseUpdate(None, None, False)
        if action is not self._last_action:
            prior_player = (
                None if prior_observation is None else prior_observation.player
            )
            prior_velocity_x = (
                0.0
                if prior_player is None
                else float(prior_player.get("velocity_x", 0.0))
            )
            already_moving = (
                action is Action.LEFT
                and prior_velocity_x <= -self.velocity_threshold
            ) or (
                action is Action.RIGHT
                and prior_velocity_x >= self.velocity_threshold
            )
            if already_moving:
                self._last_action = action
                self._pending_action = None
                self._pending_timestamp = None
                return PhysicalResponseUpdate(
                    action.name,
                    None,
                    False,
                    preexisting_motion=True,
                )
            self._pending_action = action
            self._pending_timestamp = float(command_timestamp)
        self._last_action = action
        if self._pending_action is None or self._pending_timestamp is None:
            return PhysicalResponseUpdate(action.name, None, False)

        elapsed = float(observation.timestamp) - self._pending_timestamp
        if elapsed > self.max_wait_seconds:
            direction = self._pending_action.name
            self._pending_action = None
            self._pending_timestamp = None
            return PhysicalResponseUpdate(direction, None, False, True)
        player = observation.player
        velocity_x = (
            0.0 if player is None else float(player.get("velocity_x", 0.0))
        )
        responded = (
            self._pending_action is Action.LEFT
            and velocity_x <= -self.velocity_threshold
        ) or (
            self._pending_action is Action.RIGHT
            and velocity_x >= self.velocity_threshold
        )
        if not responded:
            return PhysicalResponseUpdate(
                self._pending_action.name,
                None,
                True,
            )
        direction = self._pending_action.name
        latency_ms = max(0.0, elapsed * 1000.0)
        self._pending_action = None
        self._pending_timestamp = None
        return PhysicalResponseUpdate(direction, latency_ms, False)


def observation_confidence(observation: GameObservation) -> float:
    """Conservative deployable confidence from visible detector outputs."""

    if observation.player is None:
        return 0.0
    values = [float(observation.player.get("confidence", 0.0))]
    values.extend(
        float(platform.get("confidence", 0.0))
        for platform in observation.platforms
    )
    return float(np.clip(np.mean(values), 0.0, 1.0))


def safe_unapplied_terminal(
    observation: GameObservation,
    *,
    action_applied: bool,
    terminated: bool,
    truncated: bool,
) -> bool:
    """Accept a safety no-op only when the game has already left PLAYING."""

    return bool(
        not action_applied
        and (terminated or truncated)
        and observation.phase != GamePhase.PLAYING.value
    )


def playing_telemetry_required(
    observation: GameObservation,
    *,
    terminated: bool,
    truncated: bool,
) -> bool:
    """HUD/player telemetry is required only for an active PLAYING frame."""

    return bool(
        not terminated
        and not truncated
        and observation.phase == GamePhase.PLAYING.value
    )


def outward_wall_push_side(
    action: Action,
    *,
    player_x: float | None,
    playfield_left: float,
    playfield_right: float,
    margin: float,
) -> str | None:
    """Return the wall side only when the applied action pushes outward."""

    if player_x is None:
        return None
    if action is Action.LEFT and player_x <= playfield_left + margin:
        return "left"
    if action is Action.RIGHT and player_x >= playfield_right - margin:
        return "right"
    return None


def classify_terminal_reason(
    observation: GameObservation | None,
    *,
    forced_reason: str | None,
    reference_height: float,
) -> str:
    if forced_reason in {"step_limit", "time_limit", "total_limit"}:
        return "timeout"
    if observation is None or observation.player is None:
        return "unknown"
    health = int((observation.health or {}).get("segments") or 0)
    if health <= 0:
        return "health_depleted"
    ratio = float(observation.player.get("center_y", 0.0)) / max(
        1.0, reference_height
    )
    if ratio <= 0.28:
        return "top"
    if ratio >= 0.72:
        return "bottom"
    return "unknown"


def _quantile(values: list[float], q: float) -> float:
    return 0.0 if not values else float(np.quantile(values, q))


def _cvar_lower(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    count = max(1, ceil(len(values) * q))
    return float(np.mean(sorted(values)[:count]))


def apply_video_floor_maxima(
    episodes: Iterable[dict[str, Any]],
    observed_maxima: Iterable[int],
) -> list[dict[str, Any]]:
    """Apply independently replayed video maxima without mutating raw records.

    A video replay may recover a terminal-frame HUD increment which the live
    sidecar did not observe.  It may only increase a recorded maximum: a lower
    video value would be conflicting evidence and must be investigated instead
    of silently replacing the sidecar.
    """

    rows = [dict(item) for item in episodes]
    maxima = list(observed_maxima)
    if len(rows) != len(maxima):
        raise ValueError(
            "影片樓層數量與 episode 數量不一致："
            f"episodes={len(rows)} maxima={len(maxima)}"
        )
    for row, raw_observed in zip(rows, maxima, strict=True):
        if raw_observed is None:
            raise ValueError("影片樓層最大值不可為空。")
        observed = int(raw_observed)
        sidecar = max(
            int(row.get("floors", 0) or 0),
            int(row.get("floor_max", 0) or 0),
        )
        if observed < sidecar:
            raise ValueError(
                f"影片樓層 {observed} 低於 sidecar {sidecar}；"
                "拒絕以衝突證據覆寫。"
            )
        row["floor_max_sidecar"] = sidecar
        row["floors"] = observed
        row["floor_max"] = observed
        row["floor_video_corrected"] = observed > sidecar
    return rows


def reclassify_real_micro_episode(
    episode: dict[str, Any],
    controller_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Recompute semantic Gate telemetry from an actual controller sidecar."""

    rows = [dict(item) for item in controller_records]
    dropout = ObservationDropoutTracker(max_recoverable_steps=8)
    support_stall = SupportAlignedStallTracker()
    departure_tracker = SupportDepartureTracker(edge_threshold_pixels=20.0)
    active_wall_oscillation = DirectionOscillationTracker(max_step_gap=3)
    excluded_wall_context_steps = 0
    support_departure_abort_cooldown_count = 0
    support_departure_abort_cooldown_streak = 0
    max_support_departure_abort_cooldown_streak = 0
    landing_intercept_telemetry_available = bool(rows)
    landing_release_projection_telemetry_available = bool(rows)
    special_escape_destination_telemetry_available = bool(rows)
    special_contact_lifecycle_telemetry_available = bool(rows)
    landing_intercept_decision_count = 0
    landing_release_projection_decision_count = 0
    destination_aware_special_escape_count = 0
    momentum_guard_special_escape_count = 0
    special_escape_replan_count = 0
    special_contacts: dict[int, dict[str, Any]] = {}
    seen_special_contacts: set[int] = set()
    pre_special_context_samples: list[dict[str, Any]] = []
    preceding_invalid_streak = 0
    preceding_release_streak = 0
    preceding_dropout_release_streak = 0
    same_special_source_restart_count = 0
    special_escape_safety_abort_count = 0
    for index, row in enumerate(rows):
        action_raw = str(row.get("action", "RELEASE_ALL"))
        try:
            action = Action[action_raw]
        except KeyError as exc:
            raise ValueError(
                f"controller sidecar action 無效：{action_raw!r}"
            ) from exc
        memory_raw = row.get("controller_memory")
        memory = dict(memory_raw) if isinstance(memory_raw, dict) else {}
        reason = str(row.get("teacher_reason", ""))
        confidence = float(row.get("observation_confidence", 0.0) or 0.0)
        phase = str(memory.get("controller_phase", ""))
        landing_keys = {
            "landing_prediction_seconds",
            "landing_projected_x",
            "landing_safe_left",
            "landing_safe_right",
        }
        landing_release_keys = {
            "landing_release_projection_seconds",
            "landing_release_projected_x",
            "landing_release_horizontal_delta",
        }
        special_keys = {
            "special_escape_direction_source",
            "special_escape_destination_platform_id",
            "special_escape_replanned",
        }
        lifecycle_keys = {
            "special_contact_episode_id",
            "special_source_reacquire_count",
            "special_escape_replan_count",
            "special_escape_direction_reversal_count",
            "special_escape_forced_exit_active",
            "special_escape_safety_abort_active",
            "special_escape_safety_abort_count",
            "same_special_source_restart_count",
        }
        landing_intercept_telemetry_available = (
            landing_intercept_telemetry_available
            and landing_keys.issubset(memory)
        )
        landing_release_projection_telemetry_available = (
            landing_release_projection_telemetry_available
            and landing_release_keys.issubset(memory)
        )
        special_escape_destination_telemetry_available = (
            special_escape_destination_telemetry_available
            and special_keys.issubset(memory)
        )
        special_contact_lifecycle_telemetry_available = (
            special_contact_lifecycle_telemetry_available
            and lifecycle_keys.issubset(memory)
        )
        landing_intercept_decision_count += int(
            memory.get("landing_prediction_seconds") is not None
        )
        landing_release_projection_decision_count += int(
            memory.get("landing_release_projection_seconds") is not None
        )
        if reason.startswith("escape_special_contact"):
            direction_source = str(
                memory.get("special_escape_direction_source") or ""
            )
            destination_aware_special_escape_count += int(
                direction_source == "visible_landing"
            )
            momentum_guard_special_escape_count += int(
                direction_source
                in {"edge_momentum_guard", "edge_momentum_commit"}
            )
            special_escape_replan_count += int(
                bool(memory.get("special_escape_replanned", False))
            )
        contact_id_raw = memory.get("special_contact_episode_id")
        if contact_id_raw is not None:
            contact_id = int(contact_id_raw)
            if contact_id not in seen_special_contacts:
                pre_special_context_samples.append(
                    {
                        "step": int(row.get("step", index)),
                        "contact_id": contact_id,
                        "kind": str(
                            memory.get("special_source_platform_kind") or ""
                        ),
                        "dropout_steps": preceding_invalid_streak,
                        "release_steps": preceding_release_streak,
                        "dropout_release_steps": (
                            preceding_dropout_release_streak
                        ),
                    }
                )
                seen_special_contacts.add(contact_id)
            contact = special_contacts.setdefault(
                contact_id,
                {
                    "kind": str(
                        memory.get("special_source_platform_kind") or ""
                    ),
                    "max_steps": 0,
                    "reacquire_count": 0,
                    "replan_count": 0,
                    "direction_reversal_count": 0,
                    "direction_change_brake_count": 0,
                    "forced_exit": False,
                    "safety_abort": False,
                },
            )
            contact["max_steps"] = max(
                int(contact["max_steps"]),
                int(memory.get("special_escape_steps", 0)),
            )
            contact["reacquire_count"] = max(
                int(contact["reacquire_count"]),
                int(memory.get("special_source_reacquire_count", 0)),
            )
            contact["replan_count"] = max(
                int(contact["replan_count"]),
                int(memory.get("special_escape_replan_count", 0)),
            )
            contact["direction_reversal_count"] = max(
                int(contact["direction_reversal_count"]),
                int(
                    memory.get(
                        "special_escape_direction_reversal_count",
                        0,
                    )
                ),
            )
            contact["direction_change_brake_count"] += int(
                reason == "direction_change_brake"
            )
            contact["forced_exit"] = bool(contact["forced_exit"]) or bool(
                memory.get("special_escape_forced_exit_active", False)
            )
            contact["safety_abort"] = bool(contact["safety_abort"]) or bool(
                memory.get("special_escape_safety_abort_active", False)
            )
        same_special_source_restart_count = max(
            same_special_source_restart_count,
            int(memory.get("same_special_source_restart_count", 0)),
        )
        special_escape_safety_abort_count = max(
            special_escape_safety_abort_count,
            int(memory.get("special_escape_safety_abort_count", 0)),
        )
        floor_raw = row.get("floor")
        floor = (
            floor_raw.get("value")
            if isinstance(floor_raw, dict)
            else None
        )
        dropout.update(
            confidence=confidence,
            action=action,
            controller_phase=phase,
            floor=floor,
            approved_directional=(
                reason == "top_pressure_dropout_continue"
            ),
        )
        support_stall.update(memory, action=action, reason=reason)
        departure_tracker.update(memory, action=action, reason=reason)
        if reason == "support_departure_abort_cooldown":
            support_departure_abort_cooldown_count += 1
            support_departure_abort_cooldown_streak += 1
            max_support_departure_abort_cooldown_streak = max(
                max_support_departure_abort_cooldown_streak,
                support_departure_abort_cooldown_streak,
            )
        else:
            support_departure_abort_cooldown_streak = 0

        wall_safety_active = bool(
            memory.get("wall_guard_active")
            or memory.get("wall_evacuation_active")
        )
        excluded_context = (
            phase in {"special_escape", "launch"}
            or reason.startswith("escape_special_contact")
            or reason.startswith("escape_launch_platform")
        )
        eligible = wall_safety_active and not excluded_context
        if wall_safety_active and excluded_context:
            excluded_wall_context_steps += 1
        active_wall_oscillation.update(
            action,
            step=int(row.get("step", index)),
            eligible=eligible,
        )
        preceding_invalid_streak = (
            preceding_invalid_streak + 1 if confidence <= 0.0 else 0
        )
        preceding_release_streak = (
            preceding_release_streak + 1
            if action is Action.RELEASE_ALL
            else 0
        )
        preceding_dropout_release_streak = (
            preceding_dropout_release_streak + 1
            if confidence <= 0.0 and action is Action.RELEASE_ALL
            else 0
        )

    terminal_reason = str(episode.get("terminal_reason", "unknown"))
    dropout.finalize(
        terminal=terminal_reason in {"top", "bottom", "health_depleted"}
    )
    context_counts = Counter(
        str(sample["context"]) for sample in dropout.recovery_samples
    )
    semantically_valid = (
        dropout.unrecovered_count == 0
        and dropout.blind_directional_action_count == 0
        and dropout.max_recovered_streak <= dropout.max_recoverable_steps
        and dropout.max_approved_directional_streak <= 2
        and not any(
            str(row.get("teacher_reason", ""))
            == "top_pressure_dropout_exhausted"
            for row in rows
        )
    )
    top_pressure_dropout_exhausted_count = sum(
        str(row.get("teacher_reason", ""))
        == "top_pressure_dropout_exhausted"
        for row in rows
    )
    top_pressure_support_escape_count = sum(
        str(row.get("teacher_reason", ""))
        == "escape_top_pressure_support_dwell"
        for row in rows
    )
    return {
        **dict(episode),
        "observation_valid": semantically_valid,
        "observation_dropout_telemetry_available": bool(rows),
        "invalid_observation_step_count": dropout.invalid_step_count,
        "recovered_observation_dropout_count": dropout.recovered_count,
        "max_recovered_observation_dropout_streak": (
            dropout.max_recovered_streak
        ),
        "unrecovered_observation_dropout_count": dropout.unrecovered_count,
        "terminal_observation_dropout_count": dropout.terminal_count,
        "blind_directional_action_count": (
            dropout.blind_directional_action_count
        ),
        "top_pressure_dropout_continue_count": (
            dropout.approved_directional_action_count
        ),
        "max_top_pressure_dropout_continue_streak": (
            dropout.max_approved_directional_streak
        ),
        "top_pressure_dropout_exhausted_count": (
            top_pressure_dropout_exhausted_count
        ),
        "top_pressure_support_escape_count": (
            top_pressure_support_escape_count
        ),
        "observation_dropout_context_counts": dict(
            sorted(context_counts.items())
        ),
        "observation_dropout_samples": dropout.recovery_samples,
        "max_active_wall_direction_reversal_burst": (
            active_wall_oscillation.max_burst
        ),
        "active_wall_direction_reversal_count": (
            active_wall_oscillation.reversal_count
        ),
        "excluded_wall_special_context_steps": excluded_wall_context_steps,
        "support_settle_release_count": (
            support_stall.support_settle_release_count
        ),
        "actionable_support_release_count": (
            support_stall.actionable_support_release_count
        ),
        "max_actionable_support_aligned_release_streak": (
            support_stall.max_actionable_release_streak
        ),
        "support_departure_telemetry_available": bool(rows),
        "support_edge_actionable_telemetry_available": bool(rows),
        "same_support_departure_cycle_count": (
            departure_tracker.same_support_departure_cycle_count
        ),
        "support_departure_target_switch_count": (
            departure_tracker.support_departure_target_switch_count
        ),
        "support_departure_timeout_count": (
            departure_tracker.support_departure_timeout_count
        ),
        "support_edge_release_count": (
            departure_tracker.support_edge_release_count
        ),
        "support_edge_opportunity_count": (
            departure_tracker.support_edge_opportunity_count
        ),
        "generic_support_edge_release_count": (
            departure_tracker.generic_support_edge_release_count
        ),
        "generic_support_edge_opportunity_count": (
            departure_tracker.generic_support_edge_opportunity_count
        ),
        "support_departure_exit_samples": (
            departure_tracker.support_departure_exit_samples
        ),
        "max_support_departure_steps": (
            departure_tracker.max_support_departure_steps
        ),
        "support_departure_abort_cooldown_count": (
            support_departure_abort_cooldown_count
        ),
        "max_support_departure_abort_cooldown_streak": (
            max_support_departure_abort_cooldown_streak
        ),
        "landing_intercept_telemetry_available": (
            landing_intercept_telemetry_available
        ),
        "landing_release_projection_telemetry_available": (
            landing_release_projection_telemetry_available
        ),
        "special_escape_destination_telemetry_available": (
            special_escape_destination_telemetry_available
        ),
        "special_contact_lifecycle_telemetry_available": (
            special_contact_lifecycle_telemetry_available
        ),
        "landing_intercept_decision_count": (
            landing_intercept_decision_count
        ),
        "landing_release_projection_decision_count": (
            landing_release_projection_decision_count
        ),
        "destination_aware_special_escape_count": (
            destination_aware_special_escape_count
        ),
        "momentum_guard_special_escape_count": (
            momentum_guard_special_escape_count
        ),
        "special_escape_replan_count": special_escape_replan_count,
        "special_contact_count": len(special_contacts),
        "pre_special_context_samples": pre_special_context_samples,
        "max_pre_special_observation_dropout_streak": max(
            (
                int(item["dropout_steps"])
                for item in pre_special_context_samples
            ),
            default=0,
        ),
        "max_pre_special_release_streak": max(
            (
                int(item["release_steps"])
                for item in pre_special_context_samples
            ),
            default=0,
        ),
        "max_pre_special_dropout_release_streak": max(
            (
                int(item["dropout_release_steps"])
                for item in pre_special_context_samples
            ),
            default=0,
        ),
        "spring_special_contact_count": sum(
            str(item["kind"]) == "spring"
            for item in special_contacts.values()
        ),
        "spike_special_contact_count": sum(
            str(item["kind"]) == "spikes"
            for item in special_contacts.values()
        ),
        "special_source_reacquire_count": sum(
            int(item["reacquire_count"])
            for item in special_contacts.values()
        ),
        "same_special_source_restart_count": (
            same_special_source_restart_count
        ),
        "max_special_contact_steps": max(
            (int(item["max_steps"]) for item in special_contacts.values()),
            default=0,
        ),
        "max_special_escape_replan_count": max(
            (int(item["replan_count"]) for item in special_contacts.values()),
            default=0,
        ),
        "max_special_direction_reversal_count": max(
            (
                int(item["direction_reversal_count"])
                for item in special_contacts.values()
            ),
            default=0,
        ),
        "max_special_direction_change_brake_count": max(
            (
                int(item["direction_change_brake_count"])
                for item in special_contacts.values()
            ),
            default=0,
        ),
        "special_forced_exit_count": sum(
            bool(item["forced_exit"])
            for item in special_contacts.values()
        ),
        "special_escape_safety_abort_count": max(
            special_escape_safety_abort_count,
            sum(
                bool(item["safety_abort"])
                for item in special_contacts.values()
            ),
        ),
    }


def summarize_real_micro_gate(
    episodes: Iterable[dict[str, Any]],
    *,
    safety_events: Iterable[dict[str, Any]] = (),
    dry_run: bool = False,
    expected_episodes: int | None = None,
) -> dict[str, Any]:
    rows = [dict(item) for item in episodes]
    safety = [dict(item) for item in safety_events]
    floors = [float(item.get("floors", 0)) for item in rows]
    physical_samples = [
        dict(sample)
        for item in rows
        for sample in item.get("physical_response_samples", [])
        if sample.get("latency_ms") is not None
    ]
    physical_latencies = [
        float(sample["latency_ms"]) for sample in physical_samples
    ]
    physical_directions = {
        str(sample.get("direction")) for sample in physical_samples
    }
    actions: Counter[str] = Counter()
    for item in rows:
        actions.update(item.get("action_counts", {}))
    total_actions = sum(actions.values())
    wall_telemetry_available = bool(rows) and all(
        bool(item.get("wall_telemetry_available", False)) for item in rows
    )
    outward_wall_push_count = sum(
        int(item.get("outward_wall_push_count", 0)) for item in rows
    )
    max_outward_wall_push_streak = max(
        (
            int(item.get("max_outward_wall_push_streak", 0))
            for item in rows
        ),
        default=0,
    )
    player_telemetry_available = bool(rows) and all(
        bool(item.get("player_telemetry_available", False)) for item in rows
    )
    player_missing_step_count = sum(
        int(item.get("player_missing_step_count", 0)) for item in rows
    )
    max_player_missing_streak = max(
        (int(item.get("max_player_missing_streak", 0)) for item in rows),
        default=0,
    )
    observation_dropout_telemetry_available = bool(rows) and all(
        bool(item.get("observation_dropout_telemetry_available", False))
        for item in rows
    )
    dropout_forensic_telemetry_available = bool(rows) and all(
        bool(item.get("dropout_forensic_telemetry_available", False))
        for item in rows
    )
    dropout_forensic_snapshot_count = sum(
        int(item.get("dropout_forensic_snapshot_count", 0))
        for item in rows
    )
    dropout_forensic_dropped_snapshot_count = sum(
        int(item.get("dropout_forensic_dropped_snapshot_count", 0))
        for item in rows
    )
    invalid_observation_step_count = sum(
        int(item.get("invalid_observation_step_count", 0)) for item in rows
    )
    recovered_observation_dropout_count = sum(
        int(item.get("recovered_observation_dropout_count", 0))
        for item in rows
    )
    max_recovered_observation_dropout_streak = max(
        (
            int(item.get("max_recovered_observation_dropout_streak", 0))
            for item in rows
        ),
        default=0,
    )
    unrecovered_observation_dropout_count = sum(
        int(item.get("unrecovered_observation_dropout_count", 0))
        for item in rows
    )
    terminal_observation_dropout_count = sum(
        int(item.get("terminal_observation_dropout_count", 0))
        for item in rows
    )
    blind_directional_action_count = sum(
        int(item.get("blind_directional_action_count", 0))
        for item in rows
    )
    top_pressure_dropout_continue_count = sum(
        int(item.get("top_pressure_dropout_continue_count", 0))
        for item in rows
    )
    max_top_pressure_dropout_continue_streak = max(
        (
            int(item.get("max_top_pressure_dropout_continue_streak", 0))
            for item in rows
        ),
        default=0,
    )
    top_pressure_dropout_exhausted_count = sum(
        int(item.get("top_pressure_dropout_exhausted_count", 0))
        for item in rows
    )
    top_pressure_support_escape_count = sum(
        int(item.get("top_pressure_support_escape_count", 0))
        for item in rows
    )
    observation_dropout_context_counts: Counter[str] = Counter()
    for item in rows:
        observation_dropout_context_counts.update(
            item.get("observation_dropout_context_counts", {})
        )
    wall_reentry_cycle_count = sum(
        int(item.get("wall_reentry_cycle_count", 0)) for item in rows
    )
    rapid_direction_reversal_count = sum(
        int(item.get("rapid_direction_reversal_count", 0)) for item in rows
    )
    max_rapid_direction_reversal_burst = max(
        (
            int(item.get("max_rapid_direction_reversal_burst", 0))
            for item in rows
        ),
        default=0,
    )
    max_wall_direction_reversal_burst = max(
        (
            int(item.get("max_wall_direction_reversal_burst", 0))
            for item in rows
        ),
        default=0,
    )
    max_active_wall_direction_reversal_burst = max(
        (
            int(item.get("max_active_wall_direction_reversal_burst", 0))
            for item in rows
        ),
        default=0,
    )
    active_wall_direction_reversal_count = sum(
        int(item.get("active_wall_direction_reversal_count", 0))
        for item in rows
    )
    excluded_wall_special_context_steps = sum(
        int(item.get("excluded_wall_special_context_steps", 0))
        for item in rows
    )
    max_aligned_release_streak = max(
        (int(item.get("max_aligned_release_streak", 0)) for item in rows),
        default=0,
    )
    max_support_aligned_release_streak = max(
        (
            int(item.get("max_support_aligned_release_streak", 0))
            for item in rows
        ),
        default=0,
    )
    support_settle_release_count = sum(
        int(item.get("support_settle_release_count", 0)) for item in rows
    )
    actionable_support_release_count = sum(
        int(item.get("actionable_support_release_count", 0))
        for item in rows
    )
    max_actionable_support_aligned_release_streak = max(
        (
            int(
                item.get(
                    "max_actionable_support_aligned_release_streak",
                    0,
                )
            )
            for item in rows
        ),
        default=0,
    )
    support_departure_telemetry_available = bool(rows) and all(
        bool(item.get("support_departure_telemetry_available", False))
        for item in rows
    )
    support_edge_actionable_telemetry_available = bool(rows) and all(
        bool(
            item.get(
                "support_edge_actionable_telemetry_available",
                False,
            )
        )
        for item in rows
    )
    same_support_departure_cycle_count = sum(
        int(item.get("same_support_departure_cycle_count", 0))
        for item in rows
    )
    support_departure_target_switch_count = sum(
        int(item.get("support_departure_target_switch_count", 0))
        for item in rows
    )
    support_departure_timeout_count = sum(
        int(item.get("support_departure_timeout_count", 0))
        for item in rows
    )
    support_departure_abort_cooldown_count = sum(
        int(item.get("support_departure_abort_cooldown_count", 0))
        for item in rows
    )
    max_support_departure_abort_cooldown_streak = max(
        (
            int(item.get("max_support_departure_abort_cooldown_streak", 0))
            for item in rows
        ),
        default=0,
    )
    landing_intercept_telemetry_available = bool(rows) and all(
        bool(item.get("landing_intercept_telemetry_available", False))
        for item in rows
    )
    landing_release_projection_telemetry_available = bool(rows) and all(
        bool(
            item.get(
                "landing_release_projection_telemetry_available",
                False,
            )
        )
        for item in rows
    )
    special_escape_destination_telemetry_available = bool(rows) and all(
        bool(
            item.get(
                "special_escape_destination_telemetry_available",
                False,
            )
        )
        for item in rows
    )
    special_contact_lifecycle_telemetry_available = bool(rows) and all(
        bool(
            item.get(
                "special_contact_lifecycle_telemetry_available",
                False,
            )
        )
        for item in rows
    )
    landing_intercept_decision_count = sum(
        int(item.get("landing_intercept_decision_count", 0))
        for item in rows
    )
    landing_release_projection_decision_count = sum(
        int(item.get("landing_release_projection_decision_count", 0))
        for item in rows
    )
    destination_aware_special_escape_count = sum(
        int(item.get("destination_aware_special_escape_count", 0))
        for item in rows
    )
    momentum_guard_special_escape_count = sum(
        int(item.get("momentum_guard_special_escape_count", 0))
        for item in rows
    )
    special_escape_replan_count = sum(
        int(item.get("special_escape_replan_count", 0))
        for item in rows
    )
    special_contact_count = sum(
        int(item.get("special_contact_count", 0)) for item in rows
    )
    max_pre_special_observation_dropout_streak = max(
        (
            int(
                item.get(
                    "max_pre_special_observation_dropout_streak",
                    0,
                )
            )
            for item in rows
        ),
        default=0,
    )
    max_pre_special_release_streak = max(
        (
            int(item.get("max_pre_special_release_streak", 0))
            for item in rows
        ),
        default=0,
    )
    max_pre_special_dropout_release_streak = max(
        (
            int(
                item.get(
                    "max_pre_special_dropout_release_streak",
                    0,
                )
            )
            for item in rows
        ),
        default=0,
    )
    pre_special_context_samples = [
        {
            "episode": item.get("episode"),
            **dict(sample),
        }
        for item in rows
        for sample in item.get("pre_special_context_samples", [])
    ]
    spring_special_contact_count = sum(
        int(item.get("spring_special_contact_count", 0)) for item in rows
    )
    spike_special_contact_count = sum(
        int(item.get("spike_special_contact_count", 0)) for item in rows
    )
    special_source_reacquire_count = sum(
        int(item.get("special_source_reacquire_count", 0)) for item in rows
    )
    same_special_source_restart_count = sum(
        int(item.get("same_special_source_restart_count", 0))
        for item in rows
    )
    max_special_contact_steps = max(
        (int(item.get("max_special_contact_steps", 0)) for item in rows),
        default=0,
    )
    max_special_escape_replan_count = max(
        (
            int(item.get("max_special_escape_replan_count", 0))
            for item in rows
        ),
        default=0,
    )
    max_special_direction_reversal_count = max(
        (
            int(item.get("max_special_direction_reversal_count", 0))
            for item in rows
        ),
        default=0,
    )
    max_special_direction_change_brake_count = max(
        (
            int(item.get("max_special_direction_change_brake_count", 0))
            for item in rows
        ),
        default=0,
    )
    special_forced_exit_count = sum(
        int(item.get("special_forced_exit_count", 0)) for item in rows
    )
    special_escape_safety_abort_count = sum(
        int(item.get("special_escape_safety_abort_count", 0))
        for item in rows
    )
    support_edge_release_count = sum(
        int(item.get("support_edge_release_count", 0))
        for item in rows
    )
    support_edge_opportunity_count = sum(
        int(item.get("support_edge_opportunity_count", 0))
        for item in rows
    )
    support_edge_release_ratio = (
        support_edge_release_count / support_edge_opportunity_count
        if support_edge_opportunity_count
        else 1.0
    )
    generic_support_edge_release_count = sum(
        int(item.get("generic_support_edge_release_count", 0))
        for item in rows
    )
    generic_support_edge_opportunity_count = sum(
        int(item.get("generic_support_edge_opportunity_count", 0))
        for item in rows
    )
    generic_support_edge_release_ratio = (
        generic_support_edge_release_count
        / generic_support_edge_opportunity_count
        if generic_support_edge_opportunity_count
        else 0.0
    )
    support_departure_exit_samples = [
        int(value)
        for item in rows
        for value in item.get("support_departure_exit_samples", [])
    ]
    max_support_departure_steps = max(
        (int(item.get("max_support_departure_steps", 0)) for item in rows),
        default=0,
    )
    max_share = (
        max(actions.values(), default=0) / total_actions
        if total_actions
        else 0.0
    )
    videos_complete = bool(rows) and all(
        bool(item.get("video_complete")) for item in rows
    )
    records_complete = bool(rows) and all(
        int(item.get("controller_records", -1)) == int(item.get("steps", -2))
        and int(item.get("transition_records", -1)) == int(item.get("steps", -2))
        for item in rows
    )
    target_lock_seen = any(
        bool(item.get("target_lock_seen")) for item in rows
    )
    observation_valid = bool(rows) and all(
        bool(item.get("observation_valid")) for item in rows
    )
    floor_counter_available = bool(rows) and all(
        bool(item.get("floor_counter_available", True)) for item in rows
    )
    comparable_failures = bool(rows) and all(
        str(item.get("terminal_reason", "unknown")) in FAILURE_TAXONOMY
        for item in rows
    )
    name_entry_dialog_detected_count = sum(
        bool(item.get("name_entry_dialog_detected", False))
        for item in rows
    )
    name_entry_dialog_dismissed_count = sum(
        bool(item.get("name_entry_dialog_dismissed", False))
        for item in rows
    )
    bottom_death_count = sum(
        str(item.get("terminal_reason")) == "bottom" for item in rows
    )
    early_bottom_death_count = sum(
        str(item.get("terminal_reason")) == "bottom"
        and float(item.get("floors", 0)) < 3
        for item in rows
    )
    early_bottom_death_budget = max(
        0,
        len(rows) - ceil(0.66 * len(rows)),
    )
    special_brake_budget_violation_count = sum(
        not (
            int(item.get("max_special_direction_change_brake_count", 0))
            <= 2
            and int(
                item.get("max_special_direction_change_brake_count", 0)
            )
            <= 1
            + int(item.get("max_special_direction_reversal_count", 0))
        )
        for item in rows
    )
    metrics = {
        "episodes": len(rows),
        "floors_semantics": "visual_hud_max_floor",
        "mean_floors": float(np.mean(floors)) if floors else 0.0,
        "median_floors": float(np.median(floors)) if floors else 0.0,
        "floor_q25": _quantile(floors, 0.25),
        "floor_cvar25": _cvar_lower(floors, 0.25),
        "reach_floor_1": sum(value >= 1 for value in floors),
        "reach_floor_3": sum(value >= 3 for value in floors),
        "reach_floor_5": sum(value >= 5 for value in floors),
        "reach_floor_10": sum(value >= 10 for value in floors),
        "action_counts": dict(sorted(actions.items())),
        "max_action_share": max_share,
        "terminal_reasons": dict(
            sorted(Counter(str(item.get("terminal_reason", "unknown")) for item in rows).items())
        ),
        "safety_event_count": len(safety),
        "outward_wall_push_count": outward_wall_push_count,
        "max_outward_wall_push_streak": max_outward_wall_push_streak,
        "player_missing_step_count": player_missing_step_count,
        "max_player_missing_streak": max_player_missing_streak,
        "invalid_observation_step_count": invalid_observation_step_count,
        "recovered_observation_dropout_count": (
            recovered_observation_dropout_count
        ),
        "max_recovered_observation_dropout_streak": (
            max_recovered_observation_dropout_streak
        ),
        "unrecovered_observation_dropout_count": (
            unrecovered_observation_dropout_count
        ),
        "terminal_observation_dropout_count": (
            terminal_observation_dropout_count
        ),
        "blind_directional_action_count": blind_directional_action_count,
        "top_pressure_dropout_continue_count": (
            top_pressure_dropout_continue_count
        ),
        "max_top_pressure_dropout_continue_streak": (
            max_top_pressure_dropout_continue_streak
        ),
        "top_pressure_dropout_exhausted_count": (
            top_pressure_dropout_exhausted_count
        ),
        "top_pressure_support_escape_count": (
            top_pressure_support_escape_count
        ),
        "observation_dropout_context_counts": dict(
            sorted(observation_dropout_context_counts.items())
        ),
        "dropout_forensic_snapshot_count": dropout_forensic_snapshot_count,
        "dropout_forensic_dropped_snapshot_count": (
            dropout_forensic_dropped_snapshot_count
        ),
        "wall_reentry_cycle_count": wall_reentry_cycle_count,
        "rapid_direction_reversal_count": rapid_direction_reversal_count,
        "max_rapid_direction_reversal_burst": (
            max_rapid_direction_reversal_burst
        ),
        "max_wall_direction_reversal_burst": (
            max_wall_direction_reversal_burst
        ),
        "max_active_wall_direction_reversal_burst": (
            max_active_wall_direction_reversal_burst
        ),
        "active_wall_direction_reversal_count": (
            active_wall_direction_reversal_count
        ),
        "excluded_wall_special_context_steps": (
            excluded_wall_special_context_steps
        ),
        "max_aligned_release_streak": max_aligned_release_streak,
        "max_support_aligned_release_streak": (
            max_support_aligned_release_streak
        ),
        "support_settle_release_count": support_settle_release_count,
        "actionable_support_release_count": (
            actionable_support_release_count
        ),
        "max_actionable_support_aligned_release_streak": (
            max_actionable_support_aligned_release_streak
        ),
        "same_support_departure_cycle_count": (
            same_support_departure_cycle_count
        ),
        "support_departure_target_switch_count": (
            support_departure_target_switch_count
        ),
        "support_departure_timeout_count": support_departure_timeout_count,
        "support_departure_abort_cooldown_count": (
            support_departure_abort_cooldown_count
        ),
        "max_support_departure_abort_cooldown_streak": (
            max_support_departure_abort_cooldown_streak
        ),
        "landing_intercept_decision_count": (
            landing_intercept_decision_count
        ),
        "landing_release_projection_decision_count": (
            landing_release_projection_decision_count
        ),
        "destination_aware_special_escape_count": (
            destination_aware_special_escape_count
        ),
        "momentum_guard_special_escape_count": (
            momentum_guard_special_escape_count
        ),
        "special_escape_replan_count": special_escape_replan_count,
        "special_contact_count": special_contact_count,
        "max_pre_special_observation_dropout_streak": (
            max_pre_special_observation_dropout_streak
        ),
        "max_pre_special_release_streak": max_pre_special_release_streak,
        "max_pre_special_dropout_release_streak": (
            max_pre_special_dropout_release_streak
        ),
        "pre_special_context_samples": pre_special_context_samples,
        "spring_special_contact_count": spring_special_contact_count,
        "spike_special_contact_count": spike_special_contact_count,
        "special_source_reacquire_count": special_source_reacquire_count,
        "same_special_source_restart_count": (
            same_special_source_restart_count
        ),
        "max_special_contact_steps": max_special_contact_steps,
        "max_special_escape_replan_count": (
            max_special_escape_replan_count
        ),
        "max_special_direction_reversal_count": (
            max_special_direction_reversal_count
        ),
        "max_special_direction_change_brake_count": (
            max_special_direction_change_brake_count
        ),
        "special_forced_exit_count": special_forced_exit_count,
        "special_escape_safety_abort_count": (
            special_escape_safety_abort_count
        ),
        "support_edge_release_count": support_edge_release_count,
        "support_edge_opportunity_count": support_edge_opportunity_count,
        "support_edge_release_ratio": support_edge_release_ratio,
        "generic_support_edge_release_count": (
            generic_support_edge_release_count
        ),
        "generic_support_edge_opportunity_count": (
            generic_support_edge_opportunity_count
        ),
        "generic_support_edge_release_ratio": (
            generic_support_edge_release_ratio
        ),
        "support_departure_exit_sample_count": len(
            support_departure_exit_samples
        ),
        "support_departure_exit_steps_median": (
            None
            if not support_departure_exit_samples
            else float(np.median(support_departure_exit_samples))
        ),
        "max_support_departure_steps": max_support_departure_steps,
        "name_entry_dialog_detected_count": (
            name_entry_dialog_detected_count
        ),
        "name_entry_dialog_dismissed_count": (
            name_entry_dialog_dismissed_count
        ),
        "bottom_death_count": bottom_death_count,
        "early_bottom_death_count": early_bottom_death_count,
        "early_bottom_death_budget": early_bottom_death_budget,
        "special_brake_budget_violation_count": (
            special_brake_budget_violation_count
        ),
        "floor_1_bottom_death_count": sum(
            float(item.get("floors", 0)) <= 1
            and str(item.get("terminal_reason")) == "bottom"
            for item in rows
        ),
        "physical_response_sample_count": len(physical_samples),
        "physical_response_latency_median_ms": (
            None
            if not physical_latencies
            else float(np.median(physical_latencies))
        ),
        "physical_response_latency_p95_ms": (
            None
            if not physical_latencies
            else float(np.quantile(physical_latencies, 0.95))
        ),
    }
    checks = {
        "actual_not_dry_run": not dry_run,
        "three_complete_episodes": len(rows) >= 3,
        "requested_episodes_complete": (
            expected_episodes is None or len(rows) == expected_episodes
        ),
        "safety_events_zero": len(safety) == 0,
        "name_entry_dialogs_safely_handled": (
            name_entry_dialog_detected_count
            == name_entry_dialog_dismissed_count
        ),
        "observation_valid": observation_valid,
        "floor_counter_available": floor_counter_available,
        "wall_telemetry_available": wall_telemetry_available,
        "player_telemetry_available": player_telemetry_available,
        "observation_dropout_telemetry_available": (
            observation_dropout_telemetry_available
        ),
        "dropout_forensics_available": (
            dropout_forensic_telemetry_available
        ),
        "support_departure_telemetry_available": (
            support_departure_telemetry_available
        ),
        "support_edge_actionable_telemetry_available": (
            support_edge_actionable_telemetry_available
        ),
        "landing_intercept_telemetry_available": (
            landing_intercept_telemetry_available
        ),
        "landing_release_projection_telemetry_available": (
            landing_release_projection_telemetry_available
        ),
        "special_escape_destination_telemetry_available": (
            special_escape_destination_telemetry_available
        ),
        "special_contact_lifecycle_telemetry_available": (
            special_contact_lifecycle_telemetry_available
        ),
        "special_contact_observed": special_contact_count > 0,
        "pre_special_observation_dropout_bounded": (
            max_pre_special_observation_dropout_streak
            <= PRE_SPECIAL_DROPOUT_MAX_STEPS
        ),
        "pre_special_dropout_release_bounded": (
            max_pre_special_dropout_release_streak
            <= PRE_SPECIAL_DROPOUT_MAX_STEPS
        ),
        "same_special_source_restarts_zero": (
            same_special_source_restart_count == 0
        ),
        "special_escape_safety_aborts_zero": (
            special_escape_safety_abort_count == 0
        ),
        "special_escape_replans_bounded": (
            max_special_escape_replan_count <= 1
            and max_special_direction_reversal_count <= 1
        ),
        "special_direction_change_brakes_bounded": (
            special_brake_budget_violation_count == 0
        ),
        "special_contact_steps_bounded": (
            max_special_contact_steps
            <= SPECIAL_CONTACT_ABSOLUTE_MAX_STEPS
        ),
        "recoverable_player_dropout_bounded": (
            max_recovered_observation_dropout_streak <= 8
        ),
        "unrecovered_player_dropouts_zero": (
            unrecovered_observation_dropout_count == 0
        ),
        "blind_directional_actions_zero": (
            blind_directional_action_count == 0
        ),
        "top_pressure_continuation_bounded": (
            max_top_pressure_dropout_continue_streak <= 2
        ),
        "top_pressure_dropout_exhaustion_zero": (
            top_pressure_dropout_exhausted_count == 0
        ),
        "outward_wall_push_zero": (
            outward_wall_push_count == 0
            and max_outward_wall_push_streak == 0
        ),
        "wall_reentry_cycles_zero": wall_reentry_cycle_count == 0,
        "wall_safety_oscillation_bounded": (
            max_active_wall_direction_reversal_burst <= 2
        ),
        "actionable_support_release_zero": (
            actionable_support_release_count == 0
            and max_actionable_support_aligned_release_streak == 0
        ),
        "same_support_departure_cycles_zero": (
            same_support_departure_cycle_count == 0
        ),
        "support_departure_target_stable": (
            support_departure_target_switch_count == 0
        ),
        "support_departure_timeouts_zero": (
            support_departure_timeout_count == 0
        ),
        "support_departure_abort_cooldown_bounded": (
            max_support_departure_abort_cooldown_streak <= 2
        ),
        "support_edge_release_bounded": (
            support_edge_opportunity_count > 0
            and support_edge_release_ratio <= 0.25
        ),
        "support_departure_exit_observed": bool(
            support_departure_exit_samples
        ),
        "support_departure_steps_bounded": max_support_departure_steps <= 8,
        "floor_1_bottom_deaths_zero": not any(
            float(item.get("floors", 0)) <= 1
            and str(item.get("terminal_reason")) == "bottom"
            for item in rows
        ),
        "physical_response_latency_measured": (
            len(physical_samples) >= 2
            and {"LEFT", "RIGHT"}.issubset(physical_directions)
        ),
        "target_lock_seen": target_lock_seen,
        "controller_and_transition_records_complete": records_complete,
        "videos_complete": videos_complete,
        "no_action_collapse": total_actions > 0 and max_share < 0.98,
        "reach_floor_3_case": (
            sum(value >= 3 for value in floors)
            >= ceil(0.66 * len(rows))
        ),
        "reach_floor_5_case": (
            sum(value >= 5 for value in floors)
            >= (
                4
                if len(rows) >= 10
                else (2 if len(rows) >= 5 else 1)
            )
        ),
        "early_bottom_deaths_bounded": (
            early_bottom_death_count <= early_bottom_death_budget
        ),
        "ten_episode_special_kind_coverage": (
            len(rows) < 10
            or (
                spring_special_contact_count > 0
                and spike_special_contact_count > 0
            )
        ),
        "failure_taxonomy_comparable": comparable_failures,
    }
    return {
        "experiment": (
            f"teacher-real-game-micro-gate-v{REAL_GAME_GATE_VERSION}"
        ),
        "dry_run": dry_run,
        "episodes": rows,
        "safety_events": safety,
        "metrics": metrics,
        "gate": {
            "status": (
                "PENDING" if dry_run else ("PASS" if all(checks.values()) else "FAIL")
            ),
            "passed": bool(not dry_run and all(checks.values())),
            "checks": checks,
        },
    }


def dry_run_manifest(
    limits: RealGameMicroLimits,
    *,
    dismiss_name_entry: bool = False,
) -> dict[str, Any]:
    limits.validate()
    return {
        "experiment": (
            f"teacher-real-game-micro-gate-v{REAL_GAME_GATE_VERSION}"
        ),
        "mode": "dry-run",
        "gate_status": "PENDING",
        "limits": limits.to_dict(),
        "confirmation_phrase": "TEACHER REAL MICRO",
        "safety": {
            "auto_launch": False,
            "unique_verified_foreground_required": True,
            "f8_enabled": True,
            "release_all_on_focus_loss_exception_ctrl_c_exit": True,
            "verified_name_entry_dialog_action": (
                "exact owned #32770 modal only; press Enter once; no text"
            ),
            "verified_name_entry_dialog_dismissal_enabled": bool(
                dismiss_name_entry
            ),
            "dry_run_loads_input_backend": False,
            "dry_run_sends_input": False,
            "inward_wall_guard_enabled": True,
            "latched_wall_evacuation_enabled": True,
            "player_dropout_bridge_max_steps": 2,
            "recoverable_dropout_gate_max_steps": 8,
            "support_departure_latched": True,
            "support_edge_gate_semantics": (
                "actionable target differs from support or departure active; "
                "generic edge occupancy remains diagnostic"
            ),
            "top_pressure_dropout_directional_bridge_max_steps": 2,
            "ordinary_dropout_actions_must_release": True,
            "lossless_dropout_forensics_bounded_per_episode": 6,
            "special_escape_excluded_from_wall_oscillation": True,
            "adaptive_landing_intercept_enabled": True,
            "release_aware_landing_intercept_enabled": True,
            "destination_aware_special_escape_enabled": True,
            "semantic_special_contact_identity_enabled": True,
            "special_contact_direction_replan_limit": 1,
            "special_direction_change_brake_budget": (
                "one entry brake plus one brake per permitted reversal; "
                "absolute maximum two"
            ),
            "special_contact_absolute_max_steps": (
                SPECIAL_CONTACT_ABSOLUTE_MAX_STEPS
            ),
            "pre_special_dropout_max_steps": (
                PRE_SPECIAL_DROPOUT_MAX_STEPS
            ),
        },
        "required_gate_metrics": [
            "outward_wall_push_count",
            "max_outward_wall_push_streak",
            "max_player_missing_streak",
            "max_recovered_observation_dropout_streak",
            "unrecovered_observation_dropout_count",
            "blind_directional_action_count",
            "top_pressure_dropout_continue_count",
            "max_top_pressure_dropout_continue_streak",
            "top_pressure_dropout_exhausted_count",
            "top_pressure_support_escape_count",
            "dropout_forensic_snapshot_count",
            "dropout_forensic_dropped_snapshot_count",
            "wall_reentry_cycle_count",
            "max_rapid_direction_reversal_burst",
            "max_wall_direction_reversal_burst",
            "max_active_wall_direction_reversal_burst",
            "same_support_departure_cycle_count",
            "support_departure_target_switch_count",
            "support_departure_timeout_count",
            "support_departure_abort_cooldown_count",
            "max_support_departure_abort_cooldown_streak",
            "landing_intercept_decision_count",
            "landing_release_projection_decision_count",
            "destination_aware_special_escape_count",
            "momentum_guard_special_escape_count",
            "special_escape_replan_count",
            "special_contact_count",
            "max_pre_special_observation_dropout_streak",
            "max_pre_special_release_streak",
            "max_pre_special_dropout_release_streak",
            "spring_special_contact_count",
            "spike_special_contact_count",
            "special_source_reacquire_count",
            "same_special_source_restart_count",
            "max_special_contact_steps",
            "max_special_escape_replan_count",
            "max_special_direction_reversal_count",
            "max_special_direction_change_brake_count",
            "special_brake_budget_violation_count",
            "bottom_death_count",
            "early_bottom_death_count",
            "early_bottom_death_budget",
            "special_forced_exit_count",
            "special_escape_safety_abort_count",
            "support_edge_release_count",
            "support_edge_opportunity_count",
            "support_edge_release_ratio",
            "generic_support_edge_release_count",
            "generic_support_edge_opportunity_count",
            "generic_support_edge_release_ratio",
            "support_departure_exit_sample_count",
            "max_support_aligned_release_streak",
            "max_actionable_support_aligned_release_streak",
            "floor_1_bottom_death_count",
            "name_entry_dialog_detected_count",
            "name_entry_dialog_dismissed_count",
        ],
        "actual_artifacts": [
            "episode_XX.transitions.jsonl",
            "episode_XX.controller.jsonl",
            "episode_XX.mp4",
            "episode_XX.dropout/manifest.json",
            "episode_XX.dropout/*.raw.png (bounded)",
            "episode_XX.dropout/*.player-mask.png (bounded)",
            "teacher_real_game_micro_gate.json",
        ],
        "next_command": (
            "python scripts/run_teacher_real_game_micro_gate.py --execute "
            f"--episodes {limits.episodes} "
            f"--max-steps-per-episode {limits.max_steps_per_episode} "
            f"--max-seconds-per-episode {limits.max_seconds_per_episode} "
            f"--max-total-steps {limits.max_total_steps} "
            f"--max-total-seconds {limits.max_total_seconds}"
            + (" --dismiss-name-entry" if dismiss_name_entry else "")
        ),
    }
