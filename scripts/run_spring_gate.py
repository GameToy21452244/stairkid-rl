from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.scenarios import (
    configure_spring_choice,
    configure_spring_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        enable_spring=True,
        scroll_speed=0.0,
        max_episode_steps=40,
    )


def step_to_landing(env: ShaftEnv) -> dict:
    for _ in range(30):
        _observation, _reward, terminated, truncated, info = env.step(0)
        if "landed" in info["events"]:
            return info
        if terminated or truncated:
            return info
    return {"terminal_reason": "no_landing", "events": []}


def fixed_gates(seed_count: int = 100) -> dict:
    bounce_failures = []
    oracle_failures = []
    for seed in range(seed_count):
        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            configure_spring_landing(env.simulator)
            info = step_to_landing(env)
            if (
                info.get("spring_velocity_delta_y") != 95.0
                or not {
                    "landed",
                    "spring_contact",
                    "spring_bounce",
                }
                <= set(info.get("events", []))
                or env.simulator.player.body.velocity.y
                <= env.config.jump_velocity
            ):
                bounce_failures.append({"seed": seed, "info": info})
        finally:
            env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            _spring, safe = configure_spring_choice(env.simulator)
            decision = OracleFull().choose(env.simulator)
            if (
                decision.target_platform_kind != "normal"
                or decision.target_center_x != safe.center_x
            ):
                oracle_failures.append(
                    {
                        "seed": seed,
                        "kind": decision.target_platform_kind,
                        "center": decision.target_center_x,
                        "safe_center": safe.center_x,
                    }
                )
        finally:
            env.close()
    return {
        "seeds": seed_count,
        "stronger_bounce": {
            "passed": not bounce_failures,
            "failures": bounce_failures,
        },
        "oracle_normal_preference": {
            "passed": not oracle_failures,
            "failures": oracle_failures,
        },
    }


def main() -> int:
    fixed = fixed_gates()
    seeds = tuple(range(100))
    feature_off = evaluate_candidate(
        "baseline_spring_off",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_spring=False, fps=10),
    )
    feature_on_no_spawn = evaluate_candidate(
        "baseline_spring_enabled_no_spawn",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_spring=True, fps=10),
    )
    equivalence = [
        asdict(item) for item in feature_off.episode_results
    ] == [
        asdict(item)
        for item in feature_on_no_spawn.episode_results
    ]
    fixed_pass = all(
        fixed[name]["passed"]
        for name in ("stronger_bounce", "oracle_normal_preference")
    )
    payload = {
        "environment_version": ShaftEnvConfig(
            enable_spring=True
        ).effective_environment_version,
        "feature_default_enabled": ShaftEnvConfig().enable_spring,
        "normal_jump_velocity_px_per_second": 95.0,
        "provisional_spring_jump_velocity_px_per_second": 190.0,
        "fixed_gates": fixed,
        "no_spawn_feature_equivalence": {
            "passed": equivalence,
            "seeds": 100,
            "feature_off_mean_floors": feature_off.mean_floors,
            "feature_on_mean_floors": (
                feature_on_no_spawn.mean_floors
            ),
            "feature_off_terminal_reasons": (
                feature_off.terminal_reasons
            ),
            "feature_on_terminal_reasons": (
                feature_on_no_spawn.terminal_reasons
            ),
        },
        "renderer_test": "pytest",
        "calibration_interface_test": "pytest",
        "passed": fixed_pass and equivalence,
    }
    Path("artifacts/spring_gate_v1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
