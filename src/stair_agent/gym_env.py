from __future__ import annotations

from typing import Any, Protocol

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .config import EnvironmentConfig
from .game_state import GamePhase
from .input_controller import Action
from .observation import GameObservation


class GymEnvironmentError(RuntimeError):
    """Gymnasium 環境無法安全繼續時的明確錯誤。"""


class GameAdapter(Protocol):
    """隔離真實 Windows I/O，讓核心環境可用 mock 完整測試。"""

    def reset(self) -> GameObservation: ...

    def step(self, action: Action) -> GameObservation: ...

    def release_all(self) -> None: ...

    def close(self) -> None: ...


class FeatureEncoder:
    """將結構化辨識結果轉成固定長度、可供 RL 使用的向量。"""

    PLATFORM_KINDS = ("normal", "spikes", "spring", "conveyor", "flipping")
    PLATFORM_CODES = {
        "normal": 0.0,
        "spikes": 0.25,
        "spring": 0.5,
        "conveyor": 0.75,
        "flipping": 1.0,
    }
    MOTION_CODES = {"rising": -1.0, "stable": 0.0, "falling": 1.0}

    def __init__(
        self,
        *,
        reference_width: int = 634,
        reference_height: int = 431,
        velocity_scale: float = 500.0,
        max_platforms_per_type: int = 8,
    ) -> None:
        if reference_width <= 0 or reference_height <= 0:
            raise ValueError("觀測參考尺寸必須大於 0。")
        if velocity_scale <= 0 or max_platforms_per_type <= 0:
            raise ValueError("速度尺度與平台數尺度必須大於 0。")
        self.reference_width = float(reference_width)
        self.reference_height = float(reference_height)
        self.velocity_scale = float(velocity_scale)
        self.max_platforms_per_type = float(max_platforms_per_type)
        self.space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(16,),
            dtype=np.float32,
        )

    @staticmethod
    def _clip(value: float) -> float:
        return float(np.clip(value, -1.0, 1.0))

    def encode(self, observation: GameObservation) -> np.ndarray:
        player = observation.player
        nearest = observation.nearest_platform
        health = observation.health

        values = np.zeros(16, dtype=np.float32)
        if player is not None:
            values[0] = 1.0
            values[1] = self._clip(float(player.get("center_x", 0.0)) / self.reference_width)
            values[2] = self._clip(float(player.get("center_y", 0.0)) / self.reference_height)
            values[3] = self._clip(float(player.get("velocity_x", 0.0)) / self.velocity_scale)
            values[4] = self._clip(float(player.get("velocity_y", 0.0)) / self.velocity_scale)
            values[5] = self.MOTION_CODES.get(str(player.get("motion", "")), 0.0)

        values[6] = self._clip(float(health.get("segments", 0)) / 12.0)
        values[7] = self._clip(
            float(observation.platform_scroll_velocity_y) / self.velocity_scale
        )
        if nearest is not None:
            values[8] = 1.0
            values[9] = self._clip(
                float(nearest.get("vertical_gap") or 0.0) / self.reference_height
            )
            values[10] = self.PLATFORM_CODES.get(
                str(nearest.get("kind", "")),
                -1.0,
            )
        else:
            values[10] = -1.0

        counts = {kind: 0 for kind in self.PLATFORM_KINDS}
        for platform in observation.platforms:
            kind = str(platform.get("kind", ""))
            if kind in counts:
                counts[kind] += 1
        for index, kind in enumerate(self.PLATFORM_KINDS, start=11):
            values[index] = self._clip(
                counts[kind] / self.max_platforms_per_type
            )
        return values


class RewardCalculator:
    """第一版保守獎勵：下樓得分、掉血扣分、死亡額外扣分。"""

    def __init__(
        self,
        *,
        floor_reward: float = 1.0,
        damage_penalty_per_segment: float = 0.2,
        death_penalty: float = 5.0,
    ) -> None:
        self.floor_reward = float(floor_reward)
        self.damage_penalty_per_segment = float(damage_penalty_per_segment)
        self.death_penalty = float(death_penalty)

    def calculate(
        self,
        observation: GameObservation,
        *,
        terminated: bool,
    ) -> float:
        reward = 0.0
        for event in observation.events:
            event_type = event.get("type")
            if event_type == "floor_descended":
                reward += self.floor_reward
            elif event_type in {"damage", "spike_damage"}:
                health_delta = min(0, int(event.get("health_delta") or 0))
                reward += health_delta * self.damage_penalty_per_segment
        if terminated:
            reward -= self.death_penalty
        return float(reward)


class StairAgentEnv(gym.Env[np.ndarray, int]):
    """不包含訓練器的 Gymnasium 介面。真實 I/O 由 adapter 提供。"""

    metadata = {"render_modes": []}

    def __init__(
        self,
        adapter: GameAdapter,
        config: EnvironmentConfig | None = None,
        *,
        reference_width: int = 634,
        reference_height: int = 431,
    ) -> None:
        super().__init__()
        self.adapter = adapter
        self.config = config or EnvironmentConfig()
        self.encoder = FeatureEncoder(
            reference_width=reference_width,
            reference_height=reference_height,
            velocity_scale=self.config.velocity_scale,
            max_platforms_per_type=self.config.max_platforms_per_type,
        )
        self.reward_calculator = RewardCalculator(
            floor_reward=self.config.floor_reward,
            damage_penalty_per_segment=self.config.damage_penalty_per_segment,
            death_penalty=self.config.death_penalty,
        )
        self.action_space = spaces.Discrete(3)
        self.observation_space = self.encoder.space
        self._step_count = 0

    @staticmethod
    def _info(observation: GameObservation) -> dict[str, Any]:
        return {
            "phase": observation.phase,
            "events": [
                str(event.get("type", "unknown"))
                for event in observation.events
            ],
        }

    @staticmethod
    def _is_terminated(phase: str) -> bool:
        return phase in {
            GamePhase.MENU.value,
            GamePhase.DIALOG.value,
            GamePhase.NAME_ENTRY.value,
            GamePhase.GAME_OVER.value,
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        del options
        self._step_count = 0
        try:
            observation = self.adapter.reset()
            if observation.phase != GamePhase.PLAYING.value:
                raise GymEnvironmentError(
                    "reset 前必須由使用者手動讓遊戲進入 PLAYING；"
                    f"目前為 {observation.phase!r}。環境不會自動按 Enter。"
                )
            return self.encoder.encode(observation), self._info(observation)
        except Exception:
            self.adapter.release_all()
            raise

    def step(
        self,
        action: int,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if not self.action_space.contains(action):
            raise GymEnvironmentError(f"無效動作：{action!r}，只允許 0、1、2。")
        mapped_action = Action(int(action))
        try:
            observation = self.adapter.step(mapped_action)
            self._step_count += 1
            terminated = self._is_terminated(observation.phase)
            truncated = (
                observation.phase == GamePhase.UNKNOWN.value
                or self._step_count >= self.config.max_episode_steps
            )
            reward = self.reward_calculator.calculate(
                observation,
                terminated=terminated,
            )
            if terminated or truncated:
                self.adapter.release_all()
            return (
                self.encoder.encode(observation),
                reward,
                terminated,
                truncated,
                self._info(observation),
            )
        except Exception:
            self.adapter.release_all()
            raise

    def close(self) -> None:
        try:
            self.adapter.release_all()
        finally:
            self.adapter.close()
