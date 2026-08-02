from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.simulator.gates import (
    evaluation_summary,
    oracle_selector,
    run_reachability_gate,
)
from stair_agent.simulator.state import ShaftEnvConfig


SEEDS = tuple(range(100))
MAX_EPISODE_STEPS = 600


def curriculum_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )


def main() -> int:
    config = curriculum_config()
    reach100 = run_reachability_gate(100, config=config)
    reach1000 = run_reachability_gate(1000, config=config)
    oracle = evaluate_candidate(
        "oracle_full_spike_curriculum_v0",
        oracle_selector(),
        seeds=SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
        success_floor=10,
    )
    baseline = evaluate_candidate(
        "baseline_spike_curriculum_v0",
        baseline_selector(),
        seeds=SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
    )
    plain_baseline = evaluate_candidate(
        "baseline_plain_easy",
        baseline_selector(),
        seeds=SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=ShaftEnvConfig(distribution="easy", fps=10),
    )
    oracle_summary = evaluation_summary(oracle)
    baseline_summary = evaluation_summary(baseline)
    plain_summary = evaluation_summary(plain_baseline)
    ratio_pass = 0.04 <= reach1000.realized_spike_ratio <= 0.07
    oracle_pass = (
        oracle_summary["reach_rate_floor_10"] >= 0.95
        and oracle.terminal_reasons.get("health_depleted", 0) == 0
    )
    retention = baseline.mean_floors / max(
        plain_baseline.mean_floors, 1e-9
    )
    baseline_pass = (
        retention >= 0.80
        and baseline_summary["success_rate_floor_3"] >= 0.90
        and baseline.terminal_reasons.get("health_depleted", 0) == 0
    )
    payload = {
        "environment_version": config.effective_environment_version,
        "curriculum": {
            "spike_proposal_probability": config.spike_spawn_probability,
            "initial_safe_normal_platforms": (
                config.initial_safe_normal_platforms
            ),
            "minimum_normal_platforms_between_spikes": (
                config.minimum_normal_platforms_between_spikes
            ),
            "spike_damage_segments": config.spike_damage_segments,
            "normal_heal_segments": (
                config.normal_platform_heal_segments
            ),
        },
        "gates": {
            "reachability_100": asdict(reach100),
            "reachability_1000": asdict(reach1000),
            "spawn_ratio": {
                "passed": ratio_pass,
                "threshold": "0.04 <= realized <= 0.07",
                "realized": reach1000.realized_spike_ratio,
            },
            "oracle": {
                "passed": oracle_pass,
                "threshold": ">=95% reach floor 10; 0 health deaths",
                "evaluation": oracle_summary,
            },
            "baseline": {
                "passed": baseline_pass,
                "threshold": (
                    ">=80% plain mean floors; >=90% reach floor 3; "
                    "0 health deaths"
                ),
                "retention_vs_plain": retention,
                "evaluation": baseline_summary,
                "plain_evaluation": plain_summary,
            },
        },
    }
    payload["passed"] = all(
        (
            reach100.passed,
            reach1000.passed,
            ratio_pass,
            oracle_pass,
            baseline_pass,
        )
    )
    Path("artifacts/spike_curriculum_v0_gate.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
