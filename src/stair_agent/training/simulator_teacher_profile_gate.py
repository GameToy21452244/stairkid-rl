"""Bounded reliability Gate for separated simulator Teacher profiles."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterable, Mapping

import numpy as np

from ..data.p41_dataset_gap import (
    analyze_teacher_dataset,
    compare_same_seed_datasets,
    evaluate_v2_same_seed_readiness,
)
from ..envs.shaft_env import ShaftEnv
from ..observation import GameObservation
from ..policies.simulator_teachers import SimulatorTeacherProfile, TeacherObservable
from ..policies.simulator_teachers import TeacherDecision
from ..simulator.gates import lower_tail_mean
from ..simulator.state import ShaftEnvConfig


SAME_SEED_START = 2000
SAME_SEED_COUNT = 60
FRESH_SEED_START = 6000
FRESH_SEED_COUNT = 100


def spike_teacher_environment_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        max_episode_steps=300,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )


def split_for_index(index: int, count: int) -> str:
    if count < 6:
        raise ValueError("至少需要 6 seeds 才能建立三個非空 split。")
    if index < count * 2 // 3:
        return "train"
    if index < count * 5 // 6:
        return "validation"
    return "test"


def _performance(
    deepest_floors: list[int],
    analysis: Mapping[str, object],
) -> dict[str, float | int]:
    values = np.asarray(deepest_floors, dtype=np.float64)
    episodes = max(1, len(deepest_floors))
    outcomes = analysis["outcomes"]
    return {
        "episodes": len(deepest_floors),
        "mean_deepest_floor": float(values.mean()),
        "median_deepest_floor": float(np.median(values)),
        "deepest_floor_quantile_25": float(np.quantile(values, 0.25)),
        "deepest_floor_cvar25": lower_tail_mean(values, fraction=0.25),
        "reach_floor_10_rate": float(np.mean(values >= 10)),
        "bottom_death_rate": int(outcomes.get("bottom", 0)) / episodes,
        "health_death_rate": (
            int(outcomes.get("health_depleted", 0)) / episodes
        ),
        "release_bridged_reversals_per_100_steps": float(
            analysis["release_bridged_reversals_per_100_steps"]
        ),
    }


def evaluate_simulator_teacher_profile(
    profile: SimulatorTeacherProfile,
    seeds: Iterable[int],
    *,
    config: ShaftEnvConfig | None = None,
    decision_observer: Callable[
        [int, int, GameObservation, TeacherDecision, ShaftEnv], None
    ]
    | None = None,
) -> dict[str, Any]:
    frozen_seeds = tuple(int(seed) for seed in seeds)
    if len(frozen_seeds) < 6 or len(set(frozen_seeds)) != len(frozen_seeds):
        raise ValueError("seeds 必須至少 6 個且不可重複。")
    env_config = config or spike_teacher_environment_config()
    deepest_floors: list[int] = []
    with TemporaryDirectory(prefix="stairkid-sim-teacher-") as temporary:
        trace_path = Path(temporary) / f"{profile.name}.jsonl"
        with trace_path.open("w", encoding="utf-8", newline="\n") as stream:
            for index, seed in enumerate(frozen_seeds):
                split = split_for_index(index, len(frozen_seeds))
                episode_id = f"{profile.name}-seed-{seed:04d}"
                env = ShaftEnv(config=env_config)
                teacher = TeacherObservable(verified=True, profile=profile)
                env.reset(seed=seed)
                try:
                    for step in range(env_config.max_episode_steps):
                        visible_kinds = [
                            str(platform.get("kind", ""))
                            for platform in env.last_observation.platforms
                        ]
                        health = int(
                            (env.last_observation.health or {}).get(
                                "segments", env_config.initial_health_segments
                            )
                        )
                        decision = teacher.choose(env.last_observation)
                        if decision_observer is not None:
                            decision_observer(
                                seed,
                                step,
                                env.last_observation,
                                decision,
                                env,
                            )
                        _, _, terminated, truncated, info = env.step(
                            int(decision.action)
                        )
                        payload = {
                            "episode_id": episode_id,
                            "seed": seed,
                            "split": split,
                            "step": step,
                            "action": int(decision.action),
                            "events": list(info["events"]),
                            "terminated": bool(terminated),
                            "truncated": bool(truncated),
                            "failure_reason": info["failure_reason"],
                            "teacher_reason": decision.reason,
                            "target_platform_kind": (
                                decision.target_platform_kind
                            ),
                            "visible_platform_kinds": visible_kinds,
                            "teacher_policy_version": decision.policy_version,
                            "environment_version": (
                                env_config.effective_environment_version
                            ),
                            "health_segments": health,
                        }
                        stream.write(
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                        if (
                            env.simulator.deepest_floor >= 10
                            or terminated
                            or truncated
                        ):
                            break
                    deepest_floors.append(int(env.simulator.deepest_floor))
                finally:
                    env.close()
        analysis = analyze_teacher_dataset(trace_path)
    analysis["path"] = f"diagnostic://simulator-teacher/{profile.name}"
    return {
        "profile": asdict(profile),
        "environment_config": asdict(env_config),
        "seeds": list(frozen_seeds),
        "analysis": analysis,
        "performance": _performance(deepest_floors, analysis),
        "deepest_floor_by_seed": {
            str(seed): deepest
            for seed, deepest in zip(frozen_seeds, deepest_floors, strict=True)
        },
    }


def attach_same_seed_gate(
    frozen: Mapping[str, object],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    comparison = compare_same_seed_datasets(frozen, candidate["analysis"])
    candidate["comparison_to_frozen_v1"] = comparison
    candidate["same_seed_gate"] = evaluate_v2_same_seed_readiness(
        frozen,
        candidate["analysis"],
        comparison,
        source_fingerprint_embedded=True,
        config_fingerprint_embedded=True,
    )
    return candidate


def select_same_seed_candidate(
    candidates: Mapping[str, Mapping[str, object]],
) -> str | None:
    passing = [
        name
        for name, result in candidates.items()
        if bool(result["same_seed_gate"]["passed"])
    ]
    if not passing:
        return None

    def risk_key(name: str) -> tuple[float, ...]:
        metrics = candidates[name]["performance"]
        return (
            float(metrics["health_death_rate"]),
            float(metrics["bottom_death_rate"]),
            -float(metrics["deepest_floor_quantile_25"]),
            -float(metrics["deepest_floor_cvar25"]),
            -float(metrics["reach_floor_10_rate"]),
            float(metrics["release_bridged_reversals_per_100_steps"]),
            -float(metrics["median_deepest_floor"]),
            -float(metrics["mean_deepest_floor"]),
        )

    return min(passing, key=risk_key)


def evaluate_fresh_reliability(candidate: Mapping[str, object]) -> dict[str, Any]:
    metrics = candidate["performance"]
    checks = {
        "episode_count_100": int(metrics["episodes"]) == FRESH_SEED_COUNT,
        "reach_floor_10_at_least_90_percent": (
            float(metrics["reach_floor_10_rate"]) >= 0.90
        ),
        "bottom_death_at_most_10_percent": (
            float(metrics["bottom_death_rate"]) <= 0.10
        ),
        "health_death_zero": float(metrics["health_death_rate"]) == 0.0,
        "q25_reported": math.isfinite(
            float(metrics["deepest_floor_quantile_25"])
        ),
        "cvar25_reported": math.isfinite(
            float(metrics["deepest_floor_cvar25"])
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "criteria": {
            "seed_range": [
                FRESH_SEED_START,
                FRESH_SEED_START + FRESH_SEED_COUNT - 1,
            ],
            "reach_floor_10_rate_minimum": 0.90,
            "bottom_death_rate_maximum": 0.10,
            "health_death_rate_maximum": 0.0,
        },
        "observed": dict(metrics),
    }


__all__ = [
    "FRESH_SEED_COUNT",
    "FRESH_SEED_START",
    "SAME_SEED_COUNT",
    "SAME_SEED_START",
    "attach_same_seed_gate",
    "evaluate_fresh_reliability",
    "evaluate_simulator_teacher_profile",
    "select_same_seed_candidate",
    "spike_teacher_environment_config",
]
