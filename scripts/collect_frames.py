from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone

from _common import PROJECT_ROOT, WindowManager, find_target, load_config, run_main

import cv2

from stair_agent.diagnostics import annotate_frame, prepare_preview_window, save_image
from stair_agent.screen_capture import ScreenCapture


LABEL_KEYS = {
    ord("1"): "menu",
    ord("2"): "playing",
    ord("3"): "game_over",
    ord("4"): "dialog",
    ord("5"): "name_entry",
    ord("s"): "unclassified",
    ord("S"): "unclassified",
}


def main() -> None:
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    output_dir = PROJECT_ROOT / "captures" / "labeled"
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "metadata.jsonl"
    print(
        "1=menu、2=playing、3=game_over、4=dialog、"
        "5=name_entry、S=未分類、Esc=離開。"
    )
    window_name = "NS-SHAFT 畫面資料收集"
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
                    "2:playing  4:dialog  5:name_entry  S:unclassified",
                )
                cv2.imshow(window_name, preview)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                key = cv2.waitKey(max(1, delay_ms - elapsed_ms)) & 0xFF
                if key == 27:
                    break
                label = LABEL_KEYS.get(key)
                if label is None:
                    continue
                now = datetime.now(timezone.utc).astimezone()
                stamp = now.strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{stamp}_{label}.png"
                path = output_dir / filename
                save_image(path, frame)
                region = capture.last_region
                record = {
                    "filename": filename,
                    "label": label,
                    "capture_region": asdict(region) if region else None,
                    "original_size": {
                        "width": region.width if region else None,
                        "height": region.height if region else None,
                    },
                    "saved_frame_size": {
                        "width": int(frame.shape[1]),
                        "height": int(frame.shape[0]),
                    },
                    "saved_at": now.isoformat(),
                }
                with metadata_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(f"已儲存 [{label}]：{path}")
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    run_main(main)
