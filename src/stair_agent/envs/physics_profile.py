"""Version-neutral simulator physics profile used by Fresh V3 and R4.

The values and sampling behavior are extracted unchanged from the validated
simulator lineage.  The final runtime deliberately has no dependency on a
retired policy generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..simulator.state import ShaftEnvConfig, build_fidelity_v1_config


PHYSICS_PROFILE_VERSION = "ns-shaft-sim-physics-v1"
RANDOMIZED_FIELDS = (
    "platform_width",
    "scroll_speed",
    "horizontal_acceleration",
    "release_deceleration",
    "reverse_brake_multiplier",
    "max_horizontal_speed",
    "gravity",
    "max_fall_speed",
)


@dataclass(frozen=True)
class ObservationRandomizationConfig:
    player_position_jitter_px: float = 1.0
    platform_position_jitter_px: float = 1.0
    platform_dropout_probability: float = 0.01
    scroll_noise_px_s: float = 2.0
    scroll_zero_probability: float = 0.01

    def __post_init__(self) -> None:
        for name in (
            "player_position_jitter_px",
            "platform_position_jitter_px",
            "scroll_noise_px_s",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in ("platform_dropout_probability", "scroll_zero_probability"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True)
class PhysicsProfile:
    nominal: dict[str, float]
    ranges: dict[str, tuple[float, float]]
    observation: ObservationRandomizationConfig
    dr_enabled: bool = True
    dr_profile: str = "fresh_v3_materialized_real_v1"
    version: str = PHYSICS_PROFILE_VERSION

    def __post_init__(self) -> None:
        if self.version != PHYSICS_PROFILE_VERSION:
            raise ValueError("UNSUPPORTED_PHYSICS_PROFILE_VERSION")
        if set(self.ranges) != set(RANDOMIZED_FIELDS):
            raise ValueError("PHYSICS_RANDOMIZATION_FIELDS_INCOMPLETE")
        for name, bounds in self.ranges.items():
            low, high = bounds
            if not np.isfinite(low) or not np.isfinite(high) or low > high:
                raise ValueError(f"INVALID_PHYSICS_RANGE:{name}")
        width_low, width_high = self.ranges["platform_width"]
        if width_low < 1 or width_high > 383:
            raise ValueError("PLATFORM_WIDTH_RANGE_INVALID")

    def nominal_config(self, **overrides: Any) -> ShaftEnvConfig:
        values: dict[str, Any] = {
            "environment_version": self.version,
            **self.nominal,
        }
        values.update(overrides)
        return build_fidelity_v1_config(**values)
