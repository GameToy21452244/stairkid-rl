from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.scenarios import configure_normal_healing_landing
from stair_agent.simulator.state import ShaftEnvConfig


def fixed_landing_gate(seed_count: int = 100) -> dict:
    failures = []
    oracle = OracleFull()
    for seed in range(seed_count):
        config = ShaftEnvConfig(
            enable_health=True,
            scroll_speed=0.0,
            max_episode_steps=40,
        )
        env = ShaftEnv(config=config)
        start_health = 1 + seed % (config.max_health_segments - 1)
        try:
            env.reset(seed=seed)
            configure_normal_healing_landing(
                env.simulator, health_segments=start_health
            )
            landed = False
            for _ in range(30):
                action = int(oracle.choose(env.simulator).action)
                _observation, _reward, terminated, truncated, info = env.step(
                    action
                )
                if terminated or truncated:
                    failures.append(
                        {"seed": seed, "reason": info["terminal_reason"]}
                    )
                    break
                if "landed" in info["events"]:
                    landed = True
                    expected = min(
                        config.max_health_segments,
                        start_health
                        + config.normal_platform_heal_segments,
                    )
                    if (
                        info["health_segments"] != expected
                        or info["health_delta"] != expected - start_health
                        or "health_gained" not in info["events"]
                    ):
                        failures.append(
                            {
                                "seed": seed,
                                "reason": "incorrect_health_transition",
                                "start": start_health,
                                "info": info,
                            }
                        )
                    break
            if not landed and not any(
                item["seed"] == seed for item in failures
            ):
                failures.append({"seed": seed, "reason": "no_landing"})
        finally:
            env.close()
    return {
        "seeds": seed_count,
        "passed": not failures,
        "failures": failures,
    }


def main() -> int:
    landing = fixed_landing_gate()
    seeds = tuple(range(100))
    disabled = evaluate_candidate(
        "baseline_health_off",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_health=False, fps=10),
    )
    enabled = evaluate_candidate(
        "baseline_health_on_full",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_health=True, fps=10),
    )
    disabled_rows = [
        asdict(item) for item in disabled.episode_results
    ]
    enabled_rows = [asdict(item) for item in enabled.episode_results]
    equivalence = disabled_rows == enabled_rows
    payload = {
        "environment_version": ShaftEnvConfig(
            enable_health=True
        ).effective_environment_version,
        "feature_default_enabled": ShaftEnvConfig().enable_health,
        "normal_platform_heal_segments": 1,
        "max_health_segments": 12,
        "fixed_oracle_landing_gate": landing,
        "feature_off_on_full_health_equivalence": {
            "passed": equivalence,
            "seeds": 100,
            "off_mean_floors": disabled.mean_floors,
            "on_mean_floors": enabled.mean_floors,
            "off_terminal_reasons": disabled.terminal_reasons,
            "on_terminal_reasons": enabled.terminal_reasons,
        },
        "renderer_test": "pytest",
        "calibration_interface_test": "pytest",
        "passed": landing["passed"] and equivalence,
    }
    Path("artifacts/health_gate_v1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
