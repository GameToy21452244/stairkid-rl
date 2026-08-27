"""Thin policy runtime over the single corrected simulator implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.model_registry import LoadedCanonicalModel, load_canonical_model
from ..envs.fidelity_v3 import FidelityV3Env
from ..envs.fidelity_v3_5 import FidelityV35Env, load_fidelity_v3_5_profile
from ..envs.fidelity_v3_fresh import load_fidelity_v3_fresh_profile


def create_simulator_environment(
    project_root: Path,
    model_id: str,
    *,
    base_seed: int,
    render_mode: str | None,
) -> FidelityV3Env:
    root = project_root.resolve()
    if model_id == "v3":
        return FidelityV3Env(
            profile=load_fidelity_v3_fresh_profile(root / "configs/fidelity_v3_fresh.yaml"),
            base_seed=base_seed,
            render_mode=render_mode,
        )
    if model_id == "r4":
        return FidelityV35Env(
            profile=load_fidelity_v3_5_profile(root / "configs/fidelity_v3_5.yaml"),
            base_seed=base_seed,
            render_mode=render_mode,
        )
    raise ValueError(f"UNKNOWN_MODEL_ID:{model_id}")


def run_simulator_policy(
    project_root: Path,
    model_id: str,
    *,
    episodes: int = 1,
    max_steps_per_episode: int = 3600,
    base_seed: int = 12345,
    render_mode: str | None = None,
    loaded: LoadedCanonicalModel | None = None,
) -> dict[str, Any]:
    if episodes < 1:
        raise ValueError("EPISODES_MUST_BE_POSITIVE")
    if max_steps_per_episode < 1:
        raise ValueError("MAX_STEPS_MUST_BE_POSITIVE")
    policy = loaded or load_canonical_model(project_root, model_id)
    if policy.spec.id != model_id:
        raise ValueError("LOADED_MODEL_ID_MISMATCH")
    env = create_simulator_environment(
        project_root,
        model_id,
        base_seed=base_seed,
        render_mode=render_mode,
    )
    results: list[dict[str, Any]] = []
    try:
        for episode_index in range(episodes):
            observation, info = env.reset(seed=base_seed + episode_index)
            terminated = truncated = False
            steps = 0
            total_reward = 0.0
            while not (terminated or truncated) and steps < max_steps_per_episode:
                action = policy.predict(observation)
                observation, reward, terminated, truncated, info = env.step(action)
                total_reward += float(reward)
                steps += 1
            results.append(
                {
                    "episode": episode_index + 1,
                    "seed": base_seed + episode_index,
                    "steps": steps,
                    "reward": total_reward,
                    "deepest_floor": int(info.get("deepest_floor", 0)),
                    "terminated": bool(terminated),
                    "truncated": bool(truncated),
                    "terminal_reason": info.get("terminal_reason"),
                }
            )
    finally:
        env.close()
    return {
        "model_id": policy.spec.id,
        "model_sha256": policy.spec.sha256,
        "deterministic": True,
        "physics_source": "stair_agent.simulator.physics.ShaftSimulator",
        "observation_shape": list(policy.spec.observation_shape),
        "action_count": policy.spec.action_count,
        "episodes": results,
    }
