from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.data.resource_audit import (  # noqa: E402
    audit_jsonl_resources,
    write_audit_csvs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="稽核現有 NS-SHAFT JSONL 資料。")
    parser.add_argument("--data-dir", type=Path, default=Path("logs"))
    parser.add_argument("--inventory", type=Path, default=Path("artifacts/dataset_inventory.csv"))
    parser.add_argument(
        "--salvage", type=Path, default=Path("artifacts/dataset_salvage_manifest.csv")
    )
    args = parser.parse_args()
    paths = sorted(args.data_dir.rglob("*.jsonl"))
    if not paths:
        print(f"找不到 JSONL：{args.data_dir}", file=sys.stderr)
        return 2
    result = audit_jsonl_resources(Path.cwd(), paths)
    write_audit_csvs(result, args.inventory, args.salvage)
    counts = Counter()
    for row in result.inventory:
        counts[row.classification] += row.row_count
    print(f"files={len(paths)} episodes={len(result.inventory)} rows={result.total_rows}")
    print("classification_rows=" + ",".join(f"{key}:{value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
