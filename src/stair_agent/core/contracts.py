"""Runtime contracts shared by simulator and guarded Real adapters."""

from __future__ import annotations

from dataclasses import dataclass


OBSERVATION_DIM = 268
OBSERVATION_SCHEMA_VERSION = "stair-observation-v3-268"


@dataclass(frozen=True)
class ActionTiming:
    """Timing evidence for one Real action dispatch."""

    action_command_timestamp: float
    action_effective_timestamp: float
    next_observation_timestamp: float
    held_action: bool
    action_duration_ms: float
    action_applied: bool = True
