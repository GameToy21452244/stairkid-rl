from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from .calibration_analysis import (
    LATEST,
    PLAYER_HALF_WIDTH_PX,
    REFERENCE_HEIGHT,
    REFERENCE_WIDTH,
    VELOCITY_SCALE,
    player_state,
)


PLAYER_HALF_HEIGHT_PX = 13.5


@dataclass
class ScreenPlatform:
    center_x: float
    top: float
    width: float
    kind: float


@dataclass
class PredictedPlayer:
    x: float
    y: float
    vx: float
    vy: float
    motion: float
    phase_steps: int = 0
    rising_duration_steps: int = 3


def _linear_fit(features: list[list[float]], targets: list[float]) -> np.ndarray:
    if not features:
        raise ValueError("校正模型缺少可擬合樣本。")
    matrix = np.asarray(features, dtype=np.float64)
    values = np.asarray(targets, dtype=np.float64)
    return np.linalg.lstsq(matrix, values, rcond=None)[0]


def _platforms(values: list[float], player: dict[str, float]) -> list[ScreenPlatform]:
    result = []
    for slot in range(8):
        base = LATEST + 16 + slot * 6
        if values[base] <= 0.5:
            continue
        result.append(
            ScreenPlatform(
                center_x=(
                    player["x"] + values[base + 1] * REFERENCE_WIDTH
                ),
                top=player["y"] + values[base + 2] * REFERENCE_HEIGHT,
                width=values[base + 3] * REFERENCE_WIDTH,
                kind=values[base + 5],
            )
        )
    return result


@dataclass(frozen=True)
class CalibratedObservationModel:
    vx_coefficients: dict[int, np.ndarray]
    vy_coefficients: dict[int, np.ndarray]
    dx_coefficients: dict[int, np.ndarray]
    dy_coefficients: dict[int, np.ndarray]
    scroll_velocity_y: float
    normal_bounce_velocity_y: float
    spring_bounce_velocity_y: float
    normal_rising_duration_steps: int
    spring_rising_duration_steps: int
    apex_velocity_y: float
    apex_delta_y: float
    screen_gravity_y: float
    max_horizontal_speed: float = 230.0
    horizontal_contact_margin_px: float = 0.0
    vertical_contact_margin_px: float = 2.0

    @classmethod
    def fit(cls, rows: Iterable[dict[str, Any]]) -> "CalibratedObservationModel":
        rows = list(rows)
        continuous = []
        scroll_samples = []
        platform_velocity_samples = []
        normal_bounces = []
        spring_bounces = []
        apex_velocities = []
        apex_deltas = []
        normal_rising_durations = []
        spring_rising_durations = []
        position_gravity_samples = []
        active_landing: tuple[int, bool] | None = None
        active_source: str | None = None
        for row in rows:
            before = player_state(row["observation"])
            after = player_state(row["next_observation"])
            dt = (
                row["next_observation_timestamp"]
                - row["observation_timestamp"]
            )
            scroll_samples.append(
                row["observation"][LATEST + 7] * VELOCITY_SCALE
            )
            if dt > 0 and before["present"] > 0.5 and after["present"] > 0.5:
                before_platforms = _platforms(row["observation"], before)
                after_platforms = _platforms(row["next_observation"], after)
                used_after: set[int] = set()
                for platform in before_platforms:
                    candidates = [
                        (
                            abs(platform.center_x - candidate.center_x)
                            + abs(platform.top - candidate.top),
                            index,
                            candidate,
                        )
                        for index, candidate in enumerate(after_platforms)
                        if (
                            index not in used_after
                            and platform.kind == candidate.kind
                            and abs(platform.center_x - candidate.center_x) < 3
                            and abs(platform.top - candidate.top) < 30
                        )
                    ]
                    if not candidates:
                        continue
                    _, index, candidate = min(candidates)
                    used_after.add(index)
                    platform_velocity_samples.append(
                        (candidate.top - platform.top) / dt
                    )
            event_names = {
                event.get("type") for event in row.get("events", [])
            }
            source = str(row.get("_source", row.get("episode_id", "")))
            if source != active_source:
                active_source = source
                active_landing = None
            if "landed" in event_names:
                target = (
                    spring_bounces
                    if "spring_bounce" in event_names
                    else normal_bounces
                )
                target.append(after["vy"])
                active_landing = (
                    int(row.get("step", 0)),
                    "spring_bounce" in event_names,
                )
            if before["motion"] < -0.5 and after["motion"] > 0.5:
                apex_velocities.append(after["vy"])
                apex_deltas.append(after["y"] - before["y"])
                if active_landing is not None:
                    landing_step, was_spring = active_landing
                    duration = int(row.get("step", 0)) - landing_step
                    if duration > 0:
                        (
                            spring_rising_durations
                            if was_spring
                            else normal_rising_durations
                        ).append(duration)
                    active_landing = None
            if (
                before["present"] > 0.5
                and after["present"] > 0.5
                and not event_names
                and dt > 0
                and abs(before["motion"]) > 0.5
                and before["motion"] == after["motion"]
            ):
                continuous.append((row, before, after, dt))

        for previous, current in zip(rows, rows[1:]):
            if (
                str(previous.get("_source", previous.get("episode_id", "")))
                != str(current.get("_source", current.get("episode_id", "")))
                or int(current.get("step", -1))
                != int(previous.get("step", -2)) + 1
                or previous.get("events")
                or current.get("events")
            ):
                continue
            first = player_state(previous["observation"])
            middle = player_state(previous["next_observation"])
            last = player_state(current["next_observation"])
            dt_first = (
                previous["next_observation_timestamp"]
                - previous["observation_timestamp"]
            )
            dt_last = (
                current["next_observation_timestamp"]
                - current["observation_timestamp"]
            )
            if (
                first["present"] <= 0.5
                or middle["present"] <= 0.5
                or last["present"] <= 0.5
                or dt_first <= 0
                or dt_last <= 0
            ):
                continue
            velocity_first = (middle["y"] - first["y"]) / dt_first
            velocity_last = (last["y"] - middle["y"]) / dt_last
            position_gravity_samples.append(
                (velocity_last - velocity_first)
                / ((dt_first + dt_last) / 2)
            )

        vx_coefficients = {}
        dx_coefficients = {}
        for action in (0, 1, 2):
            subset = [
                item for item in continuous if item[0]["action"] == action
            ]
            vx_coefficients[action] = _linear_fit(
                [[before["vx"], 1.0] for _, before, _, _ in subset],
                [after["vx"] for _, _, after, _ in subset],
            )
            dx_coefficients[action] = _linear_fit(
                [
                    [before["vx"] * dt, after["vx"] * dt, dt]
                    for _, before, after, dt in subset
                ],
                [after["x"] - before["x"] for _, before, after, _ in subset],
            )

        vy_coefficients = {}
        dy_coefficients = {}
        for motion in (-1, 1):
            subset = [
                item
                for item in continuous
                if int(item[1]["motion"]) == motion
            ]
            vy_coefficients[motion] = _linear_fit(
                [[before["vy"], 1.0] for _, before, _, _ in subset],
                [after["vy"] for _, _, after, _ in subset],
            )
            dy_coefficients[motion] = _linear_fit(
                [
                    [before["vy"] * dt, after["vy"] * dt, dt]
                    for _, before, after, dt in subset
                ],
                [after["y"] - before["y"] for _, before, after, _ in subset],
            )

        def robust_median(values: list[float], fallback: float) -> float:
            return float(np.median(values)) if values else fallback

        nonzero_scroll = [value for value in scroll_samples if abs(value) > 1]
        return cls(
            vx_coefficients=vx_coefficients,
            vy_coefficients=vy_coefficients,
            dx_coefficients=dx_coefficients,
            dy_coefficients=dy_coefficients,
            scroll_velocity_y=robust_median(
                platform_velocity_samples,
                robust_median(nonzero_scroll, -96.0),
            ),
            normal_bounce_velocity_y=robust_median(normal_bounces, -92.0),
            spring_bounce_velocity_y=robust_median(spring_bounces, -180.0),
            normal_rising_duration_steps=max(
                1,
                round(robust_median(normal_rising_durations, 3.0)),
            ),
            spring_rising_duration_steps=max(
                1,
                round(robust_median(spring_rising_durations, 3.0)),
            ),
            apex_velocity_y=robust_median(apex_velocities, 55.0),
            apex_delta_y=robust_median(apex_deltas, 6.0),
            screen_gravity_y=robust_median(
                position_gravity_samples,
                192.0,
            ),
        )

    def initial_state(
        self, values: list[float]
    ) -> tuple[PredictedPlayer, list[ScreenPlatform]]:
        state = player_state(values)
        history_motions = [
            values[frame * 67 + 5] for frame in range(4)
        ]
        consecutive_rising = 0
        for motion in reversed(history_motions):
            if motion < -0.5:
                consecutive_rising += 1
            else:
                break
        return (
            PredictedPlayer(
                x=state["x"],
                y=state["y"],
                vx=state["vx"],
                vy=state["vy"],
                motion=state["motion"],
                phase_steps=max(0, consecutive_rising - 1),
                rising_duration_steps=self.normal_rising_duration_steps,
            ),
            _platforms(values, state),
        )

    def step(
        self,
        player: PredictedPlayer,
        platforms: list[ScreenPlatform],
        *,
        action: int,
        dt: float,
    ) -> bool:
        old_x = player.x
        old_y = player.y
        old_vx = player.vx
        old_vy = player.vy
        motion = -1 if player.motion < 0 else 1

        vx_coeff = self.vx_coefficients[action]
        player.vx = float(vx_coeff[0] * old_vx + vx_coeff[1])
        player.vx = float(
            np.clip(
                player.vx,
                -self.max_horizontal_speed,
                self.max_horizontal_speed,
            )
        )
        dx_coeff = self.dx_coefficients[action]
        player.x += float(
            dx_coeff
            @ np.asarray(
                [old_vx * dt, player.vx * dt, dt],
                dtype=np.float64,
            )
        )
        player.x = float(
            np.clip(
                player.x,
                PLAYER_HALF_WIDTH_PX,
                REFERENCE_WIDTH - PLAYER_HALF_WIDTH_PX,
            )
        )

        player.vy = old_vy + self.screen_gravity_y * dt
        player.y += player.vy * dt
        shift = self.scroll_velocity_y * dt
        for platform in platforms:
            platform.top += shift

        landed = False
        if motion > 0:
            old_bottom = old_y + PLAYER_HALF_HEIGHT_PX
            new_bottom = player.y + PLAYER_HALF_HEIGHT_PX
            candidates = []
            for platform in platforms:
                left = platform.center_x - platform.width / 2
                right = platform.center_x + platform.width / 2
                old_platform_top = platform.top - shift
                if (
                    player.x
                    + PLAYER_HALF_WIDTH_PX
                    + self.horizontal_contact_margin_px
                    <= left
                    or player.x
                    - PLAYER_HALF_WIDTH_PX
                    - self.horizontal_contact_margin_px
                    >= right
                ):
                    continue
                if (
                    old_bottom
                    <= old_platform_top + self.vertical_contact_margin_px
                    and new_bottom
                    >= platform.top - self.vertical_contact_margin_px
                ):
                    candidates.append(platform)
            if candidates:
                platform = min(candidates, key=lambda item: item.top)
                player.vy = (
                    self.spring_bounce_velocity_y
                    if platform.kind == 0.5
                    else self.normal_bounce_velocity_y
                )
                player.y = (
                    platform.top
                    - PLAYER_HALF_HEIGHT_PX
                    + player.vy * dt
                )
                player.motion = -1.0
                player.phase_steps = 0
                player.rising_duration_steps = (
                    self.spring_rising_duration_steps
                    if platform.kind == 0.5
                    else self.normal_rising_duration_steps
                )
                landed = True
        if not landed:
            if motion < 0 and player.vy >= 0:
                player.motion = 1.0
                player.phase_steps = 0
            else:
                player.motion = float(motion)
                player.phase_steps += 1
        return landed


def rollout_errors(
    model: CalibratedObservationModel,
    grouped_rows: Iterable[list[dict[str, Any]]],
    horizon: int,
) -> tuple[float | None, float | None, int]:
    x_errors = []
    y_errors = []
    for rows in grouped_rows:
        for start in range(0, len(rows) - horizon + 1):
            window = rows[start : start + horizon]
            if any(
                row["terminated"]
                or row["truncated"]
                or player_state(row["observation"])["present"] <= 0.5
                or player_state(row["next_observation"])["present"] <= 0.5
                for row in window
            ):
                continue
            player, platforms = model.initial_state(window[0]["observation"])
            valid = True
            for row in window:
                dt = (
                    row["next_observation_timestamp"]
                    - row["observation_timestamp"]
                )
                if dt <= 0:
                    valid = False
                    break
                model.step(
                    player,
                    platforms,
                    action=int(row["action"]),
                    dt=dt,
                )
            if not valid:
                continue
            actual = player_state(window[-1]["next_observation"])
            x_errors.append(abs(player.x - actual["x"]))
            y_errors.append(abs(player.y - actual["y"]))
    return (
        float(np.mean(x_errors)) if x_errors else None,
        float(np.mean(y_errors)) if y_errors else None,
        len(x_errors),
    )
