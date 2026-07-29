from __future__ import annotations

import ctypes
import threading
import time
from enum import IntEnum
from typing import Callable, Protocol

from .config import ControlsConfig, SafetyConfig
from .window_manager import WindowManager


class InputError(RuntimeError):
    """輸入控制因安全條件不符而中止。"""


class Action(IntEnum):
    RELEASE_ALL = 0
    LEFT = 1
    RIGHT = 2


class InputBackend(Protocol):
    def key_down(self, key: str) -> None: ...
    def key_up(self, key: str) -> None: ...
    def press(self, key: str) -> None: ...


class PyAutoGUIBackend:
    def __init__(self) -> None:
        import pyautogui

        # 不修改 pyautogui.FAILSAFE；套件預設的滑鼠角落 fail-safe 保持啟用。
        if not pyautogui.FAILSAFE:
            raise InputError("PyAutoGUI fail-safe 已在外部被關閉，拒絕啟動輸入控制。")
        self.module = pyautogui

    def key_down(self, key: str) -> None:
        self.module.keyDown(key)

    def key_up(self, key: str) -> None:
        self.module.keyUp(key)

    def press(self, key: str) -> None:
        self.module.press(key)


class PyDirectInputBackend:
    def __init__(self) -> None:
        import pydirectinput

        self.module = pydirectinput

    def key_down(self, key: str) -> None:
        self.module.keyDown(key)

    def key_up(self, key: str) -> None:
        self.module.keyUp(key)

    def press(self, key: str) -> None:
        self.module.press(key)


def create_backend(name: str) -> InputBackend:
    if name == "pyautogui":
        return PyAutoGUIBackend()
    if name == "pydirectinput":
        return PyDirectInputBackend()
    raise InputError(f"不支援的輸入後端：{name}")


class InputController:
    def __init__(
        self,
        controls: ControlsConfig,
        safety: SafetyConfig,
        window_manager: WindowManager,
        hwnd: int,
        backend: InputBackend | None = None,
    ) -> None:
        self.controls = controls
        self.safety = safety
        self.window_manager = window_manager
        self.hwnd = hwnd
        self.backend = backend or create_backend(controls.input_backend)
        self.held_keys: set[str] = set()
        self.emergency_stopped = False
        self._lock = threading.RLock()

    def __enter__(self) -> "InputController":
        return self

    def __exit__(self, *_args: object) -> None:
        self.release_all()

    def _ensure_safe_to_send(self) -> None:
        if self.emergency_stopped:
            raise InputError("F8 緊急停止已啟動。")
        if self.safety.require_foreground_window and not self.window_manager.is_foreground(
            self.hwnd
        ):
            self.release_all()
            raise InputError("遊戲不是前景視窗；已釋放按鍵並停止輸入。")

    def key_down(self, key: str) -> None:
        with self._lock:
            self._ensure_safe_to_send()
            opposite = None
            if key == self.controls.left_key:
                opposite = self.controls.right_key
            elif key == self.controls.right_key:
                opposite = self.controls.left_key
            if opposite in self.held_keys:
                self.backend.key_up(opposite)
                self.held_keys.discard(opposite)
            if key not in self.held_keys:
                self.backend.key_down(key)
                self.held_keys.add(key)

    def key_up(self, key: str) -> None:
        with self._lock:
            # 放開鍵不檢查焦點，確保失焦時仍能清理先前送出的狀態。
            try:
                self.backend.key_up(key)
            finally:
                self.held_keys.discard(key)

    def tap(self, key: str, duration_ms: int | None = None) -> None:
        duration = self.controls.action_duration_ms if duration_ms is None else duration_ms
        self.key_down(key)
        try:
            time.sleep(max(0, duration) / 1000)
        finally:
            self.key_up(key)

    def apply(self, action: Action) -> None:
        if action == Action.RELEASE_ALL:
            self.release_all()
        elif action == Action.LEFT:
            self.key_down(self.controls.left_key)
        elif action == Action.RIGHT:
            self.key_down(self.controls.right_key)
        else:
            raise InputError(f"未知動作：{action}")

    def release_all(self) -> None:
        with self._lock:
            # 即使追蹤集合因例外不完整，也固定釋放所有可能使用的方向鍵。
            keys = self.held_keys | {
                self.controls.left_key,
                self.controls.right_key,
            }
            for key in keys:
                try:
                    self.backend.key_up(key)
                except Exception:
                    pass
            self.held_keys.clear()

    def emergency_stop(self) -> None:
        self.emergency_stopped = True
        self.release_all()

    def run_safely(self, operation: Callable[[], None]) -> None:
        try:
            operation()
        finally:
            if self.safety.release_keys_on_error:
                self.release_all()


_VIRTUAL_KEYS = {
    **{f"f{index}": 0x6F + index for index in range(1, 13)},
    "esc": 0x1B,
}


def windows_key_pressed(key: str) -> bool:
    vk = _VIRTUAL_KEYS.get(key.casefold())
    if vk is None:
        raise InputError(f"緊急停止目前只支援 F1–F12 或 Esc：{key}")
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


class SafetyMonitor:
    """背景監看 F8 與遊戲焦點；觸發後立即放開方向鍵。"""

    def __init__(
        self,
        controller: InputController,
        emergency_key: str,
        key_checker: Callable[[str], bool] = windows_key_pressed,
        interval: float = 0.02,
    ) -> None:
        self.controller = controller
        self.emergency_key = emergency_key
        self.key_checker = key_checker
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "SafetyMonitor":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=0.5)
        self.controller.release_all()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.key_checker(self.emergency_key):
                    self.controller.emergency_stop()
                    self._stop.set()
                    break
                if (
                    self.controller.safety.require_foreground_window
                    and self.controller.held_keys
                    and not self.controller.window_manager.is_foreground(
                        self.controller.hwnd
                    )
                ):
                    self.controller.release_all()
                    self._stop.set()
                    break
            except Exception:
                self.controller.release_all()
                self._stop.set()
                break
            self._stop.wait(self.interval)
