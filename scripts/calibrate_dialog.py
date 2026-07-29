from __future__ import annotations

import argparse
from pathlib import Path

from _common import PROJECT_ROOT, load_config, run_main

import cv2

from stair_agent.diagnostics import load_image, save_image


POSITIVE_LABELS = {"menu", "game_over", "dialog"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="從已標記畫面中框選 NS-SHAFT 的中央對話框並建立範本。"
    )
    parser.add_argument(
        "--sample",
        type=Path,
        help="指定含對話框的 PNG；省略時自動選擇最新的 menu/game_over/dialog 圖片。",
    )
    return parser.parse_args()


def choose_sample(requested: Path | None) -> Path:
    if requested is not None:
        path = requested if requested.is_absolute() else PROJECT_ROOT / requested
        if not path.is_file():
            raise RuntimeError(f"找不到指定樣本：{path}")
        return path
    labeled_dir = PROJECT_ROOT / "captures" / "labeled"
    candidates = [
        path
        for path in labeled_dir.glob("*.png")
        if any(f"_{label}.png" in path.name for label in POSITIVE_LABELS)
    ]
    if not candidates:
        raise RuntimeError(
            "找不到 menu、game_over 或 dialog 樣本；請先執行 collect_frames.py。"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> None:
    args = parse_args()
    config = load_config()
    sample_path = choose_sample(args.sample)
    frame = load_image(sample_path)
    print(f"使用樣本：{sample_path}")
    print("請拖曳框住完整白色中央對話框，按 Enter/Space 確認，按 C 取消。")
    window_name = "框選中央對話框"
    left, top, width, height = (
        int(value)
        for value in cv2.selectROI(window_name, frame, showCrosshair=True)
    )
    cv2.destroyAllWindows()
    if width <= 0 or height <= 0:
        print("未選取有效範圍，設定未變更。")
        return

    template = frame[top : top + height, left : left + width]
    template_path = Path(config.detection.dialog_template_path)
    if not template_path.is_absolute():
        template_path = PROJECT_ROOT / template_path
    template_path.parent.mkdir(parents=True, exist_ok=True)
    save_image(template_path, template)

    config.detection.dialog_roi_left = left
    config.detection.dialog_roi_top = top
    config.detection.dialog_roi_width = width
    config.detection.dialog_roi_height = height
    config.detection.reference_width = int(frame.shape[1])
    config.detection.reference_height = int(frame.shape[0])
    config.save(PROJECT_ROOT / "config.yaml")
    print(
        f"校正完成：ROI=({left},{top},{width}x{height})，"
        f"參考畫面={frame.shape[1]}x{frame.shape[0]}"
    )
    print(f"範本已儲存：{template_path}")
    print("下一步：執行 scripts/test_state_detection.py --offline")


if __name__ == "__main__":
    run_main(main)
