import time

from _common import WindowManager, find_target, load_config, run_main

import cv2

from stair_agent.diagnostics import annotate_frame, prepare_preview_window
from stair_agent.screen_capture import ScreenCapture


def main() -> None:
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    print(f"只擷取、不控制：{target.title!r}。按 Esc 離開。")
    window_name = "NS-SHAFT 畫面擷取測試"
    prepare_preview_window(window_name, target)
    manager.focus(target.hwnd)
    delay_ms = max(1, round(1000 / config.capture.target_fps))
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        try:
            while True:
                started = time.perf_counter()
                frame = capture.capture()
                preview = annotate_frame(
                    frame,
                    capture.fps if config.diagnostics.show_fps else None,
                    config.diagnostics.draw_capture_border,
                )
                cv2.imshow(window_name, preview)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                if cv2.waitKey(max(1, delay_ms - elapsed_ms)) & 0xFF == 27:
                    break
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    run_main(main)
