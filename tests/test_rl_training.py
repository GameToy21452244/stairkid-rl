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
    load_ppo_model,
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
    assert wrapped.action_counts == {
        "RELEASE_ALL": 4,
        "LEFT": 0,
        "RIGHT": 0,
    }
    assert wrapped.longest_same_action_streak == 4
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


def test_load_ppo_model_attaches_env_and_preserves_rollout_config(
    tmp_path,
) -> None:
    source_env = TrainingSafetyWrapper(
        TwoStepEpisodeEnv(),
        max_episodes=20,
    )
    config = TrainingConfig(
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        device="cpu",
    )
    source = create_ppo_model(source_env, config, verbose=0)
    model_path = tmp_path / "model"
    source.save(model_path)
    source_env.close()

    target_env = TrainingSafetyWrapper(
        TwoStepEpisodeEnv(),
        max_episodes=20,
    )
    loaded = load_ppo_model(
        target_env,
        model_path.with_suffix(".zip"),
        config,
        verbose=0,
    )

    assert loaded.get_env() is not None
    assert loaded.n_steps == 8
    assert loaded.batch_size == 4
    assert loaded.device.type == "cpu"
    target_env.close()


def test_load_ppo_model_rejects_rollout_config_mismatch(tmp_path) -> None:
    source_env = TrainingSafetyWrapper(
        TwoStepEpisodeEnv(),
        max_episodes=20,
    )
    source_config = TrainingConfig(
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        device="cpu",
    )
    source = create_ppo_model(source_env, source_config, verbose=0)
    model_path = tmp_path / "model"
    source.save(model_path)
    source_env.close()
    target_env = TrainingSafetyWrapper(
        TwoStepEpisodeEnv(),
        max_episodes=20,
    )

    with pytest.raises(ValueError, match="n_steps"):
        load_ppo_model(
            target_env,
            model_path.with_suffix(".zip"),
            TrainingConfig(
                n_steps=16,
                batch_size=4,
                n_epochs=1,
                device="cpu",
            ),
            verbose=0,
        )
    target_env.close()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"n_epochs": 2}, "n_epochs"),
        ({"learning_rate": 0.0001}, "learning_rate"),
        ({"ent_coef": 0.03}, "ent_coef"),
        ({"target_kl": 0.02}, "target_kl"),
    ],
)
def test_load_ppo_model_rejects_optimizer_config_mismatch(
    tmp_path,
    overrides: dict[str, float | int],
    message: str,
) -> None:
    source_env = TrainingSafetyWrapper(
        TwoStepEpisodeEnv(),
        max_episodes=20,
    )
    source_config = TrainingConfig(
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        learning_rate=0.0003,
        ent_coef=0.01,
        device="cpu",
    )
    source = create_ppo_model(source_env, source_config, verbose=0)
    model_path = tmp_path / "model"
    source.save(model_path)
    source_env.close()
    target_env = TrainingSafetyWrapper(
        TwoStepEpisodeEnv(),
        max_episodes=20,
    )

    target_config = {
        "n_steps": 8,
        "batch_size": 4,
        "n_epochs": 1,
        "learning_rate": 0.0003,
        "ent_coef": 0.01,
        "target_kl": 0.01,
        "device": "cpu",
    }
    target_config.update(overrides)

    with pytest.raises(ValueError, match=message):
        load_ppo_model(
            target_env,
            model_path.with_suffix(".zip"),
            TrainingConfig(**target_config),
            verbose=0,
        )
    target_env.close()


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
