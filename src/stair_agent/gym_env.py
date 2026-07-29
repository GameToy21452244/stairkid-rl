from __future__ import annotations

from collections import deque
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
        max_observation_platforms: int = 8,
    ) -> None:
        if reference_width <= 0 or reference_height <= 0:
            raise ValueError("觀測參考尺寸必須大於 0。")
        if (
            velocity_scale <= 0
            or max_platforms_per_type <= 0
            or max_observation_platforms <= 0
        ):
            raise ValueError("速度尺度與平台數尺度必須大於 0。")
        self.reference_width = float(reference_width)
        self.reference_height = float(reference_height)
        self.velocity_scale = float(velocity_scale)
        self.max_platforms_per_type = float(max_platforms_per_type)
        self.max_observation_platforms = int(max_observation_platforms)
        self.feature_count = 16 + self.max_observation_platforms * 6
        self.space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.feature_count,),
            dtype=np.float32,
        )

    @staticmethod
    def _clip(value: float) -> float:
        return float(np.clip(value, -1.0, 1.0))

    def encode(self, observation: GameObservation) -> np.ndarray:
        player = observation.player
        nearest = observation.nearest_platform
        health = observation.health

        values = np.zeros(self.feature_count, dtype=np.float32)
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

        player_x = (
            float(player.get("center_x", 0.0))
            if player is not None
            else self.reference_width / 2
        )
        player_y = (
            float(player.get("center_y", 0.0))
            if player is not None
            else 0.0
        )

        def platform_order(item: dict[str, Any]) -> tuple[float, float, float]:
            box = item.get("box") or {}
            center_x = float(box.get("left", 0.0)) + float(
                box.get("width", 0.0)
            ) / 2
            delta_y = float(box.get("top", 0.0)) - player_y
            return (
                0.0 if delta_y >= -10.0 else 1.0,
                abs(delta_y),
                abs(center_x - player_x),
            )

        ordered = sorted(observation.platforms, key=platform_order)
        for slot, platform in enumerate(
            ordered[: self.max_observation_platforms]
        ):
            box = platform.get("box") or {}
            center_x = float(box.get("left", 0.0)) + float(
                box.get("width", 0.0)
            ) / 2
            base = 16 + slot * 6
            values[base] = 1.0
            values[base + 1] = self._clip(
                (center_x - player_x) / self.reference_width
            )
            values[base + 2] = self._clip(
                (float(box.get("top", 0.0)) - player_y)
                / self.reference_height
            )
            values[base + 3] = self._clip(
                float(box.get("width", 0.0)) / self.reference_width
            )
            values[base + 4] = self._clip(
                float(box.get("height", 0.0)) / self.reference_height
            )
            values[base + 5] = self.PLATFORM_CODES.get(
                str(platform.get("kind", "")),
                -1.0,
            )
        return values


class TemporalObservationStack:
    """以固定長度堆疊特徵，並選擇性附加造成該觀測的動作。"""

    def __init__(
        self,
        feature_count: int,
        *,
        history_frames: int,
        include_action_history: bool,
    ) -> None:
        if feature_count <= 0 or history_frames <= 0:
            raise ValueError("特徵數與歷史幀數必須大於 0。")
        self.feature_count = int(feature_count)
        self.history_frames = int(history_frames)
        self.include_action_history = bool(include_action_history)
        self.action_feature_count = 3 if include_action_history else 0
        self.frame_width = self.feature_count + self.action_feature_count
        self.feature_shape = (self.history_frames * self.frame_width,)
        self.space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=self.feature_shape,
            dtype=np.float32,
        )
        self._frames: deque[np.ndarray] = deque(
            maxlen=self.history_frames
        )
        self._actions: deque[np.ndarray] = deque(
            maxlen=self.history_frames
        )

    def _action_features(self, action: Action | None) -> np.ndarray:
        values = np.zeros(self.action_feature_count, dtype=np.float32)
        if self.include_action_history and action is not None:
            values[int(action)] = 1.0
        return values

    def _flatten(self) -> np.ndarray:
        chunks = []
        for frame, action in zip(self._frames, self._actions):
            chunks.append(
                np.concatenate((frame, action)).astype(
                    np.float32,
                    copy=False,
                )
            )
        return np.concatenate(chunks).astype(np.float32, copy=False)

    def reset(self, features: np.ndarray) -> np.ndarray:
        frame = np.asarray(features, dtype=np.float32)
        if frame.shape != (self.feature_count,):
            raise ValueError(
                f"單幀特徵尺寸必須是 {(self.feature_count,)}，"
                f"實際為 {frame.shape}。"
            )
        self._frames.clear()
        self._actions.clear()
        for _ in range(self.history_frames):
            self._frames.append(frame.copy())
            self._actions.append(self._action_features(None))
        return self._flatten()

    def append(
        self,
        features: np.ndarray,
        action: Action,
    ) -> np.ndarray:
        if len(self._frames) != self.history_frames:
            raise RuntimeError("時序觀測尚未 reset。")
        frame = np.asarray(features, dtype=np.float32)
        if frame.shape != (self.feature_count,):
            raise ValueError(
                f"單幀特徵尺寸必須是 {(self.feature_count,)}，"
                f"實際為 {frame.shape}。"
            )
        self._frames.append(frame.copy())
        self._actions.append(self._action_features(action))
        return self._flatten()


class RewardCalculator:
    """保守獎勵與可重設的短期控制 shaping。"""

    def __init__(
        self,
        *,
        floor_reward: float = 1.0,
        step_penalty: float = 0.0,
        direction_change_penalty: float = 0.0,
        direction_change_window_steps: int = 0,
        spike_dwell_penalty: float = 0.0,
        spike_dwell_grace_steps: int = 0,
        spike_contact_max_gap: int = 12,
        idle_action_penalty: float = 0.0,
        idle_action_grace_steps: int = 0,
        platform_dwell_penalty: float = 0.0,
        platform_dwell_grace_steps: int = 0,
        platform_dwell_max_gap: int = 80,
        reference_height: int = 431,
        top_danger_penalty: float = 0.0,
        top_danger_grace_steps: int = 0,
        top_danger_y_ratio: float = 0.0,
        damage_penalty_per_segment: float = 0.2,
        death_penalty: float = 5.0,
    ) -> None:
        self.floor_reward = float(floor_reward)
        self.step_penalty = float(step_penalty)
        self.direction_change_penalty = float(direction_change_penalty)
        self.direction_change_window_steps = max(
            0,
            int(direction_change_window_steps),
        )
        self.spike_dwell_penalty = float(spike_dwell_penalty)
        self.spike_dwell_grace_steps = max(
            0,
            int(spike_dwell_grace_steps),
        )
        self.spike_contact_max_gap = max(0, int(spike_contact_max_gap))
        self.idle_action_penalty = float(idle_action_penalty)
        self.idle_action_grace_steps = max(
            0,
            int(idle_action_grace_steps),
        )
        self.platform_dwell_penalty = float(platform_dwell_penalty)
        self.platform_dwell_grace_steps = max(
            0,
            int(platform_dwell_grace_steps),
        )
        self.platform_dwell_max_gap = max(
            0,
            int(platform_dwell_max_gap),
        )
        self.reference_height = max(1.0, float(reference_height))
        self.top_danger_penalty = float(top_danger_penalty)
        self.top_danger_grace_steps = max(
            0,
            int(top_danger_grace_steps),
        )
        self.top_danger_y_ratio = float(
            np.clip(top_danger_y_ratio, 0.0, 1.0)
        )
        self.damage_penalty_per_segment = float(damage_penalty_per_segment)
        self.death_penalty = float(death_penalty)
        self.last_components: dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        self._last_direction: Action | None = None
        self._steps_since_direction = 0
        self._spike_dwell_steps = 0
        self._idle_action_steps = 0
        self._platform_dwell_key: tuple[int, str] | None = None
        self._platform_dwell_steps = 0
        self._top_danger_steps = 0
        self.last_components = {
            "step_penalty": 0.0,
            "floor_reward": 0.0,
            "damage_penalty": 0.0,
            "death_penalty": 0.0,
            "direction_changed": False,
            "direction_change_penalty": 0.0,
            "spike_contact": False,
            "spike_dwell_steps": 0,
            "spike_dwell_penalty": 0.0,
            "idle_action_steps": 0,
            "idle_action_penalty": 0.0,
            "platform_dwell_steps": 0,
            "platform_dwell_penalty": 0.0,
            "top_danger": False,
            "top_danger_steps": 0,
            "top_danger_penalty": 0.0,
        }

    def _update_direction(self, action: Action) -> bool:
        if action not in {Action.LEFT, Action.RIGHT}:
            if self._last_direction is not None:
                self._steps_since_direction += 1
            return False
        changed = (
            self._last_direction is not None
            and action != self._last_direction
            and self._steps_since_direction
            <= self.direction_change_window_steps
        )
        self._last_direction = action
        self._steps_since_direction = 0
        return changed

    def _update_spike_contact(
        self,
        observation: GameObservation,
    ) -> bool:
        nearest = observation.nearest_platform
        gap = None if nearest is None else nearest.get("vertical_gap")
        contact = bool(
            nearest is not None
            and str(nearest.get("kind", "")) == "spikes"
            and gap is not None
            and 0 <= float(gap) <= self.spike_contact_max_gap
        )
        self._spike_dwell_steps = (
            self._spike_dwell_steps + 1 if contact else 0
        )
        return contact

    def _update_platform_dwell(
        self,
        observation: GameObservation,
    ) -> int:
        nearest = observation.nearest_platform
        gap = None if nearest is None else nearest.get("vertical_gap")
        track_id = None if nearest is None else nearest.get("track_id")
        if (
            nearest is None
            or track_id is None
            or gap is None
            or not 0 <= float(gap) <= self.platform_dwell_max_gap
        ):
            self._platform_dwell_key = None
            self._platform_dwell_steps = 0
            return 0
        key = (int(track_id), str(nearest.get("kind", "")))
        if key == self._platform_dwell_key:
            self._platform_dwell_steps += 1
        else:
            self._platform_dwell_key = key
            self._platform_dwell_steps = 1
        return self._platform_dwell_steps

    def _update_top_danger(
        self,
        observation: GameObservation,
    ) -> bool:
        player = observation.player
        in_danger = bool(
            player is not None
            and float(player.get("center_y", self.reference_height))
            / self.reference_height
            <= self.top_danger_y_ratio
        )
        self._top_danger_steps = (
            self._top_danger_steps + 1 if in_danger else 0
        )
        return in_danger

    def calculate(
        self,
        observation: GameObservation,
        *,
        terminated: bool,
        action: Action | None = None,
    ) -> float:
        reward = -self.step_penalty
        components: dict[str, Any] = {
            "step_penalty": -self.step_penalty,
            "floor_reward": 0.0,
            "damage_penalty": 0.0,
            "death_penalty": 0.0,
            "direction_changed": False,
            "direction_change_penalty": 0.0,
            "spike_contact": False,
            "spike_dwell_steps": 0,
            "spike_dwell_penalty": 0.0,
            "idle_action_steps": 0,
            "idle_action_penalty": 0.0,
            "platform_dwell_steps": 0,
            "platform_dwell_penalty": 0.0,
            "top_danger": False,
            "top_danger_steps": 0,
            "top_danger_penalty": 0.0,
        }
        took_damage = False
        for event in observation.events:
            event_type = event.get("type")
            if event_type == "floor_descended":
                reward += self.floor_reward
                components["floor_reward"] += self.floor_reward
            elif event_type in {"damage", "spike_damage"}:
                took_damage = True
                health_delta = min(0, int(event.get("health_delta") or 0))
                damage_penalty = (
                    health_delta * self.damage_penalty_per_segment
                )
                reward += damage_penalty
                components["damage_penalty"] += damage_penalty
        if terminated:
            reward -= self.death_penalty
            components["death_penalty"] = -self.death_penalty
        if action is not None:
            self._idle_action_steps = (
                self._idle_action_steps + 1
                if action is Action.RELEASE_ALL
                else 0
            )
            components["idle_action_steps"] = self._idle_action_steps
            if self._idle_action_steps > self.idle_action_grace_steps:
                reward -= self.idle_action_penalty
                components["idle_action_penalty"] = (
                    -self.idle_action_penalty
                )
            if took_damage:
                # 頂端尖刺可能強制角色向下穿越原平台；掉血時先清除
                # 舊平台停留歷史，避免把遊戲的強制位移算成持續駐留。
                self._platform_dwell_key = None
                self._platform_dwell_steps = 0
            platform_dwell_steps = self._update_platform_dwell(observation)
            components["platform_dwell_steps"] = platform_dwell_steps
            if (
                platform_dwell_steps
                > self.platform_dwell_grace_steps
            ):
                reward -= self.platform_dwell_penalty
                components["platform_dwell_penalty"] = (
                    -self.platform_dwell_penalty
                )
            top_danger = self._update_top_danger(observation)
            components["top_danger"] = top_danger
            components["top_danger_steps"] = self._top_danger_steps
            if (
                top_danger
                and self._top_danger_steps > self.top_danger_grace_steps
            ):
                reward -= self.top_danger_penalty
                components["top_danger_penalty"] = (
                    -self.top_danger_penalty
                )
            direction_changed = self._update_direction(action)
            components["direction_changed"] = direction_changed
            if direction_changed:
                reward -= self.direction_change_penalty
                components["direction_change_penalty"] = (
                    -self.direction_change_penalty
                )
            spike_contact = self._update_spike_contact(observation)
            components["spike_contact"] = spike_contact
            components["spike_dwell_steps"] = self._spike_dwell_steps
            if (
                spike_contact
                and self._spike_dwell_steps
                > self.spike_dwell_grace_steps
            ):
                reward -= self.spike_dwell_penalty
                components["spike_dwell_penalty"] = (
                    -self.spike_dwell_penalty
                )
        self.last_components = components
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
            max_observation_platforms=self.config.max_observation_platforms,
        )
        self.reward_calculator = RewardCalculator(
            floor_reward=self.config.floor_reward,
            step_penalty=self.config.step_penalty,
            direction_change_penalty=(
                self.config.direction_change_penalty
            ),
            direction_change_window_steps=(
                self.config.direction_change_window_steps
            ),
            spike_dwell_penalty=self.config.spike_dwell_penalty,
            spike_dwell_grace_steps=self.config.spike_dwell_grace_steps,
            spike_contact_max_gap=self.config.spike_contact_max_gap,
            idle_action_penalty=self.config.idle_action_penalty,
            idle_action_grace_steps=self.config.idle_action_grace_steps,
            platform_dwell_penalty=self.config.platform_dwell_penalty,
            platform_dwell_grace_steps=(
                self.config.platform_dwell_grace_steps
            ),
            platform_dwell_max_gap=self.config.platform_dwell_max_gap,
            reference_height=reference_height,
            top_danger_penalty=self.config.top_danger_penalty,
            top_danger_grace_steps=self.config.top_danger_grace_steps,
            top_danger_y_ratio=self.config.top_danger_y_ratio,
            damage_penalty_per_segment=self.config.damage_penalty_per_segment,
            death_penalty=self.config.death_penalty,
        )
        self.temporal_stack = TemporalObservationStack(
            self.encoder.feature_count,
            history_frames=self.config.observation_history_frames,
            include_action_history=self.config.include_action_history,
        )
        self.action_space = spaces.Discrete(3)
        self.observation_space = self.temporal_stack.space
        self._step_count = 0
        self.last_observation: GameObservation | None = None

    def _info(
        self,
        observation: GameObservation,
        *,
        reward_components: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        info = {
            "phase": observation.phase,
            "events": [
                str(event.get("type", "unknown"))
                for event in observation.events
            ],
            "history_frames": self.temporal_stack.history_frames,
            "raw_feature_count": self.encoder.feature_count,
            "stacked_feature_count": self.observation_space.shape[0],
        }
        if reward_components is not None:
            info["reward_components"] = dict(reward_components)
        return info

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
        self.reward_calculator.reset()
        try:
            observation = self.adapter.reset()
            self.last_observation = observation
            if observation.phase != GamePhase.PLAYING.value:
                raise GymEnvironmentError(
                    "reset adapter 未能讓遊戲進入 PLAYING；"
                    f"目前為 {observation.phase!r}。"
                )
            features = self.encoder.encode(observation)
            return self.temporal_stack.reset(features), self._info(observation)
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
            self.last_observation = observation
            self._step_count += 1
            terminated = self._is_terminated(observation.phase)
            truncated = (
                observation.phase == GamePhase.UNKNOWN.value
                or self._step_count >= self.config.max_episode_steps
            )
            reward = self.reward_calculator.calculate(
                observation,
                terminated=terminated,
                action=mapped_action,
            )
            if terminated or truncated:
                self.adapter.release_all()
            return (
                self.temporal_stack.append(
                    self.encoder.encode(observation),
                    mapped_action,
                ),
                reward,
                terminated,
                truncated,
                self._info(
                    observation,
                    reward_components=(
                        self.reward_calculator.last_components
                    ),
                ),
            )
        except Exception:
            self.adapter.release_all()
            raise

    def close(self) -> None:
        try:
            self.adapter.release_all()
        finally:
            self.adapter.close()
