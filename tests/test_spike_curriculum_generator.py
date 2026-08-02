from __future__ import annotations

import numpy as np
import pytest

from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.simulator.generator import (
    generate_platforms,
    next_platform_kind,
    sequence_is_health_safe,
)
from stair_agent.simulator.state import ShaftEnvConfig


def curriculum_config(**changes) -> ShaftEnvConfig:
    return ShaftEnvConfig(
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=changes.pop(
            "spike_spawn_probability", 0.10
        ),
        **changes,
    )


def test_spike_curriculum_configuration_rejects_unsafe_spacing() -> None:
    with pytest.raises(ValueError, match="需要 enable_spikes"):
        ShaftEnvConfig(spike_spawn_probability=0.1)
    with pytest.raises(ValueError, match="不足以恢復"):
        ShaftEnvConfig(
            enable_health=True,
            enable_spikes=True,
            spike_spawn_probability=0.1,
            minimum_normal_platforms_between_spikes=4,
        )
    with pytest.raises(ValueError, match="介於 0 與 1"):
        curriculum_config(spike_spawn_probability=1.1)


def test_default_generator_remains_normal_only() -> None:
    platforms = generate_platforms(
        ShaftEnvConfig(),
        np.random.default_rng(11),
    )
    assert {item.kind for item in platforms} == {"normal"}


def test_seeded_spike_generation_is_reproducible_and_health_safe() -> None:
    config = curriculum_config()
    first = generate_platforms(config, np.random.default_rng(12))
    second = generate_platforms(config, np.random.default_rng(12))
    assert [
        (item.floor_index, item.center_x, item.kind) for item in first
    ] == [
        (item.floor_index, item.center_x, item.kind) for item in second
    ]
    assert all(
        item.kind == "normal"
        for item in first[: config.initial_safe_normal_platforms]
    )
    assert sequence_is_health_safe(config, first)
    assert config.effective_environment_version.endswith(
        "+spike-curriculum-v0"
    )


def test_long_kind_sequence_enforces_recovery_gap() -> None:
    config = curriculum_config(spike_spawn_probability=1.0)
    rng = np.random.default_rng(13)
    kinds: list[str] = []
    for floor in range(100):
        kinds.append(
            next_platform_kind(
                config,
                rng,
                floor_index=floor,
                previous_kinds=kinds,
            )
        )
    spike_indices = [
        index for index, kind in enumerate(kinds) if kind == "spikes"
    ]
    assert spike_indices[0] >= config.initial_safe_normal_platforms
    assert all(
        right - left - 1
        >= config.minimum_normal_platforms_between_spikes
        for left, right in zip(spike_indices, spike_indices[1:])
    )


def test_thousand_seed_curriculum_reachability_and_ratio() -> None:
    result = run_reachability_gate(
        1000,
        config=curriculum_config(),
    )
    assert result.passed
    assert result.health_safe
    assert result.reproducible
    assert not result.unreachable_seeds
    assert not result.unsafe_health_seeds
    assert 0.04 <= result.realized_spike_ratio <= 0.07
