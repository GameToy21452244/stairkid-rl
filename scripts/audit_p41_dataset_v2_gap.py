from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import _common  # noqa: F401,E402

from stair_agent.data.p41_dataset_gap import (
    analyze_teacher_dataset,
    compare_same_seed_datasets,
    evaluate_v2_readiness,
)


POLICY_SOURCE_FILES = (
    "src/stair_agent/baseline_policy.py",
    "src/stair_agent/config.py",
    "src/stair_agent/policies/simulator_teachers.py",
    "scripts/generate_spike_teacher_dataset.py",
)


def _source_fingerprint(root: Path) -> dict[str, object]:
    combined = sha256()
    files: dict[str, str] = {}
    for relative in POLICY_SOURCE_FILES:
        payload = (root / relative).read_bytes()
        digest = sha256(payload).hexdigest()
        files[relative] = digest
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(payload)
        combined.update(b"\0")
    return {"sha256": combined.hexdigest(), "files": files}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _verify_summary(summary: dict[str, object], analysis: dict[str, object]) -> None:
    for field in ("records", "episodes"):
        if int(summary[field]) != int(analysis[field]):
            raise ValueError(f"summary {field}與JSONL不一致。")
    if summary["action_counts"] != analysis["action_counts"]:
        raise ValueError("summary action_counts與JSONL不一致。")
    expected_outcomes = {
        ("bottom" if key == "bottom" else key): int(value)
        for key, value in summary["terminal_reasons"].items()
    }
    if expected_outcomes != analysis["outcomes"]:
        raise ValueError("summary terminal_reasons與JSONL outcomes不一致。")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frozen",
        type=Path,
        default=Path("artifacts/spike_teacher_dataset_v1.jsonl"),
    )
    parser.add_argument(
        "--frozen-summary",
        type=Path,
        default=Path("artifacts/spike_teacher_dataset_v1_summary.json"),
    )
    parser.add_argument("--current-diagnostic", type=Path, required=True)
    parser.add_argument("--current-summary", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/p41_dataset_v2_gap_audit.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = Path(__file__).resolve().parents[1]
    frozen_summary = json.loads(args.frozen_summary.read_text(encoding="utf-8"))
    current_summary = json.loads(args.current_summary.read_text(encoding="utf-8"))
    if "diagnostic_only" not in str(current_summary.get("dataset_id", "")):
        raise ValueError("current對照必須明確標記diagnostic_only。")
    frozen = analyze_teacher_dataset(args.frozen)
    current = analyze_teacher_dataset(args.current_diagnostic)
    _verify_summary(frozen_summary, frozen)
    _verify_summary(current_summary, current)
    frozen_seeds = sorted(int(seed) for seed in frozen["episode_details"])
    current_seeds = sorted(int(seed) for seed in current["episode_details"])
    if frozen_seeds != current_seeds:
        raise ValueError("同seed對照的seed集合不一致。")
    comparison = compare_same_seed_datasets(frozen, current)
    source_fingerprint = _source_fingerprint(root)
    readiness = evaluate_v2_readiness(
        frozen,
        current,
        comparison,
        source_fingerprint_embedded=False,
        fresh_reliability_evaluated=False,
    )
    if readiness["passed"]:
        raise RuntimeError("未執行fresh reliability卻意外通過Dataset v2 readiness。")
    output = {
        "schema_version": "p41-dataset-v2-gap-audit-v1",
        "experiment": "P4.1-Dataset-v2-gap-audit",
        "status": "FAIL_STOP_BEFORE_V2_GENERATION",
        "training_started": False,
        "formal_dataset_v2_generated": False,
        "diagnostic_same_seeds": frozen_seeds,
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "current_policy_source_fingerprint": source_fingerprint,
        "frozen_summary_dataset_gate_passed": bool(
            frozen_summary.get("dataset_gate", {}).get("passed")
        ),
        "current_summary_dataset_gate_passed": bool(
            current_summary.get("dataset_gate", {}).get("passed")
        ),
        "legacy_gate_false_positive": bool(
            current_summary.get("dataset_gate", {}).get("passed")
            and float(current["outcome_rates"].get("target_reached", 0.0)) < 0.90
        ),
        "frozen_dataset_v1": frozen,
        "current_teacher_diagnostic": current,
        "same_seed_comparison": comparison,
        "proposed_dataset_v2_readiness_gate": readiness,
        "decision": (
            "Current Teacher cannot generate Dataset v2: same-seed target reliability "
            "regressed and bottom deaths increased while the policy version stayed v2."
        ),
        "next_stage": "SEPARATE_OR_REPAIR_SIMULATOR_TEACHER_THEN_FRESH_RELIABILITY_GATE",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "legacy_gate_false_positive": output["legacy_gate_false_positive"],
                "v2_ready": readiness["passed"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
