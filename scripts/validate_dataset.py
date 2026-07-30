from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import PROJECT_ROOT, run_main

from stair_agent.data.validator import DatasetValidator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="驗證新版 NS-SHAFT transition JSONL；不操作遊戲。"
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, help="選擇性寫出 JSON 報告。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = (
        args.dataset
        if args.dataset.is_absolute()
        else PROJECT_ROOT / args.dataset
    )
    report = DatasetValidator().validate_file(dataset)
    payload = report.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output is not None:
        output = (
            args.output
            if args.output.is_absolute()
            else PROJECT_ROOT / args.output
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"拒絕覆寫既有報告：{output}")
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if not report.valid:
        raise RuntimeError(f"資料驗證失敗：{report.error_count} 個錯誤。")


if __name__ == "__main__":
    run_main(main)
