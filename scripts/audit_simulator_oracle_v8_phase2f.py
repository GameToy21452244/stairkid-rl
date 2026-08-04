"""Run bounded, offline-only Oracle v8 Phase 2F diagnostics."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean

import _common  # noqa: F401,E402

from stair_agent.training.simulator_oracle_v8_phase2f import (
    TOP_FAILURE_SEEDS,
    review_top_failure,
)


FORMAL_ARTIFACT = Path(
    "artifacts/simulator_oracle_v8_terminal_guard_development_v1.json"
)
RAW_OUTPUT = Path(
    "artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.json"
)
CSV_OUTPUT = Path(
    "artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.csv"
)
SVG_OUTPUT = Path(
    "artifacts/simulator_oracle_v8_phase2f_trigger_timeline.svg"
)
PROTOCOL = Path("reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_PROTOCOL.md")
ORACLE_SOURCE = Path("src/stair_agent/policies/simulator_teachers.py")
PLANNER_SOURCE = Path("src/stair_agent/policies/simulator_route_planner.py")

EXPECTED_HASHES = {
    FORMAL_ARTIFACT: "b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166",
    PROTOCOL: "78df06c393ff8123d559a98657fadbd791eee3ce3f532aa6a3fabe2cc3f5289e",
    ORACLE_SOURCE: "18018669ed6e97056be20bf07642afd766dfa0b3c0bf4e232e476c26c295cbbb",
    PLANNER_SOURCE: "c52671e08c607d919e8c83b5f63b5c0faaf8b92541322996bdc736b66444a394",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        raise FileExistsError(f"拒絕覆寫Phase 2F artifact：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _forced_any_nonterminal(
    forced: dict[str, dict[str, object]],
) -> bool:
    return any(
        item["selected"]["predicted_terminal_reason"] is None
        for item in forced.values()
    )


def _extended_any_nonterminal(
    trigger: dict[str, object],
    key: str,
) -> bool | None:
    diagnostics = trigger["extended_diagnostics"]
    if key not in diagnostics:
        return None
    return _forced_any_nonterminal(diagnostics[key])


def _summary(reviews: list[dict[str, object]]) -> dict[str, object]:
    triggers = [
        trigger
        for review in reviews
        for trigger in review["terminal_triggers"]
    ]
    replans = [
        item
        for item in triggers
        if item["trigger_kind"] == "terminal_risk_replan"
    ]
    later_death = [
        item
        for item in triggers
        if item["different_first_action_dies_later"]
    ]
    runtime_by_config: dict[str, list[float]] = {}
    expanded_by_config: dict[str, list[int]] = {}
    for trigger in triggers:
        for key, forced in {
            "h12_b24": trigger["forced_first_actions"],
            **trigger["extended_diagnostics"],
        }.items():
            runtime_by_config.setdefault(key, []).extend(
                float(item["runtime_seconds"]) for item in forced.values()
            )
            expanded_by_config.setdefault(key, []).extend(
                int(item["expanded_nodes"]) for item in forced.values()
            )
    return {
        "terminal_plan_calls": len(triggers),
        "terminal_risk_replans": len(replans),
        "all_selected_first_actions_match_v6_cache": all(
            item["same_as_v6_cached_action"] for item in triggers
        ),
        "same_first_action_different_suffix_count": sum(
            bool(item["different_suffix_same_first_action"])
            for item in triggers
        ),
        "all_selected_first_actions_executed": all(
            item["selected_first_action_executed"] for item in triggers
        ),
        "all_production_plans_match_diagnostic": all(
            item["production_plan_matches_diagnostic"]
            for item in triggers
        ),
        "all_h12_b24_forced_first_candidates_terminal": all(
            not item["nonterminal_candidate_exists_h12_b24"]
            for item in triggers
        ),
        "h24_b24_surviving_trigger_count": sum(
            _extended_any_nonterminal(item, "h24_b24") is True
            for item in triggers
        ),
        "h12_b96_surviving_trigger_count": sum(
            _extended_any_nonterminal(item, "h12_b96") is True
            for item in triggers
        ),
        "h24_b96_surviving_representative_count": sum(
            _extended_any_nonterminal(item, "h24_b96") is True
            for item in triggers
        ),
        "h24_b96_representative_trigger_count": sum(
            _extended_any_nonterminal(item, "h24_b96") is not None
            for item in triggers
        ),
        "different_first_action_dies_later_trigger_count": len(
            later_death
        ),
        "different_first_action_dies_later_steps": [
            {"seed": item["seed"], "step": item["episode_step"]}
            for item in later_death
        ],
        "trigger_timing": {
            str(review["seed"]): review["trigger_timing"]
            for review in reviews
        },
        "integrity": {
            str(review["seed"]): review["integrity"]
            for review in reviews
        },
        "compute_cost": {
            key: {
                "searches": len(runtime_by_config[key]),
                "mean_runtime_seconds": mean(runtime_by_config[key]),
                "mean_expanded_nodes": mean(expanded_by_config[key]),
                "total_runtime_seconds": sum(runtime_by_config[key]),
                "total_expanded_nodes": sum(expanded_by_config[key]),
            }
            for key in sorted(runtime_by_config)
        },
    }


def _write_csv(reviews: list[dict[str, object]]) -> None:
    fields = [
        "seed",
        "episode_step",
        "trigger_kind",
        "headroom",
        "supported_floor",
        "airborne",
        "cached_first_action",
        "selected_first_action",
        "same_as_v6_cached_action",
        "different_suffix_same_first_action",
        "selected_terminal_reason",
        "selected_terminal_step",
        "selected_score",
        "nonterminal_h12_b24",
        "release_terminal_h12_b24",
        "release_step_h12_b24",
        "release_score_h12_b24",
        "left_terminal_h12_b24",
        "left_step_h12_b24",
        "left_score_h12_b24",
        "right_terminal_h12_b24",
        "right_step_h12_b24",
        "right_score_h12_b24",
        "different_first_action_dies_later",
        "nonterminal_h24_b24",
        "nonterminal_h12_b96",
        "nonterminal_h24_b96",
        "selected_first_action_executed",
        "snapshot_restored",
    ]
    rows = []
    for review in reviews:
        for trigger in review["terminal_triggers"]:
            forced = trigger["forced_first_actions"]
            selected = trigger["selected_candidate"]
            row = {
                "seed": trigger["seed"],
                "episode_step": trigger["episode_step"],
                "trigger_kind": trigger["trigger_kind"],
                "headroom": trigger["player_state"]["headroom"],
                "supported_floor": trigger["support_state"][
                    "supported_floor"
                ],
                "airborne": trigger["support_state"]["airborne"],
                "cached_first_action": trigger["cached_first_action"],
                "selected_first_action": trigger["selected_first_action"],
                "same_as_v6_cached_action": trigger[
                    "same_as_v6_cached_action"
                ],
                "different_suffix_same_first_action": trigger[
                    "different_suffix_same_first_action"
                ],
                "selected_terminal_reason": selected[
                    "predicted_terminal_reason"
                ],
                "selected_terminal_step": selected["terminal_step"],
                "selected_score": selected["score"],
                "nonterminal_h12_b24": trigger[
                    "nonterminal_candidate_exists_h12_b24"
                ],
                "different_first_action_dies_later": "|".join(
                    trigger["different_first_action_dies_later"]
                ),
                "nonterminal_h24_b24": _extended_any_nonterminal(
                    trigger, "h24_b24"
                ),
                "nonterminal_h12_b96": _extended_any_nonterminal(
                    trigger, "h12_b96"
                ),
                "nonterminal_h24_b96": _extended_any_nonterminal(
                    trigger, "h24_b96"
                ),
                "selected_first_action_executed": trigger[
                    "selected_first_action_executed"
                ],
                "snapshot_restored": trigger["formal_global_search"][
                    "snapshot_restored"
                ],
            }
            for prefix, action in (
                ("release", "RELEASE_ALL"),
                ("left", "LEFT"),
                ("right", "RIGHT"),
            ):
                candidate = forced[action]["selected"]
                row[f"{prefix}_terminal_h12_b24"] = candidate[
                    "predicted_terminal_reason"
                ]
                row[f"{prefix}_step_h12_b24"] = candidate[
                    "terminal_step"
                ]
                row[f"{prefix}_score_h12_b24"] = candidate["score"]
            rows.append(row)
    if CSV_OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫Phase 2F CSV：{CSV_OUTPUT}")
    with CSV_OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_svg(reviews: list[dict[str, object]]) -> None:
    if SVG_OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫Phase 2F SVG：{SVG_OUTPUT}")
    width = 1100
    height = 620
    left = 70
    right = 30
    top = 55
    panel_height = 235
    gap = 55
    colors = {16002: "#2563eb", 16030: "#dc2626"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#111827}'
        '.axis{stroke:#9ca3af;stroke-width:1}.grid{stroke:#e5e7eb;stroke-width:1}'
        '.trigger{stroke:#111827;stroke-width:1;stroke-dasharray:4 3}</style>',
        '<text x="70" y="30" font-size="20" font-weight="600">'
        'Oracle v8 Phase 2F: headroom and bounded survival timeline</text>',
    ]
    for panel, review in enumerate(reviews):
        timeline = review["timeline"]
        seed = int(review["seed"])
        y0 = top + panel * (panel_height + gap)
        plot_width = width - left - right
        steps = [int(row["step"]) for row in timeline]
        headrooms = [float(row["headroom"]) for row in timeline]
        survivals = [
            float(row["forced_first_max_survival_steps"])
            for row in timeline
        ]
        x_min, x_max = min(steps), max(steps)
        h_min = min(min(headrooms), -2.0)
        h_max = max(max(headrooms), 12.0)

        def sx(step: float) -> float:
            return left + (step - x_min) / max(1, x_max - x_min) * plot_width

        def sy_head(value: float) -> float:
            return y0 + panel_height - (
                (value - h_min) / max(1e-9, h_max - h_min) * panel_height
            )

        def sy_survival(value: float) -> float:
            return y0 + panel_height - value / 12.0 * panel_height

        parts.extend([
            f'<line class="axis" x1="{left}" y1="{y0 + panel_height}" '
            f'x2="{width-right}" y2="{y0 + panel_height}"/>',
            f'<line class="axis" x1="{left}" y1="{y0}" x2="{left}" '
            f'y2="{y0 + panel_height}"/>',
            f'<text x="{left}" y="{y0 - 12}" font-size="15" font-weight="600">'
            f'seed {seed} (solid=headroom px, dashed=max forced survival steps)</text>',
        ])
        for value in (0, 6, 12):
            y = sy_survival(value)
            parts.append(
                f'<line class="grid" x1="{left}" y1="{y}" x2="{width-right}" y2="{y}"/>'
            )
        head_points = " ".join(
            f"{sx(step):.1f},{sy_head(value):.1f}"
            for step, value in zip(steps, headrooms, strict=True)
        )
        survival_points = " ".join(
            f"{sx(step):.1f},{sy_survival(value):.1f}"
            for step, value in zip(steps, survivals, strict=True)
        )
        color = colors[seed]
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{head_points}"/>'
        )
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-dasharray="7 4" points="{survival_points}"/>'
        )
        entry = int(review["trigger_timing"]["v8_terminal_risk_entry_step"])
        unavoidable = review["trigger_timing"][
            "first_persistently_unavoidable_step_h12_b24"
        ]
        for step, label in ((entry, "v8 trigger"), (unavoidable, "unavoidable")):
            if step is None:
                continue
            x = sx(float(step))
            parts.append(
                f'<line class="trigger" x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" '
                f'y2="{y0 + panel_height}"/>'
            )
            parts.append(
                f'<text x="{x + 4:.1f}" y="{y0 + 16}" font-size="11">{label} {step}</text>'
            )
        parts.append(
            f'<text x="{width-right-150}" y="{y0 + panel_height + 24}" '
            f'font-size="12">episode step {x_min}–{x_max}</text>'
        )
    parts.append('</svg>')
    SVG_OUTPUT.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    for path, expected in EXPECTED_HASHES.items():
        if not path.exists() or _sha256(path) != expected:
            raise RuntimeError(f"frozen evidence hash mismatch：{path}")
    formal = json.loads(FORMAL_ARTIFACT.read_text(encoding="utf-8"))
    failures = {
        int(row["seed"]): (
            row["v6"]["terminal_reason"],
            int(row["v6"]["deepest_floor"]),
        )
        for row in formal["development"]["per_seed_paired_results"]
        if row["outcome"] == "both_failure"
    }
    expected_failures = {
        16002: ("top", 5),
        16009: ("bottom", 7),
        16030: ("top", 7),
        16086: ("bottom", 7),
    }
    source_checks = {
        "formal_status_is_fail_stop_v8_development": (
            formal.get("status") == "FAIL_STOP_V8_DEVELOPMENT"
        ),
        "both_failure_seeds_and_outcomes_exact": failures == expected_failures,
        "top_failure_seeds_exact": TOP_FAILURE_SEEDS == (16002, 16030),
        "holdout_unused": formal["holdout"]["used"] is False,
        "all_frozen_hashes_match": True,
    }
    if not all(source_checks.values()):
        raise RuntimeError(f"Phase 2F source checks failed：{source_checks}")

    reviews = [review_top_failure(seed) for seed in TOP_FAILURE_SEEDS]
    summary = _summary(reviews)
    integrity_passed = all(
        all(bool(value) for value in review["integrity"].values())
        for review in reviews
    )
    payload = {
        "schema_version": "simulator-oracle-v8-phase2f-trigger-diagnostics-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formal_gate": False,
        "development_diagnostic_only": True,
        "production_modified": False,
        "protocol_modified": False,
        "source_artifact": str(FORMAL_ARTIFACT),
        "source_artifact_sha256": _sha256(FORMAL_ARTIFACT),
        "protocol": str(PROTOCOL),
        "protocol_sha256": _sha256(PROTOCOL),
        "source_hashes": {
            str(path): _sha256(path) for path in EXPECTED_HASHES
        },
        "source_checks": source_checks,
        "failure_seed_ledger": {
            str(seed): {"terminal_reason": reason, "deepest_floor": floor}
            for seed, (reason, floor) in failures.items()
        },
        "reviewed_top_failure_seeds": list(TOP_FAILURE_SEEDS),
        "summary": summary,
        "episode_reviews": reviews,
        "integrity_passed": integrity_passed,
        "holdout": {"partition": "17000-17099", "used": False},
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
    }
    _write_json(RAW_OUTPUT, payload)
    _write_csv(reviews)
    _write_svg(reviews)
    print(json.dumps({
        "status": "PHASE2F_TRIGGER_DIAGNOSTICS_COMPLETE",
        "raw_artifact": str(RAW_OUTPUT),
        "csv": str(CSV_OUTPUT),
        "visualization": str(SVG_OUTPUT),
        "summary": summary,
        "integrity_passed": integrity_passed,
        "holdout_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
