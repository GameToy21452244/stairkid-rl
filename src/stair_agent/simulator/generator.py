from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .platform import SimulatorPlatform
from .state import ShaftEnvConfig


@dataclass(frozen=True)
class PlatformCenterGeneration:
    center_x: float
    attempts: int
    rejections: int
    used_fallback: bool


def maximum_shift(config: ShaftEnvConfig) -> float:
    if config.distribution == "easy":
        return min(config.easy_max_platform_shift, config.max_platform_shift)
    if config.distribution == "hard":
        return config.hard_max_platform_shift
    return config.max_platform_shift


def safe_center_interval(
    config: ShaftEnvConfig, center_x: float
) -> tuple[float, float]:
    half = config.platform_width / 2 - config.safe_landing_margin
    return center_x - half, center_x + half


def pair_has_safe_reach(
    config: ShaftEnvConfig, source_x: float, target_x: float
) -> bool:
    # Conservative v0.2 engineering bound. Easy generation is intentionally
    # narrower than the calibrated distribution and never requires edge pixels.
    source_left, source_right = safe_center_interval(config, source_x)
    target_left, target_right = safe_center_interval(config, target_x)
    reachable = config.easy_max_platform_shift + 2 * (
        config.platform_width / 2 - config.safe_landing_margin
    )
    gap = max(0.0, target_left - source_right, source_left - target_right)
    return gap <= reachable


def sequence_is_reachable(
    config: ShaftEnvConfig,
    platforms: list[SimulatorPlatform],
    *,
    lookahead: int | None = None,
) -> bool:
    ordered = sorted(platforms, key=lambda item: item.floor_index)
    horizon = lookahead or config.reachability_lookahead
    if len(ordered) < horizon + 1:
        return False
    geometry_safe = all(
        pair_has_safe_reach(config, source.center_x, target.center_x)
        for source, target in zip(ordered, ordered[1:])
    )
    return geometry_safe and sequence_is_health_safe(config, ordered)


def sequence_is_health_safe(
    config: ShaftEnvConfig,
    platforms: list[SimulatorPlatform],
) -> bool:
    if not config.enable_health:
        return not any(
            platform.kind == "spikes" for platform in platforms
        )
    health = config.initial_health_segments
    for platform in sorted(
        platforms, key=lambda item: item.floor_index
    ):
        if platform.kind == "spikes":
            health = max(0, health - config.spike_damage_segments)
        elif platform.kind == "normal":
            health = min(
                config.max_health_segments,
                health + config.normal_platform_heal_segments,
            )
        if health <= 0:
            return False
    return True


def next_platform_kind(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
    *,
    floor_index: int,
    previous_kinds: list[str],
) -> str:
    if floor_index < config.initial_safe_normal_platforms:
        return "normal"

    min_special_spacing = getattr(
        config, "minimum_normal_platforms_between_specials", 1
    )
    if min_special_spacing > 0 and len(previous_kinds) > 0:
        recent = previous_kinds[-min_special_spacing:]
        if any(k != "normal" for k in recent):
            return "normal"

    spike_enabled = (
        config.enable_spikes and config.spike_spawn_probability > 0
    )
    spring_enabled = (
        config.enable_spring and config.spring_spawn_probability > 0
    )
    conveyor_enabled = (
        config.enable_conveyor
        and getattr(config, "conveyor_spawn_probability", 0.0) > 0
    )
    flipping_enabled = (
        config.enable_flipping
        and getattr(config, "flipping_spawn_probability", 0.0) > 0
    )

    if spike_enabled:
        gap = config.minimum_normal_platforms_between_spikes
        if "spikes" in previous_kinds:
            last_spike = len(previous_kinds) - 1 - previous_kinds[::-1].index(
                "spikes"
            )
            since_spike = previous_kinds[last_spike + 1 :]
            spike_allowed = (
                len(since_spike) >= gap
                and all(kind == "normal" for kind in since_spike[-gap:])
            )
        else:
            spike_allowed = "spikes" not in previous_kinds[-gap:]
        if (
            spike_allowed
            and float(rng.random()) < config.spike_spawn_probability
        ):
            return "spikes"

    if spring_enabled:
        gap = config.minimum_normal_platforms_before_spring
        spring_allowed = (
            len(previous_kinds) >= gap
            and all(kind == "normal" for kind in previous_kinds[-gap:])
        )
        if (
            spring_allowed
            and float(rng.random()) < config.spring_spawn_probability
        ):
            return "spring"

    if conveyor_enabled:
        prob = getattr(config, "conveyor_spawn_probability", 0.0)
        if float(rng.random()) < prob:
            return (
                "conveyor_left"
                if float(rng.random()) < 0.5
                else "conveyor_right"
            )

    if flipping_enabled:
        prob = getattr(config, "flipping_spawn_probability", 0.0)
        if float(rng.random()) < prob:
            return "flipping"

    return "normal"


def next_platform_center(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
    previous_x: float,
) -> float:
    return next_platform_center_with_diagnostics(
        config,
        rng,
        previous_x,
    ).center_x


def next_platform_center_with_diagnostics(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
    previous_x: float,
) -> PlatformCenterGeneration:
    maximum_shift_value = maximum_shift(config)
    minimum_shift = min(
        config.minimum_horizontal_platform_shift,
        maximum_shift_value,
    )
    half_width = config.platform_width / 2
    minimum = config.effective_playfield_left + half_width
    maximum = config.effective_playfield_right - half_width
    # Preserve the frozen v0.3 RNG stream and layout exactly.  The calibrated
    # candidate opts into bounded rejection with a positive minimum shift.
    if minimum_shift == 0.0 and config.generator_max_attempts == 1:
        shift = float(rng.uniform(-maximum_shift_value, maximum_shift_value))
        return PlatformCenterGeneration(
            center_x=float(np.clip(previous_x + shift, minimum, maximum)),
            attempts=1,
            rejections=0,
            used_fallback=False,
        )
    rejections = 0
    for attempt in range(1, config.generator_max_attempts + 1):
        magnitude = float(rng.uniform(minimum_shift, maximum_shift_value))
        direction = -1.0 if float(rng.random()) < 0.5 else 1.0
        candidate = float(
            np.clip(previous_x + direction * magnitude, minimum, maximum)
        )
        if abs(candidate - previous_x) + 1e-9 >= minimum_shift:
            return PlatformCenterGeneration(
                center_x=candidate,
                attempts=attempt,
                rejections=rejections,
                used_fallback=False,
            )
        rejections += 1

    left_room = max(0.0, previous_x - minimum)
    right_room = max(0.0, maximum - previous_x)
    direction = -1.0 if left_room >= right_room else 1.0
    distance = min(max(left_room, right_room), max(minimum_shift, 1.0))
    candidate = float(np.clip(previous_x + direction * distance, minimum, maximum))
    return PlatformCenterGeneration(
        center_x=candidate,
        attempts=config.generator_max_attempts,
        rejections=rejections,
        used_fallback=True,
    )


def generate_platforms(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
) -> list[SimulatorPlatform]:
    platforms: list[SimulatorPlatform] = []
    starting_y = (
        config.initial_platform_center_y
        if config.enable_calibrated_playfield
        else 96.0
    )
    center_x = (
        config.effective_playfield_left
        + config.effective_playfield_right
    ) / 2
    for floor_index in range(config.platform_count):
        if floor_index:
            center_x = next_platform_center(config, rng, center_x)
        kind = next_platform_kind(
            config,
            rng,
            floor_index=floor_index,
            previous_kinds=[item.kind for item in platforms],
        )
        platforms.append(
            SimulatorPlatform.create(
                floor_index=floor_index,
                center_x=center_x,
                center_y=starting_y
                - floor_index * config.platform_spacing,
                width=config.platform_width,
                height=config.platform_height,
                kind=kind,
            )
        )
    return platforms


__all__ = [
    "generate_platforms",
    "maximum_shift",
    "next_platform_center",
    "next_platform_center_with_diagnostics",
    "next_platform_kind",
    "PlatformCenterGeneration",
    "pair_has_safe_reach",
    "safe_center_interval",
    "sequence_is_reachable",
    "sequence_is_health_safe",
]
