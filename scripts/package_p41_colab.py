from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import _common  # noqa: F401,E402

from stair_agent.p41_bundle import create_p41_bundle


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../ai-stair-agent-p41-colab.zip"),
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="只供開發檢查；正式上傳前應使用 clean commit。",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dirty = bool(_git_output("status", "--porcelain").strip())
    if dirty and not args.allow_dirty:
        raise RuntimeError("工作樹不是 clean；正式 P4.1 bundle 必須由已 commit 版本建立。")
    names = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8").split("\0")
    source_files = [root / name for name in names if name]
    summary = create_p41_bundle(
        repo_root=root,
        target=(root / args.output).resolve(),
        source_files=source_files,
        dataset_path=root / "artifacts" / "spike_teacher_dataset_v1.jsonl",
        git_commit=_git_output("rev-parse", "HEAD").strip(),
        dirty=dirty,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
