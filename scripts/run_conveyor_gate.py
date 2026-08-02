from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.scenarios import (
    configure_conveyor_choice,
    configure_conveyor_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        enable_conveyor=True,
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
    direction_failures: dict[str, list[dict]] = {
        "left": [],
        "right": [],
    }
    oracle_failures = []
    for seed in range(seed_count):
        for direction, expected in (("left", -80.0), ("right", 80.0)):
            env = ShaftEnv(config=config())
            try:
                env.reset(seed=seed)
                configure_conveyor_landing(
                    env.simulator,
                    direction=direction,
                )
                info = step_to_landing(env)
                required_events = {
                    "landed",
                    "conveyor_contact",
                    f"conveyor_{direction}",
                }
                if (
                    info.get("conveyor_velocity_delta_x") != expected
                    or not required_events <= set(info.get("events", []))
                ):
                    direction_failures[direction].append(
                        {"seed": seed, "info": info}
                    )
            finally:
                env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            _conveyor, safe = configure_conveyor_choice(env.simulator)
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
        "left_velocity": {
            "passed": not direction_failures["left"],
            "failures": direction_failures["left"],
        },
        "right_velocity": {
            "passed": not direction_failures["right"],
            "failures": direction_failures["right"],
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
        "baseline_conveyor_off",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_conveyor=False, fps=10),
    )
    feature_on_no_spawn = evaluate_candidate(
        "baseline_conveyor_enabled_no_spawn",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(enable_conveyor=True, fps=10),
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
            "left_velocity",
            "right_velocity",
            "oracle_normal_preference",
        )
    )
    payload = {
        "environment_version": ShaftEnvConfig(
            enable_conveyor=True
        ).effective_environment_version,
        "feature_default_enabled": ShaftEnvConfig().enable_conveyor,
        "provisional_velocity_delta_px_per_second": 80.0,
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
    Path("artifacts/conveyor_gate_v1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
