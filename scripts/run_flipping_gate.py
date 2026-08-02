from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.scenarios import (
    configure_flipping_choice,
    configure_flipping_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        enable_flipping=True,
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
    active_failures = []
    inactive_failures = []
    oracle_failures = []
    for seed in range(seed_count):
        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            floor = configure_flipping_landing(
                env.simulator,
                active=True,
            )
            info = step_to_landing(env)
            if (
                env.simulator.last_landed_floor != floor
                or "flipping_contact" not in info.get("events", [])
            ):
                active_failures.append({"seed": seed, "info": info})
        finally:
            env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            floor = configure_flipping_landing(
                env.simulator,
                active=False,
            )
            events = []
            for _ in range(5):
                _observation, _reward, terminated, truncated, info = (
                    env.step(0)
                )
                events.extend(info.get("events", []))
                if terminated or truncated:
                    break
            if (
                env.simulator.last_landed_floor == floor
                or "flipping_contact" in events
            ):
                inactive_failures.append(
                    {
                        "seed": seed,
                        "events": events,
                        "last_landed_floor": (
                            env.simulator.last_landed_floor
                        ),
                    }
                )
        finally:
            env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            _flipping, safe = configure_flipping_choice(env.simulator)
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
        "active_collision": {
            "passed": not active_failures,
            "failures": active_failures,
        },
        "inactive_passthrough": {
            "passed": not inactive_failures,
            "failures": inactive_failures,
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
        "baseline_flipping_off",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_flipping=False, fps=10),
    )
    feature_on_no_spawn = evaluate_candidate(
        "baseline_flipping_enabled_no_spawn",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_flipping=True, fps=10),
    )
    equivalence = [
        asdict(item) for item in feature_off.episode_results
    ] == [
        asdict(item)
        for item in feature_on_no_spawn.episode_results
    ]
    fixed_pass = all(
        fixed[name]["passed"]
        for name in (
            "active_collision",
            "inactive_passthrough",
            "oracle_normal_preference",
        )
    )
    payload = {
        "environment_version": ShaftEnvConfig(
            enable_flipping=True
        ).effective_environment_version,
        "feature_default_enabled": ShaftEnvConfig().enable_flipping,
        "provisional_active_seconds": 1.0,
        "provisional_inactive_seconds": 1.0,
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
    Path("artifacts/flipping_gate_v1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
