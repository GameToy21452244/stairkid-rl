"""Frozen helpers for the bounded Spring curriculum v0 Gate."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

import numpy as np

from ..learnability import ProbeEvaluation
from ..simulator.generator import generate_platforms, next_platform_kind
from ..simulator.state import ShaftEnvConfig


REACHABILITY_SEED_START = 9000
REACHABILITY_SMOKE_COUNT = 100
REACHABILITY_FULL_COUNT = 1000
EVALUATION_SEED_START = 10000
EVALUATION_SEED_COUNT = 100
MAX_EPISODE_STEPS = 600
ENGINEERING_SEQUENCE_SEED = 8999
SPRING_RATIO_RANGE = (0.02, 0.05)
SPIKE_RATIO_RANGE = (0.035, 0.07)
MIN_SPRING_CONTACT_EPISODES = 20


def spring_curriculum_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
        enable_spring=True,
        spring_spawn_probability=0.06,
        minimum_normal_platforms_before_spring=3,
    )


def spike_reference_config() -> ShaftEnvConfig:
    return replace(
        spring_curriculum_config(),
        enable_spring=False,
        spring_spawn_probability=0.0,
    )


def _platform_signature(config: ShaftEnvConfig, seed: int) -> list[tuple]:
    platforms = generate_platforms(config, np.random.default_rng(seed))
    return [
        (
            item.floor_index,
            item.center_x,
            item.center_y,
            item.kind,
        )
        for item in sorted(platforms, key=lambda platform: platform.floor_index)
    ]


def engineering_checks() -> dict[str, object]:
    config = spring_curriculum_config()
    reference = spike_reference_config()
    enabled_no_spawn = replace(config, spring_spawn_probability=0.0)
    equivalence_seeds = range(
        REACHABILITY_SEED_START,
        REACHABILITY_SEED_START + REACHABILITY_SMOKE_COUNT,
    )
    mismatches = [
        seed
        for seed in equivalence_seeds
        if _platform_signature(reference, seed)
        != _platform_signature(enabled_no_spawn, seed)
    ]

    rng = np.random.default_rng(ENGINEERING_SEQUENCE_SEED)
    kinds: list[str] = []
    for floor_index in range(2000):
        kinds.append(
            next_platform_kind(
                config,
                rng,
                floor_index=floor_index,
                previous_kinds=kinds,
            )
        )
    initial_safe = all(
        kind == "normal"
        for kind in kinds[: config.initial_safe_normal_platforms]
    )
    spring_gap_safe = all(
        kinds[index - config.minimum_normal_platforms_before_spring : index]
        == ["normal"] * config.minimum_normal_platforms_before_spring
        for index, kind in enumerate(kinds)
        if kind == "spring"
    )
    spike_indices = [
        index for index, kind in enumerate(kinds) if kind == "spikes"
    ]
    spike_gap_safe = all(
        right - left - 1
        >= config.minimum_normal_platforms_between_spikes
        and kinds[
            right - config.minimum_normal_platforms_between_spikes : right
        ]
        == ["normal"] * config.minimum_normal_platforms_between_spikes
        for left, right in zip(spike_indices, spike_indices[1:])
    )
    generated = generate_platforms(config, np.random.default_rng(9000))
    one_platform_per_floor = (
        len(generated) == config.platform_count
        and len({item.floor_index for item in generated})
        == config.platform_count
    )
    checks = {
        "feature_off_sequence_equivalence": not mismatches,
        "initial_safe_normal_platforms": initial_safe,
        "spring_normal_gap": spring_gap_safe,
        "spike_real_normal_gap": spike_gap_safe,
        "one_platform_per_floor": one_platform_per_floor,
        "spring_generated_in_long_sequence": "spring" in kinds,
        "spikes_generated_in_long_sequence": "spikes" in kinds,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "feature_off_mismatch_seeds": mismatches,
        "long_sequence_seed": ENGINEERING_SEQUENCE_SEED,
        "long_sequence_floors": len(kinds),
        "long_sequence_counts": {
            kind: kinds.count(kind) for kind in ("normal", "spikes", "spring")
        },
    }


def event_episode_coverage(
    evaluation: ProbeEvaluation,
    event_name: str,
) -> int:
    return sum(
        int(episode.event_counts.get(event_name, 0) > 0)
        for episode in evaluation.episode_results
    )


def seeds_overlap_reserved_fresh(seeds: Iterable[int]) -> bool:
    return any(6000 <= int(seed) <= 6099 for seed in seeds)


__all__ = [
    "ENGINEERING_SEQUENCE_SEED",
    "EVALUATION_SEED_COUNT",
    "EVALUATION_SEED_START",
    "MAX_EPISODE_STEPS",
    "MIN_SPRING_CONTACT_EPISODES",
    "REACHABILITY_FULL_COUNT",
    "REACHABILITY_SEED_START",
    "REACHABILITY_SMOKE_COUNT",
    "SPIKE_RATIO_RANGE",
    "SPRING_RATIO_RANGE",
    "engineering_checks",
    "event_episode_coverage",
    "seeds_overlap_reserved_fresh",
    "spike_reference_config",
    "spring_curriculum_config",
]
