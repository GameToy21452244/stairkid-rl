from __future__ import annotations

import argparse
from pathlib import Path

from _common import PROJECT_ROOT, load_config, run_main

import cv2

from stair_agent.diagnostics import load_image, save_image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="從 playing 樣本框選遊戲場地或指定平台範本。"
    )
    parser.add_argument(
        "--sample",
        type=Path,
        help="指定 playing PNG；省略時使用最新的 *_playing.png。",
    )
    parser.add_argument(
        "--kind",
        choices=(
            "normal",
            "spikes",
            "spring",
            "green",
            "conveyor",
            "metal",
            "flipping",
        ),
        default="normal",
        help="要校正的平台類型（預設：normal）。",
    )
    parser.add_argument(
        "--variant",
        help="動畫範本編號，例如 2；適用 spring／conveyor／flipping。",
    )
    parser.add_argument(
        "--box",
        help="已知範圍 left,top,width,height；省略時以滑鼠框選。",
    )
    return parser.parse_args()


def choose_sample(requested: Path | None) -> Path:
    if requested is not None:
        path = requested if requested.is_absolute() else PROJECT_ROOT / requested
        if not path.is_file():
            raise RuntimeError(f"找不到指定樣本：{path}")
        return path
    candidates = list(
        (PROJECT_ROOT / "captures" / "labeled").glob("*_playing.png")
    )
    if not candidates:
        raise RuntimeError("找不到 playing 樣本；請先執行 collect_frames.py。")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def select_box(name: str, frame, instruction: str) -> tuple[int, int, int, int]:
    print(instruction)
    values = tuple(
        int(value)
        for value in cv2.selectROI(name, frame, showCrosshair=True)
    )
    cv2.destroyWindow(name)
    if values[2] <= 0 or values[3] <= 0:
        raise RuntimeError("未選取有效範圍，設定未變更。")
    return values


def parse_box(value: str, frame) -> tuple[int, int, int, int]:
    try:
        box = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise RuntimeError("--box 必須是四個整數：left,top,width,height。") from exc
    if len(box) != 4:
        raise RuntimeError("--box 必須是四個整數：left,top,width,height。")
    left, top, width, height = box
    if (
        left < 0
        or top < 0
        or width <= 0
        or height <= 0
        or left + width > frame.shape[1]
        or top + height > frame.shape[0]
    ):
        raise RuntimeError("--box 超出樣本畫面或尺寸無效。")
    return left, top, width, height


def main() -> None:
    args = parse_args()
    config = load_config()
    sample_path = choose_sample(args.sample)
    frame = load_image(sample_path)
    print(f"使用樣本：{sample_path}")
    aliases = {"metal": "conveyor", "green": "spring"}
    kind = aliases.get(args.kind, args.kind)
    if args.variant and kind not in {"spring", "conveyor", "flipping"}:
        raise RuntimeError("--variant 只適用 spring、conveyor 或 flipping。")

    playfield = None
    if kind == "normal":
        playfield = select_box(
            "1/2 框選遊戲場地",
            frame,
            "請框住左側可遊玩的藍色場地內部，排除 LIFE、樓層與右側按鈕。",
        )
    labels = {
        "normal": "完整的亮青色普通冰平台",
        "spikes": "完整的尖刺平台（包含尖刺與底座）",
        "green": "完整的綠色特殊平台",
        "conveyor": "完整的輸送帶（包含兩端圓輪）",
        "flipping": "完整的向下翻轉石板",
    }
    platform = (
        parse_box(args.box, frame)
        if args.box
        else select_box(
            f"框選 {kind} 平台",
            frame,
            f"請精確框住一個{labels[kind]}，不要包含其他物件。",
        )
    )
    left, top, width, height = platform
    template = frame[top : top + height, left : left + width]
    path_attributes = {
        "normal": "normal_platform_template_path",
        "spikes": "spikes_platform_template_path",
        "spring": "green_platform_template_path",
        "conveyor": "metal_platform_template_path",
    }
    if kind == "flipping":
        variant = args.variant or "1"
        relative_path = f"captures/templates/platform_flipping_{variant}.png"
        if relative_path not in config.vision.flipping_platform_template_paths:
            config.vision.flipping_platform_template_paths.append(relative_path)
        template_path = Path(relative_path)
    elif kind in {"spring", "conveyor"} and args.variant:
        relative_path = (
            f"captures/templates/platform_{kind}_{args.variant}.png"
        )
        paths = (
            config.vision.green_platform_template_paths
            if kind == "spring"
            else config.vision.metal_platform_template_paths
        )
        if relative_path not in paths:
            paths.append(relative_path)
        template_path = Path(relative_path)
    else:
        template_path = Path(getattr(config.vision, path_attributes[kind]))
    if not template_path.is_absolute():
        template_path = PROJECT_ROOT / template_path
    template_path.parent.mkdir(parents=True, exist_ok=True)
    save_image(template_path, template)

    if playfield is not None:
        (
            config.vision.playfield_left,
            config.vision.playfield_top,
            config.vision.playfield_width,
            config.vision.playfield_height,
        ) = playfield
        config.vision.reference_width = int(frame.shape[1])
        config.vision.reference_height = int(frame.shape[0])
    config.save(PROJECT_ROOT / "config.yaml")
    if playfield is not None:
        print(
            f"場地 ROI={playfield}，平台模板={platform}，"
            f"參考畫面={frame.shape[1]}x{frame.shape[0]}"
        )
    print(f"{kind} 平台範本已儲存：{template_path}")


if __name__ == "__main__":
    run_main(main)
