from __future__ import annotations

import argparse
import time
import winsound

from _common import (
    PROJECT_ROOT,
    WindowManager,
    find_target,
    load_config,
    run_main,
)

from stair_agent.dialog_handler import (
    DialogActionHandler,
    DialogActionOutcome,
)
from stair_agent.game_state import GameStateDetector
from stair_agent.input_controller import (
    InputController,
    InputError,
    SafetyMonitor,
)
from stair_agent.live_env import build_dialog_focus_guard
from stair_agent.screen_capture import ScreenCapture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "互動式安全測試：穩定偵測 DIALOG 後，經人工確認只按一次 Enter。"
        )
    )
    parser.add_argument(
        "--consecutive-frames",
        type=int,
        default=3,
        help="送鍵前後需要連續相同狀態的幀數（預設：3）。",
    )
    return parser.parse_args()


def countdown(seconds: int = 3) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"{remaining}...", flush=True)
        try:
            winsound.Beep(880, 120)
        except RuntimeError:
            pass
        time.sleep(1)


def request_game_foreground(
    manager: WindowManager,
    hwnd: int,
    message: str,
) -> None:
    print(message)
    print("看到 3... 後請立即手動點一下遊戲；程式不會在倒數前自動搶焦點。")
    countdown()
    if not manager.is_foreground(hwnd):
        raise InputError("倒數結束時遊戲不是前景視窗；沒有送出任何按鍵。")


def print_result(outcome: DialogActionOutcome, change: float) -> None:
    if outcome is DialogActionOutcome.PLAYING:
        print("結果：DIALOG → PLAYING，單次 Enter 測試成功。")
    elif outcome is DialogActionOutcome.DIALOG_CHANGED:
        print(
            "結果：仍是 DIALOG，但內容已改變"
            f"（畫面差異={change:.3f}）。沒有送出第二次 Enter。"
        )
        print("若要處理下一層對話框，請重新執行本腳本並再次人工確認。")
    elif outcome is DialogActionOutcome.DIALOG_UNCHANGED:
        print(
            "結果：DIALOG 沒有明顯改變"
            f"（畫面差異={change:.3f}）。可能未接受 Enter，已停止。"
        )
    else:
        print("結果：按鍵後狀態不穩定或無法辨識，已停止。")


def main() -> None:
    args = parse_args()
    if args.consecutive_frames <= 0:
        raise RuntimeError("--consecutive-frames 必須大於 0。")
    config = load_config()
    focus_guard = build_dialog_focus_guard(config.detection)
    manager = WindowManager()
    target = find_target(config, manager)
    detector = GameStateDetector.from_config(config.detection, PROJECT_ROOT)
    print(f"目標：{target.title!r}，class={target.class_name!r}")
    print(
        f"本工具最多只會送出一次 {config.controls.restart_key!r}；"
        f"按 {config.safety.emergency_stop_key.upper()} 可緊急停止。"
    )
    print(
        "確認後只需切換一次：倒數期間點選遊戲，之後不要再切換視窗。"
    )
    answer = input(
        f"確認偵測到 DIALOG 時只按一次 {config.controls.restart_key!r}？"
        "輸入大寫 YES 繼續："
    ).strip()
    if answer != "YES":
        print("未確認，已取消，沒有送出按鍵。")
        return

    frame_delay = 1 / config.capture.target_fps
    max_frames = max(args.consecutive_frames * 5, args.consecutive_frames)
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        with InputController(
            config.controls,
            config.safety,
            manager,
            target.hwnd,
        ) as controller:
            handler = DialogActionHandler(
                detector,
                controller,
                config.controls.restart_key,
                capture.capture,
                key_duration_ms=config.controls.restart_duration_ms,
                required_consecutive=args.consecutive_frames,
                max_observation_frames=max_frames,
                observation_delay_seconds=frame_delay,
                confirm_guard=focus_guard,
            )
            with SafetyMonitor(
                controller,
                config.safety.emergency_stop_key,
            ):
                request_game_foreground(
                    manager,
                    target.hwnd,
                    "3 秒後會辨識 DIALOG，符合才送出一次 Enter。",
                )
                if controller.emergency_stopped:
                    raise InputError("已由 F8 緊急停止。")
                result = handler.execute_once()
                if controller.emergency_stopped:
                    raise InputError("已由 F8 緊急停止。")
                print(
                    "已送出一次按鍵："
                    f"backend={config.controls.input_backend}，"
                    f"key={config.controls.restart_key!r}，"
                    f"duration={config.controls.restart_duration_ms} ms"
                )
                print(
                    f"送鍵前：{result.before.phase.value} "
                    f"(score={result.before.score:.3f})"
                )
                print(
                    f"送鍵後：{result.after.phase.value} "
                    f"(score={result.after.score:.3f})"
                )
                print_result(result.outcome, result.frame_change)
    print("測試結束，所有按鍵已釋放。")


if __name__ == "__main__":
    run_main(main)
