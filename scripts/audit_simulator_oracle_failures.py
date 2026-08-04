"""Audit the seven retired Oracle-full v6 holdout failures."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.simulator.gates import run_reachability_gate
from stair_agent.training.simulator_oracle_failure_taxonomy import (
    DIAGNOSTIC_MODES,
    RETIRED_FAILURE_EXPECTATIONS,
    counterfactual_attribution,
    current_failure_phenotype,
    run_diagnostic_episode,
)
from stair_agent.training.simulator_v03_edge_gate import edge_fidelity_config


SOURCE = Path("artifacts/simulator_observable_route_intent_gate_v1.json")
OUTPUT = Path("artifacts/simulator_oracle_failure_taxonomy_v1.json")
PROTOCOL = Path("reports/SIMULATOR_ORACLE_FAILURE_TAXONOMY_PROTOCOL.md")


def _source_failures(payload: dict[str, object]) -> dict[int, tuple[int, str]]:
    holdout = payload["holdout"]
    oracle = holdout["oracle"]
    episodes = oracle["episode_results"]
    return {
        int(episode["seed"]): (
            int(episode["deepest_floor"]),
            str(episode["terminal_reason"]),
        )
        for episode in episodes
        if int(episode["deepest_floor"]) < 10
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫 diagnostic artifact：{OUTPUT}")
    if not SOURCE.exists() or not PROTOCOL.exists():
        raise FileNotFoundError("缺少正式來源 artifact 或 frozen protocol。")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    source_failures = _source_failures(source)
    source_checks = {
        "source_status_is_fail_stop_oracle_holdout": (
            source.get("status") == "FAIL_STOP_ORACLE_HOLDOUT"
        ),
        "source_reach10_is_0_93": (
            source["holdout"]["oracle"]["reach_floor_10_rate"] == 0.93
        ),
        "retired_failures_match_exactly": (
            source_failures == RETIRED_FAILURE_EXPECTATIONS
        ),
    }
    if not all(source_checks.values()):
        raise RuntimeError(f"source integrity check failed：{source_checks}")

    reachability = run_reachability_gate(
        100,
        config=edge_fidelity_config(),
        seed_start=14000,
    )
    results = []
    for seed, expected in RETIRED_FAILURE_EXPECTATIONS.items():
        episodes = [
            run_diagnostic_episode(seed, mode) for mode in DIAGNOSTIC_MODES
        ]
        current = episodes[0]
        reproduced = (
            current.deepest_floor,
            current.terminal_reason,
        ) == expected
        results.append({
            "seed": seed,
            "expected_current_v6": {
                "deepest_floor": expected[0],
                "terminal_reason": expected[1],
            },
            "current_v6_reproduced": reproduced,
            "phenotype": current_failure_phenotype(current),
            "counterfactual_attribution": counterfactual_attribution(episodes),
            "modes": {
                episode.mode: episode.to_dict() for episode in episodes
            },
        })

    mode_reach10 = {
        mode: sum(
            item["modes"][mode]["reached_target"] for item in results
        )
        for mode in DIAGNOSTIC_MODES
    }
    all_reproduced = all(
        item["current_v6_reproduced"] for item in results
    )
    all_state_restored = all(
        mode["planner_state_restored"]
        for item in results
        for mode in item["modes"].values()
    )
    bounded = all(
        mode["max_expanded_nodes"]
        <= 3 * (
            24 if mode_name == "extended_always_receding" else 12
        ) * (96 if mode_name == "extended_always_receding" else 24)
        for item in results
        for mode_name, mode in item["modes"].items()
    )
    if not all_reproduced or not all_state_restored or not bounded:
        status = "INVALID_DIAGNOSTIC"
    elif mode_reach10["receding_current_trigger"] >= 4:
        status = "EVIDENCE_OPEN_LOOP_PRIMARY"
    elif mode_reach10["always_receding"] >= 4:
        status = "EVIDENCE_TRIGGER_PRIMARY"
    elif mode_reach10["extended_always_receding"] >= 4:
        status = "EVIDENCE_SEARCH_CAPACITY_PRIMARY"
    else:
        status = "INSUFFICIENT_EVIDENCE_STOP"

    payload = {
        "schema_version": "simulator-oracle-failure-taxonomy-v1",
        "protocol": str(PROTOCOL),
        "source_artifact": str(SOURCE),
        "status": status,
        "formal_gate": False,
        "retired_diagnostic_seeds_only": True,
        "source_checks": source_checks,
        "reachability_14000_14099": asdict(reachability),
        "mode_reach_floor_10_counts_out_of_7": mode_reach10,
        "all_current_v6_failures_reproduced": all_reproduced,
        "all_planner_calls_restored_state": all_state_restored,
        "all_searches_within_fixed_bounds": bounded,
        "failure_results": results,
        "training_started": False,
        "real_game_started": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": status,
        "artifact": str(OUTPUT),
        "mode_reach_floor_10_counts_out_of_7": mode_reach10,
        "all_current_v6_failures_reproduced": all_reproduced,
        "reachability_passed": reachability.passed,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

