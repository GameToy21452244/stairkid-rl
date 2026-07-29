from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from _common import PROJECT_ROOT, WindowManager, find_target, load_config, run_main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "唯讀監看 NS-SHAFT 同程序視窗與新出現的可見視窗；"
            "用於識別外部姓名輸入框。"
        )
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=120.0,
        help="監看秒數（預設：120）。",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="輪詢間隔秒數（預設：0.25）。",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="JSONL 日誌路徑；省略時寫入 logs/window_watch_時間戳.jsonl。",
    )
    return parser.parse_args()


def describe(prefix, item, log_file) -> None:
    rect = item.rect
    print(
        f"{prefix} hwnd={item.hwnd} pid={item.process_id} "
        f"class={item.class_name!r} title={item.title!r} "
        f"owner={item.owner_hwnd} "
        f"rect=({rect.left},{rect.top},{rect.width}x{rect.height})"
    )
    record = {
        "observed_at": datetime.now().astimezone().isoformat(),
        "category": prefix,
        "hwnd": item.hwnd,
        "process_id": item.process_id,
        "class_name": item.class_name,
        "title": item.title,
        "owner_hwnd": item.owner_hwnd,
        "rect": {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        },
    }
    log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    log_file.flush()


def main() -> None:
    args = parse_args()
    if args.seconds <= 0 or args.interval <= 0:
        raise RuntimeError("--seconds 與 --interval 必須大於 0。")
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager, allow_launch=False)
    log_path = args.log
    if log_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = PROJECT_ROOT / "logs" / f"window_watch_{stamp}.jsonl"
    elif not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    baseline = {item.hwnd for item in manager.list_windows()}
    seen_related: set[int] = set()
    seen_new: set[int] = set()
    with log_path.open("a", encoding="utf-8") as log_file:
        describe("GAME", target, log_file)
        print(f"JSONL 日誌：{log_path}")
        print(
            "開始唯讀監看。請正常操作遊戲；若姓名視窗出現，不要輸入，"
            "等待本工具列出它。Ctrl+C 可結束。"
        )
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            windows = manager.list_windows()
            related = manager.related_windows(target)
            for item in related:
                if item.hwnd not in seen_related:
                    describe("RELATED", item, log_file)
                    seen_related.add(item.hwnd)
            for item in windows:
                if (
                    item.hwnd not in baseline
                    and item.hwnd not in seen_new
                    and item.hwnd != target.hwnd
                ):
                    describe("NEW", item, log_file)
                    seen_new.add(item.hwnd)
            time.sleep(args.interval)
    print("監看時間結束；本工具沒有送出任何按鍵。")


if __name__ == "__main__":
    run_main(main)
