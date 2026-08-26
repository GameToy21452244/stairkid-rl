from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import AppConfig, DetectionConfig
from .data.writer import ActionTiming
from .dialog_handler import DialogActionHandler, DialogFocusGuard, DialogFocusLocation
from .episode_reset import SingleEnterEpisodeResetter
from .game_state import GamePhase, GameStateDetector
from .gym_env import StairAgentEnv
from .hud_detection import HudDetector
from .input_controller import Action, InputController, SafetyMonitor
from .object_detection import ObjectDetector
from .observation import GameObservation
from .real_observation_pipeline import RealFrameObservationPipeline
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
        self.frame_pipeline = RealFrameObservationPipeline(
            object_detector=object_detector,
            hud_detector=hud_detector,
            landing_contact_gap=landing_contact_gap,
            spring_contact_gap=spring_contact_gap,
            correlation_frames=correlation_frames,
        )
        # Preserve the established diagnostic attributes for callers/tests.
        self.player_tracker = self.frame_pipeline.player_tracker
        self.platform_tracker = self.frame_pipeline.platform_tracker
        self.platform_stabilizer = self.frame_pipeline.platform_stabilizer
        self.health_tracker = self.frame_pipeline.health_tracker
        self.floor_tracker = self.frame_pipeline.floor_tracker
        self.event_detector = self.frame_pipeline.event_detector
        self.builder = self.frame_pipeline.builder
        self.last_frame: Any | None = None
        self.last_phase = GamePhase.UNKNOWN

    def reset(self) -> None:
        self.frame_pipeline.reset()

    @staticmethod
    def _empty(timestamp: float, phase: GamePhase) -> GameObservation:
        return RealFrameObservationPipeline.empty_observation(timestamp, phase)

    def observe(self) -> GameObservation:
        frame = self.capture.capture()
        self.last_frame = frame.copy()
        phase = self.state_detector.detect(frame)
        self.last_phase = phase
        now = time.monotonic()
        return self.frame_pipeline.observe_frame(
            frame,
            timestamp=now,
            phase=phase,
        )


class LiveGameAdapter:
    """跨 observation 保持同方向，並以短 lease 防止控制迴圈卡鍵。"""

    def __init__(
        self,
        *,
        controller: InputController | Any,
        observe: Callable[[], GameObservation],
        reset_pipeline: Callable[[], None],
        action_duration_ms: int,
        max_continuous_hold_ms: int = 500,
        capture: ScreenCapture | Any | None = None,
        monitor: SafetyMonitor | Any | None = None,
        episode_resetter: SingleEnterEpisodeResetter | Any | None = None,
        latest_phase: Callable[[], GamePhase] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        frame_provider: Callable[[], Any | None] | None = None,
    ) -> None:
        self.controller = controller
        self.observe = observe
        self.reset_pipeline = reset_pipeline
        self.action_duration_ms = action_duration_ms
        if max_continuous_hold_ms < action_duration_ms:
            raise ValueError(
                "max_continuous_hold_ms 不可小於 action_duration_ms。"
            )
        self.max_continuous_hold_ms = max_continuous_hold_ms
        self.capture = capture
        self.monitor = monitor
        self.episode_resetter = episode_resetter
        # This provider must be cache-only.  A fresh capture here would put
        # capture/phase-detection latency between observation_t and action_t.
        self.latest_phase = latest_phase
        self.sleeper = sleeper
        self.frame_provider = frame_provider
        self._closed = False
        self._hold_lock = threading.RLock()
        self._hold_generation = 0
        self._hold_timer: threading.Timer | None = None
        self._held_action: Action | None = None
        self.last_action_timing: ActionTiming | None = None

    def _cancel_hold_watchdog(self) -> None:
        with self._hold_lock:
            self._hold_generation += 1
            timer = self._hold_timer
            self._hold_timer = None
        if timer is not None:
            timer.cancel()

    def _arm_hold_watchdog(self, action: Action) -> None:
        self._cancel_hold_watchdog()
        with self._hold_lock:
            self._held_action = action
            generation = self._hold_generation
            timer = threading.Timer(
                self.max_continuous_hold_ms / 1000.0,
                self._expire_hold,
                args=(generation,),
            )
            timer.daemon = True
            self._hold_timer = timer
        timer.start()

    def _expire_hold(self, generation: int) -> None:
        with self._hold_lock:
            if (
                generation != self._hold_generation
                or self._held_action is None
            ):
                return
            self._hold_generation += 1
            self._hold_timer = None
            self._held_action = None
        self.controller.release_all()

    def _is_held(self, action: Action) -> bool:
        with self._hold_lock:
            return self._held_action is action

    def reset(self) -> GameObservation:
        self.release_all()
        if self.episode_resetter is not None:
            return self.episode_resetter.reset()
        self.reset_pipeline()
        return self.observe()

    def step(self, action: Action) -> GameObservation:
        self.last_action_timing = None
        try:
            if (
                self.latest_phase is not None
                and self.latest_phase() is not GamePhase.PLAYING
            ):
                self.release_all()
                observation = self.observe()
                now = time.monotonic()
                self.last_action_timing = ActionTiming(
                    now,
                    now,
                    float(getattr(observation, "timestamp", now)),
                    False,
                    0.0,
                    False,
                )
                return observation
            command_timestamp = time.monotonic()
            if action is Action.RELEASE_ALL:
                self._cancel_hold_watchdog()
                with self._hold_lock:
                    self._held_action = None
                self.controller.apply(action)
            else:
                # 先撤銷上一個 lease，再由 InputController 的 idempotent key_down
                # 保持同向按鍵或安全地釋放反向鍵。
                self._cancel_hold_watchdog()
                self.controller.apply(action)
                self._arm_hold_watchdog(action)
            effective_timestamp = time.monotonic()
            self.sleeper(self.action_duration_ms / 1000.0)
            observation = self.observe()
        except BaseException:
            # 包含 Ctrl+C；任何 action、sleep 或 capture 例外都立即清鍵。
            self.release_all()
            raise
        next_timestamp = float(
            getattr(observation, "timestamp", time.monotonic())
        )
        phase = getattr(observation, "phase", None)
        if phase is not None and phase != GamePhase.PLAYING.value:
            self.release_all()
        held_action = (
            action is not Action.RELEASE_ALL and self._is_held(action)
        )
        action_duration_ms = (
            max(0.0, 1000.0 * (next_timestamp - effective_timestamp))
            if action is not Action.RELEASE_ALL
            else 0.0
        )
        self.last_action_timing = ActionTiming(
            action_command_timestamp=command_timestamp,
            action_effective_timestamp=effective_timestamp,
            next_observation_timestamp=next_timestamp,
            held_action=held_action,
            action_duration_ms=action_duration_ms,
            action_applied=True,
        )
        return observation

    def release_all(self) -> None:
        self._cancel_hold_watchdog()
        with self._hold_lock:
            self._held_action = None
        self.controller.release_all()

    def latest_frame(self) -> Any | None:
        if self.frame_provider is None:
            return None
        frame = self.frame_provider()
        return None if frame is None else frame.copy()

    @property
    def emergency_stopped(self) -> bool:
        return bool(self.controller.emergency_stopped)

    def is_foreground(self) -> bool:
        return bool(self.controller.is_target_active())

    def verified_name_entry_dialog(self):
        return self.controller.verified_name_entry_dialog()

    def dismiss_verified_name_entry_dialog(
        self,
        *,
        focus_target: bool,
        settle_seconds: float = 0.25,
    ):
        """略過精確驗證的姓名 modal；未知 related window 保持 fail-closed。"""
        self.release_all()
        dialog = self.controller.dismiss_verified_name_entry_dialog()
        if dialog is None:
            return None
        self.sleeper(max(0.0, settle_seconds))
        if focus_target:
            self.controller.window_manager.focus(self.controller.hwnd)
            self.sleeper(0.1)
        if not self.controller.resume_after_related_window():
            return None
        if self.monitor is not None:
            self.monitor.start()
        return dialog

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.release_all()
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
        config.menu_exit_button_left,
        config.menu_exit_button_top,
        config.menu_exit_button_width,
        config.menu_exit_button_height,
    )
    if any(value is None for value in focus_values):
        raise RuntimeError(
            "自動重設需要校正 detection.menu_start_button_* 與 "
            "menu_two_player_button_* 與 menu_exit_button_*，"
            "否則無法安全確認選單焦點。"
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
        exit_left,
        exit_top,
        exit_width,
        exit_height,
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
        exit_button_rect=(
            exit_left,
            exit_top,
            exit_width,
            exit_height,
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
            focus_correction_max_presses=(
                config.environment.reset_focus_correction_max_presses
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
        max_continuous_hold_ms=config.controls.max_continuous_hold_ms,
        capture=capture,
        monitor=monitor,
        episode_resetter=episode_resetter,
        latest_phase=lambda: pipeline.last_phase,
        frame_provider=lambda: getattr(pipeline, "last_frame", None),
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
