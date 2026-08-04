"""Run the frozen observable route-intent Gate in strict order."""

from __future__ import annotations

import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.policies.observable_route_intent import (
    OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
)
from stair_agent.training.simulator_v03_edge_gate import (
    DEVELOPMENT_SEEDS,
    HOLDOUT_SEEDS,
    MAX_EPISODE_STEPS,
    baseline_checks,
    edge_fidelity_config,
    evaluate_edge_candidate,
    observable_route_intent_factory,
    oracle_checks,
    route_planner_oracle_factory,
)


REFERENCE = Path("artifacts/simulator_v03_edge_fidelity_gate_v5.json")
OUTPUT = Path("artifacts/simulator_observable_route_intent_gate_v1.json")


def _all(checks: dict[str, bool] | None) -> bool:
    return bool(checks) and all(checks.values())


def _reference_checks(payload: dict[str, object]) -> dict[str, bool]:
    development = payload.get("development") or {}
    oracle = development.get("oracle") or {}
    holdout = payload.get("holdout") or {}
    return {
        "status_is_expected_baseline_stop": (
            payload.get("status") == "FAIL_STOP_BASELINE_DEVELOPMENT"
        ),
        "environment_is_v03": (
            payload.get("environment_version") == "ns-shaft-sim-v0.3"
        ),
        "oracle_development_reach10_is_0_96": (
            oracle.get("reach_floor_10_rate") == 0.96
        ),
        "oracle_development_has_zero_violations": (
            oracle.get("invariant_violation_count") == 0
        ),
        "holdout_was_unused": holdout.get("used") is False,
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫正式 Gate artifact：{OUTPUT}")
    if not REFERENCE.exists():
        raise FileNotFoundError(f"缺少前一 Gate artifact：{REFERENCE}")
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    reference_checks = _reference_checks(reference)

    development = None
    development_checks = None
    holdout_oracle = None
    holdout_oracle_checks = None
    holdout_candidate = None
    holdout_candidate_checks = None
    config = edge_fidelity_config()

    if _all(reference_checks):
        development = evaluate_edge_candidate(
            OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
            observable_route_intent_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        development_checks = baseline_checks(development)
    if _all(development_checks):
        holdout_oracle = evaluate_edge_candidate(
            "oracle-full-v6-bounded-route-planner",
            route_planner_oracle_factory,
            seeds=HOLDOUT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        holdout_oracle_checks = oracle_checks(holdout_oracle)
    if _all(holdout_oracle_checks):
        holdout_candidate = evaluate_edge_candidate(
            OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
            observable_route_intent_factory,
            seeds=HOLDOUT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        holdout_candidate_checks = baseline_checks(holdout_candidate)

    if not _all(reference_checks):
        status = "FAIL_STOP_REFERENCE_INTEGRITY"
    elif not _all(development_checks):
        status = "FAIL_STOP_ROUTE_INTENT_DEVELOPMENT"
    elif not _all(holdout_oracle_checks):
        status = "FAIL_STOP_ORACLE_HOLDOUT"
    elif not _all(holdout_candidate_checks):
        status = "FAIL_STOP_ROUTE_INTENT_HOLDOUT"
    else:
        status = "PASS_OBSERVABLE_ROUTE_INTENT"

    payload = {
        "schema_version": "simulator-observable-route-intent-gate-v1",
        "protocol": "reports/SIMULATOR_OBSERVABLE_ROUTE_INTENT_PROTOCOL.md",
        "status": status,
        "passed": status == "PASS_OBSERVABLE_ROUTE_INTENT",
        "candidate": OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
        "environment_version": config.effective_environment_version,
        "reference": {
            "path": str(REFERENCE),
            "checks": reference_checks,
        },
        "development": {
            "seeds": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
            "checks": development_checks,
            "result": None if development is None else development.to_dict(),
        },
        "holdout": {
            "seeds": [HOLDOUT_SEEDS[0], HOLDOUT_SEEDS[-1]],
            "used": holdout_oracle is not None,
            "oracle_checks": holdout_oracle_checks,
            "oracle": (
                None if holdout_oracle is None else holdout_oracle.to_dict()
            ),
            "candidate_checks": holdout_candidate_checks,
            "candidate": (
                None
                if holdout_candidate is None
                else holdout_candidate.to_dict()
            ),
        },
        "training_started": False,
        "real_game_started": False,
        "next_stage": (
            "v0.3 special-platform revalidation before Dataset or Student"
            if status == "PASS_OBSERVABLE_ROUTE_INTENT"
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
        "development_checks": development_checks,
        "holdout_used": holdout_oracle is not None,
        "holdout_oracle_checks": holdout_oracle_checks,
        "holdout_candidate_checks": holdout_candidate_checks,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
