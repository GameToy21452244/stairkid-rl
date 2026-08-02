from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.simulator.gates import evaluation_summary
from stair_agent.simulator.state import ShaftEnvConfig


def recovery_selector(reason_counts: Counter[str]):
    policy = SafePlatformPolicy(BaselineConfig())

    def choose(_observation, env, _rng) -> int:
        decision = policy.choose(env.last_observation)
        reason_counts[decision.reason] += 1
        return int(decision.action)

    setattr(choose, "reset", policy.reset)
    return choose


def spike_config(*, initial_health: int) -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        max_episode_steps=600,
        enable_health=True,
        initial_health_segments=initial_health,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, default=1600)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/teacher_recovery_gate_v0.json"),
    )
    args = parser.parse_args()
    seeds = tuple(range(args.seed_start, args.seed_start + 100))
    reasons: Counter[str] = Counter()
    low_health = evaluation_summary(
        evaluate_candidate(
            "teacher_observable_recovery",
            recovery_selector(reasons),
            seeds=seeds,
            max_episode_steps=600,
            config=spike_config(initial_health=7),
        )
    )
    full_health = evaluation_summary(
        evaluate_candidate(
            "teacher_observable_full_health_reference",
            baseline_selector(),
            seeds=seeds,
            max_episode_steps=600,
            config=spike_config(initial_health=12),
        )
    )
    health_deaths = int(
        low_health["terminal_reasons"].get("health_depleted", 0)
    )
    recovery_decisions = sum(
        count
        for reason, count in reasons.items()
        if "recovery" in reason
    )
    recovery_safety_passed = bool(
        recovery_decisions > 0
        and health_deaths == 0
        and not low_health["collapsed"]
        and low_health["reach_rate_floor_10"]
        >= full_health["reach_rate_floor_10"] - 0.02
        and low_health["deepest_floor_quantile_25"]
        >= 0.8 * full_health["deepest_floor_quantile_25"]
    )
    reliability_passed = bool(
        low_health["reach_rate_floor_10"] >= 0.90
        and low_health["deepest_floor_quantile_25"] >= 10.0
    )
    passed = recovery_safety_passed and reliability_passed
    output = {
        "experiment": "teacher-observable-health-recovery-v0",
        "gate_seeds": list(seeds),
        "initial_health_segments": 7,
        "recovery_full_health_segments": 12,
        "reason_counts": dict(reasons),
        "recovery_decisions": recovery_decisions,
        "low_health_evaluation": low_health,
        "full_health_reference": full_health,
        "gate": {
            "passed": passed,
            "recovery_safety_non_regression_passed": recovery_safety_passed,
            "absolute_reliability_passed": reliability_passed,
            "criteria": (
                "recovery decisions >0, no health death/collapse, "
                "within 2pp of full-health reach-floor-10 and >=80% reference Q25; "
                "absolute reach-floor-10 >=90%, deepest-floor Q25 >=10"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "gate": output["gate"],
                "recovery_decisions": recovery_decisions,
                "mean_deepest_floor": low_health["mean_deepest_floor"],
                "deepest_floor_quantile_25": low_health[
                    "deepest_floor_quantile_25"
                ],
                "successful_descents_rate_10": low_health["success_rate_floor_10"],
                "reach_rate_floor_10": low_health["reach_rate_floor_10"],
                "terminal_reasons": low_health["terminal_reasons"],
                "full_health_successful_descents_rate_10": full_health["success_rate_floor_10"],
                "full_health_reach_rate_floor_10": full_health["reach_rate_floor_10"],
                "full_health_deepest_floor_quantile_25": full_health[
                    "deepest_floor_quantile_25"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
