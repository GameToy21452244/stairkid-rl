from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

from _common import load_config, run_main

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from stair_agent.rl_training import create_ppo_model


class MockTrainingEnv(gym.Env):
    """完全離線的小型環境，只驗證 PPO 建立、學習、存檔與載入。"""

    def __init__(self, feature_count: int) -> None:
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            -1.0,
            1.0,
            shape=(feature_count,),
            dtype=np.float32,
        )
        self.steps = 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        del options
        self.steps = 0
        return np.zeros(self.observation_space.shape, dtype=np.float32), {}

    def step(self, action):
        self.steps += 1
        observation = np.zeros(
            self.observation_space.shape,
            dtype=np.float32,
        )
        observation[0] = min(1.0, self.steps / 16.0)
        reward = 1.0 if int(action) == self.steps % 3 else 0.0
        terminated = self.steps >= 16
        return observation, reward, terminated, False, {}


def main() -> None:
    from stable_baselines3 import PPO

    config = load_config()
    frame_width = 16 + config.environment.max_observation_platforms * 6
    if config.environment.include_action_history:
        frame_width += 3
    feature_count = (
        config.environment.observation_history_frames * frame_width
    )
    smoke_config = replace(
        config.training,
        n_steps=16,
        batch_size=8,
        n_epochs=1,
        policy_hidden_sizes=[32, 32],
    )
    env = MockTrainingEnv(feature_count)
    try:
        model = create_ppo_model(env, smoke_config, verbose=0)
        model.learn(total_timesteps=64)
        with tempfile.TemporaryDirectory(prefix="stair_ppo_smoke_") as temp:
            path = Path(temp) / "ppo_smoke"
            model.save(path)
            loaded = PPO.load(path, env=env, device="cpu")
            observation, _info = env.reset()
            action, _state = loaded.predict(
                observation,
                deterministic=True,
            )
            if not env.action_space.contains(int(action)):
                raise RuntimeError(f"PPO 預測了無效動作：{action}")
        print(
            f"PPO mock smoke test 通過：features={feature_count}，"
            "timesteps=64，device=cpu；暫存模型已自動清除。"
        )
    finally:
        env.close()


if __name__ == "__main__":
    run_main(main)
