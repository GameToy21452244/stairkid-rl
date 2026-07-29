from __future__ import annotations

import argparse
import time

from _common import (
    PROJECT_ROOT,
    WindowError,
    WindowManager,
    find_target,
    load_config,
    run_main,
)

import cv2

from stair_agent.diagnostics import (
    annotate_frame,
    load_image,
    prepare_preview_window,
)
from stair_agent.game_state import GameStateDetector
from stair_agent.screen_capture import ScreenCapture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="測試中央對話框 template matching；不控制遊戲。"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="只檢查 captures/labeled 內的圖片，不開啟即時預覽。",
    )
    return parser.parse_args()


def run_offline(detector: GameStateDetector) -> None:
    paths = sorted((PROJECT_ROOT / "captures" / "labeled").glob("*.png"))
    if not paths:
        raise RuntimeError("captures/labeled 內沒有 PNG 樣本。")
    correct = 0
    evaluated = 0
    for path in paths:
        expected_dialog = any(
            suffix in path.name
            for suffix in ("_menu.png", "_game_over.png", "_dialog.png")
        )
        phase, score = detector.detect_with_score(load_image(path))
        predicted_dialog = phase.value == "dialog"
        is_correct = expected_dialog == predicted_dialog
        correct += int(is_correct)
        evaluated += 1
        status = "OK" if is_correct else "MISS"
        print(f"{status:<4} score={score:.3f} phase={phase.value:<7} {path.name}")
    print(f"\n離線結果：{correct}/{evaluated} 正確")


def run_live(detector: GameStateDetector) -> None:
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    window_name = "NS-SHAFT 狀態偵測（不控制遊戲）"
    prepare_preview_window(window_name, target)
    try:
        manager.focus(target.hwnd)
    except WindowError:
        print("Windows 拒絕自動聚焦；請手動點一下遊戲並避免其他視窗遮住它。")
    delay_ms = max(1, round(1000 / config.capture.target_fps))
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        try:
            while True:
                started = time.perf_counter()
                frame = capture.capture()
                phase, score = detector.detect_with_score(frame)
                message = f"phase={phase.value}  dialog_score={score:.3f}"
                preview = annotate_frame(
                    frame,
                    capture.fps if config.diagnostics.show_fps else None,
                    config.diagnostics.draw_capture_border,
                    message,
                )
                cv2.imshow(window_name, preview)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                if cv2.waitKey(max(1, delay_ms - elapsed_ms)) & 0xFF == 27:
                    break
        finally:
            cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    config = load_config()
    detector = GameStateDetector.from_config(config.detection, PROJECT_ROOT)
    if args.offline:
        run_offline(detector)
    else:
        print("此工具只辨識畫面，不會送出任何按鍵。按 Esc 離開。")
        run_live(detector)


if __name__ == "__main__":
    run_main(main)
