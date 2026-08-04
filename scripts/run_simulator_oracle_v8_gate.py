"""Run the frozen v8 terminal-risk Oracle Gate in strict order."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.policies.observable_route_intent import (
    OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
)
from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.training.simulator_oracle_robustness_gate import (
    DEVELOPMENT_SEEDS,
    HOLDOUT_SEEDS,
)
from stair_agent.training.simulator_oracle_v8_gate import (
    ORACLE_V8_POLICY_VERSION,
    decide_v8_gate_status,
    edge_evaluation_from_dict,
    paired_development_metrics,
    terminal_audit_source_checks,
    terminal_guard_oracle_factory,
    v8_development_checks,
)
from stair_agent.training.simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    baseline_checks,
    edge_fidelity_config,
    evaluate_edge_candidate,
    observable_route_intent_factory,
    oracle_checks,
)


FORMAL_V7 = Path("artifacts/simulator_oracle_robustness_gate_v1.json")
TERMINAL_AUDIT = Path("artifacts/simulator_oracle_terminal_plan_audit_v1.json")
PROTOCOL = Path("reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_PROTOCOL.md")
OUTPUT = Path("artifacts/simulator_oracle_v8_terminal_guard_gate_v1.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all(checks: dict[str, bool] | None) -> bool:
    return bool(checks) and all(checks.values())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫正式Gate artifact：{OUTPUT}")
    for path in (FORMAL_V7, TERMINAL_AUDIT, PROTOCOL):
        if not path.exists():
            raise FileNotFoundError(path)
    formal = json.loads(FORMAL_V7.read_text(encoding="utf-8"))
    audit = json.loads(TERMINAL_AUDIT.read_text(encoding="utf-8"))
    source_checks = {
        "v7_formal_status_is_development_fail": (
            formal.get("status")
            == "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"
        ),
        "v7_formal_holdout_unused": formal["holdout"]["used"] is False,
        "terminal_audit_source_hash_matches": (
            audit.get("source_artifact_sha256") == _sha256(FORMAL_V7)
        ),
        "terminal_audit_protocol_hash_matches": (
            audit.get("protocol_sha256")
            == _sha256(Path(audit["protocol"]))
        ),
        **{
            f"terminal_audit_{key}": value
            for key, value in terminal_audit_source_checks(audit).items()
        },
    }
    config = edge_fidelity_config()
    reference_v6 = edge_evaluation_from_dict(
        formal["development"]["reference_v6"]
    )
    development_reachability = None
    development_v8 = None
    development_checks = None
    development_metrics = None
    holdout_reachability = None
    holdout_oracle = None
    holdout_oracle_checks = None
    holdout_observable = None
    holdout_observable_checks = None

    if _all(source_checks):
        development_reachability = run_reachability_gate(
            len(DEVELOPMENT_SEEDS),
            config=config,
            seed_start=DEVELOPMENT_SEEDS[0],
        )
    if (
        development_reachability is not None
        and development_reachability.passed
    ):
        development_v8 = evaluate_edge_candidate(
            ORACLE_V8_POLICY_VERSION,
            terminal_guard_oracle_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        development_metrics = paired_development_metrics(
            reference_v6,
            development_v8,
        )
        development_checks = v8_development_checks(
            reference_v6,
            development_v8,
        )
    if _all(development_checks):
        holdout_reachability = run_reachability_gate(
            len(HOLDOUT_SEEDS),
            config=config,
            seed_start=HOLDOUT_SEEDS[0],
        )
    if holdout_reachability is not None and holdout_reachability.passed:
        holdout_oracle = evaluate_edge_candidate(
            ORACLE_V8_POLICY_VERSION,
            terminal_guard_oracle_factory,
            seeds=HOLDOUT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        holdout_oracle_checks = oracle_checks(holdout_oracle)
    if _all(holdout_oracle_checks):
        holdout_observable = evaluate_edge_candidate(
            OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
            observable_route_intent_factory,
            seeds=HOLDOUT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        holdout_observable_checks = baseline_checks(holdout_observable)

    status = decide_v8_gate_status(
        source_checks=source_checks,
        development_reachability_passed=(
            None
            if development_reachability is None
            else development_reachability.passed
        ),
        development_checks=development_checks,
        holdout_reachability_passed=(
            None
            if holdout_reachability is None
            else holdout_reachability.passed
        ),
        holdout_oracle_checks=holdout_oracle_checks,
        holdout_observable_checks=holdout_observable_checks,
    )
    payload = {
        "schema_version": "simulator-oracle-v8-terminal-guard-gate-v1",
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "formal_v7_source": str(FORMAL_V7),
        "formal_v7_source_sha256": _sha256(FORMAL_V7),
        "terminal_audit_source": str(TERMINAL_AUDIT),
        "terminal_audit_source_sha256": _sha256(TERMINAL_AUDIT),
        "status": status,
        "passed": status == "PASS_V8_ORACLE_AND_ROUTE_INTENT",
        "environment_version": config.effective_environment_version,
        "oracle_candidate": ORACLE_V8_POLICY_VERSION,
        "observable_candidate": OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
        "source_checks": source_checks,
        "development": {
            "seeds": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
            "reachability": (
                None
                if development_reachability is None
                else asdict(development_reachability)
            ),
            "reference_v6": reference_v6.to_dict(),
            "candidate_v8": (
                None if development_v8 is None else development_v8.to_dict()
            ),
            "paired_metrics": development_metrics,
            "checks": development_checks,
        },
        "holdout": {
            "seeds": [HOLDOUT_SEEDS[0], HOLDOUT_SEEDS[-1]],
            "used": holdout_reachability is not None,
            "reachability": (
                None
                if holdout_reachability is None
                else asdict(holdout_reachability)
            ),
            "oracle_v8": (
                None if holdout_oracle is None else holdout_oracle.to_dict()
            ),
            "oracle_checks": holdout_oracle_checks,
            "observable_candidate": (
                None
                if holdout_observable is None
                else holdout_observable.to_dict()
            ),
            "observable_checks": holdout_observable_checks,
        },
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
        "next_stage": (
            "v0.3 special-platform revalidation"
            if status == "PASS_V8_ORACLE_AND_ROUTE_INTENT"
            else "stop at the first failed Gate"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": status,
        "artifact": str(OUTPUT),
        "development_v8_reach10": (
            None
            if development_v8 is None
            else development_v8.reach_floor_10_rate
        ),
        "development_metrics": development_metrics,
        "development_checks": development_checks,
        "holdout_used": holdout_reachability is not None,
        "holdout_oracle_reach10": (
            None
            if holdout_oracle is None
            else holdout_oracle.reach_floor_10_rate
        ),
        "holdout_observable_reach3": (
            None
            if holdout_observable is None
            else holdout_observable.reach_floor_3_rate
        ),
        "holdout_observable_mean": (
            None
            if holdout_observable is None
            else holdout_observable.mean_deepest_floor
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

