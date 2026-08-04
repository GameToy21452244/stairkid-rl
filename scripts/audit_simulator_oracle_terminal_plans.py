"""Audit terminal-plan incidence on exposed v6 development traces."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.training.simulator_oracle_receding_failure_audit import (
    run_oracle_trace,
)


SOURCE = Path("artifacts/simulator_oracle_robustness_gate_v1.json")
TAXONOMY = Path("artifacts/simulator_oracle_failure_taxonomy_v1.json")
PROTOCOL = Path("reports/SIMULATOR_ORACLE_TERMINAL_PLAN_AUDIT_PROTOCOL.md")
OUTPUT = Path("artifacts/simulator_oracle_terminal_plan_audit_v1.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan_incidence(trace) -> dict[str, object]:
    plans = [
        step
        for step in trace.steps
        if step.planned_now and step.plan_predicted_terminal is not None
    ]
    return {
        "seed": trace.seed,
        "deepest_floor": trace.deepest_floor,
        "terminal_reason": trace.terminal_reason,
        "terminal_plan_exposed": bool(plans),
        "terminal_plan_count": len(plans),
        "first_terminal_plan": (
            None
            if not plans
            else {
                "step": plans[0].step,
                "floor": plans[0].deepest_floor_before,
                "predicted_terminal": plans[0].plan_predicted_terminal,
                "actions": plans[0].plan_actions,
                "expanded_nodes": plans[0].plan_expanded_nodes,
            }
        ),
        "all_plans_within_bounds": all(
            step.plan_expanded_nodes is None
            or step.plan_expanded_nodes <= 3 * 12 * 24
            for step in trace.steps
        ),
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫audit artifact：{OUTPUT}")
    for path in (SOURCE, TAXONOMY, PROTOCOL):
        if not path.exists():
            raise FileNotFoundError(path)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    reference = source["development"]["reference_v6"]
    formal_by_seed = {
        int(item["seed"]): item for item in reference["episode_results"]
    }
    source_checks = {
        "formal_status_is_development_fail_stop": (
            source.get("status")
            == "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"
        ),
        "holdout_unused": source["holdout"]["used"] is False,
        "development_seeds_exact": (
            tuple(sorted(formal_by_seed)) == tuple(range(16000, 16100))
        ),
        "reference_reach10_is_0_96": reference["reach_floor_10_rate"] == 0.96,
        "taxonomy_status_is_open_loop_evidence": (
            taxonomy.get("status") == "EVIDENCE_OPEN_LOOP_PRIMARY"
        ),
    }
    if not all(source_checks.values()):
        raise RuntimeError(f"source integrity failed：{source_checks}")

    episodes = []
    for seed in range(16000, 16100):
        trace = run_oracle_trace(seed, "cached")
        expected = formal_by_seed[seed]
        reproduced = (
            trace.deepest_floor == int(expected["deepest_floor"])
            and trace.terminal_reason == str(expected["terminal_reason"])
        )
        item = _plan_incidence(trace)
        item["formal_result_reproduced"] = reproduced
        episodes.append(item)

    groups = {
        "success": [item for item in episodes if item["deepest_floor"] >= 10],
        "top_failure": [
            item for item in episodes if item["terminal_reason"] == "top"
        ],
        "bottom_failure": [
            item for item in episodes if item["terminal_reason"] == "bottom"
        ],
    }
    group_summaries = {
        name: {
            "episodes": len(items),
            "terminal_plan_exposed": sum(
                bool(item["terminal_plan_exposed"]) for item in items
            ),
            "terminal_plan_exposure_rate": (
                sum(bool(item["terminal_plan_exposed"]) for item in items)
                / max(1, len(items))
            ),
            "terminal_plan_kinds": dict(Counter(
                item["first_terminal_plan"]["predicted_terminal"]
                for item in items
                if item["first_terminal_plan"] is not None
            )),
        }
        for name, items in groups.items()
    }
    retired_search_failures = [
        item
        for item in taxonomy["failure_results"]
        if item["phenotype"] == "search_found_no_survival"
    ]
    retired_exposed = sum(
        any(
            trace["predicted_terminal"] is not None
            for trace in item["modes"]["current_v6"]["plan_traces"]
        )
        for item in retired_search_failures
    )
    evidence_checks = {
        "all_development_results_reproduced": all(
            item["formal_result_reproduced"] for item in episodes
        ),
        "successful_terminal_plan_exposure_at_most_0_05": (
            group_summaries["success"]["terminal_plan_exposure_rate"] <= 0.05
        ),
        "all_development_top_failures_exposed": (
            group_summaries["top_failure"]["episodes"] > 0
            and group_summaries["top_failure"]["terminal_plan_exposed"]
            == group_summaries["top_failure"]["episodes"]
        ),
        "all_three_retired_search_failures_exposed": (
            len(retired_search_failures) == 3 and retired_exposed == 3
        ),
        "all_searches_within_fixed_bounds": all(
            item["all_plans_within_bounds"] for item in episodes
        ),
    }
    status = (
        "EVIDENCE_TERMINAL_RISK_ISOLATION"
        if all(evidence_checks.values())
        else "INSUFFICIENT_EVIDENCE_STOP"
    )
    payload = {
        "schema_version": "simulator-oracle-terminal-plan-audit-v1",
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "source_artifact": str(SOURCE),
        "source_artifact_sha256": _sha256(SOURCE),
        "taxonomy_artifact": str(TAXONOMY),
        "taxonomy_artifact_sha256": _sha256(TAXONOMY),
        "status": status,
        "formal_gate": False,
        "development_diagnostic_only": True,
        "holdout_used": False,
        "source_checks": source_checks,
        "evidence_checks": evidence_checks,
        "development_group_summaries": group_summaries,
        "retired_search_failure_count": len(retired_search_failures),
        "retired_search_failure_terminal_plan_exposed": retired_exposed,
        "episode_results": episodes,
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
        "development_group_summaries": group_summaries,
        "retired_search_failure_terminal_plan_exposed": retired_exposed,
        "evidence_checks": evidence_checks,
        "holdout_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

