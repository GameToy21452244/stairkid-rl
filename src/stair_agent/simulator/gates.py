from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import math
from time import perf_counter
from typing import Any, Iterable

import numpy as np

from ..learnability import (
    ProbeEvaluation,
    baseline_selector,
    evaluate_candidate,
    random_selector,
    release_selector,
)
from ..policies.simulator_teachers import OracleFull
from .generator import sequence_is_health_safe, sequence_is_reachable
from .physics import ShaftSimulator
from .state import ShaftEnvConfig


FAILURE_REASONS = (
    "unreachable_sequence",
    "wrong_target",
    "brake_too_late",
    "wall_collision",
    "platform_not_visible_in_time",
    "missed_platform",
    "top_death",
    "bottom_death",
    "health_depleted",
    "timeout",
    "unknown",
)


@dataclass(frozen=True)
class ReachabilityGate:
    seed_start: int
    seeds: int
    passed: bool
    unreachable_seeds: tuple[int, ...]
    reproducible: bool
    lookahead: int
    health_safe: bool
    unsafe_health_seeds: tuple[int, ...]
    spike_platforms: int
    total_platforms: int
    realized_spike_ratio: float
    platform_kind_counts: dict[str, int]
    realized_platform_kind_ratios: dict[str, float]
    effective_environment_version: str


def run_reachability_gate(
    seed_count: int,
    *,
    config: ShaftEnvConfig,
    seed_start: int = 0,
) -> ReachabilityGate:
    if seed_count <= 0:
        raise ValueError("seed_count 必須大於 0。")
    if seed_start < 0:
        raise ValueError("seed_start 不可小於 0。")
    unreachable = []
    unsafe_health = []
    reproducible = True
    spike_platforms = 0
    total_platforms = 0
    kind_counts: Counter[str] = Counter()
    for seed in range(seed_start, seed_start + seed_count):
        first = ShaftSimulator(config, np.random.default_rng(seed))
        second = ShaftSimulator(config, np.random.default_rng(seed))
        first_sequence = [
            (item.floor_index, item.center_x, item.center_y, item.kind)
            for item in sorted(first.platforms, key=lambda item: item.floor_index)
        ]
        second_sequence = [
            (item.floor_index, item.center_x, item.center_y, item.kind)
            for item in sorted(second.platforms, key=lambda item: item.floor_index)
        ]
        reproducible &= first_sequence == second_sequence
        spike_platforms += sum(
            item.kind == "spikes" for item in first.platforms
        )
        kind_counts.update(item.kind for item in first.platforms)
        total_platforms += len(first.platforms)
        if not sequence_is_health_safe(config, first.platforms):
            unsafe_health.append(seed)
        if not sequence_is_reachable(config, first.platforms):
            unreachable.append(seed)
    return ReachabilityGate(
        seed_start=seed_start,
        seeds=seed_count,
        passed=not unreachable and not unsafe_health and reproducible,
        unreachable_seeds=tuple(unreachable),
        reproducible=reproducible,
        lookahead=config.reachability_lookahead,
        health_safe=not unsafe_health,
        unsafe_health_seeds=tuple(unsafe_health),
        spike_platforms=spike_platforms,
        total_platforms=total_platforms,
        realized_spike_ratio=(
            spike_platforms / max(1, total_platforms)
        ),
        platform_kind_counts={
            kind: int(kind_counts.get(kind, 0))
            for kind in (
                "normal",
                "spikes",
                "spring",
                "conveyor_left",
                "conveyor_right",
                "flipping",
            )
        },
        realized_platform_kind_ratios={
            kind: float(kind_counts.get(kind, 0) / max(1, total_platforms))
            for kind in (
                "normal",
                "spikes",
                "spring",
                "conveyor_left",
                "conveyor_right",
                "flipping",
            )
        },
        effective_environment_version=config.effective_environment_version,
    )


def oracle_selector(oracle: OracleFull | None = None):
    controller = oracle or OracleFull()

    def choose(_observation, env, _rng) -> int:
        return int(controller.choose(env.simulator).action)

    return choose


def bootstrap_ci(values: Iterable[float], *, seed: int = 20260730) -> tuple[float, float]:
    array = np.asarray(list(values), dtype=np.float64)
    if not len(array):
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(array), size=(2000, len(array)))
    means = array[indices].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def lower_tail_mean(values: Iterable[float], *, fraction: float = 0.25) -> float:
    """Return the mean of the exact worst ``ceil(n * fraction)`` samples."""

    array = np.sort(np.asarray(list(values), dtype=np.float64))
    if not len(array):
        return float("nan")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("tail fraction 必須位於 (0, 1]。")
    count = max(1, int(math.ceil(len(array) * fraction)))
    return float(array[:count].mean())


def evaluation_summary(result: ProbeEvaluation) -> dict[str, Any]:
    floors = np.asarray([episode.floors for episode in result.episode_results], dtype=float)
    deepest_floors = np.asarray(
        [episode.deepest_floor for episode in result.episode_results],
        dtype=float,
    )
    ci_low, ci_high = bootstrap_ci(floors)
    return {
        **result.to_dict(),
        "median_floors": float(np.median(floors)),
        "std_floors": float(np.std(floors)),
        "floor_quantile_25": float(np.quantile(floors, 0.25)),
        "mean_deepest_floor": float(np.mean(deepest_floors)),
        "median_deepest_floor": float(np.median(deepest_floors)),
        "deepest_floor_quantile_25": float(
            np.quantile(deepest_floors, 0.25)
        ),
        "floor_cvar25": lower_tail_mean(floors, fraction=0.25),
        "deepest_floor_cvar25": lower_tail_mean(
            deepest_floors, fraction=0.25
        ),
        "bottom_death_rate": float(
            result.terminal_reasons.get("bottom", 0)
            / max(1, result.episodes)
        ),
        "health_death_rate": float(
            result.terminal_reasons.get("health_depleted", 0)
            / max(1, result.episodes)
        ),
        "direction_switches_per_100_steps": float(
            100.0 * result.direction_switches / max(1, result.total_steps)
        ),
        "direction_reversals_per_100_steps": float(
            100.0 * result.direction_reversals / max(1, result.total_steps)
        ),
        "floors_bootstrap_ci95": [ci_low, ci_high],
        "success_rate_floor_1": float(np.mean(floors >= 1)),
        "success_rate_floor_3": float(np.mean(floors >= 3)),
        "success_rate_floor_5": float(np.mean(floors >= 5)),
        "success_rate_floor_10": float(np.mean(floors >= 10)),
        "reach_rate_floor_1": float(np.mean(deepest_floors >= 1)),
        "reach_rate_floor_3": float(np.mean(deepest_floors >= 3)),
        "reach_rate_floor_5": float(np.mean(deepest_floors >= 5)),
        "reach_rate_floor_10": float(np.mean(deepest_floors >= 10)),
    }


def evaluate_gate_candidates(
    *,
    config: ShaftEnvConfig,
    seeds: Iterable[int],
    max_episode_steps: int = 600,
) -> dict[str, ProbeEvaluation]:
    seed_list = list(seeds)
    return {
        "oracle_full": evaluate_candidate(
            "oracle_full",
            oracle_selector(),
            seeds=seed_list,
            max_episode_steps=max_episode_steps,
            config=config,
            success_floor=10,
        ),
        "baseline": evaluate_candidate(
            "baseline",
            baseline_selector(),
            seeds=seed_list,
            max_episode_steps=max_episode_steps,
            config=config,
        ),
        "random": evaluate_candidate(
            "random",
            random_selector,
            seeds=seed_list,
            max_episode_steps=max_episode_steps,
            config=config,
        ),
        "release": evaluate_candidate(
            "release",
            release_selector,
            seeds=seed_list,
            max_episode_steps=max_episode_steps,
            config=config,
        ),
    }


def benchmark_candidate(result: ProbeEvaluation, elapsed: float) -> dict[str, Any]:
    summary = evaluation_summary(result)
    summary["simulation_steps_per_second"] = result.total_steps / max(elapsed, 1e-9)
    summary["mean_action_duration_ms"] = 1000.0 / 8.0
    summary["oscillation_rate"] = result.direction_switches / max(1, result.total_steps)
    summary["missed_platform_proxy_rate"] = (
        result.terminal_reasons.get("bottom", 0) / max(1, result.episodes)
    )
    return summary


__all__ = [
    "FAILURE_REASONS",
    "ReachabilityGate",
    "benchmark_candidate",
    "bootstrap_ci",
    "evaluate_gate_candidates",
    "evaluation_summary",
    "lower_tail_mean",
    "oracle_selector",
    "run_reachability_gate",
]
