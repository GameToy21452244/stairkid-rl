"""Run the frozen Simulator v0.3 edge-departure Gate."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.training.simulator_v03_edge_gate import (
    DEVELOPMENT_SEEDS,
    HOLDOUT_SEEDS,
    MAX_EPISODE_STEPS,
    baseline_checks,
    baseline_factory,
    edge_fidelity_config,
    evaluate_edge_candidate,
    oracle_checks,
    release_factory,
    route_planner_oracle_factory,
)


OUTPUT = Path("artifacts/simulator_v03_edge_fidelity_gate_v5.json")


def _all(checks: dict[str, bool]) -> bool:
    return all(checks.values())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫正式 Gate artifact：{OUTPUT}")
    config = edge_fidelity_config()
    release = evaluate_edge_candidate(
        "release",
        release_factory,
        seeds=DEVELOPMENT_SEEDS[:20],
        max_episode_steps=100,
        config=config,
    )
    release_checks = {
        "all_episodes_remain_floor_zero": all(
            episode.deepest_floor == 0
            for episode in release.episode_results
        ),
        "floor_descents_zero": release.floor_descents == 0,
        "edge_invariant_violations_zero": (
            release.invariant_violation_count == 0
        ),
    }
    reachability_100 = run_reachability_gate(
        100,
        config=config,
        seed_start=DEVELOPMENT_SEEDS[0],
    )
    reachability_1000 = (
        run_reachability_gate(
            1000,
            config=config,
            seed_start=DEVELOPMENT_SEEDS[0],
        )
        if reachability_100.passed
        else None
    )
    engineering_passed = (
        _all(release_checks)
        and reachability_100.passed
        and reachability_1000 is not None
        and reachability_1000.passed
        and config.effective_environment_version == "ns-shaft-sim-v0.3"
    )

    development_oracle = None
    development_oracle_checks = None
    development_baseline = None
    development_baseline_checks = None
    holdout_oracle = None
    holdout_oracle_checks = None
    holdout_baseline = None
    holdout_baseline_checks = None
    if engineering_passed:
        development_oracle = evaluate_edge_candidate(
            "oracle-full-v6-bounded-route-planner",
            route_planner_oracle_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        development_oracle_checks = oracle_checks(development_oracle)
    if development_oracle_checks and _all(development_oracle_checks):
        development_baseline = evaluate_edge_candidate(
            "safe-platform-baseline",
            baseline_factory,
            seeds=DEVELOPMENT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        development_baseline_checks = baseline_checks(development_baseline)
    if development_baseline_checks and _all(development_baseline_checks):
        holdout_oracle = evaluate_edge_candidate(
            "oracle-full-v6-bounded-route-planner",
            route_planner_oracle_factory,
            seeds=HOLDOUT_SEEDS,
            max_episode_steps=MAX_EPISODE_STEPS,
            config=config,
        )
        holdout_oracle_checks = oracle_checks(holdout_oracle)
        if _all(holdout_oracle_checks):
            holdout_baseline = evaluate_edge_candidate(
                "safe-platform-baseline",
                baseline_factory,
                seeds=HOLDOUT_SEEDS,
                max_episode_steps=MAX_EPISODE_STEPS,
                config=config,
            )
            holdout_baseline_checks = baseline_checks(holdout_baseline)

    if not engineering_passed:
        status = "FAIL_STOP_ENGINEERING"
    elif not development_oracle_checks or not _all(development_oracle_checks):
        status = "FAIL_STOP_ORACLE_DEVELOPMENT"
    elif not development_baseline_checks or not _all(development_baseline_checks):
        status = "FAIL_STOP_BASELINE_DEVELOPMENT"
    elif not holdout_oracle_checks or not _all(holdout_oracle_checks):
        status = "FAIL_STOP_ORACLE_HOLDOUT"
    elif not holdout_baseline_checks or not _all(holdout_baseline_checks):
        status = "FAIL_STOP_BASELINE_HOLDOUT"
    else:
        status = "PASS_SIMULATOR_V03_EDGE_FIDELITY"

    payload = {
        "schema_version": "simulator-v03-edge-fidelity-gate-v1",
        "protocol": "reports/SIMULATOR_V03_EDGE_FIDELITY_PROTOCOL.md",
        "status": status,
        "passed": status == "PASS_SIMULATOR_V03_EDGE_FIDELITY",
        "environment_version": config.effective_environment_version,
        "training_started": False,
        "real_game_started": False,
        "real_reference": {
            "directory": "logs/teacher_real_micro_20260803_205952_924961",
            "episodes": 3,
            "records": 308,
            "example_episode": 3,
            "example_steps": [32, 40],
        },
        "engineering": {
            "passed": engineering_passed,
            "release_checks": release_checks,
            "release": release.to_dict(),
            "reachability_100": asdict(reachability_100),
            "reachability_1000": (
                None
                if reachability_1000 is None
                else asdict(reachability_1000)
            ),
        },
        "development": {
            "seeds": [DEVELOPMENT_SEEDS[0], DEVELOPMENT_SEEDS[-1]],
            "oracle_checks": development_oracle_checks,
            "oracle": (
                None
                if development_oracle is None
                else development_oracle.to_dict()
            ),
            "baseline_checks": development_baseline_checks,
            "baseline": (
                None
                if development_baseline is None
                else development_baseline.to_dict()
            ),
        },
        "holdout": {
            "seeds": [HOLDOUT_SEEDS[0], HOLDOUT_SEEDS[-1]],
            "used": holdout_oracle is not None,
            "oracle_checks": holdout_oracle_checks,
            "oracle": (
                None if holdout_oracle is None else holdout_oracle.to_dict()
            ),
            "baseline_checks": holdout_baseline_checks,
            "baseline": (
                None
                if holdout_baseline is None
                else holdout_baseline.to_dict()
            ),
        },
        "next_stage": (
            "visual_real/simulator comparison and special-platform revalidation"
            if status == "PASS_SIMULATOR_V03_EDGE_FIDELITY"
            else "stop at the first failed Gate and repair only that layer"
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
        "development_oracle_checks": development_oracle_checks,
        "development_baseline_checks": development_baseline_checks,
        "holdout_used": holdout_oracle is not None,
        "holdout_oracle_checks": holdout_oracle_checks,
        "holdout_baseline_checks": holdout_baseline_checks,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
