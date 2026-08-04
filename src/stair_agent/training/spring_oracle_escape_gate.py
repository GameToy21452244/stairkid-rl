"""Metrics and frozen thresholds for the Spring Oracle escape Gate."""

from __future__ import annotations

from typing import Any

from ..learnability import ProbeEvaluation
from ..simulator.gates import evaluation_summary


DEVELOPMENT_SEEDS = tuple(range(11000, 11100))
HOLDOUT_SEEDS = tuple(range(12000, 12100))
MAX_EPISODE_STEPS = 600


def spring_branch_metrics(result: ProbeEvaluation) -> dict[str, Any]:
    spring_episodes = [
        episode
        for episode in result.episode_results
        if episode.event_counts.get("spring_contact", 0) > 0
    ]
    no_spring_episodes = [
        episode
        for episode in result.episode_results
        if episode.event_counts.get("spring_contact", 0) == 0
    ]
    spring_count = len(spring_episodes)
    no_spring_count = len(no_spring_episodes)
    spring_reached = sum(
        episode.deepest_floor >= 10 for episode in spring_episodes
    )
    no_spring_reached = sum(
        episode.deepest_floor >= 10 for episode in no_spring_episodes
    )
    spring_early_top = sum(
        episode.terminal_reason == "top" and episode.deepest_floor < 3
        for episode in spring_episodes
    )
    return {
        "spring_episode_count": spring_count,
        "spring_reach_floor_10_count": spring_reached,
        "spring_reach_floor_10_rate": spring_reached / max(1, spring_count),
        "spring_top_death_count": sum(
            episode.terminal_reason == "top" for episode in spring_episodes
        ),
        "spring_early_top_death_count": spring_early_top,
        "spring_early_top_death_rate": spring_early_top
        / max(1, spring_count),
        "no_spring_episode_count": no_spring_count,
        "no_spring_reach_floor_10_count": no_spring_reached,
        "no_spring_reach_floor_10_rate": no_spring_reached
        / max(1, no_spring_count),
    }


def oracle_gate(result: ProbeEvaluation) -> dict[str, Any]:
    summary = evaluation_summary(result)
    branch = spring_branch_metrics(result)
    top_rate = result.terminal_reasons.get("top", 0) / max(1, result.episodes)
    checks = {
        "overall_reach_floor_10_at_least_0.95": (
            summary["reach_rate_floor_10"] >= 0.95
        ),
        "spring_episodes_at_least_20": branch["spring_episode_count"] >= 20,
        "spring_reach_floor_10_at_least_0.90": (
            branch["spring_reach_floor_10_rate"] >= 0.90
        ),
        "top_death_rate_at_most_0.05": top_rate <= 0.05,
        "health_deaths_zero": (
            result.terminal_reasons.get("health_depleted", 0) == 0
        ),
        "no_spring_reach_floor_10_1.0": (
            branch["no_spring_reach_floor_10_rate"] == 1.0
        ),
        "not_collapsed": not result.collapsed,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "top_death_rate": top_rate,
        "branch": branch,
        "evaluation": summary,
    }


def baseline_gate(
    candidate: ProbeEvaluation,
    reference: ProbeEvaluation,
) -> dict[str, Any]:
    candidate_summary = evaluation_summary(candidate)
    reference_summary = evaluation_summary(reference)
    branch = spring_branch_metrics(candidate)
    retention = candidate.mean_floors / max(reference.mean_floors, 1e-9)
    checks = {
        "mean_floor_retention_at_least_0.80": retention >= 0.80,
        "reach_floor_3_at_least_0.90": (
            candidate_summary["reach_rate_floor_3"] >= 0.90
        ),
        "health_deaths_zero": (
            candidate.terminal_reasons.get("health_depleted", 0) == 0
        ),
        "not_collapsed": not candidate.collapsed,
        "spring_episodes_at_least_20": branch["spring_episode_count"] >= 20,
        "spring_early_top_rate_at_most_0.10": (
            branch["spring_early_top_death_rate"] <= 0.10
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "retention_vs_spike_reference": retention,
        "branch": branch,
        "evaluation": candidate_summary,
        "spike_reference_evaluation": reference_summary,
    }


__all__ = [
    "DEVELOPMENT_SEEDS",
    "HOLDOUT_SEEDS",
    "MAX_EPISODE_STEPS",
    "baseline_gate",
    "oracle_gate",
    "spring_branch_metrics",
]
