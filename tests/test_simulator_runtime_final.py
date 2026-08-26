from __future__ import annotations

from pathlib import Path

import pytest

from stair_agent.core.model_registry import MODEL_IDS, load_canonical_model
from stair_agent.sim.runtime import create_simulator_environment, run_simulator_policy


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_simulator_contract_and_deterministic_inference(model_id: str) -> None:
    loaded = load_canonical_model(ROOT, model_id)
    env = create_simulator_environment(
        ROOT, model_id, base_seed=12345, render_mode=None
    )
    try:
        observation, _ = env.reset(seed=12345)
        assert observation.shape == (268,)
        assert env.action_space.n == 3
        assert env.config.physics_hz == 60
        action = loaded.predict(observation)
        assert action in (0, 1, 2)
        next_observation, *_ = env.step(action)
        assert next_observation.shape == (268,)
    finally:
        env.close()

    result = run_simulator_policy(
        ROOT,
        model_id,
        episodes=1,
        max_steps_per_episode=12,
        base_seed=12345,
        render_mode=None,
        loaded=loaded,
    )
    assert result["model_id"] == model_id
    assert result["deterministic"] is True
    assert result["observation_shape"] == [268]
    assert result["action_count"] == 3
    assert result["episodes"][0]["steps"] > 0
