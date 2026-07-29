from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import AppConfig, DetectionConfig
from .dialog_handler import DialogActionHandler, DialogFocusGuard
from .episode_reset import SingleEnterEpisodeResetter
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
        episode_resetter: SingleEnterEpisodeResetter | Any | None = None,
        action_phase_probe: Callable[[], GamePhase] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.controller = controller
        self.observe = observe
        self.reset_pipeline = reset_pipeline
        self.action_duration_ms = action_duration_ms
        self.capture = capture
        self.monitor = monitor
        self.episode_resetter = episode_resetter
        self.action_phase_probe = action_phase_probe
        self.sleeper = sleeper
        self._closed = False

    def reset(self) -> GameObservation:
        self.controller.release_all()
        if self.episode_resetter is not None:
            return self.episode_resetter.reset()
        self.reset_pipeline()
        return self.observe()

    def step(self, action: Action) -> GameObservation:
        try:
            if (
                self.action_phase_probe is not None
                and self.action_phase_probe() is not GamePhase.PLAYING
            ):
                self.controller.release_all()
                return self.observe()
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
        return bool(self.controller.is_target_active())

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


def build_dialog_focus_guard(
    config: DetectionConfig,
) -> DialogFocusGuard:
    focus_values = (
        config.reference_width,
        config.reference_height,
        config.menu_start_button_left,
        config.menu_start_button_top,
        config.menu_start_button_width,
        config.menu_start_button_height,
        config.menu_two_player_button_left,
        config.menu_two_player_button_top,
        config.menu_two_player_button_width,
        config.menu_two_player_button_height,
    )
    if any(value is None for value in focus_values):
        raise RuntimeError(
            "自動重設需要校正 detection.menu_start_button_* 與 "
            "menu_two_player_button_*，否則無法避免誤選雙人模式。"
        )
    (
        reference_width,
        reference_height,
        start_left,
        start_top,
        start_width,
        start_height,
        two_left,
        two_top,
        two_width,
        two_height,
    ) = (int(value) for value in focus_values)
    return DialogFocusGuard(
        reference_width=reference_width,
        reference_height=reference_height,
        start_button_rect=(
            start_left,
            start_top,
            start_width,
            start_height,
        ),
        two_player_button_rect=(
            two_left,
            two_top,
            two_width,
            two_height,
        ),
        focused_border_mean_max=config.menu_focus_border_mean_max,
        minimum_contrast=config.menu_focus_minimum_contrast,
        focused_inner_gray_max=config.menu_focus_inner_gray_max,
        focused_inner_dark_ratio_min=(
            config.menu_focus_inner_dark_ratio_min
        ),
    )


def create_live_environment(
    config: AppConfig,
    project_root: str | Path,
    *,
    allow_single_enter_reset: bool | None = None,
) -> tuple[StairAgentEnv, WindowInfo]:
    """建立真實環境，但不啟動遊戲、不聚焦視窗，也不送出任何按鍵。"""

    root = Path(project_root)
    reset_enabled = (
        config.environment.auto_restart_on_reset
        if allow_single_enter_reset is None
        else allow_single_enter_reset
    )
    focus_guard = (
        build_dialog_focus_guard(config.detection)
        if reset_enabled
        else None
    )
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
    episode_resetter = None
    if reset_enabled:
        assert focus_guard is not None
        handler = DialogActionHandler(
            pipeline.state_detector,
            controller,
            config.controls.restart_key,
            capture.capture,
            key_duration_ms=config.controls.restart_duration_ms,
            required_consecutive=(
                config.environment.reset_required_consecutive_frames
            ),
            max_observation_frames=(
                config.environment.reset_max_observation_frames
            ),
            observation_delay_seconds=1.0 / config.capture.target_fps,
            post_action_delay_seconds=(
                config.environment.reset_post_action_delay_seconds
            ),
            focus_guard=focus_guard,
            focus_correction_key=(
                config.controls.menu_focus_correction_key
            ),
            focus_correction_duration_ms=(
                config.controls.action_duration_ms
            ),
            focus_max_observation_frames=(
                config.environment.reset_focus_max_observation_frames
            ),
            focus_correction_max_observation_frames=(
                config.environment
                .reset_focus_correction_max_observation_frames
            ),
        )
        episode_resetter = SingleEnterEpisodeResetter(
            handler=handler,
            controller=controller,
            observe=pipeline.observe,
            reset_pipeline=pipeline.reset,
        )
    adapter = LiveGameAdapter(
        controller=controller,
        observe=pipeline.observe,
        reset_pipeline=pipeline.reset,
        action_duration_ms=config.controls.action_duration_ms,
        capture=capture,
        monitor=monitor,
        episode_resetter=episode_resetter,
        action_phase_probe=lambda: pipeline.state_detector.detect(
            capture.capture()
        ),
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
    vision_reference_width = (
        config.vision.reference_width or reference_width
    )
    playfield_scale_x = reference_width / vision_reference_width
    playfield_left = (
        float(config.vision.playfield_left or 0) * playfield_scale_x
    )
    playfield_width = float(
        config.vision.playfield_width or vision_reference_width
    ) * playfield_scale_x
    env = StairAgentEnv(
        adapter,
        config.environment,
        reference_width=reference_width,
        reference_height=reference_height,
        playfield_left=playfield_left,
        playfield_right=playfield_left + playfield_width,
    )
    return env, target
