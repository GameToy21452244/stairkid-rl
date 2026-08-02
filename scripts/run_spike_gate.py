from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.scenarios import (
    configure_normal_healing_landing,
    configure_spike_choice,
    configure_spike_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        enable_health=True,
        enable_spikes=True,
        scroll_speed=0.0,
        max_episode_steps=40,
    )


def step_to_landing(env: ShaftEnv, *, oracle: bool = False):
    controller = OracleFull()
    for _ in range(30):
        action = int(controller.choose(env.simulator).action) if oracle else 0
        _observation, _reward, terminated, truncated, info = env.step(action)
        if "landed" in info["events"]:
            return terminated, info
        if terminated or truncated:
            return terminated, info
    return False, {"terminal_reason": "no_landing", "events": []}


def fixed_gates(seed_count: int = 100) -> dict:
    damage_failures = []
    lethal_failures = []
    heal_failures = []
    choice_failures = []
    for seed in range(seed_count):
        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            configure_spike_landing(env.simulator, health_segments=12)
            terminated, info = step_to_landing(env)
            if (
                terminated
                or info.get("health_segments") != 7
                or info.get("health_delta") != -5
                or "damage" not in info.get("events", [])
            ):
                damage_failures.append({"seed": seed, "info": info})
        finally:
            env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            configure_spike_landing(env.simulator, health_segments=5)
            terminated, info = step_to_landing(env)
            if (
                not terminated
                or info.get("health_segments") != 0
                or info.get("terminal_reason") != "health_depleted"
            ):
                lethal_failures.append({"seed": seed, "info": info})
        finally:
            env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            configure_normal_healing_landing(
                env.simulator, health_segments=8
            )
            _terminated, info = step_to_landing(env)
            if (
                info.get("health_segments") != 9
                or info.get("health_delta") != 1
                or "health_gained" not in info.get("events", [])
            ):
                heal_failures.append({"seed": seed, "info": info})
        finally:
            env.close()

        env = ShaftEnv(config=config())
        try:
            env.reset(seed=seed)
            _spike, safe = configure_spike_choice(env.simulator)
            decision = OracleFull().choose(env.simulator)
            if (
                decision.target_platform_kind != "normal"
                or decision.target_center_x != safe.center_x
            ):
                choice_failures.append(
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
        "damage": {
            "passed": not damage_failures,
            "failures": damage_failures,
        },
        "lethal": {
            "passed": not lethal_failures,
            "failures": lethal_failures,
        },
        "normal_heal_interaction": {
            "passed": not heal_failures,
            "failures": heal_failures,
        },
        "oracle_avoidance": {
            "passed": not choice_failures,
            "failures": choice_failures,
        },
    }


def main() -> int:
    fixed = fixed_gates()
    seeds = tuple(range(100))
    health_only = evaluate_candidate(
        "baseline_health_only",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(
            enable_health=True, enable_spikes=False, fps=10
        ),
    )
    spikes_no_spawn = evaluate_candidate(
        "baseline_spikes_enabled_no_spawn",
        baseline_selector(),
        seeds=seeds,
        max_episode_steps=600,
        config=ShaftEnvConfig(
            enable_health=True, enable_spikes=True, fps=10
        ),
    )
    equivalence = [
        asdict(item) for item in health_only.episode_results
    ] == [asdict(item) for item in spikes_no_spawn.episode_results]
    fixed_pass = all(
        fixed[name]["passed"]
        for name in (
            "damage",
            "lethal",
            "normal_heal_interaction",
            "oracle_avoidance",
        )
    )
    payload = {
        "environment_version": ShaftEnvConfig(
            enable_health=True, enable_spikes=True
        ).effective_environment_version,
        "feature_default_enabled": ShaftEnvConfig().enable_spikes,
        "spike_damage_segments": 5,
        "fixed_gates": fixed,
        "no_spawn_feature_equivalence": {
            "passed": equivalence,
            "seeds": 100,
            "health_only_mean_floors": health_only.mean_floors,
            "spikes_enabled_mean_floors": spikes_no_spawn.mean_floors,
            "health_only_terminal_reasons": health_only.terminal_reasons,
            "spikes_enabled_terminal_reasons": (
                spikes_no_spawn.terminal_reasons
            ),
        },
        "renderer_test": "pytest",
        "calibration_interface_test": "pytest",
        "passed": fixed_pass and equivalence,
    }
    Path("artifacts/spike_gate_v1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
