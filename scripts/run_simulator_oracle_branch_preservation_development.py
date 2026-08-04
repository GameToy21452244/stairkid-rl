"""Run only the frozen branch-preservation development partition."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import _common  # noqa: F401,E402

from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.training.simulator_oracle_branch_preservation_development import (
    aggregate_branch_metrics,
    episode_reproducible,
    paired_branch_diagnostics,
    run_branch_episode,
    validate_development_execution_seeds,
)
from stair_agent.training.simulator_oracle_branch_preservation_gate import (
    CONDITIONAL_DEVELOPMENT_EXTENSION,
    PRIMARY_DEVELOPMENT_SEEDS,
    branch_preservation_development_checks,
    incomplete_stage_payload,
    select_development_seeds,
)
from stair_agent.training.simulator_v03_edge_gate import edge_fidelity_config


PROTOCOL = Path("reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md")
PROTOCOL_ARTIFACT = Path(
    "artifacts/simulator_oracle_branch_preservation_protocol_v1.json"
)
LEDGER = Path(
    "artifacts/simulator_oracle_branch_preservation_seed_ledger_v1.json"
)
IMPLEMENTATION = Path(
    "artifacts/simulator_oracle_branch_preservation_implementation_v1.json"
)
OUTPUT = Path(
    "artifacts/simulator_oracle_branch_preservation_development_v1.json"
)
COMBINED_OUTPUT = Path(
    "artifacts/simulator_oracle_branch_preservation_gate_v1.json"
)
JOURNAL = Path("artifacts/colab_readiness_stage_journal.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _source_checks() -> tuple[dict[str, bool], dict[str, str]]:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    expected = implementation["formal_source_hashes"]
    actual = {path: _sha256(Path(path)) for path in expected}
    checks = {
        "implementation_status_ready": (
            implementation.get("status") == "READY_FOR_DEVELOPMENT"
        ),
        "all_formal_source_hashes_match": actual == expected,
        "protocol_hash_matches": (
            implementation.get("protocol_sha256") == _sha256(PROTOCOL)
        ),
        "protocol_artifact_hash_matches": (
            implementation.get("protocol_artifact_sha256")
            == _sha256(PROTOCOL_ARTIFACT)
        ),
        "seed_ledger_hash_matches": (
            implementation.get("seed_ledger_sha256") == _sha256(LEDGER)
        ),
        "combined_holdout_artifact_absent": not COMBINED_OUTPUT.exists(),
    }
    return checks, actual


def _evaluate(seeds: tuple[int, ...], execution: str):
    return [run_branch_episode(seed, execution) for seed in seeds]


def _run(started_at: str) -> dict[str, object]:
    source_checks, source_hashes = _source_checks()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    holdout_partition = ledger["partitions"]["one_time_holdout"]
    base = {
        "schema_version": "simulator-oracle-branch-preservation-development-v1",
        "formal_gate": True,
        "development_only": True,
        "started_at": started_at,
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "protocol_artifact": str(PROTOCOL_ARTIFACT),
        "protocol_artifact_sha256": _sha256(PROTOCOL_ARTIFACT),
        "seed_ledger": str(LEDGER),
        "seed_ledger_sha256": _sha256(LEDGER),
        "source_checks": source_checks,
        "source_hashes": source_hashes,
        "holdout": {
            "partition": (
                f"{holdout_partition['start']}-{holdout_partition['end']}"
            ),
            "used": False,
            "started_at": None,
        },
        "holdout_used": False,
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
    }
    if not all(source_checks.values()):
        return {
            **base,
            "status": "FAIL_STOP_BRANCH_PRESERVATION_SOURCE_INTEGRITY",
            "passed": False,
            "development_completed": False,
            "completed_at": _utc_now(),
            "stop_reason": "source_integrity",
        }

    runtime: dict[str, float] = {}
    phase_started = perf_counter()
    primary_reference = _evaluate(PRIMARY_DEVELOPMENT_SEEDS, "cached")
    runtime["primary_v6_seconds"] = perf_counter() - phase_started
    primary_v6_top_failures = sum(
        item.terminal_reason == "top" for item in primary_reference
    )
    seeds = select_development_seeds(
        v6_primary_top_failures=primary_v6_top_failures
    )
    validate_development_execution_seeds(seeds)
    extension_used = len(seeds) > len(PRIMARY_DEVELOPMENT_SEEDS)
    reference = list(primary_reference)
    if extension_used:
        phase_started = perf_counter()
        reference.extend(_evaluate(
            CONDITIONAL_DEVELOPMENT_EXTENSION,
            "cached",
        ))
        runtime["extension_v6_seconds"] = perf_counter() - phase_started
    v6_top_failures = sum(item.terminal_reason == "top" for item in reference)

    phase_started = perf_counter()
    reachability = run_reachability_gate(
        len(seeds),
        config=edge_fidelity_config(),
        seed_start=seeds[0],
    )
    runtime["reachability_seconds"] = perf_counter() - phase_started
    reference_metrics = aggregate_branch_metrics(reference)
    if v6_top_failures == 0:
        runtime["total_seconds"] = sum(runtime.values())
        return {
            **base,
            "status": "INSUFFICIENT_EVIDENCE_NO_V6_TOP_FAILURE",
            "passed": False,
            "development_completed": True,
            "completed_at": _utc_now(),
            "development": {
                "partition": [seeds[0], seeds[-1]],
                "seed_count": len(seeds),
                "conditional_extension_used": extension_used,
                "primary_v6_top_failures": primary_v6_top_failures,
                "combined_v6_top_failures": 0,
                "reachability": reachability.__dict__,
                "v6": reference_metrics,
                "candidate": None,
                "checks": None,
            },
            "runtime": runtime,
            "stop_reason": "no v6 top failure in pre-frozen 200-seed development",
        }

    phase_started = perf_counter()
    candidate = _evaluate(seeds, "branch_preserved")
    runtime["candidate_seconds"] = perf_counter() - phase_started
    phase_started = perf_counter()
    duplicate_reference = _evaluate(seeds, "cached")
    duplicate_candidate = _evaluate(seeds, "branch_preserved")
    runtime["duplicate_replay_seconds"] = perf_counter() - phase_started

    candidate_metrics = aggregate_branch_metrics(candidate)
    paired_rows = [
        paired_branch_diagnostics(old, new)
        for old, new in zip(reference, candidate)
    ]
    reproducible = all(
        episode_reproducible(first, second)
        for first, second in zip(reference, duplicate_reference)
    ) and all(
        episode_reproducible(first, second)
        for first, second in zip(candidate, duplicate_candidate)
    )
    non_terminal_rows = [
        item for item in paired_rows if item["non_terminal_reference_path"]
    ]
    non_terminal_identity = bool(non_terminal_rows) and all(
        item["action_sequence_identical"] for item in non_terminal_rows
    )
    v6_success_regressions = sum(
        bool(item["v6_success_regressed"]) for item in paired_rows
    )
    v6_top_repaired = sum(
        bool(item["v6_top_failure_repaired"]) for item in paired_rows
    )
    checks = branch_preservation_development_checks(
        reference=reference_metrics,
        candidate=candidate_metrics,
        v6_success_regressions=v6_success_regressions,
        v6_top_failures=v6_top_failures,
        v6_top_failures_repaired=v6_top_repaired,
        non_terminal_paths_identical=non_terminal_identity,
        reproducible=reproducible,
        planner_bounds_passed=bool(
            candidate_metrics["all_plans_within_bounds"]
        ),
    )
    checks["reachability_pass"] = bool(reachability.passed)
    passed = all(checks.values())
    runtime["total_seconds"] = sum(runtime.values())
    outcomes = Counter(str(item["outcome"]) for item in paired_rows)
    divergences = Counter(
        "identical"
        if item["first_divergence"] is None
        else str(item["first_divergence"]["classification"])
        for item in paired_rows
    )
    return {
        **base,
        "status": (
            "PASS_BRANCH_PRESERVATION_DEVELOPMENT"
            if passed
            else "FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT"
        ),
        "passed": passed,
        "development_completed": True,
        "completed_at": _utc_now(),
        "environment_version": edge_fidelity_config().effective_environment_version,
        "oracle_reference": "oracle-full-v6-bounded-route-planner",
        "oracle_candidate": "oracle-full-v9-terminal-branch-preserving",
        "development": {
            "partition": [seeds[0], seeds[-1]],
            "seed_count": len(seeds),
            "conditional_extension_used": extension_used,
            "primary_v6_top_failures": primary_v6_top_failures,
            "combined_v6_top_failures": v6_top_failures,
            "reachability": reachability.__dict__,
            "v6": reference_metrics,
            "candidate": candidate_metrics,
            "paired_outcomes": {
                name: int(outcomes.get(name, 0))
                for name in (
                    "both_success",
                    "v6_only_success",
                    "candidate_only_success",
                    "both_failure",
                )
            },
            "v6_success_regressions": v6_success_regressions,
            "v6_top_failures_repaired": v6_top_repaired,
            "non_terminal_paths_identical": non_terminal_identity,
            "first_divergence_taxonomy": dict(divergences),
            "reproducibility": {
                "duplicate_replay_pass": reproducible,
            },
            "checks": checks,
            "per_seed_paired_results": paired_rows,
        },
        "runtime": runtime,
        "stop_reason": None if passed else "development Gate failed",
        "next_stage": (
            "run_simulator_oracle_branch_preservation_holdout.py"
            if passed
            else "BLOCKED_WITH_EVIDENCE"
        ),
    }


def _update_journal(
    *,
    started_at: str,
    payload: dict[str, object] | None,
    reason: str | None = None,
) -> None:
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    phase = (journal.setdefault("phases", {})).setdefault(
        "branch_preservation_development",
        {},
    )
    phase.update({
        "started_at": started_at,
        "completed_at": None if payload is None else payload.get("completed_at"),
        "protocol": str(PROTOCOL),
        "protocol_hash": _sha256(PROTOCOL),
        "seed_partition": "18000-18099; conditional 18100-18199",
        "status": "INCOMPLETE" if payload is None else payload["status"],
        "artifact_paths": [] if payload is None else [str(OUTPUT)],
        "stop_reason": reason if payload is None else payload.get("stop_reason"),
    })
    if payload is not None and OUTPUT.exists():
        phase["artifact_sha256"] = _sha256(OUTPUT)
    journal["current_phase"] = "branch_preservation_development"
    journal["overall_status"] = (
        "INCOMPLETE"
        if payload is None
        else "AWAITING_ONE_TIME_HOLDOUT"
        if payload.get("passed")
        else "BLOCKED_WITH_EVIDENCE"
    )
    journal["updated_at"] = _utc_now()
    _write_json(JOURNAL, journal)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫formal development artifact：{OUTPUT}")
    for path in (PROTOCOL, PROTOCOL_ARTIFACT, LEDGER, IMPLEMENTATION, JOURNAL):
        if not path.exists():
            raise FileNotFoundError(path)
    started_at = _utc_now()
    _update_journal(started_at=started_at, payload=None, reason="running")
    try:
        payload = _run(started_at)
        _write_json(OUTPUT, payload)
    except BaseException as exc:
        incomplete = {
            **incomplete_stage_payload(
                stage="development",
                reason=f"{type(exc).__name__}: {exc}",
            ),
            "started_at": started_at,
            "completed_at": _utc_now(),
            "protocol": str(PROTOCOL),
            "protocol_sha256": _sha256(PROTOCOL),
            "holdout_used": False,
        }
        _write_json(OUTPUT, incomplete)
        _update_journal(
            started_at=started_at,
            payload=None,
            reason=incomplete["stop_reason"],
        )
        raise
    _update_journal(started_at=started_at, payload=payload)
    print(json.dumps({
        "status": payload["status"],
        "artifact": str(OUTPUT),
        "development": payload.get("development"),
        "runtime": payload.get("runtime"),
        "holdout_used": payload["holdout_used"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
