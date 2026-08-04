from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

import _common  # noqa: F401,E402

from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.gates import oracle_selector
from stair_agent.training.spring_curriculum_gate import (
    spike_reference_config,
    spring_curriculum_config,
)
from stair_agent.training.spring_oracle_escape_gate import (
    DEVELOPMENT_SEEDS,
    HOLDOUT_SEEDS,
    MAX_EPISODE_STEPS,
    baseline_gate,
    oracle_gate,
)


OUTPUT = Path("artifacts/spring_oracle_escape_gate_v1.json")
PROTOCOL = Path("reports/SPRING_ORACLE_ESCAPE_CANDIDATE_PROTOCOL.md")
SOURCE_FILES = (
    "src/stair_agent/learnability.py",
    "src/stair_agent/policies/simulator_teachers.py",
    "src/stair_agent/simulator/physics.py",
    "src/stair_agent/simulator/state.py",
    "src/stair_agent/training/spring_curriculum_gate.py",
    "src/stair_agent/training/spring_oracle_escape_gate.py",
    "scripts/run_spring_oracle_escape_gate.py",
)


def _source_fingerprint(root: Path) -> dict[str, object]:
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


def _git_metadata(root: Path) -> dict[str, object]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout

    status = run("status", "--porcelain=v1")
    return {
        "commit": run("rev-parse", "HEAD").strip(),
        "dirty": bool(status.strip()),
        "status_sha256": sha256(status.encode("utf-8")).hexdigest(),
    }


def _write(payload: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stop(payload: dict[str, Any], status: str) -> int:
    payload["status"] = status
    payload["passed"] = False
    _write(payload)
    print(f"STATUS: {status}")
    print(f"OUTPUT: {OUTPUT.resolve()}")
    return 0


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫既有Gate artifact：{OUTPUT}")
    if any(6000 <= seed <= 6099 for seed in (*DEVELOPMENT_SEEDS, *HOLDOUT_SEEDS)):
        raise ValueError("Spring Oracle Gate不得使用6000..6099。")
    root = Path(__file__).resolve().parents[1]
    config = spring_curriculum_config()
    reference_config = spike_reference_config()
    oracle = OracleFull(enable_spring_escape=True, spring_clearance=2.0)
    payload: dict[str, Any] = {
        "experiment": "spring-oracle-escape-gate-v1",
        "status": "RUNNING",
        "passed": False,
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
        "oracle_policy_version": oracle.policy_version,
        "protocol": {
            "path": PROTOCOL.as_posix(),
            "sha256": sha256((root / PROTOCOL).read_bytes()).hexdigest(),
            "frozen_before_execution": True,
        },
        "seed_partitions": {
            "development": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
            "untouched_holdout": [HOLDOUT_SEEDS[0], HOLDOUT_SEEDS[-1]],
            "reserved_fresh_6000_6099_used": False,
        },
        "max_episode_steps": MAX_EPISODE_STEPS,
        "candidate_environment_config": asdict(config),
        "reference_environment_config": asdict(reference_config),
        "source_fingerprint": _source_fingerprint(root),
        "git": _git_metadata(root),
        "gates": {},
    }

    development = evaluate_candidate(
        "oracle_full_v2_spring_clearance_development",
        oracle_selector(oracle),
        seeds=DEVELOPMENT_SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
        success_floor=10,
    )
    payload["gates"]["development_oracle"] = oracle_gate(development)
    if not payload["gates"]["development_oracle"]["passed"]:
        return _stop(payload, "FAIL_STOP_DEVELOPMENT_ORACLE")

    holdout_oracle = evaluate_candidate(
        "oracle_full_v2_spring_clearance_holdout",
        oracle_selector(
            OracleFull(enable_spring_escape=True, spring_clearance=2.0)
        ),
        seeds=HOLDOUT_SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
        success_floor=10,
    )
    payload["gates"]["holdout_oracle"] = oracle_gate(holdout_oracle)
    if not payload["gates"]["holdout_oracle"]["passed"]:
        return _stop(payload, "FAIL_STOP_HOLDOUT_ORACLE")

    candidate_baseline = evaluate_candidate(
        "baseline_spring_curriculum_v0_holdout",
        baseline_selector(),
        seeds=HOLDOUT_SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
    )
    reference_baseline = evaluate_candidate(
        "baseline_spike_curriculum_v0_holdout_reference",
        baseline_selector(),
        seeds=HOLDOUT_SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=reference_config,
    )
    payload["gates"]["holdout_baseline"] = baseline_gate(
        candidate_baseline,
        reference_baseline,
    )
    if not payload["gates"]["holdout_baseline"]["passed"]:
        return _stop(payload, "FAIL_STOP_HOLDOUT_BASELINE")

    payload["status"] = "PASS_SPRING_ORACLE_ESCAPE_AND_BASELINE"
    payload["passed"] = True
    _write(payload)
    print(f"STATUS: {payload['status']}")
    print(f"OUTPUT: {OUTPUT.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
