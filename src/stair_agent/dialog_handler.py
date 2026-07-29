from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import cv2
import numpy as np

from .game_state import GamePhase


class DialogActionError(RuntimeError):
    """對話框動作的安全前置條件不成立。"""


@dataclass(frozen=True)
class DialogFocusGuard:
    """只在單人開始按鈕具有深色焦點外框時允許確認。"""

    reference_width: int
    reference_height: int
    start_button_rect: tuple[int, int, int, int]
    two_player_button_rect: tuple[int, int, int, int]
    focused_border_mean_max: float = 180.0
    minimum_contrast: float = 20.0

    def _top_border_mean(
        self,
        gray: np.ndarray,
        rect: tuple[int, int, int, int],
    ) -> float:
        left, top, width, height = rect
        scale_x = gray.shape[1] / self.reference_width
        scale_y = gray.shape[0] / self.reference_height
        x = round(left * scale_x)
        y = round(top * scale_y)
        w = max(1, round(width * scale_x))
        h = max(1, round(height * scale_y))
        if (
            x < 0
            or y < 0
            or x + w > gray.shape[1]
            or y + h > gray.shape[0]
        ):
            return 255.0
        border_height = max(1, round(scale_y))
        return float(np.mean(gray[y : y + border_height, x : x + w]))

    def __call__(self, frame: np.ndarray) -> bool:
        if (
            self.reference_width <= 0
            or self.reference_height <= 0
            or frame.size == 0
        ):
            return False
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if frame.ndim == 3
            else frame
        )
        start_mean = self._top_border_mean(
            gray,
            self.start_button_rect,
        )
        two_player_mean = self._top_border_mean(
            gray,
            self.two_player_button_rect,
        )
        return (
            start_mean <= self.focused_border_mean_max
            and two_player_mean - start_mean >= self.minimum_contrast
        )


class Detector(Protocol):
    def detect_with_score(self, frame: np.ndarray) -> tuple[GamePhase, float]: ...


class Controller(Protocol):
    def tap(self, key: str, duration_ms: int | None = None) -> None: ...
    def release_all(self) -> None: ...


@dataclass(frozen=True)
class StableObservation:
    phase: GamePhase
    score: float
    frame: np.ndarray
    consecutive_frames: int


class DialogActionOutcome(Enum):
    PLAYING = "playing"
    DIALOG_CHANGED = "dialog_changed"
    DIALOG_UNCHANGED = "dialog_unchanged"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DialogActionResult:
    before: StableObservation
    after: StableObservation
    outcome: DialogActionOutcome
    frame_change: float


def normalized_frame_difference(before: np.ndarray, after: np.ndarray) -> float:
    """回傳 0–1 平均像素差，用於判斷同為 DIALOG 時內容是否已切換。"""
    if before.ndim != after.ndim:
        return 1.0
    if before.shape[:2] != after.shape[:2]:
        after = cv2.resize(
            after,
            (before.shape[1], before.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
    before_float = before.astype(np.float32)
    after_float = after.astype(np.float32)
    return float(np.mean(np.abs(before_float - after_float)) / 255.0)


class DialogActionHandler:
    """確認穩定 DIALOG 後只送一次 Enter，並重新觀察結果。"""

    def __init__(
        self,
        detector: Detector,
        controller: Controller,
        restart_key: str,
        frame_source: Callable[[], np.ndarray],
        *,
        key_duration_ms: int | None = None,
        required_consecutive: int = 3,
        max_observation_frames: int = 30,
        observation_delay_seconds: float = 1 / 15,
        post_action_delay_seconds: float = 0.4,
        dialog_change_threshold: float = 0.05,
        confirm_guard: Callable[[np.ndarray], bool] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if required_consecutive <= 0:
            raise ValueError("required_consecutive 必須大於 0。")
        if max_observation_frames < required_consecutive:
            raise ValueError("max_observation_frames 不可小於 required_consecutive。")
        self.detector = detector
        self.controller = controller
        self.restart_key = restart_key
        self.key_duration_ms = key_duration_ms
        self.frame_source = frame_source
        self.required_consecutive = required_consecutive
        self.max_observation_frames = max_observation_frames
        self.observation_delay_seconds = max(0.0, observation_delay_seconds)
        self.post_action_delay_seconds = max(0.0, post_action_delay_seconds)
        self.dialog_change_threshold = max(0.0, dialog_change_threshold)
        self.confirm_guard = confirm_guard
        self.sleep_fn = sleep_fn

    def observe_stable(self) -> StableObservation:
        last_phase: GamePhase | None = None
        consecutive = 0
        last_score = 0.0
        last_frame: np.ndarray | None = None
        for index in range(self.max_observation_frames):
            frame = self.frame_source()
            phase, score = self.detector.detect_with_score(frame)
            if phase is last_phase:
                consecutive += 1
            else:
                last_phase = phase
                consecutive = 1
            last_frame = frame.copy()
            last_score = score
            if consecutive >= self.required_consecutive:
                return StableObservation(phase, score, last_frame, consecutive)
            if index + 1 < self.max_observation_frames:
                self.sleep_fn(self.observation_delay_seconds)
        assert last_frame is not None
        return StableObservation(
            GamePhase.UNKNOWN,
            last_score,
            last_frame,
            consecutive,
        )

    def execute_once(
        self,
        confirmed_before: StableObservation | None = None,
    ) -> DialogActionResult:
        try:
            before = confirmed_before or self.observe_stable()
            if before.phase is not GamePhase.DIALOG:
                raise DialogActionError(
                    f"目前穩定狀態不是 DIALOG，而是 {before.phase.value}；"
                    "沒有送出 Enter。"
                )
            if (
                self.confirm_guard is not None
                and not self.confirm_guard(before.frame)
            ):
                raise DialogActionError(
                    "無法確認焦點位於單人開始按鈕；沒有送出 Enter，"
                    "避免誤選雙人模式。"
                )
            self.controller.release_all()
            self.controller.tap(self.restart_key, self.key_duration_ms)
            self.controller.release_all()
            self.sleep_fn(self.post_action_delay_seconds)
            after = self.observe_stable()
            frame_change = normalized_frame_difference(before.frame, after.frame)
            if after.phase is GamePhase.PLAYING:
                outcome = DialogActionOutcome.PLAYING
            elif after.phase is GamePhase.DIALOG:
                outcome = (
                    DialogActionOutcome.DIALOG_CHANGED
                    if frame_change >= self.dialog_change_threshold
                    else DialogActionOutcome.DIALOG_UNCHANGED
                )
            else:
                outcome = DialogActionOutcome.UNKNOWN
            return DialogActionResult(before, after, outcome, frame_change)
        finally:
            self.controller.release_all()
