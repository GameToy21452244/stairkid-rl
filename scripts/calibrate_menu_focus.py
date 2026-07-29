from __future__ import annotations

import argparse
import time

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.dialog_handler import (
    DialogActionHandler,
    DialogFocusLocation,
)
from stair_agent.game_state import GamePhase, GameStateDetector
from stair_agent.input_controller import InputController, SafetyMonitor
from stair_agent.live_env import build_dialog_focus_guard
from stair_agent.screen_capture import ScreenCapture
from stair_agent.window_manager import WindowManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "只測試一次選單焦點切換，不按 Enter、不開始遊戲。"
        )
    )
    parser.add_argument(
        "--candidate-key",
        choices=("tab", "right"),
        default="tab",
    )
    return parser.parse_args()


def wait_focus(
    *,
    capture,
    detector,
    guard,
    desired: DialogFocusLocation,
    required: int,
    max_frames: int,
    delay: float,
) -> bool:
    consecutive = 0
    for index in range(max_frames):
        frame = capture()
        phase, _score = detector.detect_with_score(frame)
        if (
            phase is GamePhase.DIALOG
            and guard.focus_location(frame) is desired
        ):
            consecutive += 1
            if consecutive >= required:
                return True
        else:
            consecutive = 0
        if index + 1 < max_frames:
            time.sleep(delay)
    return False


def main() -> None:
    args = parse_args()
    config = load_config()
    manager = WindowManager()
    target = manager.require_ready(
        config.game.window_title_contains,
        config.game.window_class_name,
    )
    detector = GameStateDetector.from_config(
        config.detection,
        PROJECT_ROOT,
    )
    guard = build_dialog_focus_guard(config.detection)
    print(
        f"目標：{target.title!r}，client="
        f"{target.client_rect.width}x{target.client_rect.height}"
    )
    print(
        "本工具不按 Enter，也不製造雙人焦點。只有目前已是中央雙人焦點時，"
        "才測試一次候選鍵。"
    )
    print(
        f"候選鍵：{args.candidate_key!r}；"
        f"按 {config.safety.emergency_stop_key.upper()} 可停止。"
    )
    if input("確認執行焦點校正？輸入大寫 FOCUS：").strip() != "FOCUS":
        print("未確認，已安全取消。")
        return
    print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
    for value in (3, 2, 1):
        print(f"{value}...")
        time.sleep(1)

    required = config.environment.reset_required_consecutive_frames
    max_frames = config.environment.reset_focus_max_observation_frames
    delay = 1.0 / config.capture.target_fps
    with ScreenCapture(
        config.capture,
        manager,
        target.hwnd,
    ) as capture:
        with InputController(
            config.controls,
            config.safety,
            manager,
            target.hwnd,
        ) as controller:
            with SafetyMonitor(
                controller,
                config.safety.emergency_stop_key,
            ):
                handler = DialogActionHandler(
                    detector,
                    controller,
                    config.controls.restart_key,
                    capture.capture,
                    required_consecutive=required,
                    max_observation_frames=(
                        config.environment.reset_max_observation_frames
                    ),
                    observation_delay_seconds=delay,
                    focus_guard=guard,
                    sleep_fn=time.sleep,
                )
                initial = handler.observe_stable()
                if initial.phase is not GamePhase.DIALOG:
                    raise RuntimeError(
                        f"目前不是穩定 DIALOG，而是 {initial.phase.value}。"
                    )
                location = guard.focus_location(initial.frame)
                if location is DialogFocusLocation.UNKNOWN:
                    raise RuntimeError("目前選單焦點不明，沒有送出按鍵。")
                if location is DialogFocusLocation.START:
                    raise RuntimeError(
                        "目前已是單人開始焦點，不需要修正；沒有送出按鍵。"
                        "請只在真實出現中央雙人焦點時執行本工具。"
                    )

                controller.tap(
                    args.candidate_key,
                    config.controls.action_duration_ms,
                )
                controller.release_all()
                if not wait_focus(
                    capture=capture.capture,
                    detector=detector,
                    guard=guard,
                    desired=DialogFocusLocation.START,
                    required=required,
                    max_frames=max_frames,
                    delay=delay,
                ):
                    raise RuntimeError(
                        f"一次 {args.candidate_key.upper()} 後未確認"
                        "右側單人開始焦點。"
                    )
                print(
                    f"校正成功：中央雙人 → {args.candidate_key.upper()} "
                    "一次 → 右側單人開始。沒有按 Enter。"
                )


if __name__ == "__main__":
    run_main(main)
