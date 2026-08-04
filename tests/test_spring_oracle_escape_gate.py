from __future__ import annotations

from dataclasses import replace

from stair_agent.learnability import evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.gates import oracle_selector
from stair_agent.training.spring_curriculum_gate import (
    spike_reference_config,
    spring_curriculum_config,
)
from stair_agent.training.spring_oracle_escape_gate import (
    oracle_gate,
    spring_branch_metrics,
)


def test_spring_branch_metrics_separate_contact_and_no_contact_episodes() -> None:
    result = evaluate_candidate(
        "spring-branch-metrics",
        oracle_selector(OracleFull(enable_spring_escape=True)),
        seeds=range(10000, 10020),
        max_episode_steps=120,
        config=spring_curriculum_config(),
        success_floor=10,
    )
    branch = spring_branch_metrics(result)
    assert branch["spring_episode_count"] > 0
    assert branch["no_spring_episode_count"] > 0
    assert (
        branch["spring_episode_count"] + branch["no_spring_episode_count"]
        == result.episodes
    )


def test_frozen_v02_oracle_escape_small_regression_sample_is_reliable() -> None:
    legacy_config = replace(
        spring_curriculum_config(),
        environment_version="ns-shaft-sim-v0.2",
        enable_support_ownership=False,
        enable_calibrated_playfield=False,
    )
    result = evaluate_candidate(
        "spring-oracle-small-regression",
        oracle_selector(OracleFull(enable_spring_escape=True)),
        seeds=(10004, 10007, 10015, 10022, 10034),
        max_episode_steps=120,
        config=legacy_config,
        success_floor=10,
    )
    gate = oracle_gate(result)
    assert gate["evaluation"]["reach_rate_floor_10"] == 1.0
    assert gate["top_death_rate"] == 0.0


def test_spring_escape_is_exact_no_spawn_non_regression() -> None:
    config = spike_reference_config()
    legacy = evaluate_candidate(
        "oracle-no-spring",
        oracle_selector(OracleFull(enable_spring_escape=False)),
        seeds=range(40),
        max_episode_steps=120,
        config=config,
        success_floor=10,
    )
    candidate = evaluate_candidate(
        "oracle-no-spring",
        oracle_selector(OracleFull(enable_spring_escape=True)),
        seeds=range(40),
        max_episode_steps=120,
        config=config,
        success_floor=10,
    )
    assert candidate.to_dict() == legacy.to_dict()
