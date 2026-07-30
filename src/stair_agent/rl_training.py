from __future__ import annotations

import time
from math import isclose
from pathlib import Path
from typing import Any

import gymnasium as gym

from .config import TrainingConfig


class TrainingSafetyWrapper(gym.Wrapper):
    """在最後核准回合阻止 VecEnv 自動 reset，避免多送一次 Enter。"""

    def __init__(self, env: gym.Env, *, max_episodes: int) -> None:
        if max_episodes <= 0:
            raise ValueError("max_episodes 必須大於 0。")
        super().__init__(env)
        self.max_episodes = int(max_episodes)
        self.completed_episodes = 0
        self.action_counts = {
            "RELEASE_ALL": 0,
            "LEFT": 0,
            "RIGHT": 0,
        }
        self.longest_same_action_streak = 0
        self.reward_component_totals: dict[str, float] = {}
        self._previous_action: int | None = None
        self._current_action_streak = 0

    def step(self, action):
        action_value = int(action)
        action_name = {
            0: "RELEASE_ALL",
            1: "LEFT",
            2: "RIGHT",
        }.get(action_value, f"UNKNOWN_{action_value}")
        self.action_counts[action_name] = (
            self.action_counts.get(action_name, 0) + 1
        )
        if action_value == self._previous_action:
            self._current_action_streak += 1
        else:
            self._previous_action = action_value
            self._current_action_streak = 1
        self.longest_same_action_streak = max(
            self.longest_same_action_streak,
            self._current_action_streak,
        )
        observation, reward, terminated, truncated, info = self.env.step(
            action
        )
        for name, value in (
            info.get("reward_components") or {}
        ).items():
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and (
                    name.endswith("_reward")
                    or name.endswith("_penalty")
                )
            ):
                self.reward_component_totals[name] = (
                    self.reward_component_totals.get(name, 0.0)
                    + float(value)
                )
        info = dict(info)
        if terminated or truncated:
            self.completed_episodes += 1
            info["completed_episodes"] = self.completed_episodes
            if self.completed_episodes >= self.max_episodes:
                # DummyVecEnv 會在 done=True 時立刻 reset，早於 callback。
                # 最後一回合改以 info 通知 callback，讓它在下一動作前停止。
                info["training_budget_exhausted"] = True
                terminated = False
                truncated = False
        return observation, reward, terminated, truncated, info


class SafetyStopCallback:
    """延遲匯入 SB3 callback，讓非 RL 工具不必安裝 PyTorch。"""

    def __new__(
        cls,
        *,
        max_seconds: float,
        verbose: int = 0,
    ):
        from stable_baselines3.common.callbacks import BaseCallback

        if max_seconds <= 0:
            raise ValueError("max_seconds 必須大於 0。")

        class _Callback(BaseCallback):
            def __init__(self) -> None:
                super().__init__(verbose=verbose)
                self.started_at = 0.0
                self.stop_reason: str | None = None

            def _on_training_start(self) -> None:
                self.started_at = time.monotonic()

            def _on_step(self) -> bool:
                infos = self.locals.get("infos") or []
                if any(
                    bool(info.get("training_budget_exhausted"))
                    for info in infos
                ):
                    self.stop_reason = "episode_limit"
                    return False
                if time.monotonic() - self.started_at >= max_seconds:
                    self.stop_reason = "time_limit"
                    return False
                return True

        return _Callback()


def validate_training_budget(config: TrainingConfig) -> None:
    """避免 PPO 為完成 rollout 而超過核准的實機送鍵步數。"""
    if config.total_timesteps < config.n_steps:
        raise ValueError(
            "training.total_timesteps 不可小於 training.n_steps，"
            "否則 PPO 仍會多收集一個完整 rollout。"
        )
    if config.total_timesteps % config.n_steps != 0:
        raise ValueError(
            "training.total_timesteps 必須可被 training.n_steps 整除，"
            "避免實際送鍵步數超過設定上限。"
        )


def create_ppo_model(
    env: gym.Env,
    config: TrainingConfig,
    *,
    verbose: int = 1,
):
    from stable_baselines3 import PPO

    validate_training_budget(config)
    return PPO(
        "MlpPolicy",
        env,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        n_epochs=config.n_epochs,
        gamma=config.gamma,
        gae_lambda=config.gae_lambda,
        ent_coef=config.ent_coef,
        target_kl=config.target_kl,
        policy_kwargs={
            "net_arch": list(config.policy_hidden_sizes),
        },
        seed=config.seed,
        device=config.device,
        verbose=verbose,
    )


def load_ppo_model(
    env: gym.Env,
    model_path: str | Path,
    config: TrainingConfig,
    *,
    verbose: int = 1,
):
    """載入既有 PPO，並拒絕與目前訓練設定不相容的 checkpoint。"""
    from stable_baselines3 import PPO

    validate_training_budget(config)
    model = PPO.load(
        model_path,
        env=env,
        device=config.device,
        verbose=verbose,
    )
    if int(model.n_steps) != int(config.n_steps):
        raise ValueError(
            "續訓模型的 n_steps 與目前 training.n_steps 不一致；"
            "拒絕以不同 rollout 大小繼續。"
        )
    if int(model.batch_size) != int(config.batch_size):
        raise ValueError(
            "續訓模型的 batch_size 與目前 training.batch_size 不一致。"
        )
    if int(model.n_epochs) != int(config.n_epochs):
        raise ValueError(
            "續訓模型的 n_epochs 與目前 training.n_epochs 不一致；"
            "請以新設定重新建立模型。"
        )

    model_learning_rate = model.learning_rate
    if callable(model_learning_rate):
        model_learning_rate = model.lr_schedule(1.0)
    if not isclose(
        float(model_learning_rate),
        float(config.learning_rate),
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "續訓模型的 learning_rate 與目前 training.learning_rate "
            "不一致；請以新設定重新建立模型。"
        )
    if not isclose(
        float(model.ent_coef),
        float(config.ent_coef),
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "續訓模型的 ent_coef 與目前 training.ent_coef 不一致；"
            "請以新設定重新建立模型。"
        )
    if not isclose(
        float(model.target_kl),
        float(config.target_kl),
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "續訓模型的 target_kl 與目前 training.target_kl 不一致；"
            "請以新設定重新建立模型。"
        )
    return model


def resolve_model_directory(
    project_root: str | Path,
    configured_path: str,
) -> Path:
    root = Path(project_root).resolve()
    raw = Path(configured_path)
    if raw.is_absolute():
        raise ValueError("training.model_dir 必須是專案內的相對路徑。")
    target = (root / raw).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("training.model_dir 不可離開專案目錄。") from exc
    if not relative.parts or relative.parts[0].casefold() != "models":
        raise ValueError("training.model_dir 必須位於 models/ 之下。")
    return target
