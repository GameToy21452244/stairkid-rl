from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.simulator.generator import generate_platforms, next_platform_kind
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.spring_curriculum_gate import (
    engineering_checks,
    event_episode_coverage,
    spike_reference_config,
    spring_curriculum_config as frozen_spring_curriculum_config,
)


def spring_curriculum_config(**changes) -> ShaftEnvConfig:
    config = ShaftEnvConfig(
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
    return replace(config, **changes)


def test_spring_curriculum_configuration_requires_enabled_feature() -> None:
    with pytest.raises(ValueError, match="需要 enable_spring"):
        ShaftEnvConfig(spring_spawn_probability=0.06)
    with pytest.raises(ValueError, match="介於 0 與 1"):
        spring_curriculum_config(spring_spawn_probability=1.01)
    with pytest.raises(ValueError, match="不可小於 1"):
        spring_curriculum_config(minimum_normal_platforms_before_spring=0)


def test_spring_spawn_zero_preserves_spike_curriculum_sequences() -> None:
    spike_only = replace(
        spring_curriculum_config(),
        enable_spring=False,
        spring_spawn_probability=0.0,
    )
    no_spawn = replace(
        spring_curriculum_config(),
        spring_spawn_probability=0.0,
    )
    for seed in range(100):
        left = generate_platforms(spike_only, np.random.default_rng(seed))
        right = generate_platforms(no_spawn, np.random.default_rng(seed))
        assert [
            (item.floor_index, item.center_x, item.kind) for item in left
        ] == [
            (item.floor_index, item.center_x, item.kind) for item in right
        ]


def test_long_sequence_enforces_real_normal_gaps_for_both_hazards() -> None:
    config = spring_curriculum_config(
        spike_spawn_probability=0.35,
        spring_spawn_probability=1.0,
    )
    kinds: list[str] = []
    rng = np.random.default_rng(9031)
    for floor in range(500):
        kinds.append(
            next_platform_kind(
                config,
                rng,
                floor_index=floor,
                previous_kinds=kinds,
            )
        )

    assert kinds[: config.initial_safe_normal_platforms] == [
        "normal"
    ] * config.initial_safe_normal_platforms
    assert "spring" in kinds
    assert "spikes" in kinds
    for index, kind in enumerate(kinds):
        if kind == "spring":
            gap = config.minimum_normal_platforms_before_spring
            assert kinds[index - gap : index] == ["normal"] * gap
        if kind == "spikes" and "spikes" in kinds[:index]:
            previous = max(
                position
                for position, previous_kind in enumerate(kinds[:index])
                if previous_kind == "spikes"
            )
            between = kinds[previous + 1 : index]
            assert len(between) >= config.minimum_normal_platforms_between_spikes
            assert all(item == "normal" for item in between[-5:])


def test_reachability_gate_reports_seed_range_and_platform_distribution() -> None:
    result = run_reachability_gate(
        40,
        seed_start=9000,
        config=spring_curriculum_config(),
    )
    assert result.seed_start == 9000
    assert result.seeds == 40
    assert result.passed
    assert result.platform_kind_counts["spring"] > 0
    assert result.platform_kind_counts["spikes"] > 0
    assert result.platform_kind_counts["normal"] > 0
    assert result.realized_platform_kind_ratios["spring"] == pytest.approx(
        result.platform_kind_counts["spring"] / result.total_platforms
    )
    assert result.effective_environment_version.endswith(
        "+spring-v1+spring-curriculum-v0"
    )


def test_frozen_spring_curriculum_engineering_checks_pass() -> None:
    config = frozen_spring_curriculum_config()
    reference = spike_reference_config()
    result = engineering_checks()
    assert config.spring_spawn_probability == 0.06
    assert config.minimum_normal_platforms_before_spring == 3
    assert reference.spike_spawn_probability == 0.10
    assert not reference.enable_spring
    assert result["passed"]


def test_event_episode_coverage_counts_episodes_not_repeat_contacts() -> None:
    class Episode:
        def __init__(self, count: int) -> None:
            self.event_counts = {"spring_contact": count}

    class Evaluation:
        episode_results = [Episode(3), Episode(0), Episode(1)]

    assert event_episode_coverage(Evaluation(), "spring_contact") == 2
