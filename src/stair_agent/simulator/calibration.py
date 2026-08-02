from __future__ import annotations

from dataclasses import dataclass, replace

from .state import ShaftEnvConfig


@dataclass(frozen=True)
class HealthCalibration:
    max_segments: int = 12
    initial_segments: int = 12
    normal_platform_heal_segments: int = 1

    def apply(self, config: ShaftEnvConfig) -> ShaftEnvConfig:
        return replace(
            config,
            max_health_segments=self.max_segments,
            initial_health_segments=self.initial_segments,
            normal_platform_heal_segments=self.normal_platform_heal_segments,
        )


@dataclass(frozen=True)
class SpikeCalibration:
    damage_segments: int = 5

    def apply(self, config: ShaftEnvConfig) -> ShaftEnvConfig:
        return replace(
            config,
            spike_damage_segments=self.damage_segments,
        )


@dataclass(frozen=True)
class ConveyorCalibration:
    velocity_delta: float = 80.0

    def apply(self, config: ShaftEnvConfig) -> ShaftEnvConfig:
        return replace(
            config,
            conveyor_velocity_delta=self.velocity_delta,
        )


@dataclass(frozen=True)
class SpringCalibration:
    jump_velocity: float = 190.0

    def apply(self, config: ShaftEnvConfig) -> ShaftEnvConfig:
        return replace(
            config,
            spring_jump_velocity=self.jump_velocity,
        )


@dataclass(frozen=True)
class FlippingCalibration:
    active_seconds: float = 1.0
    inactive_seconds: float = 1.0

    def apply(self, config: ShaftEnvConfig) -> ShaftEnvConfig:
        return replace(
            config,
            flipping_active_seconds=self.active_seconds,
            flipping_inactive_seconds=self.inactive_seconds,
        )


__all__ = [
    "ConveyorCalibration",
    "FlippingCalibration",
    "HealthCalibration",
    "SpringCalibration",
    "SpikeCalibration",
]
