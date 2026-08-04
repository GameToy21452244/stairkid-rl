"""Run committed-branch full-episode counterfactuals for Phase 2F."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.input_controller import Action
from stair_agent.training.simulator_oracle_v8_phase2f import (
    TOP_FAILURE_SEEDS,
    run_committed_branch_counterfactual,
)


SOURCE = Path(
    "artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.json"
)
FORMAL = Path(
    "artifacts/simulator_oracle_v8_terminal_guard_development_v1.json"
)
OUTPUT = Path(
    "artifacts/simulator_oracle_v8_phase2f_counterfactuals_v1.json"
)
EXPECTED_FORMAL_SHA256 = (
    "b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫Phase 2F artifact：{OUTPUT}")
    if not SOURCE.exists() or _sha256(FORMAL) != EXPECTED_FORMAL_SHA256:
        raise RuntimeError("Phase 2F source或formal artifact hash不一致。")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    if source["holdout"]["used"] is not False:
        raise RuntimeError("holdout ledger不為unused。")
    triggers = [
        trigger
        for review in source["episode_reviews"]
        for trigger in review["terminal_triggers"]
    ]
    results = []
    selected_by_trigger = {
        (int(item["seed"]), int(item["episode_step"])): str(
            item["selected_first_action"]
        )
        for item in triggers
    }
    for trigger in triggers:
        seed = int(trigger["seed"])
        step = int(trigger["episode_step"])
        for action in Action:
            result = run_committed_branch_counterfactual(
                seed=seed,
                trigger_step=step,
                forced_first_action=action,
            )
            result["production_selected_first_action"] = trigger[
                "selected_first_action"
            ]
            result["different_from_production_first_action"] = (
                action.name != trigger["selected_first_action"]
            )
            results.append(result)
    local_nonterminal = [
        item for item in results if item["branch_predicted_terminal"] is None
    ]
    full_rescues = [item for item in results if item["reached_floor_10"]]
    different_first_rescues = [
        item
        for item in full_rescues
        if item["different_from_production_first_action"]
    ]
    payload = {
        "schema_version": "simulator-oracle-v8-phase2f-counterfactuals-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formal_gate": False,
        "development_diagnostic_only": True,
        "source": str(SOURCE),
        "source_sha256": _sha256(SOURCE),
        "formal_source": str(FORMAL),
        "formal_source_sha256": _sha256(FORMAL),
        "reviewed_top_failure_seeds": list(TOP_FAILURE_SEEDS),
        "method": (
            "replay the original trajectory to each terminal-plan call, "
            "commit the selected isolated forced-first 12/24 branch, then "
            "resume a fresh frozen v8 oracle; diagnostic-only"
        ),
        "summary": {
            "trigger_count": len(triggers),
            "counterfactual_count": len(results),
            "local_nonterminal_or_floor_progress_count": len(
                local_nonterminal
            ),
            "full_reach_floor_10_count": len(full_rescues),
            "different_first_action_full_reach_floor_10_count": len(
                different_first_rescues
            ),
            "full_rescues_by_seed": {
                str(seed): sum(
                    item["seed"] == seed for item in full_rescues
                )
                for seed in TOP_FAILURE_SEEDS
            },
            "different_first_action_rescue_rows": [
                {
                    "seed": item["seed"],
                    "trigger_step": item["trigger_step"],
                    "forced_first_action": item["forced_first_action"],
                    "branch_floor_after_execution": item[
                        "branch_floor_after_execution"
                    ],
                    "final_deepest_floor": item["final_deepest_floor"],
                    "total_episode_steps": item["total_episode_steps"],
                }
                for item in different_first_rescues
            ],
            "production_selected_first_actions": {
                f"{seed}:{step}": action
                for (seed, step), action in selected_by_trigger.items()
            },
        },
        "results": results,
        "production_modified": False,
        "protocol_modified": False,
        "holdout": {"partition": "17000-17099", "used": False},
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PHASE2F_COUNTERFACTUALS_COMPLETE",
        "artifact": str(OUTPUT),
        "summary": payload["summary"],
        "holdout_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
