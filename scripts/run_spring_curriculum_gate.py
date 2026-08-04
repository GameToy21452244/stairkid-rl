from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

import _common  # noqa: F401,E402

from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.simulator.gates import (
    evaluation_summary,
    oracle_selector,
    run_reachability_gate,
)
from stair_agent.training.spring_curriculum_gate import (
    EVALUATION_SEED_COUNT,
    EVALUATION_SEED_START,
    MAX_EPISODE_STEPS,
    MIN_SPRING_CONTACT_EPISODES,
    REACHABILITY_FULL_COUNT,
    REACHABILITY_SEED_START,
    REACHABILITY_SMOKE_COUNT,
    SPIKE_RATIO_RANGE,
    SPRING_RATIO_RANGE,
    engineering_checks,
    event_episode_coverage,
    seeds_overlap_reserved_fresh,
    spike_reference_config,
    spring_curriculum_config,
)


OUTPUT = Path("artifacts/spring_curriculum_v0_gate.json")
PROTOCOL = Path("reports/SPRING_CURRICULUM_V0_PROTOCOL.md")
SOURCE_FILES = (
    "src/stair_agent/learnability.py",
    "src/stair_agent/simulator/gates.py",
    "src/stair_agent/simulator/generator.py",
    "src/stair_agent/simulator/physics.py",
    "src/stair_agent/simulator/state.py",
    "src/stair_agent/training/spring_curriculum_gate.py",
    "scripts/run_spring_curriculum_gate.py",
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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
    diff = run("diff", "--binary", "--", *SOURCE_FILES)
    return {
        "commit": run("rev-parse", "HEAD").strip(),
        "dirty": bool(status.strip()),
        "status_sha256": sha256(status.encode("utf-8")).hexdigest(),
        "tracked_source_diff_sha256": sha256(diff.encode("utf-8")).hexdigest(),
    }


def _base_payload(root: Path) -> dict[str, Any]:
    reach_seeds = list(
        range(
            REACHABILITY_SEED_START,
            REACHABILITY_SEED_START + REACHABILITY_FULL_COUNT,
        )
    )
    eval_seeds = list(
        range(
            EVALUATION_SEED_START,
            EVALUATION_SEED_START + EVALUATION_SEED_COUNT,
        )
    )
    if seeds_overlap_reserved_fresh((*reach_seeds, *eval_seeds)):
        raise ValueError("Spring curriculum Gate不得使用保留的6000..6099 seeds。")
    config = spring_curriculum_config()
    reference = spike_reference_config()
    return {
        "experiment": "spring-curriculum-v0-gate",
        "status": "RUNNING",
        "passed": False,
        "dataset_generated": False,
        "training_started": False,
        "real_game_started": False,
        "protocol": {
            "path": PROTOCOL.as_posix(),
            "sha256": _sha256(root / PROTOCOL),
            "frozen_before_execution": True,
        },
        "seed_partitions": {
            "reachability_smoke": [
                REACHABILITY_SEED_START,
                REACHABILITY_SEED_START + REACHABILITY_SMOKE_COUNT - 1,
            ],
            "reachability_full": [reach_seeds[0], reach_seeds[-1]],
            "paired_evaluation": [eval_seeds[0], eval_seeds[-1]],
            "reserved_fresh_6000_6099_used": False,
        },
        "max_episode_steps": MAX_EPISODE_STEPS,
        "candidate_environment_config": asdict(config),
        "reference_environment_config": asdict(reference),
        "source_fingerprint": _source_fingerprint(root),
        "git": _git_metadata(root),
        "gates": {},
    }


def _write(payload: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _finish_failure(payload: dict[str, Any], status: str) -> int:
    payload["status"] = status
    payload["passed"] = False
    _write(payload)
    print(f"STATUS: {status}")
    print(f"OUTPUT: {OUTPUT.resolve()}")
    return 0


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫既有Gate artifact：{OUTPUT}")
    root = Path(__file__).resolve().parents[1]
    payload = _base_payload(root)
    config = spring_curriculum_config()
    reference_config = spike_reference_config()

    engineering = engineering_checks()
    payload["gates"]["engineering"] = engineering
    if not engineering["passed"]:
        return _finish_failure(payload, "FAIL_STOP_ENGINEERING")

    reach100 = run_reachability_gate(
        REACHABILITY_SMOKE_COUNT,
        seed_start=REACHABILITY_SEED_START,
        config=config,
    )
    payload["gates"]["reachability_100"] = asdict(reach100)
    if not reach100.passed:
        return _finish_failure(payload, "FAIL_STOP_REACHABILITY_100")

    reach1000 = run_reachability_gate(
        REACHABILITY_FULL_COUNT,
        seed_start=REACHABILITY_SEED_START,
        config=config,
    )
    payload["gates"]["reachability_1000"] = asdict(reach1000)
    if not reach1000.passed:
        return _finish_failure(payload, "FAIL_STOP_REACHABILITY_1000")

    spring_ratio = reach1000.realized_platform_kind_ratios["spring"]
    spike_ratio = reach1000.realized_platform_kind_ratios["spikes"]
    ratio_checks = {
        "spring_ratio_0.02_0.05": (
            SPRING_RATIO_RANGE[0] <= spring_ratio <= SPRING_RATIO_RANGE[1]
        ),
        "spike_ratio_0.035_0.07": (
            SPIKE_RATIO_RANGE[0] <= spike_ratio <= SPIKE_RATIO_RANGE[1]
        ),
    }
    payload["gates"]["spawn_ratio"] = {
        "passed": all(ratio_checks.values()),
        "checks": ratio_checks,
        "spring": spring_ratio,
        "spikes": spike_ratio,
        "spring_threshold": list(SPRING_RATIO_RANGE),
        "spikes_threshold": list(SPIKE_RATIO_RANGE),
    }
    if not all(ratio_checks.values()):
        return _finish_failure(payload, "FAIL_STOP_SPAWN_RATIO")

    eval_seeds = range(
        EVALUATION_SEED_START,
        EVALUATION_SEED_START + EVALUATION_SEED_COUNT,
    )
    oracle = evaluate_candidate(
        "oracle_full_spring_curriculum_v0",
        oracle_selector(),
        seeds=eval_seeds,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
        success_floor=10,
    )
    oracle_summary = evaluation_summary(oracle)
    oracle_spring_episodes = event_episode_coverage(oracle, "spring_contact")
    oracle_checks = {
        "reach_floor_10_at_least_0.95": (
            oracle_summary["reach_rate_floor_10"] >= 0.95
        ),
        "health_deaths_zero": (
            oracle.terminal_reasons.get("health_depleted", 0) == 0
        ),
        "spring_contact_episodes_at_least_20": (
            oracle_spring_episodes >= MIN_SPRING_CONTACT_EPISODES
        ),
    }
    payload["gates"]["oracle"] = {
        "passed": all(oracle_checks.values()),
        "checks": oracle_checks,
        "spring_contact_episodes": oracle_spring_episodes,
        "evaluation": oracle_summary,
    }
    if not all(oracle_checks.values()):
        return _finish_failure(payload, "FAIL_STOP_ORACLE")

    baseline = evaluate_candidate(
        "baseline_spring_curriculum_v0",
        baseline_selector(),
        seeds=eval_seeds,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
    )
    reference = evaluate_candidate(
        "baseline_spike_curriculum_v0_reference",
        baseline_selector(),
        seeds=eval_seeds,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=reference_config,
    )
    baseline_summary = evaluation_summary(baseline)
    reference_summary = evaluation_summary(reference)
    retention = baseline.mean_floors / max(reference.mean_floors, 1e-9)
    baseline_spring_episodes = event_episode_coverage(
        baseline, "spring_contact"
    )
    baseline_checks = {
        "mean_floor_retention_at_least_0.80": retention >= 0.80,
        "reach_floor_3_at_least_0.90": (
            baseline_summary["reach_rate_floor_3"] >= 0.90
        ),
        "health_deaths_zero": (
            baseline.terminal_reasons.get("health_depleted", 0) == 0
        ),
        "not_collapsed": not baseline.collapsed,
        "spring_contact_episodes_at_least_20": (
            baseline_spring_episodes >= MIN_SPRING_CONTACT_EPISODES
        ),
    }
    payload["gates"]["baseline"] = {
        "passed": all(baseline_checks.values()),
        "checks": baseline_checks,
        "retention_vs_spike_reference": retention,
        "spring_contact_episodes": baseline_spring_episodes,
        "evaluation": baseline_summary,
        "spike_reference_evaluation": reference_summary,
    }
    if not all(baseline_checks.values()):
        return _finish_failure(payload, "FAIL_STOP_BASELINE")

    payload["status"] = "PASS_SPRING_CURRICULUM_V0"
    payload["passed"] = True
    _write(payload)
    print(f"STATUS: {payload['status']}")
    print(f"OUTPUT: {OUTPUT.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
