from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from ..core.contracts import OBSERVATION_SCHEMA_VERSION
from ..game_state import GamePhase
from ..gym_env import FeatureEncoder, TemporalObservationStack
from ..input_controller import Action
from ..observation import GameObservation
from ..simulator.physics import ShaftSimulator
from ..simulator.renderer import SimulatorRenderer
from ..simulator.state import ShaftEnvConfig, SupportDepartureRecord
from .reward import SimulatorRewardCalculator


class ShaftEnv(gym.Env[np.ndarray, int]):
    """Gymnasium/Pymunk simulator v0.2 with no dependency on the real game."""

    metadata = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 30,
    }

    def __init__(
        self,
        *,
        config: ShaftEnvConfig | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        if render_mode not in {None, "human", "rgb_array"}:
            raise ValueError(f"不支援 render_mode={render_mode!r}。")
        self.config = config or ShaftEnvConfig()
        self.render_mode = render_mode
        self.action_space = spaces.Discrete(3)
        self.encoder = FeatureEncoder(
            reference_width=self.config.width,
            reference_height=self.config.height,
        )
        self.temporal_stack = TemporalObservationStack(
            self.encoder.feature_count,
            history_frames=self.config.observation_history_frames,
            include_action_history=self.config.include_action_history,
        )
        self.observation_space = self.temporal_stack.space
        self.reward_calculator = SimulatorRewardCalculator(self.config)
        self.renderer = SimulatorRenderer()
        self.simulator: ShaftSimulator | None = None
        self.last_observation: GameObservation | None = None
        self._step_count = 0
        self._diagnostics: dict[str, object] = {}

    def _game_observation(
        self,
        *,
        events: tuple[str, ...] = (),
        terminated: bool = False,
    ) -> GameObservation:
        if self.simulator is None:
            raise RuntimeError("環境尚未 reset。")
        simulator = self.simulator
        player = simulator.player
        body = player.body
        screen_x = float(body.position.x)
        screen_y = float(self.config.height - body.position.y)
        player_screen_bottom = screen_y + player.height / 2
        velocity_x = float(body.velocity.x)
        velocity_y = float(-body.velocity.y)
        if velocity_y < -5:
            motion = "rising"
        elif velocity_y > 5:
            motion = "falling"
        else:
            motion = "stable"

        platforms = []
        nearest = None
        nearest_gap = float("inf")
        for platform in simulator.platforms:
            top = float(self.config.height - platform.top)
            item = {
                "track_id": platform.floor_index,
                "kind": platform.kind,
                "active": simulator.platform_is_active(platform),
                "confidence": 1.0,
                "box": {
                    "left": platform.left,
                    "top": top,
                    "width": platform.width,
                    "height": platform.height,
                },
            }
            if -platform.height <= top <= self.config.height + platform.height:
                platforms.append(item)
            gap = top - player_screen_bottom
            horizontal_overlap = (
                screen_x + player.width / 2 > platform.left
                and screen_x - player.width / 2 < platform.right
            )
            if horizontal_overlap and gap >= -2 and gap < nearest_gap:
                nearest_gap = gap
                nearest = {**item, "vertical_gap": gap}

        health_delta = simulator.last_health_delta
        if health_delta > 0:
            health_event = "increased"
        elif health_delta < 0:
            health_event = "decreased"
        else:
            health_event = "unchanged"
        return GameObservation(
            timestamp=self._step_count * self.config.dt,
            phase=(
                GamePhase.GAME_OVER.value
                if terminated
                else GamePhase.PLAYING.value
            ),
            player={
                "center_x": screen_x,
                "center_y": screen_y,
                "velocity_x": velocity_x,
                "velocity_y": velocity_y,
                "motion": motion,
                "confidence": 1.0,
            },
            health={
                "segments": simulator.health_segments,
                "delta": health_delta,
                "event": health_event,
            },
            nearest_platform=nearest,
            platforms=platforms,
            platform_scroll_velocity_y=-self.config.scroll_speed,
            events=[
                {
                    "type": event,
                    "health_delta": (
                        health_delta
                        if event in {"health_gained", "damage"}
                        else None
                    ),
                }
                for event in events
            ],
        )

    def _info(
        self,
        *,
        events: tuple[str, ...] = (),
        support_departures: tuple[SupportDepartureRecord, ...] = (),
        terminal_reason: str | None = None,
        reward_components: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        if self.simulator is None:
            raise RuntimeError("環境尚未 reset。")
        return {
            "events": list(events),
            "support_departures": [
                {
                    "source_floor": int(record.source_floor),
                    "clearance": float(record.clearance),
                }
                for record in support_departures
            ],
            "terminal_reason": terminal_reason,
            "reward_components": dict(reward_components or {}),
            "raw_feature_count": self.encoder.feature_count,
            "stacked_feature_count": self.observation_space.shape[0],
            "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
            "environment_version": self.config.effective_environment_version,
            "control_frequency_hz": self.config.fps,
            "physics_frequency_hz": self.config.physics_hz,
            "health_enabled": self.config.enable_health,
            "health_segments": self.simulator.health_segments,
            "health_delta": self.simulator.last_health_delta,
            "spikes_enabled": self.config.enable_spikes,
            "conveyor_enabled": self.config.enable_conveyor,
            "conveyor_velocity_delta_x": (
                self.simulator.last_conveyor_velocity_delta_x
            ),
            "spring_enabled": self.config.enable_spring,
            "spring_velocity_delta_y": (
                self.simulator.last_spring_velocity_delta_y
            ),
            "support_ownership_enabled": (
                self.config.enable_support_ownership
            ),
            "supported_platform_floor": self.simulator.supported_floor,
            "support_active": self.simulator.supported_platform is not None,
            "flipping_enabled": self.config.enable_flipping,
            "collision_diagnostic": self.simulator.last_collision_diagnostic,
            "failure_reason": self._failure_reason(terminal_reason),
            "platforms": [
                {
                    "floor_index": platform.floor_index,
                    "center_x": platform.center_x,
                    "center_y": platform.center_y,
                    "kind": platform.kind,
                    "active": self.simulator.platform_is_active(platform),
                }
                for platform in self.simulator.platforms
            ],
        }

    @staticmethod
    def _failure_reason(terminal_reason: str | None) -> str | None:
        return {
            None: None,
            "bottom": "bottom_death",
            "top": "top_death",
            "time_limit": "timeout",
            "health_depleted": "health_depleted",
        }.get(terminal_reason, "unknown")

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        del options
        self._step_count = 0
        self.simulator = ShaftSimulator(self.config, self.np_random)
        self._diagnostics = {}
        self.last_observation = self._game_observation()
        features = self.encoder.encode(self.last_observation)
        return self.temporal_stack.reset(features), self._info()

    def step(
        self,
        action: int,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if not self.action_space.contains(action):
            raise ValueError(f"無效動作：{action!r}，只允許 0、1、2。")
        if self.simulator is None:
            raise RuntimeError("step 前必須先 reset。")
        mapped_action = Action(int(action))
        result = self.simulator.step(mapped_action)
        self._step_count += 1
        truncated = (
            not result.terminated
            and self._step_count >= self.config.max_episode_steps
        )
        terminal_reason = (
            result.terminal_reason
            if result.terminated
            else ("time_limit" if truncated else None)
        )
        reward = self.reward_calculator.calculate(result)
        self.last_observation = self._game_observation(
            events=result.events,
            terminated=result.terminated,
        )
        observation = self.temporal_stack.append(
            self.encoder.encode(self.last_observation),
            mapped_action,
        )
        body = self.simulator.player.body
        self._diagnostics = {
            "action": mapped_action.name,
            "action_values": None,
            "target": self.simulator.deepest_floor + 1,
            "floor": self.simulator.deepest_floor,
            "reward": round(reward, 4),
            "reward_components": self.reward_calculator.last_components,
            "x_y": (
                round(float(body.position.x), 2),
                round(float(body.position.y), 2),
            ),
            "vx_vy": (
                round(float(body.velocity.x), 2),
                round(float(body.velocity.y), 2),
            ),
            "control_hz": self.config.fps,
            "terminal_reason": terminal_reason,
            "support_floor": self.simulator.supported_floor,
        }
        if self.render_mode == "human":
            self.render()
        return (
            observation,
            reward,
            result.terminated,
            truncated,
            self._info(
                events=result.events,
                support_departures=result.support_departures,
                terminal_reason=terminal_reason,
                reward_components=self.reward_calculator.last_components,
            ),
        )

    def render(self) -> np.ndarray | None:
        if self.simulator is None:
            return None
        if self.render_mode is None:
            return None
        if self.render_mode == "human":
            self.renderer.human(self.simulator, self._diagnostics)
            return None
        return self.renderer.rgb_array(self.simulator, self._diagnostics)

    def close(self) -> None:
        self.renderer.close()
        self.simulator = None


__all__ = ["ShaftEnv", "ShaftEnvConfig"]
