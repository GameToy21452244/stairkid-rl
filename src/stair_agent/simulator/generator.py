from __future__ import annotations

import numpy as np

from .platform import SimulatorPlatform
from .state import ShaftEnvConfig


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
    if (
        not config.enable_spikes
        or config.spike_spawn_probability <= 0
        or floor_index < config.initial_safe_normal_platforms
    ):
        return "normal"
    gap = config.minimum_normal_platforms_between_spikes
    if "spikes" in previous_kinds[-gap:]:
        return "normal"
    return (
        "spikes"
        if float(rng.random()) < config.spike_spawn_probability
        else "normal"
    )


def next_platform_center(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
    previous_x: float,
) -> float:
    shift = float(rng.uniform(-maximum_shift(config), maximum_shift(config)))
    margin = config.platform_width / 2 + config.safe_landing_margin
    return float(np.clip(previous_x + shift, margin, config.width - margin))


def generate_platforms(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
) -> list[SimulatorPlatform]:
    platforms: list[SimulatorPlatform] = []
    starting_y = 96.0
    center_x = config.width / 2
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
    "next_platform_kind",
    "pair_has_safe_reach",
    "safe_center_interval",
    "sequence_is_reachable",
    "sequence_is_health_safe",
]
