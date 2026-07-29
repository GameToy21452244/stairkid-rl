from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import AppConfig
from .game_events import GameplayEventDetector
from .game_state import GamePhase, GameStateDetector
from .gym_env import StairAgentEnv
from .hud_detection import HealthTracker, HudDetector
from .input_controller import Action, InputController, SafetyMonitor
from .object_detection import ObjectDetector, PlatformKind
from .object_tracking import (
    PlatformStabilizer,
    PlatformTracker,
    PlatformTrackingState,
    PlayerTracker,
)
from .observation import GameObservation, ObservationBuilder
from .screen_capture import ScreenCapture
from .window_manager import WindowInfo, WindowManager


class LiveObservationPipeline:
    """把單幀畫面轉為結構化觀測；不負責任何鍵盤輸入。"""

    def __init__(
        self,
        *,
        capture: ScreenCapture,
        state_detector: GameStateDetector,
        object_detector: ObjectDetector,
        hud_detector: HudDetector,
        landing_contact_gap: int,
        spring_contact_gap: int,
        correlation_frames: int,
    ) -> None:
        self.capture = capture
        self.state_detector = state_detector
        self.object_detector = object_detector
        self.hud_detector = hud_detector
        self.player_tracker = PlayerTracker()
        self.platform_tracker = PlatformTracker()
        self.platform_stabilizer = PlatformStabilizer(
            persistent_kinds={
                PlatformKind.CONVEYOR,
                PlatformKind.FLIPPING,
                PlatformKind.SPRING,
            },
            persistence_frames=2,
        )
        self.health_tracker = HealthTracker()
        self.event_detector = GameplayEventDetector(
            landing_contact_gap=landing_contact_gap,
            spring_contact_gap=spring_contact_gap,
            correlation_frames=correlation_frames,
        )
        self.builder = ObservationBuilder()

    def reset(self) -> None:
        self.player_tracker.reset()
        self.platform_tracker.reset()
        self.platform_stabilizer.reset()
        self.health_tracker.reset()
        self.event_detector.reset()

    @staticmethod
    def _empty(timestamp: float, phase: GamePhase) -> GameObservation:
        return GameObservation(
            timestamp=timestamp,
            phase=phase.value,
            player=None,
            health={"segments": 0, "delta": None, "event": "unknown"},
            nearest_platform=None,
            platforms=[],
            platform_scroll_velocity_y=0.0,
            events=[],
        )

    def observe(self) -> GameObservation:
        frame = self.capture.capture()
        phase = self.state_detector.detect(frame)
        now = time.monotonic()
        if phase is not GamePhase.PLAYING:
            self.reset()
            return self._empty(now, phase)

        raw_objects = self.object_detector.detect(frame)
        platform_state = self.platform_tracker.update(raw_objects, now)
        objects = self.platform_stabilizer.update(platform_state.objects)
        platform_state = PlatformTrackingState(
            objects,
            platform_state.scroll_velocity_y,
            platform_state.matched_platforms,
        )
        player_state = self.player_tracker.update(objects, now)
        health = self.hud_detector.detect_health(frame)
        health_update = self.health_tracker.update(health.segments)
        events = self.event_detector.update(player_state, health_update)
        return self.builder.build(
            timestamp=now,
            phase=phase,
            player_state=player_state,
            platform_state=platform_state,
            health=health_update,
            events=events,
        )


class LiveGameAdapter:
    """每一步只送一個有時間上限的動作，且一定在擷取前放開按鍵。"""

    def __init__(
        self,
        *,
        controller: InputController | Any,
        observe: Callable[[], GameObservation],
        reset_pipeline: Callable[[], None],
        action_duration_ms: int,
        capture: ScreenCapture | Any | None = None,
        monitor: SafetyMonitor | Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.controller = controller
        self.observe = observe
        self.reset_pipeline = reset_pipeline
        self.action_duration_ms = action_duration_ms
        self.capture = capture
        self.monitor = monitor
        self.sleeper = sleeper
        self._closed = False

    def reset(self) -> GameObservation:
        self.controller.release_all()
        self.reset_pipeline()
        return self.observe()

    def step(self, action: Action) -> GameObservation:
        try:
            self.controller.apply(action)
            self.sleeper(self.action_duration_ms / 1000.0)
        finally:
            self.controller.release_all()
        return self.observe()

    def release_all(self) -> None:
        self.controller.release_all()

    @property
    def emergency_stopped(self) -> bool:
        return bool(self.controller.emergency_stopped)

    def is_foreground(self) -> bool:
        return bool(
            self.controller.window_manager.is_foreground(
                self.controller.hwnd
            )
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.controller.release_all()
        finally:
            if self.monitor is not None:
                self.monitor.stop()
            if self.capture is not None:
                self.capture.close()


def create_live_environment(
    config: AppConfig,
    project_root: str | Path,
) -> tuple[StairAgentEnv, WindowInfo]:
    """建立真實環境，但不啟動遊戲、不聚焦視窗，也不送出任何按鍵。"""

    root = Path(project_root)
    manager = WindowManager()
    target = manager.require_ready(
        config.game.window_title_contains,
        config.game.window_class_name,
    )
    capture = ScreenCapture(config.capture, manager, target.hwnd)
    pipeline = LiveObservationPipeline(
        capture=capture,
        state_detector=GameStateDetector.from_config(config.detection, root),
        object_detector=ObjectDetector.from_config(config.vision, root),
        hud_detector=HudDetector(config.hud),
        landing_contact_gap=config.events.landing_contact_gap,
        spring_contact_gap=config.events.spring_contact_gap,
        correlation_frames=config.events.correlation_frames,
    )
    controller = InputController(
        config.controls,
        config.safety,
        manager,
        target.hwnd,
    )
    monitor = SafetyMonitor(
        controller,
        config.safety.emergency_stop_key,
    )
    monitor.start()
    adapter = LiveGameAdapter(
        controller=controller,
        observe=pipeline.observe,
        reset_pipeline=pipeline.reset,
        action_duration_ms=config.controls.action_duration_ms,
        capture=capture,
        monitor=monitor,
    )

    reference_width = (
        config.capture.resize_width
        if config.capture.resize_width and config.capture.resize_height
        else config.capture.width
        or target.client_rect.width - (config.capture.left or 0)
    )
    reference_height = (
        config.capture.resize_height
        if config.capture.resize_width and config.capture.resize_height
        else config.capture.height
        or target.client_rect.height - (config.capture.top or 0)
    )
    env = StairAgentEnv(
        adapter,
        config.environment,
        reference_width=reference_width,
        reference_height=reference_height,
    )
    return env, target
