from __future__ import annotations

from .physics import ShaftSimulator
from .platform import SimulatorPlatform


def configure_normal_healing_landing(
    simulator: ShaftSimulator,
    *,
    health_segments: int,
    fall_speed: float = -180.0,
) -> int:
    """Place the player above floor 0 for a deterministic normal landing."""
    if not 0 <= health_segments <= simulator.config.max_health_segments:
        raise ValueError("health_segments 超出 simulator health 範圍。")
    platform = min(
        simulator.platforms, key=lambda item: item.floor_index
    )
    simulator.health_segments = health_segments
    simulator.last_health_delta = 0
    simulator.supported_floor = None
    simulator.player.body.position = (
        platform.center_x,
        platform.top + simulator.player.height / 2 + 18.0,
    )
    simulator.player.body.velocity = (0.0, fall_speed)
    return platform.floor_index


def configure_spike_landing(
    simulator: ShaftSimulator,
    *,
    health_segments: int,
    fall_speed: float = -180.0,
) -> int:
    floor = configure_normal_healing_landing(
        simulator,
        health_segments=health_segments,
        fall_speed=fall_speed,
    )
    platform = min(
        simulator.platforms, key=lambda item: item.floor_index
    )
    platform.kind = "spikes"
    return floor


def configure_spike_choice(
    simulator: ShaftSimulator,
) -> tuple[SimulatorPlatform, SimulatorPlatform]:
    next_floor = min(
        item.floor_index
        for item in simulator.platforms
        if item.floor_index > simulator.deepest_floor
    )
    spike = next(
        item
        for item in simulator.platforms
        if item.floor_index == next_floor
    )
    spike.kind = "spikes"
    margin = simulator.config.platform_width / 2 + 8
    safe_x = float(
        max(
            margin,
            min(
                simulator.config.width - margin,
                spike.center_x
                + (
                    70.0
                    if spike.center_x < simulator.config.width / 2
                    else -70.0
                ),
            ),
        )
    )
    safe = SimulatorPlatform.create(
        floor_index=next_floor,
        center_x=safe_x,
        center_y=spike.center_y,
        width=simulator.config.platform_width,
        height=simulator.config.platform_height,
        kind="normal",
    )
    simulator.platforms.append(safe)
    simulator.space.add(safe.body, safe.shape)
    return spike, safe


def configure_conveyor_landing(
    simulator: ShaftSimulator,
    *,
    direction: str,
    fall_speed: float = -180.0,
) -> int:
    if direction not in {"left", "right"}:
        raise ValueError("direction 只支援 left 或 right。")
    floor = configure_normal_healing_landing(
        simulator,
        health_segments=simulator.health_segments,
        fall_speed=fall_speed,
    )
    platform = min(
        simulator.platforms, key=lambda item: item.floor_index
    )
    platform.kind = f"conveyor_{direction}"
    return floor


def configure_conveyor_choice(
    simulator: ShaftSimulator,
    *,
    direction: str = "right",
) -> tuple[SimulatorPlatform, SimulatorPlatform]:
    if direction not in {"left", "right"}:
        raise ValueError("direction 只支援 left 或 right。")
    next_floor = min(
        item.floor_index
        for item in simulator.platforms
        if item.floor_index > simulator.deepest_floor
    )
    conveyor = next(
        item
        for item in simulator.platforms
        if item.floor_index == next_floor
    )
    conveyor.kind = f"conveyor_{direction}"
    margin = simulator.config.platform_width / 2 + 8
    safe_x = float(
        max(
            margin,
            min(
                simulator.config.width - margin,
                conveyor.center_x
                + (
                    70.0
                    if conveyor.center_x < simulator.config.width / 2
                    else -70.0
                ),
            ),
        )
    )
    safe = SimulatorPlatform.create(
        floor_index=next_floor,
        center_x=safe_x,
        center_y=conveyor.center_y,
        width=simulator.config.platform_width,
        height=simulator.config.platform_height,
        kind="normal",
    )
    simulator.platforms.append(safe)
    simulator.space.add(safe.body, safe.shape)
    return conveyor, safe


def configure_spring_landing(
    simulator: ShaftSimulator,
    *,
    fall_speed: float = -180.0,
) -> int:
    floor = configure_normal_healing_landing(
        simulator,
        health_segments=simulator.health_segments,
        fall_speed=fall_speed,
    )
    platform = min(
        simulator.platforms, key=lambda item: item.floor_index
    )
    platform.kind = "spring"
    return floor


def configure_spring_choice(
    simulator: ShaftSimulator,
) -> tuple[SimulatorPlatform, SimulatorPlatform]:
    next_floor = min(
        item.floor_index
        for item in simulator.platforms
        if item.floor_index > simulator.deepest_floor
    )
    spring = next(
        item
        for item in simulator.platforms
        if item.floor_index == next_floor
    )
    spring.kind = "spring"
    margin = simulator.config.platform_width / 2 + 8
    safe_x = float(
        max(
            margin,
            min(
                simulator.config.width - margin,
                spring.center_x
                + (
                    70.0
                    if spring.center_x < simulator.config.width / 2
                    else -70.0
                ),
            ),
        )
    )
    safe = SimulatorPlatform.create(
        floor_index=next_floor,
        center_x=safe_x,
        center_y=spring.center_y,
        width=simulator.config.platform_width,
        height=simulator.config.platform_height,
        kind="normal",
    )
    simulator.platforms.append(safe)
    simulator.space.add(safe.body, safe.shape)
    return spring, safe


def configure_flipping_landing(
    simulator: ShaftSimulator,
    *,
    active: bool,
    fall_speed: float = -180.0,
) -> int:
    floor = configure_normal_healing_landing(
        simulator,
        health_segments=simulator.health_segments,
        fall_speed=fall_speed,
    )
    platform = min(
        simulator.platforms, key=lambda item: item.floor_index
    )
    platform.kind = "flipping"
    if active:
        simulator.flipping_states[platform.floor_index] = {"state": "READY", "elapsed": 0.0}
    else:
        simulator.flipping_states[platform.floor_index] = {"state": "INACTIVE", "elapsed": 0.0}
    return floor


def configure_flipping_choice(
    simulator: ShaftSimulator,
) -> tuple[SimulatorPlatform, SimulatorPlatform]:
    next_floor = min(
        item.floor_index
        for item in simulator.platforms
        if item.floor_index > simulator.deepest_floor
    )
    flipping = next(
        item
        for item in simulator.platforms
        if item.floor_index == next_floor
    )
    flipping.kind = "flipping"
    margin = simulator.config.platform_width / 2 + 8
    safe_x = float(
        max(
            margin,
            min(
                simulator.config.width - margin,
                flipping.center_x
                + (
                    70.0
                    if flipping.center_x < simulator.config.width / 2
                    else -70.0
                ),
            ),
        )
    )
    safe = SimulatorPlatform.create(
        floor_index=next_floor,
        center_x=safe_x,
        center_y=flipping.center_y,
        width=simulator.config.platform_width,
        height=simulator.config.platform_height,
        kind="normal",
    )
    simulator.platforms.append(safe)
    simulator.space.add(safe.body, safe.shape)
    return flipping, safe


__all__ = [
    "configure_conveyor_choice",
    "configure_conveyor_landing",
    "configure_flipping_choice",
    "configure_flipping_landing",
    "configure_normal_healing_landing",
    "configure_spring_choice",
    "configure_spring_landing",
    "configure_spike_choice",
    "configure_spike_landing",
]
