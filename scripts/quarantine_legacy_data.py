from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import PROJECT_ROOT, run_main
from stair_agent.data.migration import build_quarantine_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="唯讀掃描 legacy JSONL 並產生 quarantine manifest。"
    )
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "logs")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports" / "LEGACY_DATA_QUARANTINE.json",
    )
    args = parser.parse_args()
    source = args.source if args.source.is_absolute() else PROJECT_ROOT / args.source
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    if output.exists():
        raise FileExistsError(f"拒絕覆寫既有 manifest：{output}")
    manifest = build_quarantine_manifest(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"quarantine 完成：files={manifest['file_count']} "
        f"rows={manifest['total_rows']} output={output}"
    )
    print("沒有修改、遷移或升格任何 legacy transition。")


if __name__ == "__main__":
    run_main(main)
