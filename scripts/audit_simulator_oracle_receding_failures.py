"""Run the frozen paired v6/v7 receding failure audit."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean

import _common  # noqa: F401,E402

from stair_agent.training.simulator_oracle_receding_failure_audit import (
    BOTH_FAILURE_SEEDS,
    CONTROL_SEEDS,
    REGRESSION_SEEDS,
    RESCUE_SEEDS,
    paired_trace_summary,
    run_oracle_trace,
    select_audit_seeds,
)


SOURCE = Path("artifacts/simulator_oracle_robustness_gate_v1.json")
PROTOCOL = Path(
    "reports/SIMULATOR_ORACLE_RECEDING_FAILURE_AUDIT_PROTOCOL.md"
)
OUTPUT = Path(
    "artifacts/simulator_oracle_receding_failure_audit_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _group_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    classifications = Counter(
        (
            "no_divergence_before_terminal"
            if row["first_divergence"] is None
            else row["first_divergence"]["classification"]
        )
        for row in rows
    )
    return {
        "episodes": len(rows),
        "first_divergence_classifications": dict(classifications),
        "all_first_divergence_states_identical": all(
            row["first_divergence"] is None
            or row["first_divergence"]["states_identical"]
            for row in rows
        ),
        "mean_action_switch_delta_v7_minus_v6": mean(
            float(row["action_switch_delta_v7_minus_v6"])
            for row in rows
        ),
        "mean_plan_first_switch_delta_v7_minus_v6": mean(
            float(row["plan_first_switch_delta_v7_minus_v6"])
            for row in rows
        ),
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫audit artifact：{OUTPUT}")
    if not SOURCE.exists() or not PROTOCOL.exists():
        raise FileNotFoundError("缺少formal Gate artifact或frozen audit protocol。")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    development = source["development"]
    selected = select_audit_seeds(
        development["reference_v6"]["episode_results"],
        development["candidate_v7"]["episode_results"],
    )
    expected = {
        "regression": REGRESSION_SEEDS,
        "rescue": RESCUE_SEEDS,
        "both_failure": BOTH_FAILURE_SEEDS,
        "control": CONTROL_SEEDS,
    }
    source_checks = {
        "source_status_is_development_fail_stop": (
            source.get("status")
            == "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"
        ),
        "source_holdout_unused": source["holdout"]["used"] is False,
        "source_v6_reach10_is_0_96": (
            development["reference_v6"]["reach_floor_10_rate"] == 0.96
        ),
        "source_v7_reach10_is_0_76": (
            development["candidate_v7"]["reach_floor_10_rate"] == 0.76
        ),
        "selected_seed_groups_match_protocol": selected == expected,
    }
    if not all(source_checks.values()):
        raise RuntimeError(f"source integrity failed：{source_checks}")

    results: dict[str, list[dict[str, object]]] = {}
    summaries: dict[str, dict[str, object]] = {}
    for group, seeds in expected.items():
        rows = []
        for seed in seeds:
            v6 = run_oracle_trace(seed, "cached")
            v7 = run_oracle_trace(seed, "receding")
            rows.append(paired_trace_summary(v6, v7))
        results[group] = rows
        summaries[group] = _group_summary(rows)

    regression_classes = Counter(
        row["first_divergence"]["classification"]
        if row["first_divergence"] is not None
        else "no_divergence_before_terminal"
        for row in results["regression"]
    )
    dominant_class, dominant_count = regression_classes.most_common(1)[0]
    control_same_class_count = int(
        summaries["control"]["first_divergence_classifications"].get(
            dominant_class,
            0,
        )
    )
    evidence_checks = {
        "all_first_divergence_states_identical": all(
            summary["all_first_divergence_states_identical"]
            for summary in summaries.values()
        ),
        "dominant_regression_class_at_least_16_of_21": (
            dominant_count >= 16
        ),
        "same_class_in_controls_at_most_5_of_10": (
            control_same_class_count <= 5
        ),
    }
    status = (
        "EVIDENCE_DOMINANT_FIRST_DIVERGENCE"
        if all(evidence_checks.values())
        else "INSUFFICIENT_EVIDENCE_STOP"
    )
    payload = {
        "schema_version": "simulator-oracle-receding-failure-audit-v1",
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "source_artifact": str(SOURCE),
        "source_artifact_sha256": _sha256(SOURCE),
        "status": status,
        "formal_gate": False,
        "development_diagnostic_only": True,
        "holdout_used": False,
        "source_checks": source_checks,
        "evidence_checks": evidence_checks,
        "dominant_regression_class": dominant_class,
        "dominant_regression_count": dominant_count,
        "control_same_class_count": control_same_class_count,
        "group_summaries": summaries,
        "paired_results": results,
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
        "dominant_regression_class": dominant_class,
        "dominant_regression_count": dominant_count,
        "control_same_class_count": control_same_class_count,
        "group_summaries": summaries,
        "holdout_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

