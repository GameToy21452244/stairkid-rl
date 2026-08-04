from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import _common  # noqa: F401,E402

from stair_agent.data.p41_dataset_gap import analyze_teacher_dataset
from stair_agent.policies.simulator_teachers import SIMULATOR_TEACHER_PROFILES
from stair_agent.training.simulator_teacher_profile_gate import (
    FRESH_SEED_COUNT,
    FRESH_SEED_START,
    SAME_SEED_COUNT,
    SAME_SEED_START,
    attach_same_seed_gate,
    evaluate_fresh_reliability,
    evaluate_simulator_teacher_profile,
    select_same_seed_candidate,
)


SCHEMA_VERSION = "simulator-teacher-profile-gate-v1"
PROFILE_ORDER = ("current", "departure_delayed", "departure_disabled")
SOURCE_FILES = (
    "src/stair_agent/baseline_policy.py",
    "src/stair_agent/data/p41_dataset_gap.py",
    "src/stair_agent/envs/shaft_env.py",
    "src/stair_agent/policies/simulator_teachers.py",
    "src/stair_agent/simulator/generator.py",
    "src/stair_agent/simulator/physics.py",
    "src/stair_agent/simulator/state.py",
    "src/stair_agent/training/simulator_teacher_profile_gate.py",
    "scripts/run_simulator_teacher_profile_gate.py",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprint(root: Path) -> dict[str, object]:
    combined = sha256()
    files: dict[str, str] = {}
    for relative in SOURCE_FILES:
        payload = (root / relative).read_bytes()
        digest = sha256(payload).hexdigest()
        files[relative] = digest
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(payload)
        combined.update(b"\0")
    return {"sha256": combined.hexdigest(), "files": files}


def _config_fingerprint(candidate: dict[str, object]) -> str:
    payload = {
        "profile": candidate["profile"],
        "environment_config": candidate["environment_config"],
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
        "--output",
        type=Path,
        default=Path("artifacts/simulator_teacher_profile_gate_v1.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected_hash = str(manifest["dataset"]["sha256"])
    observed_hash = _sha256(args.frozen_dataset)
    if observed_hash != expected_hash:
        raise RuntimeError(
            "Frozen Dataset v1 SHA-256不符，拒絕執行profile Gate。"
        )
    frozen = analyze_teacher_dataset(args.frozen_dataset)
    expected_seeds = list(range(SAME_SEED_START, SAME_SEED_START + SAME_SEED_COUNT))
    if sorted(int(seed) for seed in frozen["episode_details"]) != expected_seeds:
        raise RuntimeError("Frozen Dataset v1 seed集合不是2000～2059。")

    candidates: dict[str, dict[str, object]] = {}
    for name in PROFILE_ORDER:
        result = evaluate_simulator_teacher_profile(
            SIMULATOR_TEACHER_PROFILES[name],
            expected_seeds,
        )
        result["config_fingerprint_sha256"] = _config_fingerprint(result)
        candidates[name] = attach_same_seed_gate(frozen, result)
    selected = select_same_seed_candidate(candidates)

    fresh = None
    if selected is None:
        status = "FAIL_STOP_SAME_SEED_RELIABILITY"
    else:
        fresh_seeds = range(FRESH_SEED_START, FRESH_SEED_START + FRESH_SEED_COUNT)
        fresh = evaluate_simulator_teacher_profile(
            SIMULATOR_TEACHER_PROFILES[selected],
            fresh_seeds,
        )
        fresh["config_fingerprint_sha256"] = _config_fingerprint(fresh)
        fresh["fresh_gate"] = evaluate_fresh_reliability(fresh)
        status = (
            "PASS_READY_FOR_FORMAL_DATASET_V2"
            if fresh["fresh_gate"]["passed"]
            else "FAIL_STOP_FRESH_RELIABILITY"
        )

    output = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "Simulator-Teacher-profile-bounded-micro-ablation",
        "status": status,
        "training_started": False,
        "real_game_started": False,
        "formal_dataset_v2_generated": False,
        "frozen_dataset": {
            "path": args.frozen_dataset.as_posix(),
            "sha256": observed_hash,
            "records": frozen["records"],
            "episodes": frozen["episodes"],
            "policy_versions": frozen["policy_versions"],
        },
        "same_seed_protocol": {
            "seed_range": [
                SAME_SEED_START,
                SAME_SEED_START + SAME_SEED_COUNT - 1,
            ],
            "candidate_order": list(PROFILE_ORDER),
            "selection_order": [
                "health_death",
                "bottom_death",
                "q25",
                "cvar25",
                "reach_floor_10",
                "release_bridged_reversal",
                "median",
                "mean",
            ],
        },
        "fresh_protocol": {
            "executed": fresh is not None,
            "seed_range": [
                FRESH_SEED_START,
                FRESH_SEED_START + FRESH_SEED_COUNT - 1,
            ],
            "episodes": FRESH_SEED_COUNT,
        },
        "source_fingerprint": _source_fingerprint(root),
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "candidates": candidates,
        "selected_profile": selected,
        "fresh_reliability": fresh,
        "next_stage": (
            "GENERATE_FORMAL_DATASET_V2"
            if status == "PASS_READY_FOR_FORMAL_DATASET_V2"
            else "STOP_AND_REVIEW_SIMULATOR_TEACHER"
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
                "selected_profile": selected,
                "same_seed": {
                    name: {
                        "passed": result["same_seed_gate"]["passed"],
                        **result["performance"],
                    }
                    for name, result in candidates.items()
                },
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
