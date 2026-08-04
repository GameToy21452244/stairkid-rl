"""Freeze the offline branch-preservation protocol review evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


PROTOCOL = Path("reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md")
LEDGER = Path("artifacts/simulator_oracle_branch_preservation_seed_ledger_v1.json")
PHASE2F = Path("artifacts/simulator_oracle_v8_phase2f_review_v1.json")
TRIGGERS = Path("artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.json")
COUNTERFACTUALS = Path("artifacts/simulator_oracle_v8_phase2f_counterfactuals_v1.json")
ORACLE_SOURCE = Path("src/stair_agent/policies/simulator_teachers.py")
PLANNER_SOURCE = Path("src/stair_agent/policies/simulator_route_planner.py")
OUTPUT = Path("artifacts/simulator_oracle_branch_preservation_protocol_v1.json")

EXPECTED = {
    PROTOCOL: "9d4fae44ae6c47714e48a3ebdae4b953f9e6f257c6f6604f8469cfd10859ccbe",
    LEDGER: "9da4b0b725f0ce7f932f6a15cc7819bf3d7471a59262dc8f861156ad58230c54",
    PHASE2F: "1343e9183d670c4f4afa865f65818287c7f0fdce667ad48dd300321558e9c98c",
    ORACLE_SOURCE: "18018669ed6e97056be20bf07642afd766dfa0b3c0bf4e232e476c26c295cbbb",
    PLANNER_SOURCE: "c52671e08c607d919e8c83b5f63b5c0faaf8b92541322996bdc736b66444a394",
}
LANE_ORDER = ("RELEASE_ALL", "LEFT", "RIGHT")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫frozen protocol artifact：{OUTPUT}")
    actual = {str(path): _sha256(path) for path in EXPECTED}
    if any(actual[str(path)] != expected for path, expected in EXPECTED.items()):
        raise RuntimeError("Protocol review input hash mismatch。")

    ledger = _load(LEDGER)
    phase2f = _load(PHASE2F)
    triggers = _load(TRIGGERS)
    counterfactuals = _load(COUNTERFACTUALS)
    if ledger["status"] != "CLEAN_AND_FROZEN":
        raise RuntimeError("Seed ledger不為clean/frozen。")
    if phase2f["holdout"]["used"] is not False:
        raise RuntimeError("Retired v8 holdout ledger不一致。")
    rescue_keys = {
        (int(item["seed"]), int(item["trigger_step"]))
        for item in counterfactuals["summary"][
            "different_first_action_rescue_rows"
        ]
    }
    rows = []
    for episode in triggers["episode_reviews"]:
        for trigger in episode["terminal_triggers"]:
            key = (int(trigger["seed"]), int(trigger["episode_step"]))
            if key not in rescue_keys:
                continue
            lane_winners = {
                action: trigger["forced_first_actions"][action]["selected"]
                for action in LANE_ORDER
            }
            selected_action = max(
                LANE_ORDER,
                key=lambda action: lane_winners[action]["score"],
            )
            selected = lane_winners[selected_action]
            rows.append(
                {
                    "seed": key[0],
                    "trigger_step": key[1],
                    "lane_order": list(LANE_ORDER),
                    "lane_scores": {
                        action: float(lane_winners[action]["score"])
                        for action in LANE_ORDER
                    },
                    "lane_terminal_reasons": {
                        action: lane_winners[action][
                            "predicted_terminal_reason"
                        ]
                        for action in LANE_ORDER
                    },
                    "existing_selector_action": selected_action,
                    "existing_selector_terminal_reason": selected[
                        "predicted_terminal_reason"
                    ],
                    "existing_selector_completion_reason": selected[
                        "completion_reason"
                    ],
                    "committed_counterfactual_reach10": True,
                    "passed": (
                        selected_action == "RIGHT"
                        and selected["predicted_terminal_reason"] is None
                    ),
                }
            )
    if len(rows) != 14 or not all(item["passed"] for item in rows):
        raise RuntimeError("Cross-lane existing-selector audit未通過14/14。")

    payload = {
        "schema_version": "simulator-oracle-branch-preservation-protocol-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "READY_FOR_TEST_FIRST_IMPLEMENTATION",
        "candidate": "oracle-full-v9-terminal-branch-preserving",
        "single_production_variable": (
            "three independent first-action lanes only during terminal-risk search"
        ),
        "frozen_hashes": actual,
        "selector_audit": {
            "selector": "max(lane_winner.score) in RELEASE_ALL/LEFT/RIGHT stable order",
            "selector_modified": False,
            "score_modified": False,
            "trigger_count": len(rows),
            "passed_count": sum(bool(item["passed"]) for item in rows),
            "all_select_right_survivor": True,
            "rows": rows,
        },
        "lane_bounds": {
            "actions": list(LANE_ORDER),
            "horizon_per_lane": 12,
            "beam_width_per_lane": 24,
            "theoretical_expanded_nodes_per_lane": 793,
            "theoretical_expanded_nodes_total": 2379,
            "structural_peak_node_snapshots": 364,
            "wall_clock_watchdog_seconds": 5.0,
            "sequential_lane_execution": True,
        },
        "tie_break": "stable lane order RELEASE_ALL, LEFT, RIGHT",
        "empty_lane_handling": "INCOMPLETE invariant failure",
        "all_terminal_fallback": (
            "existing max-score selector; cache and execute full selected suffix"
        ),
        "commit_semantics": {
            "cache_full_suffix": True,
            "receding_lane_switch": False,
            "cooldown_added": False,
            "hysteresis_added": False,
            "minimum_commitment_threshold_added": False,
        },
        "development": {
            "primary_partition": "18000-18099",
            "conditional_extension": "18100-18199",
            "extension_condition": "paired v6 primary top failures == 0",
            "combined_gate_if_extended": "all checks over 18000-18199",
            "zero_top_after_extension": "INSUFFICIENT_EVIDENCE",
        },
        "holdout": {
            "partition": "19000-19099",
            "used": False,
            "one_time_only": True,
        },
        "forbidden_seed_partitions": [
            "14000-14099",
            "16000-16099",
            "17000-17099",
        ],
        "production_modified_during_review": False,
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
        "next_phase": "TEST_FIRST_IMPLEMENTATION",
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} sha256={_sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
