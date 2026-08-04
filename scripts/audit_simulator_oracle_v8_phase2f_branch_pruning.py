"""Trace successful forced RIGHT paths through the shared production beam."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.input_controller import Action
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.training.simulator_oracle_v8_phase2f import (
    diagnose_search,
    trace_forced_path_pruning,
)
from stair_agent.training.simulator_v03_edge_gate import edge_fidelity_config


SOURCE = Path(
    "artifacts/simulator_oracle_v8_phase2f_counterfactuals_v1.json"
)
TRIGGERS = Path(
    "artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.json"
)
OUTPUT = Path(
    "artifacts/simulator_oracle_v8_phase2f_branch_pruning_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trace(seed: int, trigger_step: int) -> dict[str, object]:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    env.reset(seed=seed)
    try:
        for _step in range(1, trigger_step):
            decision = oracle.choose(env.simulator)
            _, _, terminated, truncated, _ = env.step(int(decision.action))
            if terminated or truncated:
                raise RuntimeError("trigger前replay已終局。")
        forced = diagnose_search(
            env.simulator,
            horizon=12,
            beam_width=24,
            forced_first_action=Action.RIGHT,
        )
        actions = tuple(
            Action[name] for name in forced["selected"]["actions"]
        )
        pruning = trace_forced_path_pruning(
            env.simulator,
            actions,
            horizon=12,
            beam_width=24,
        )
        return {
            "seed": seed,
            "trigger_step": trigger_step,
            "forced_branch": forced,
            "global_beam_pruning_trace": pruning,
        }
    finally:
        env.close()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫Phase 2F artifact：{OUTPUT}")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    trigger_source = json.loads(TRIGGERS.read_text(encoding="utf-8"))
    if source["holdout"]["used"] is not False:
        raise RuntimeError("holdout ledger不為unused。")
    rescue_rows = source["summary"]["different_first_action_rescue_rows"]
    traces = [
        _trace(int(row["seed"]), int(row["trigger_step"]))
        for row in rescue_rows
    ]
    prune_depths = Counter(
        item["global_beam_pruning_trace"]["first_pruned_depth"]
        for item in traces
    )
    prune_events = []
    for item in traces:
        pruning = item["global_beam_pruning_trace"]
        depth = pruning["first_pruned_depth"]
        row = next(
            detail for detail in pruning["depths"] if detail["depth"] == depth
        )
        prune_events.append({
            "seed": item["seed"],
            "trigger_step": item["trigger_step"],
            "prune_depth": depth,
            "forced_unique_rank": row["forced_signature_unique_rank"],
            "forced_score": row["forced_score"],
            "beam_cutoff_score": row["beam_cutoff_score"],
            "score_below_cutoff": (
                row["forced_score"] < row["beam_cutoff_score"]
            ),
            "beam_first_action_counts": row[
                "global_beam_first_action_counts"
            ],
        })
    payload = {
        "schema_version": "simulator-oracle-v8-phase2f-branch-pruning-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formal_gate": False,
        "development_diagnostic_only": True,
        "source": str(SOURCE),
        "source_sha256": _sha256(SOURCE),
        "trigger_source": str(TRIGGERS),
        "trigger_source_sha256": _sha256(TRIGGERS),
        "summary": {
            "full_rescue_path_count": len(traces),
            "first_prune_depth_counts": {
                str(key): value for key, value in sorted(prune_depths.items())
            },
            "all_rescue_paths_pruned_from_global_beam": all(
                item["global_beam_pruning_trace"]["first_pruned_depth"]
                is not None
                for item in traces
            ),
            "all_pruned_scores_below_beam_cutoff": all(
                item["score_below_cutoff"] for item in prune_events
            ),
            "prune_events": prune_events,
        },
        "traces": traces,
        "production_modified": False,
        "protocol_modified": False,
        "holdout": {"partition": "17000-17099", "used": False},
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PHASE2F_BRANCH_PRUNING_COMPLETE",
        "artifact": str(OUTPUT),
        "summary": payload["summary"],
        "holdout_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
