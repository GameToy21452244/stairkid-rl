"""Run the frozen Oracle v7 robustness Gate in strict order."""

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
    ORACLE_V7_POLICY_VERSION,
    decide_gate_status,
    development_oracle_checks,
    receding_route_planner_oracle_factory,
    taxonomy_source_checks,
)
from stair_agent.training.simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    baseline_checks,
    edge_fidelity_config,
    evaluate_edge_candidate,
    observable_route_intent_factory,
    oracle_checks,
    route_planner_oracle_factory,
)


SOURCE = Path("artifacts/simulator_oracle_failure_taxonomy_v1.json")
PROTOCOL = Path("reports/SIMULATOR_ORACLE_ROBUSTNESS_PROTOCOL.md")
OUTPUT = Path("artifacts/simulator_oracle_robustness_gate_v1.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all(checks: dict[str, bool] | None) -> bool:
    return bool(checks) and all(checks.values())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫正式 Gate artifact：{OUTPUT}")
    if not SOURCE.exists() or not PROTOCOL.exists():
        raise FileNotFoundError("缺少 taxonomy artifact 或 frozen protocol。")

    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    source_checks = taxonomy_source_checks(source)
    config = edge_fidelity_config()

    development_reachability = None
    development_reference = None
    development_candidate = None
    development_checks = None
    holdout_reachability = None
    holdout_oracle = None
    holdout_oracle_checks = None
    holdout_candidate = None
    holdout_candidate_checks = None

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
        development_reference = evaluate_edge_candidate(
            "oracle-full-v6-bounded-route-planner",
            route_planner_oracle_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        development_candidate = evaluate_edge_candidate(
            ORACLE_V7_POLICY_VERSION,
            receding_route_planner_oracle_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        development_checks = development_oracle_checks(
            development_reference,
            development_candidate,
        )
    if _all(development_checks):
        holdout_reachability = run_reachability_gate(
            len(HOLDOUT_SEEDS),
            config=config,
            seed_start=HOLDOUT_SEEDS[0],
        )
    if holdout_reachability is not None and holdout_reachability.passed:
        holdout_oracle = evaluate_edge_candidate(
            ORACLE_V7_POLICY_VERSION,
            receding_route_planner_oracle_factory,
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

    status = decide_gate_status(
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
        holdout_candidate_checks=holdout_candidate_checks,
    )
    payload = {
        "schema_version": "simulator-oracle-robustness-gate-v1",
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "source_artifact": str(SOURCE),
        "source_artifact_sha256": _sha256(SOURCE),
        "status": status,
        "passed": status == "PASS_ORACLE_ROBUSTNESS_AND_ROUTE_INTENT",
        "environment_version": config.effective_environment_version,
        "oracle_candidate": ORACLE_V7_POLICY_VERSION,
        "observable_candidate": OBSERVABLE_ROUTE_INTENT_POLICY_VERSION,
        "source_checks": source_checks,
        "development": {
            "seeds": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
            "reachability": (
                None
                if development_reachability is None
                else asdict(development_reachability)
            ),
            "reference_v6": (
                None
                if development_reference is None
                else development_reference.to_dict()
            ),
            "candidate_v7": (
                None
                if development_candidate is None
                else development_candidate.to_dict()
            ),
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
            "oracle_v7": (
                None if holdout_oracle is None else holdout_oracle.to_dict()
            ),
            "oracle_checks": holdout_oracle_checks,
            "observable_candidate": (
                None
                if holdout_candidate is None
                else holdout_candidate.to_dict()
            ),
            "observable_checks": holdout_candidate_checks,
        },
        "training_started": False,
        "real_game_started": False,
        "dataset_generated": False,
        "next_stage": (
            "v0.3 special-platform revalidation"
            if status == "PASS_ORACLE_ROBUSTNESS_AND_ROUTE_INTENT"
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
        "development_reachability_passed": (
            None
            if development_reachability is None
            else development_reachability.passed
        ),
        "development_reference_reach10": (
            None
            if development_reference is None
            else development_reference.reach_floor_10_rate
        ),
        "development_candidate_reach10": (
            None
            if development_candidate is None
            else development_candidate.reach_floor_10_rate
        ),
        "development_checks": development_checks,
        "holdout_used": holdout_reachability is not None,
        "holdout_oracle_reach10": (
            None
            if holdout_oracle is None
            else holdout_oracle.reach_floor_10_rate
        ),
        "observable_holdout_reach3": (
            None
            if holdout_candidate is None
            else holdout_candidate.reach_floor_3_rate
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

