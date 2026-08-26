"""Isolated Real-anchored V3 layout generation; V1/V2 stay frozen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .generator import next_platform_kind
from .platform import SimulatorPlatform
from .state import ShaftEnvConfig


@dataclass(frozen=True)
class ShiftComponent:
    name: str
    probability: float
    low: float
    high: float


@dataclass(frozen=True)
class V3LayoutProfile:
    width_range: tuple[float, float]
    spacing: float
    components: tuple[ShiftComponent, ...]
    left_probability: float
    initial_safe_component_names: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "V3LayoutProfile":
        mixture = raw["horizontal_shift_mixture"]
        components = tuple(
            ShiftComponent(
                name=name,
                probability=float(value["probability"]),
                low=float(value["magnitude_range_px"][0]),
                high=float(value["magnitude_range_px"][1]),
            )
            for name, value in mixture.items()
            if name != "direction_left_probability"
        )
        profile = cls(
            width_range=tuple(map(float, raw["platform_width_range_px"])),
            spacing=float(raw["platform_spacing_px"]),
            components=components,
            left_probability=float(mixture["direction_left_probability"]),
            initial_safe_component_names=tuple(
                map(str, raw.get("initial_safe_shift_components", ("small", "ordinary")))
            ),
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        if abs(sum(item.probability for item in self.components) - 1.0) > 1e-9:
            raise ValueError("V3_SHIFT_MIXTURE_PROBABILITIES")
        if self.spacing != 48.0:
            raise ValueError("V3_VERTICAL_CORE_MUST_BE_48")
        if not 0.0 <= self.left_probability <= 1.0:
            raise ValueError("V3_LEFT_PROBABILITY")
        if any(item.low < 0 or item.high < item.low for item in self.components):
            raise ValueError("V3_SHIFT_COMPONENT_RANGE")
        component_names = {item.name for item in self.components}
        if not self.initial_safe_component_names or not set(self.initial_safe_component_names) <= component_names:
            raise ValueError("V3_INITIAL_SAFE_SHIFT_COMPONENTS")


def sample_shift(
    profile: V3LayoutProfile,
    rng: np.random.Generator,
    previous_x: float,
    minimum: float,
    maximum: float,
    *,
    allowed_component_names: tuple[str, ...] | None = None,
) -> tuple[float, str, float]:
    components = (
        profile.components
        if allowed_component_names is None
        else tuple(item for item in profile.components if item.name in allowed_component_names)
    )
    total_probability = sum(item.probability for item in components)
    if not components or total_probability <= 0:
        raise ValueError("V3_SHIFT_COMPONENT_SELECTION")
    pick = float(rng.random())
    cumulative = 0.0
    component = components[-1]
    for candidate in components:
        cumulative += candidate.probability / total_probability
        if pick <= cumulative:
            component = candidate
            break
    requested = float(rng.uniform(component.low, component.high))
    direction = -1.0 if float(rng.random()) < profile.left_probability else 1.0
    room = previous_x - minimum if direction < 0 else maximum - previous_x
    opposite_room = maximum - previous_x if direction < 0 else previous_x - minimum
    if room < requested <= opposite_room:
        direction *= -1.0
        room = opposite_room
    actual = min(requested, room)
    return float(np.clip(previous_x + direction * actual, minimum, maximum)), component.name, requested


def generate_v3_platforms(config: ShaftEnvConfig, rng: np.random.Generator, profile: V3LayoutProfile) -> tuple[list[SimulatorPlatform], list[dict[str, Any]]]:
    platforms: list[SimulatorPlatform] = []
    diagnostics: list[dict[str, Any]] = []
    starting_y = config.initial_platform_center_y if config.enable_calibrated_playfield else 96.0
    half = config.platform_width / 2
    minimum = config.effective_playfield_left + half
    maximum = config.effective_playfield_right - half
    center_x = (config.effective_playfield_left + config.effective_playfield_right) / 2
    for floor_index in range(config.platform_count):
        component = "initial"
        requested = 0.0
        prior = center_x
        if floor_index:
            # Platforms 0..initial_safe_normal_platforms-1 form the mandatory
            # safe-start window.  Transitions targeting platforms 1..N-1 use
            # the configured safe components; the full Real-anchored mixture,
            # including the large tail, remains unchanged from platform N on.
            initial_safe = floor_index < config.initial_safe_normal_platforms
            center_x, component, requested = sample_shift(
                profile,
                rng,
                center_x,
                minimum,
                maximum,
                allowed_component_names=(
                    profile.initial_safe_component_names if initial_safe else None
                ),
            )
        kind = next_platform_kind(config, rng, floor_index=floor_index, previous_kinds=[item.kind for item in platforms])
        platforms.append(SimulatorPlatform.create(
            floor_index=floor_index, center_x=center_x,
            center_y=starting_y - floor_index * profile.spacing,
            width=config.platform_width, height=config.platform_height, kind=kind,
        ))
        diagnostics.append({
            "floor_index": floor_index, "component": component,
            "requested_shift": requested, "actual_signed_shift": center_x - prior,
            "initial_safe_restriction": bool(
                floor_index and floor_index < config.initial_safe_normal_platforms
            ),
        })
    return platforms, diagnostics


__all__ = ["ShiftComponent", "V3LayoutProfile", "generate_v3_platforms", "sample_shift"]
