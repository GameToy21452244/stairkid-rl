import gymnasium as gym
import numpy as np
import pytest
from gymnasium import spaces

pytest.importorskip("stable_baselines3")

from stable_baselines3.common.vec_env import DummyVecEnv

from stair_agent.config import TrainingConfig
from stair_agent.rl_training import (
    TrainingSafetyWrapper,
    create_ppo_model,
)


class TwoStepEpisodeEnv(gym.Env):
    def __init__(self):
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            -1.0,
            1.0,
            shape=(8,),
            dtype=np.float32,
        )
        self.reset_count = 0
        self.steps = 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        del options
        self.reset_count += 1
        self.steps = 0
        return np.zeros(8, dtype=np.float32), {}

    def step(self, action):
        del action
        self.steps += 1
        terminated = self.steps >= 2
        return (
            np.zeros(8, dtype=np.float32),
            0.0,
            terminated,
            False,
            {},
        )


def test_final_episode_budget_prevents_vec_env_auto_reset() -> None:
    raw = TwoStepEpisodeEnv()
    wrapped = TrainingSafetyWrapper(raw, max_episodes=2)
    vec = DummyVecEnv([lambda: wrapped])

    vec.reset()
    vec.step([0])
    _obs, _reward, first_done, _info = vec.step([0])
    assert first_done.tolist() == [True]
    assert raw.reset_count == 2

    vec.step([0])
    _obs, _reward, final_done, infos = vec.step([0])

    assert final_done.tolist() == [False]
    assert infos[0]["training_budget_exhausted"]
    assert raw.reset_count == 2
    vec.close()


def test_create_ppo_model_uses_bounded_cpu_configuration() -> None:
    env = TrainingSafetyWrapper(TwoStepEpisodeEnv(), max_episodes=2)
    config = TrainingConfig(
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        device="cpu",
    )

    model = create_ppo_model(env, config, verbose=0)

    assert model.n_steps == 8
    assert model.batch_size == 4
    assert model.n_epochs == 1
    assert model.device.type == "cpu"
    env.close()


@pytest.mark.parametrize("total_timesteps", [4, 9])
def test_create_ppo_model_rejects_rollout_budget_overshoot(
    total_timesteps: int,
) -> None:
    env = TrainingSafetyWrapper(TwoStepEpisodeEnv(), max_episodes=2)
    config = TrainingConfig(
        total_timesteps=total_timesteps,
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        device="cpu",
    )

    with pytest.raises(ValueError, match="total_timesteps"):
        create_ppo_model(env, config, verbose=0)
    env.close()
