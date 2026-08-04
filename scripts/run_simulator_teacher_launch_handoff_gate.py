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
)
from stair_agent.policies.simulator_teachers import SIMULATOR_TEACHER_PROFILES
from stair_agent.training.simulator_teacher_profile_gate import (
    FRESH_SEED_COUNT,
    FRESH_SEED_START,
    SAME_SEED_COUNT,
    SAME_SEED_START,
    attach_same_seed_gate,
    evaluate_fresh_reliability,
    evaluate_simulator_teacher_profile,
)


SCHEMA_VERSION = "simulator-teacher-launch-handoff-gate-v1"
BASE_PROFILE = "departure_delayed"
CANDIDATE_PROFILE = "departure_delayed_launch_handoff"
SOURCE_FILES = (
    "src/stair_agent/baseline_policy.py",
    "src/stair_agent/data/p41_dataset_gap.py",
    "src/stair_agent/envs/shaft_env.py",
    "src/stair_agent/policies/simulator_teachers.py",
    "src/stair_agent/simulator/generator.py",
    "src/stair_agent/simulator/physics.py",
    "src/stair_agent/simulator/state.py",
    "src/stair_agent/training/simulator_teacher_profile_gate.py",
    "scripts/run_simulator_teacher_launch_handoff_gate.py",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint_files(root: Path) -> dict[str, object]:
    combined = sha256()
    files: dict[str, str] = {}
    for relative in SOURCE_FILES:
        payload = (root / relative).read_bytes()
        files[relative] = sha256(payload).hexdigest()
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(payload)
        combined.update(b"\0")
    return {"sha256": combined.hexdigest(), "files": files}


def _config_fingerprint(result: dict[str, object]) -> str:
    payload = {
        "profile": result["profile"],
        "environment_config": result["environment_config"],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _assert_base_reproduced(
    result: dict[str, object],
    source_artifact: dict[str, object],
) -> None:
    expected = source_artifact["candidates"][BASE_PROFILE]
    if result["analysis"]["sha256"] != expected["analysis"]["sha256"]:
        raise RuntimeError("Delayed base trace SHA-256未重現前一Gate。")
    if result["performance"] != expected["performance"]:
        raise RuntimeError("Delayed base performance未重現前一Gate。")
    if result["deepest_floor_by_seed"] != expected["deepest_floor_by_seed"]:
        raise RuntimeError("Delayed base per-seed floors未重現前一Gate。")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frozen-dataset",
        type=Path,
        default=Path("artifacts/spike_teacher_dataset_v1.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/p41_experiment_manifest.json"),
    )
    parser.add_argument(
        "--base-artifact",
        type=Path,
        default=Path("artifacts/simulator_teacher_profile_gate_v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/simulator_teacher_launch_handoff_gate_v1.json"
        ),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected_dataset_hash = str(manifest["dataset"]["sha256"])
    observed_dataset_hash = _sha256(args.frozen_dataset)
    if observed_dataset_hash != expected_dataset_hash:
        raise RuntimeError("Frozen Dataset v1 SHA-256不符。")
    source_artifact = json.loads(
        args.base_artifact.read_text(encoding="utf-8")
    )
    if source_artifact["status"] != "FAIL_STOP_SAME_SEED_RELIABILITY":
        raise RuntimeError("來源profile Gate狀態不符。")
    if source_artifact["fresh_protocol"]["executed"]:
        raise RuntimeError("來源profile Gate不應使用fresh seeds。")

    frozen = analyze_teacher_dataset(args.frozen_dataset)
    same_seeds = list(
        range(SAME_SEED_START, SAME_SEED_START + SAME_SEED_COUNT)
    )
    base = evaluate_simulator_teacher_profile(
        SIMULATOR_TEACHER_PROFILES[BASE_PROFILE],
        same_seeds,
    )
    _assert_base_reproduced(base, source_artifact)
    base["config_fingerprint_sha256"] = _config_fingerprint(base)
    base = attach_same_seed_gate(frozen, base)

    candidate = evaluate_simulator_teacher_profile(
        SIMULATOR_TEACHER_PROFILES[CANDIDATE_PROFILE],
        same_seeds,
    )
    candidate["config_fingerprint_sha256"] = _config_fingerprint(candidate)
    candidate = attach_same_seed_gate(frozen, candidate)
    candidate["comparison_to_delayed_base"] = compare_same_seed_datasets(
        base["analysis"],
        candidate["analysis"],
    )

    same_seed_passed = bool(candidate["same_seed_gate"]["passed"])
    fresh = None
    if same_seed_passed:
        fresh = evaluate_simulator_teacher_profile(
            SIMULATOR_TEACHER_PROFILES[CANDIDATE_PROFILE],
            range(FRESH_SEED_START, FRESH_SEED_START + FRESH_SEED_COUNT),
        )
        fresh["config_fingerprint_sha256"] = _config_fingerprint(fresh)
        fresh["fresh_gate"] = evaluate_fresh_reliability(fresh)
        status = (
            "PASS_READY_FOR_FORMAL_DATASET_V2"
            if fresh["fresh_gate"]["passed"]
            else "FAIL_STOP_LAUNCH_HANDOFF_FRESH_RELIABILITY"
        )
    else:
        status = "FAIL_STOP_LAUNCH_HANDOFF_SAME_SEED"

    output = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "Simulator-Teacher-support-aware-launch-handoff",
        "status": status,
        "training_started": False,
        "real_game_started": False,
        "formal_dataset_v2_generated": False,
        "source_profile_gate": {
            "path": args.base_artifact.as_posix(),
            "sha256": _sha256(args.base_artifact),
            "status": source_artifact["status"],
            "fresh_executed": source_artifact["fresh_protocol"]["executed"],
        },
        "frozen_dataset": {
            "path": args.frozen_dataset.as_posix(),
            "sha256": observed_dataset_hash,
            "records": frozen["records"],
            "episodes": frozen["episodes"],
        },
        "same_seed_protocol": {
            "seed_range": [
                SAME_SEED_START,
                SAME_SEED_START + SAME_SEED_COUNT - 1,
            ],
            "base_profile": BASE_PROFILE,
            "candidate_profile": CANDIDATE_PROFILE,
            "only_one_new_candidate": True,
            "base_reproduced": True,
        },
        "fresh_protocol": {
            "executed": fresh is not None,
            "seed_range": [
                FRESH_SEED_START,
                FRESH_SEED_START + FRESH_SEED_COUNT - 1,
            ],
            "episodes": FRESH_SEED_COUNT,
        },
        "source_fingerprint": _fingerprint_files(root),
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "base": base,
        "candidate": candidate,
        "selected_profile": CANDIDATE_PROFILE if same_seed_passed else None,
        "fresh_reliability": fresh,
        "next_stage": (
            "GENERATE_FORMAL_DATASET_V2"
            if status == "PASS_READY_FOR_FORMAL_DATASET_V2"
            else "STOP_AND_REVIEW_LAUNCH_HANDOFF"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "base": base["performance"],
                "candidate": candidate["performance"],
                "candidate_same_seed_gate": candidate["same_seed_gate"],
                "fresh_gate_passed": (
                    None if fresh is None else fresh["fresh_gate"]["passed"]
                ),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
