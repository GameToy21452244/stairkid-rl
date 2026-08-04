"""Run only the frozen Oracle v8 development partition and write evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import _common  # noqa: F401,E402

from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.training.simulator_oracle_v8_development_artifact import (
    DEVELOPMENT_SEEDS,
    aggregate_episode_metrics,
    paired_episode_diagnostics,
    paired_outcome_metrics,
    result_reproduces_formal,
    run_development_episode,
    switch_inflation_checks,
    validate_development_seeds,
)
from stair_agent.training.simulator_oracle_v8_gate import (
    ORACLE_V8_POLICY_VERSION,
    edge_evaluation_from_dict,
    terminal_audit_source_checks,
    terminal_guard_oracle_factory,
    v8_development_checks,
)
from stair_agent.training.simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    edge_fidelity_config,
    evaluate_edge_candidate,
)


FORMAL_V7 = Path("artifacts/simulator_oracle_robustness_gate_v1.json")
TERMINAL_AUDIT = Path("artifacts/simulator_oracle_terminal_plan_audit_v1.json")
PROTOCOL = Path("reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_PROTOCOL.md")
ORACLE_SOURCE = Path("src/stair_agent/policies/simulator_teachers.py")
PLANNER_SOURCE = Path("src/stair_agent/policies/simulator_route_planner.py")
GATE_HELPER = Path("src/stair_agent/training/simulator_oracle_v8_gate.py")
COMBINED_RUNNER = Path("scripts/run_simulator_oracle_v8_gate.py")
OUTPUT = Path(
    "artifacts/simulator_oracle_v8_terminal_guard_development_v1.json"
)
COMBINED_OUTPUT = Path(
    "artifacts/simulator_oracle_v8_terminal_guard_gate_v1.json"
)
JOURNAL = Path("artifacts/colab_readiness_stage_journal.json")

EXPECTED_HASHES = {
    FORMAL_V7: "a8d6bbc14079e477dd99281011a3f4809692d749c3dc17a2266df0f8e74cf63a",
    TERMINAL_AUDIT: "d4189c59bef8071c57f915cafc2db564242cc4adbed847b28b6a87a6bcce4354",
    PROTOCOL: "78df06c393ff8123d559a98657fadbd791eee3ce3f532aa6a3fabe2cc3f5289e",
    ORACLE_SOURCE: "18018669ed6e97056be20bf07642afd766dfa0b3c0bf4e232e476c26c295cbbb",
    PLANNER_SOURCE: "c52671e08c607d919e8c83b5f63b5c0faaf8b92541322996bdc736b66444a394",
    GATE_HELPER: "bcdab11c8bc52ed8de0f773c0efd350a4c7286f204bb7aae8b9bde7056d209cd",
    COMBINED_RUNNER: "6d4f6f81b14265893ecf05587712408dd35725cae13355143e1c365b7ac16729",
}


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


def _started_journal(
    started_at: str,
    attempt_history: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "colab-readiness-stage-journal-v1",
        "overall_status": "INCOMPLETE",
        "current_phase": "oracle_v8_development",
        "phases": {
            "oracle_v8_development": {
                "development_started": True,
                "development_completed": False,
                "development_gate_result": "INCOMPLETE",
                "attempt": len(attempt_history) + 1,
                "started_at": started_at,
                "completed_at": None,
                "protocol": str(PROTOCOL),
                "protocol_hash": _sha256(PROTOCOL),
                "source": str(ORACLE_SOURCE),
                "source_hash": _sha256(ORACLE_SOURCE),
                "development_runner_hash": _sha256(Path(__file__)),
                "seed_partition": {
                    "role": "development",
                    "start": DEVELOPMENT_SEEDS[0],
                    "end": DEVELOPMENT_SEEDS[-1],
                    "count": len(DEVELOPMENT_SEEDS),
                },
                "status": "INCOMPLETE",
                "artifact_paths": [],
                "stop_reason": (
                    "formal development is running; completion has not yet "
                    "been recorded"
                ),
            }
        },
        "holdout": {
            "partition": "17000-17099",
            "used": False,
            "started_at": None,
        },
        "dataset_generated": False,
        "training_started": False,
        "real_game_started": False,
        "attempt_history": attempt_history,
        "updated_at": started_at,
    }


def _source_checks(
    formal: dict[str, object],
    audit: dict[str, object],
) -> dict[str, bool]:
    expected_reference = formal["development"]["reference_v6"]
    reference_seeds = tuple(
        int(row["seed"]) for row in expected_reference["episode_results"]
    )
    checks = {
        "all_frozen_hashes_match": all(
            path.exists() and _sha256(path) == expected
            for path, expected in EXPECTED_HASHES.items()
        ),
        "v7_formal_status_is_development_fail": (
            formal.get("status")
            == "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"
        ),
        "v7_formal_holdout_unused": formal["holdout"]["used"] is False,
        "development_seeds_exact": (
            reference_seeds == DEVELOPMENT_SEEDS
            and validate_development_seeds(reference_seeds)
            == DEVELOPMENT_SEEDS
        ),
        "v6_reference_reach10_is_0_96": (
            expected_reference["reach_floor_10_rate"] == 0.96
        ),
        "terminal_audit_source_hash_matches": (
            audit.get("source_artifact_sha256") == _sha256(FORMAL_V7)
        ),
        "terminal_audit_protocol_hash_matches": (
            audit.get("protocol_sha256")
            == _sha256(Path(str(audit["protocol"])))
        ),
        "combined_v8_artifact_absent": not COMBINED_OUTPUT.exists(),
    }
    checks.update({
        f"terminal_audit_{key}": value
        for key, value in terminal_audit_source_checks(audit).items()
    })
    return checks


def _run_development(started_at: str) -> dict[str, object]:
    phase_times: dict[str, float] = {}
    formal = json.loads(FORMAL_V7.read_text(encoding="utf-8"))
    audit = json.loads(TERMINAL_AUDIT.read_text(encoding="utf-8"))
    source_checks = _source_checks(formal, audit)
    if not all(source_checks.values()):
        return {
            "schema_version": (
                "simulator-oracle-v8-terminal-guard-development-v1"
            ),
            "status": "FAIL_STOP_V8_SOURCE_INTEGRITY",
            "passed": False,
            "development_completed": False,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "source_checks": source_checks,
            "holdout": {"partition": "17000-17099", "used": False},
            "training_started": False,
            "dataset_generated": False,
            "real_game_started": False,
        }

    config = edge_fidelity_config()
    reference_v6 = edge_evaluation_from_dict(
        formal["development"]["reference_v6"]
    )

    phase_started = perf_counter()
    reachability = run_reachability_gate(
        len(DEVELOPMENT_SEEDS),
        config=config,
        seed_start=DEVELOPMENT_SEEDS[0],
    )
    phase_times["reachability_seconds"] = perf_counter() - phase_started

    candidate_v8 = None
    development_checks = None
    if reachability.passed:
        phase_started = perf_counter()
        candidate_v8 = evaluate_edge_candidate(
            ORACLE_V8_POLICY_VERSION,
            terminal_guard_oracle_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        phase_times["formal_v8_evaluation_seconds"] = (
            perf_counter() - phase_started
        )
        development_checks = v8_development_checks(
            reference_v6,
            candidate_v8,
        )

    if candidate_v8 is None:
        return {
            "schema_version": (
                "simulator-oracle-v8-terminal-guard-development-v1"
            ),
            "status": "FAIL_STOP_V8_DEVELOPMENT",
            "passed": False,
            "development_completed": True,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "protocol": str(PROTOCOL),
            "protocol_sha256": _sha256(PROTOCOL),
            "source_checks": source_checks,
            "development": {
                "seeds": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
                "reachability": asdict(reachability),
                "checks": None,
            },
            "runtime": phase_times,
            "holdout": {"partition": "17000-17099", "used": False},
            "training_started": False,
            "dataset_generated": False,
            "real_game_started": False,
        }

    phase_started = perf_counter()
    reference_traces = []
    candidate_traces = []
    paired_rows = []
    for seed in DEVELOPMENT_SEEDS:
        reference_trace = run_development_episode(seed, "cached")
        candidate_trace = run_development_episode(seed, "terminal_guarded")
        reference_traces.append(reference_trace)
        candidate_traces.append(candidate_trace)
        paired_rows.append(
            paired_episode_diagnostics(reference_trace, candidate_trace)
        )
    phase_times["paired_diagnostic_replay_seconds"] = (
        perf_counter() - phase_started
    )

    reference_metrics = aggregate_episode_metrics(reference_traces)
    candidate_metrics = aggregate_episode_metrics(candidate_traces)
    formal_reference_by_seed = {
        int(row["seed"]): row
        for row in formal["development"]["reference_v6"]["episode_results"]
    }
    formal_candidate_by_seed = {
        item.seed: asdict(item) for item in candidate_v8.episode_results
    }
    v6_reproduced = all(
        result_reproduces_formal(
            item,
            formal_reference_by_seed[item.seed],
        )
        for item in reference_traces
    )
    v8_reproduced = all(
        result_reproduces_formal(
            item,
            formal_candidate_by_seed[item.seed],
        )
        for item in candidate_traces
    )
    non_terminal_rows = [
        row for row in paired_rows if row["non_terminal_reference_path"]
    ]
    non_terminal_paths_identical = bool(non_terminal_rows) and all(
        row["action_sequence_identical"] for row in non_terminal_rows
    )
    switch_checks = switch_inflation_checks(
        v6_switches=int(reference_metrics["action_switch_count"]),
        v6_steps=int(reference_metrics["steps"]),
        v8_switches=int(candidate_metrics["action_switch_count"]),
        v8_steps=int(candidate_metrics["steps"]),
        non_terminal_paths_identical=non_terminal_paths_identical,
    )
    reproducibility = {
        "v6_replay_matches_formal_reference_per_seed": v6_reproduced,
        "v8_duplicate_replay_matches_formal_evaluation_per_seed": (
            v8_reproduced
        ),
    }
    diagnostic_checks = {
        "health_deaths_zero": candidate_metrics["health_deaths"] == 0,
        "all_plans_within_fixed_bounds": bool(
            candidate_metrics["all_plans_within_bounds"]
        ),
        **reproducibility,
        **switch_checks,
    }
    paired_outcomes = paired_outcome_metrics(
        (item.result_dict() for item in reference_traces),
        (item.result_dict() for item in candidate_traces),
    )
    divergence_taxonomy = Counter(
        "identical"
        if row["first_divergence"] is None
        else str(row["first_divergence"]["classification"])
        for row in paired_rows
    )
    gate_passed = (
        reachability.passed
        and bool(development_checks)
        and all(development_checks.values())
        and all(diagnostic_checks.values())
    )
    status = (
        "PASS_V8_DEVELOPMENT_AWAITING_HOLDOUT"
        if gate_passed
        else "FAIL_STOP_V8_DEVELOPMENT"
    )
    completed_at = _utc_now()
    phase_times["total_seconds"] = sum(phase_times.values())
    return {
        "schema_version": "simulator-oracle-v8-terminal-guard-development-v1",
        "formal_gate": True,
        "development_only": True,
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "status": status,
        "passed": gate_passed,
        "development_completed": True,
        "started_at": started_at,
        "completed_at": completed_at,
        "environment_version": config.effective_environment_version,
        "oracle_reference": "oracle-full-v6-bounded-route-planner",
        "oracle_candidate": ORACLE_V8_POLICY_VERSION,
        "source_checks": source_checks,
        "source_hashes": {
            **{str(path): _sha256(path) for path in EXPECTED_HASHES},
            str(Path(__file__)): _sha256(Path(__file__)),
        },
        "development": {
            "seeds": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
            "seed_count": len(DEVELOPMENT_SEEDS),
            "reachability": asdict(reachability),
            "v6": reference_metrics,
            "v8": {
                **candidate_metrics,
                "safety_violations": candidate_v8.invariant_violation_count,
                "episodes_with_safety_violations": (
                    candidate_v8.episodes_with_violations
                ),
                "max_action_share": candidate_v8.max_action_share,
                "collapsed": candidate_v8.collapsed,
            },
            "frozen_protocol_checks": development_checks,
            "diagnostic_checks": diagnostic_checks,
            "switch_inflation_definition": (
                "v8 action switches per 100 steps must be <= 1.05 times v6; "
                "all v6 paths without terminal-plan exposure must be identical"
            ),
            "paired_outcomes": paired_outcomes,
            "first_divergence_taxonomy": dict(divergence_taxonomy),
            "terminal_plan_exposure": {
                "v6_episodes": reference_metrics[
                    "terminal_plan_exposed_episodes"
                ],
                "v6_plans": reference_metrics["terminal_plan_count"],
                "v8_episodes": candidate_metrics[
                    "terminal_plan_exposed_episodes"
                ],
                "v8_plans": candidate_metrics["terminal_plan_count"],
            },
            "reproducibility": reproducibility,
            "per_seed_paired_results": paired_rows,
        },
        "runtime": phase_times,
        "holdout": {
            "partition": "17000-17099",
            "used": False,
            "reachability": None,
            "oracle": None,
            "observable": None,
        },
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
        "next_stage": (
            "await explicit authorization for one-time holdout"
            if gate_passed
            else "BLOCKED_WITH_EVIDENCE"
        ),
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫formal development artifact：{OUTPUT}")
    required = tuple(EXPECTED_HASHES)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"缺少formal source：{missing}")
    started_at = _utc_now()
    attempt_history: list[dict[str, object]] = []
    if JOURNAL.exists():
        previous = json.loads(JOURNAL.read_text(encoding="utf-8"))
        attempt_history.extend(previous.get("attempt_history") or [])
        previous_phase = (previous.get("phases") or {}).get(
            "oracle_v8_development"
        )
        if previous_phase and previous_phase.get("development_started"):
            attempt_history.append({
                "attempt": previous_phase.get("attempt", 1),
                "started_at": previous_phase.get("started_at"),
                "ended_at": previous.get("updated_at"),
                "status": previous_phase.get("status"),
                "development_gate_result": previous_phase.get(
                    "development_gate_result"
                ),
                "stop_reason": previous_phase.get("stop_reason"),
                "artifact_paths": previous_phase.get("artifact_paths") or [],
                "holdout_used": (previous.get("holdout") or {}).get(
                    "used", False
                ),
            })
    journal = _started_journal(started_at, attempt_history)
    _write_json(JOURNAL, journal)
    try:
        payload = _run_development(started_at)
        _write_json(OUTPUT, payload)
    except BaseException as exc:
        phase = journal["phases"]["oracle_v8_development"]
        phase["status"] = "INCOMPLETE"
        phase["development_gate_result"] = "INCOMPLETE"
        phase["stop_reason"] = f"{type(exc).__name__}: {exc}"
        journal["overall_status"] = "INCOMPLETE"
        journal["updated_at"] = _utc_now()
        _write_json(JOURNAL, journal)
        raise

    phase = journal["phases"]["oracle_v8_development"]
    phase["development_completed"] = bool(
        payload.get("development_completed")
    )
    phase["completed_at"] = payload.get("completed_at")
    phase["status"] = payload["status"]
    phase["development_gate_result"] = (
        "PASS" if payload.get("passed") else "FAIL"
    )
    phase["artifact_paths"] = [str(OUTPUT)]
    phase["artifact_sha256"] = _sha256(OUTPUT)
    phase["stop_reason"] = (
        None if payload.get("passed") else payload["status"]
    )
    journal["overall_status"] = (
        "AWAITING_HOLDOUT_AUTHORIZATION"
        if payload.get("passed")
        else "BLOCKED_WITH_EVIDENCE"
    )
    journal["updated_at"] = _utc_now()
    _write_json(JOURNAL, journal)
    development = payload.get("development") or {}
    print(json.dumps({
        "status": payload["status"],
        "artifact": str(OUTPUT),
        "development_completed": payload.get("development_completed"),
        "v6": development.get("v6"),
        "v8": development.get("v8"),
        "paired_outcomes": development.get("paired_outcomes"),
        "frozen_protocol_checks": development.get(
            "frozen_protocol_checks"
        ),
        "diagnostic_checks": development.get("diagnostic_checks"),
        "runtime": payload.get("runtime"),
        "holdout_used": payload["holdout"]["used"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
