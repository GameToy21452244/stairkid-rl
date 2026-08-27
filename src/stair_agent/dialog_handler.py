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


class DialogFocusLocation(Enum):
    START = "start"
    TWO_PLAYER = "two_player"
    EXIT = "exit"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DialogFocusGuard:
    """只在單人開始按鈕具有深色焦點外框時允許確認。"""

    reference_width: int
    reference_height: int
    start_button_rect: tuple[int, int, int, int]
    two_player_button_rect: tuple[int, int, int, int]
    exit_button_rect: tuple[int, int, int, int] | None = None
    focused_border_mean_max: float = 180.0
    minimum_contrast: float = 20.0
    focused_inner_gray_max: int = 80
    focused_inner_dark_ratio_min: float = 0.20

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

    def _inner_border_dark_ratio(
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
        inset_x = max(1, round(4 * scale_x))
        inset_y = max(1, round(3 * scale_y))
        if (
            x < 0
            or y < 0
            or x + w > gray.shape[1]
            or y + h > gray.shape[0]
            or w <= inset_x * 2
            or h <= inset_y * 2
        ):
            return 0.0
        top_line = gray[
            y + inset_y,
            x + inset_x : x + w - inset_x,
        ]
        bottom_line = gray[
            y + h - inset_y - 1,
            x + inset_x : x + w - inset_x,
        ]
        left_line = gray[
            y + inset_y : y + h - inset_y,
            x + inset_x,
        ]
        right_line = gray[
            y + inset_y : y + h - inset_y,
            x + w - inset_x - 1,
        ]
        border = np.concatenate(
            (top_line, bottom_line, left_line, right_line)
        )
        return float(np.mean(border <= self.focused_inner_gray_max))

    def focus_location(
        self,
        frame: np.ndarray,
    ) -> DialogFocusLocation:
        if (
            self.reference_width <= 0
            or self.reference_height <= 0
            or frame.size == 0
        ):
            return DialogFocusLocation.UNKNOWN
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if frame.ndim == 3
            else frame
        )
        button_rects = {
            DialogFocusLocation.START: self.start_button_rect,
            DialogFocusLocation.TWO_PLAYER: self.two_player_button_rect,
        }
        if self.exit_button_rect is not None:
            button_rects[DialogFocusLocation.EXIT] = self.exit_button_rect
        border_means = {
            location: self._top_border_mean(gray, rect)
            for location, rect in button_rects.items()
        }
        inner_focus = [
            location
            for location, rect in button_rects.items()
            if self._inner_border_dark_ratio(gray, rect)
            >= self.focused_inner_dark_ratio_min
        ]
        if len(inner_focus) == 1:
            return inner_focus[0]
        if inner_focus:
            return DialogFocusLocation.UNKNOWN
        for location, focused_mean in border_means.items():
            other_means = [
                mean
                for other_location, mean in border_means.items()
                if other_location is not location
            ]
            if (
                focused_mean <= self.focused_border_mean_max
                and all(
                    other_mean - focused_mean >= self.minimum_contrast
                    for other_mean in other_means
                )
            ):
                return location
        return DialogFocusLocation.UNKNOWN

    def __call__(self, frame: np.ndarray) -> bool:
        return self.focus_location(frame) is DialogFocusLocation.START


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
    focus_corrected: bool = False
    focus_recovered_without_input: bool = False
    focus_trace: tuple[DialogFocusLocation, ...] = ()


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
        focus_guard: DialogFocusGuard | None = None,
        focus_correction_key: str | None = None,
        focus_correction_duration_ms: int | None = None,
        focus_correction_max_presses: int = 1,
        focus_correction_delay_seconds: float = 0.1,
        focus_max_observation_frames: int | None = None,
        focus_correction_max_observation_frames: int | None = None,
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
        self.focus_guard = focus_guard
        self.focus_correction_key = focus_correction_key
        self.focus_correction_duration_ms = focus_correction_duration_ms
        self.focus_correction_max_presses = max(
            1,
            int(focus_correction_max_presses),
        )
        self.focus_correction_delay_seconds = max(
            0.0,
            focus_correction_delay_seconds,
        )
        self.focus_max_observation_frames = (
            self.max_observation_frames
            if focus_max_observation_frames is None
            else int(focus_max_observation_frames)
        )
        if self.focus_max_observation_frames < self.required_consecutive:
            raise ValueError(
                "focus_max_observation_frames 不可小於 required_consecutive。"
            )
        self.focus_correction_max_observation_frames = (
            self.focus_max_observation_frames
            if focus_correction_max_observation_frames is None
            else int(focus_correction_max_observation_frames)
        )
        if (
            self.focus_correction_max_observation_frames
            < self.required_consecutive
        ):
            raise ValueError(
                "focus_correction_max_observation_frames "
                "不可小於 required_consecutive。"
            )
        self.sleep_fn = sleep_fn
        self.last_focus_trace: list[DialogFocusLocation] = []

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

    def _observe_stable_start_focus(
        self,
        max_frames: int | None = None,
    ) -> StableObservation | None:
        assert self.focus_guard is not None
        observation_frames = (
            self.focus_max_observation_frames
            if max_frames is None
            else max(self.required_consecutive, int(max_frames))
        )
        consecutive = 0
        for index in range(observation_frames):
            frame = self.frame_source()
            phase, score = self.detector.detect_with_score(frame)
            if (
                phase is GamePhase.DIALOG
                and self.focus_guard.focus_location(frame)
                is DialogFocusLocation.START
            ):
                consecutive += 1
                if consecutive >= self.required_consecutive:
                    return StableObservation(
                        phase,
                        score,
                        frame.copy(),
                        consecutive,
                    )
            else:
                consecutive = 0
            if index + 1 < observation_frames:
                self.sleep_fn(self.observation_delay_seconds)
        return None

    def _observe_stable_known_focus(
        self,
        max_frames: int,
    ) -> tuple[StableObservation, DialogFocusLocation] | None:
        """逐幀擷取，直到同一個已知 DIALOG focus 連續穩定。"""
        assert self.focus_guard is not None
        observation_frames = max(
            self.required_consecutive,
            int(max_frames),
        )
        last_location = DialogFocusLocation.UNKNOWN
        consecutive = 0
        for index in range(observation_frames):
            frame = self.frame_source()
            phase, score = self.detector.detect_with_score(frame)
            location = (
                self.focus_guard.focus_location(frame)
                if phase is GamePhase.DIALOG
                else DialogFocusLocation.UNKNOWN
            )
            if (
                location is not DialogFocusLocation.UNKNOWN
                and location is last_location
            ):
                consecutive += 1
            elif location is not DialogFocusLocation.UNKNOWN:
                last_location = location
                consecutive = 1
            else:
                last_location = DialogFocusLocation.UNKNOWN
                consecutive = 0
            if consecutive >= self.required_consecutive:
                return (
                    StableObservation(
                        phase,
                        score,
                        frame.copy(),
                        consecutive,
                    ),
                    location,
                )
            if index + 1 < observation_frames:
                self.sleep_fn(self.observation_delay_seconds)
        return None

    def execute_once(
        self,
        confirmed_before: StableObservation | None = None,
    ) -> DialogActionResult:
        try:
            self.last_focus_trace = []
            before = confirmed_before or self.observe_stable()
            focus_corrected = False
            focus_recovered_without_input = False
            if before.phase is not GamePhase.DIALOG:
                raise DialogActionError(
                    f"目前穩定狀態不是 DIALOG，而是 {before.phase.value}；"
                    "沒有送出 Enter。"
                )
            if self.focus_guard is not None:
                location = self.focus_guard.focus_location(before.frame)
                self.last_focus_trace.append(location)
                if (
                    location is not DialogFocusLocation.START
                    and (
                        location is not DialogFocusLocation.UNKNOWN
                        or (
                            self.focus_correction_key is not None
                            and self.focus_correction_key.casefold() == "tab"
                        )
                    )
                ):
                    # 死亡可能發生在方向鍵狀態切換期間。先釋放控制器
                    # 實際追蹤的按鍵，再以有界步數逐次修正。每次按鍵後
                    # 都重新擷取並辨識最新 focus；未確認 START 絕不 Enter。
                    self.controller.release_all()
                    corrected = None
                    if not self.focus_correction_key:
                        raise DialogActionError(
                            "選單焦點不在 START，且未設定安全修正鍵；"
                            "沒有送出 Enter。"
                        )
                    for _attempt in range(
                        self.focus_correction_max_presses
                    ):
                        previous_location = location
                        self.controller.release_all()
                        self.controller.tap(
                            self.focus_correction_key,
                            self.focus_correction_duration_ms,
                        )
                        self.controller.release_all()
                        self.sleep_fn(
                            self.focus_correction_delay_seconds
                        )
                        is_right_correction = (
                            self.focus_correction_key.casefold() == "right"
                        )
                        if is_right_correction:
                            observed = self._observe_stable_known_focus(
                                self.focus_correction_max_observation_frames,
                            )
                        else:
                            start_observation = (
                                self._observe_stable_start_focus(
                                    self.focus_correction_max_observation_frames,
                                )
                            )
                            observed = (
                                (start_observation, DialogFocusLocation.START)
                                if start_observation is not None
                                else None
                            )
                        if observed is None:
                            if is_right_correction:
                                raise DialogActionError(
                                    "焦點修正後無法辨識穩定的選單焦點；"
                                    "沒有送出 Enter，也不會繼續送方向鍵。"
                                )
                            self.last_focus_trace.append(
                                DialogFocusLocation.UNKNOWN
                            )
                            continue
                        still_dialog, location = observed
                        self.last_focus_trace.append(location)
                        if is_right_correction:
                            expected_locations = (
                                {
                                    DialogFocusLocation.TWO_PLAYER,
                                    DialogFocusLocation.START,
                                }
                                if previous_location
                                is DialogFocusLocation.EXIT
                                else {DialogFocusLocation.START}
                            )
                            if location not in expected_locations:
                                expected_names = "/".join(
                                    item.name
                                    for item in sorted(
                                        expected_locations,
                                        key=lambda item: item.value,
                                    )
                                )
                                raise DialogActionError(
                                    "RIGHT 後焦點轉移不符預期："
                                    f"{previous_location.name} 應到 "
                                    f"{expected_names}，實際為 "
                                    f"{location.name}；沒有送出 Enter。"
                                )
                        if location is DialogFocusLocation.START:
                            corrected = still_dialog
                            break
                    if corrected is None:
                        raise DialogActionError(
                            "已達焦點修正次數上限，但無法確認單人開始；"
                            "沒有送出 Enter。"
                        )
                    before = corrected
                    focus_corrected = True
                elif location is not DialogFocusLocation.START:
                    raise DialogActionError(
                        "無法判斷選單焦點位置；沒有送出 Enter。"
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
            return DialogActionResult(
                before,
                after,
                outcome,
                frame_change,
                focus_corrected,
                focus_recovered_without_input,
                tuple(self.last_focus_trace),
            )
        finally:
            self.controller.release_all()
