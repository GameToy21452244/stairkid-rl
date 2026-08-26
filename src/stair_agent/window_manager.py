from __future__ import annotations

import ctypes
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class WindowError(RuntimeError):
    """找不到或無法操作目標視窗。"""


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def valid(self) -> bool:
        return self.width > 0 and self.height > 0


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    rect: Rect
    client_rect: Rect
    minimized: bool = False
    class_name: str = ""
    process_id: int = 0
    owner_hwnd: int = 0


class WindowBackend(Protocol):
    def list_visible(self) -> list[WindowInfo]: ...
    def foreground_hwnd(self) -> int: ...
    def bring_to_foreground(self, hwnd: int) -> bool: ...
    def get_window(self, hwnd: int) -> WindowInfo | None: ...


def attach_interactive_desktop() -> None:
    """讓背景/CLI 進程能正常存取與列舉 WinSta0/Default 的桌面視窗。"""
    try:
        user32 = ctypes.windll.user32
        h_winsta = user32.OpenWindowStationW("WinSta0", False, 0x37F)
        if h_winsta:
            user32.SetProcessWindowStation(h_winsta)
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass


def enable_dpi_awareness() -> None:
    """避免 Windows DPI scaling 造成畫面座標偏移。"""
    attach_interactive_desktop()
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


# 必須在 OpenCV 建立視窗或其他 GUI 套件鎖定 DPI 模式之前執行。
enable_dpi_awareness()


class PyWin32Backend:
    def __init__(self) -> None:
        enable_dpi_awareness()
        try:
            import win32con
            import win32gui
            import win32process
        except ModuleNotFoundError as exc:
            raise WindowError(
                "PYWIN32_NOT_INSTALLED: 找不到 pywin32 Python module，"
                "請先安裝 requirements.txt。"
            ) from exc
        except (ImportError, OSError) as exc:
            raise WindowError(
                "PYWIN32_NATIVE_DLL_LOAD_FAILED: pywin32 已安裝，"
                f"但 Windows native DLL 無法載入：{exc}"
            ) from exc
        self.win32con = win32con
        self.win32gui = win32gui
        self.win32process = win32process
        self.user32 = ctypes.windll.user32

    def _info(self, hwnd: int) -> WindowInfo | None:
        w = self.win32gui
        if not w.IsWindow(hwnd) or not w.IsWindowVisible(hwnd):
            return None
        title = w.GetWindowText(hwnd).strip()
        if not title:
            return None
        left, top, right, bottom = w.GetWindowRect(hwnd)
        c_left, c_top = w.ClientToScreen(hwnd, (0, 0))
        c_right, c_bottom = w.ClientToScreen(hwnd, w.GetClientRect(hwnd)[2:])
        return WindowInfo(
            hwnd=hwnd,
            title=title,
            rect=Rect(left, top, right - left, bottom - top),
            client_rect=Rect(c_left, c_top, c_right - c_left, c_bottom - c_top),
            minimized=bool(w.IsIconic(hwnd)),
            class_name=w.GetClassName(hwnd),
            process_id=int(self.win32process.GetWindowThreadProcessId(hwnd)[1]),
            owner_hwnd=int(w.GetWindow(hwnd, self.win32con.GW_OWNER) or 0),
        )

    def list_visible(self) -> list[WindowInfo]:
        result: list[WindowInfo] = []

        def callback(hwnd: int, _extra: object) -> bool:
            try:
                info = self._info(hwnd)
                if info:
                    result.append(info)
            except Exception:
                pass
            return True

        try:
            self.win32gui.EnumWindows(callback, None)
        except Exception:
            # 即使部分權限受限視窗引起 EnumWindows 警示，亦回傳已成功列舉之視窗列表
            pass
        return result

    def foreground_hwnd(self) -> int:
        return int(self.win32gui.GetForegroundWindow())

    def bring_to_foreground(self, hwnd: int) -> bool:
        try:
            if self.win32gui.IsIconic(hwnd):
                self.win32gui.ShowWindow(hwnd, self.win32con.SW_RESTORE)
            self.win32gui.BringWindowToTop(hwnd)
            self.win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        if self.foreground_hwnd() == hwnd:
            return True
        try:
            # Windows 的 foreground lock 可能無聲拒絕 SetForegroundWindow。
            # 只對呼叫者已驗證的同一個 hwnd 使用原生切換備援。
            self.user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            return False
        return self.foreground_hwnd() == hwnd

    def get_window(self, hwnd: int) -> WindowInfo | None:
        return self._info(hwnd)


class WindowManager:
    _NAME_ENTRY_TITLE_HINTS = (
        "輸入名稱",
        "輸入姓名",
        "輸入名字",
        "entername",
        "inputname",
        "playername",
        "nameentry",
    )

    def __init__(self, backend: WindowBackend | None = None) -> None:
        self.backend = backend or PyWin32Backend()

    def list_windows(self) -> list[WindowInfo]:
        return self.backend.list_visible()

    @staticmethod
    def _normalized_title(value: str) -> str:
        return "".join(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))

    @staticmethod
    def title_matches(title: str, partial: str) -> bool:
        partial = partial.strip()
        if not partial:
            return False
        raw_match = partial.casefold() in title.casefold()
        normalized_partial = WindowManager._normalized_title(partial)
        normalized_match = normalized_partial in WindowManager._normalized_title(title)
        return raw_match or bool(normalized_partial and normalized_match)

    @classmethod
    def _match_priority(cls, title: str, partial: str) -> tuple[int, int]:
        title_folded = title.strip().casefold()
        partial_folded = partial.strip().casefold()
        title_normalized = cls._normalized_title(title)
        partial_normalized = cls._normalized_title(partial)
        if title_folded == partial_folded:
            rank = 0
        elif title_normalized == partial_normalized:
            rank = 1
        elif title_folded.startswith(partial_folded):
            rank = 2
        elif title_normalized.startswith(partial_normalized):
            rank = 3
        else:
            rank = 4
        return rank, len(title)

    def find_window(
        self, partial_title: str, class_name: str | None = None
    ) -> WindowInfo:
        matches = [
            item
            for item in self.list_windows()
            if self.title_matches(item.title, partial_title)
            and (
                class_name is None
                or item.class_name.casefold() == class_name.strip().casefold()
            )
        ]
        if not matches:
            class_hint = f"、class 為「{class_name}」" if class_name else ""
            raise WindowError(
                f"遊戲尚未開啟：找不到標題包含「{partial_title}」"
                f"{class_hint}的可見視窗。"
            )
        return min(matches, key=lambda item: self._match_priority(item.title, partial_title))

    def require_ready(
        self, partial_title: str, class_name: str | None = None
    ) -> WindowInfo:
        """在任何擷取／輸入前確認遊戲已開啟且 client area 可用。"""
        info = self.find_window(partial_title, class_name)
        info = self.refresh(info.hwnd)
        if not info.client_rect.valid:
            raise WindowError("目標遊戲視窗的 client area 尺寸無效。")
        return info

    def refresh(self, hwnd: int) -> WindowInfo:
        info = self.backend.get_window(hwnd)
        if info is None:
            raise WindowError("目標遊戲視窗已關閉或不可見。")
        if info.minimized:
            raise WindowError("目標遊戲視窗已最小化。")
        return info

    def is_foreground(self, hwnd: int) -> bool:
        return self.backend.foreground_hwnd() == hwnd

    def foreground_hwnd(self) -> int:
        return self.backend.foreground_hwnd()

    def focus(self, hwnd: int) -> None:
        if not self.backend.bring_to_foreground(hwnd):
            raise WindowError("無法將遊戲切換至前景；已停止，不會送出按鍵。")

    def launch_if_enabled(
        self, exe_path: Path, enabled: bool, wait_seconds: float = 3.0
    ) -> None:
        if not enabled:
            return
        subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
        time.sleep(max(0.0, wait_seconds))

    def related_windows(self, target: WindowInfo) -> list[WindowInfo]:
        """列出與目標同程序或由目標擁有的其他可見視窗。"""
        related = [
            item
            for item in self.list_windows()
            if item.hwnd != target.hwnd
            and (
                (target.process_id > 0 and item.process_id == target.process_id)
                or item.owner_hwnd == target.hwnd
            )
        ]
        return sorted(related, key=lambda item: (item.rect.top, item.rect.left, item.hwnd))

    def blocking_related_windows(self, hwnd: int) -> list[WindowInfo]:
        """回傳可能是模態對話框的同程序／owner 可見視窗。"""
        target = self.refresh(hwnd)
        return self.related_windows(target)

    @classmethod
    def _is_name_entry_dialog(
        cls,
        target: WindowInfo,
        candidate: WindowInfo,
    ) -> bool:
        title = cls._normalized_title(candidate.title)
        title_match = any(
            cls._normalized_title(hint) in title
            for hint in cls._NAME_ENTRY_TITLE_HINTS
        )
        same_process = (
            target.process_id > 0
            and candidate.process_id == target.process_id
        )
        return bool(
            candidate.class_name.casefold() == "#32770"
            and candidate.owner_hwnd == target.hwnd
            and same_process
            and title_match
        )

    def find_name_entry_dialog(self, hwnd: int) -> WindowInfo | None:
        """只接受唯一、同程序、由遊戲擁有且標題符合的姓名 modal。"""
        target = self.refresh(hwnd)
        related = self.related_windows(target)
        if len(related) != 1:
            return None
        candidate = related[0]
        return (
            candidate
            if self._is_name_entry_dialog(target, candidate)
            else None
        )
