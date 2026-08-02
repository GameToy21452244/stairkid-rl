from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from _common import PROJECT_ROOT, run_main
from stair_agent.calibration_analysis import player_state
from stair_agent.teacher_control_audit import (
    ACTION_NAMES,
    aggregate_special_encounters,
    leave_one_episode_out,
    select_normal_transition,
)


DEFAULT_RUNS = (
    "logs/teacher_real_micro_20260803_010405_293428",
    "logs/teacher_real_micro_20260803_011114_410228",
    "logs/teacher_real_micro_20260803_012857_250916",
    "logs/teacher_real_micro_20260803_014454_612146",
)
DEFAULT_PRIMARY_RUN = "logs/teacher_real_micro_20260803_012857_250916"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offline-only Teacher action-dynamics and special-encounter audit; "
            "this command never loads an input backend or sends game input."
        )
    )
    parser.add_argument(
        "--run",
        action="append",
        dest="runs",
        help="Real micro run directory; may be repeated.",
    )
    parser.add_argument(
        "--primary-run",
        default=DEFAULT_PRIMARY_RUN,
        help="Complete run used for current separated Gate status.",
    )
    parser.add_argument(
        "--primary-gate",
        help=(
            "Optional immutable Gate/reclassification artifact used for the "
            "current status instead of the run's original Gate JSON."
        ),
    )
    parser.add_argument(
        "--artifact",
        default="artifacts/teacher_control_strategy_audit_v1.json",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_evidence(
    run_paths: list[Path],
) -> tuple[list, list[dict[str, Any]], list[dict[str, str]], int]:
    normal_samples = []
    encounters: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    transition_count = 0
    for run_path in run_paths:
        if not run_path.is_dir():
            raise RuntimeError(f"找不到 run 目錄：{run_path}")
        transition_paths = sorted(run_path.glob("episode_*.transitions.jsonl"))
        if not transition_paths:
            raise RuntimeError(f"run 缺少 transitions：{run_path}")
        for transition_path in transition_paths:
            stem = transition_path.name.replace(".transitions.jsonl", "")
            controller_path = run_path / f"{stem}.controller.jsonl"
            if not controller_path.is_file():
                raise RuntimeError(f"缺少 controller sidecar：{controller_path}")
            transitions = _jsonl(transition_path)
            controllers = _jsonl(controller_path)
            source = f"{run_path.name}/{stem}"
            transition_by_step = {
                int(row.get("step", -1)): row for row in transitions
            }
            enriched_controllers = []
            for controller in controllers:
                step = int(controller.get("step", -1))
                transition = transition_by_step.get(step) or {}
                enriched_controllers.append(
                    {
                        **controller,
                        "terminated": bool(transition.get("terminated")),
                        "truncated": bool(transition.get("truncated")),
                    }
                )
            controller_by_step = {
                int(row.get("step", -1)): row for row in enriched_controllers
            }
            previous_action: int | None = None
            for transition in transitions:
                step = int(transition.get("step", -1))
                selected = select_normal_transition(
                    transition,
                    controller_by_step.get(step),
                    source=source,
                    previous_action=previous_action,
                )
                if selected is not None:
                    normal_samples.append(selected)
                try:
                    previous_action = int(transition["action"])
                except (KeyError, TypeError, ValueError):
                    previous_action = None
            encounters.extend(
                aggregate_special_encounters(enriched_controllers, source=source)
            )
            transition_count += len(transitions)
            for path in (transition_path, controller_path):
                sources.append(
                    {
                        "path": str(path.relative_to(PROJECT_ROOT)),
                        "sha256": _sha256(path),
                    }
                )
    return normal_samples, encounters, sources, transition_count


def _quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "p95": None, "minimum": None, "maximum": None}
    return {
        "median": float(np.median(values)),
        "p95": float(np.quantile(values, 0.95)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def action_audit(samples: list) -> dict[str, Any]:
    held_out = leave_one_episode_out(samples)
    counts = {
        ACTION_NAMES[action]: sum(row.action == action for row in samples)
        for action in sorted(ACTION_NAMES)
    }
    regimes = {
        regime: sum(row.regime == regime for row in samples)
        for regime in sorted({row.regime for row in samples})
    }
    release_rows = [
        row for row in samples if row.action == 0 and abs(row.vx) >= 20.0
    ]
    release_displacements = [abs(row.next_x - row.x) for row in release_rows]
    old_release_errors = [
        abs(row.x + row.vx * 0.25 - row.next_x) for row in release_rows
    ]
    short_release_errors = [
        abs(row.x + row.vx * 0.05 - row.next_x) for row in release_rows
    ]
    overall = held_out["overall"]
    by_action = held_out["by_action"]
    rollouts = held_out["rollouts"]
    checks = {
        "at_least_8_held_out_episodes": held_out["episodes"] >= 8,
        "each_action_has_30_samples": all(value >= 30 for value in counts.values()),
        "reverse_braking_each_has_30_samples": (
            regimes.get("left_reverse_braking", 0) >= 30
            and regimes.get("right_reverse_braking", 0) >= 30
        ),
        "overall_x_beats_carry_baseline": bool(
            overall["model_x_mae"] is not None
            and overall["carry_x_mae"] is not None
            and overall["model_x_mae"] < overall["carry_x_mae"]
        ),
        "overall_vx_beats_carry_baseline": bool(
            overall["model_vx_mae"] is not None
            and overall["carry_vx_mae"] is not None
            and overall["model_vx_mae"] < overall["carry_vx_mae"]
        ),
        "each_action_x_beats_carry_baseline": all(
            metrics["model_x_mae"] is not None
            and metrics["carry_x_mae"] is not None
            and metrics["model_x_mae"] < metrics["carry_x_mae"]
            for metrics in by_action.values()
        ),
        "two_to_five_step_rollouts_beat_carry": all(
            metrics["windows"] >= 20
            and metrics["model_x_mae"] is not None
            and metrics["carry_x_mae"] is not None
            and metrics["model_x_mae"] < metrics["carry_x_mae"]
            for metrics in rollouts.values()
        ),
    }
    return {
        "strict_sample_count": len(samples),
        "counts_by_action": counts,
        "counts_by_regime": regimes,
        "timing_ms": {
            "observation_to_next": _quantiles(
                [row.observation_to_next_ms for row in samples]
            ),
            "effective_to_next": _quantiles(
                [row.effective_to_next_ms for row in samples]
            ),
            "processing_to_command": _quantiles(
                [row.processing_to_command_ms for row in samples]
            ),
        },
        "release_nonzero": {
            "samples": len(release_rows),
            "absolute_displacement_px": _quantiles(release_displacements),
            "old_vx_times_0_25_x_mae_px": float(np.mean(old_release_errors))
            if old_release_errors
            else None,
            "short_vx_times_0_05_x_mae_px": float(np.mean(short_release_errors))
            if short_release_errors
            else None,
        },
        "held_out": held_out,
        "checks": checks,
        "shadow_model_eligible": all(checks.values()),
        "live_deployment_approved": False,
    }


def calibration_regime_audit() -> tuple[dict[str, Any], list[dict[str, str]]]:
    paths = sorted((PROJECT_ROOT / "logs").glob("calibration_v1*.jsonl"))
    review_path = (
        PROJECT_ROOT
        / "artifacts"
        / "reverse_braking_calibration_manifest_v1.json"
    )
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.is_file()
        else {"runs": []}
    )
    excluded_names = {
        Path(row["path"]).name
        for row in review.get("runs", [])
        if not row.get("include_in_diagnostic_summary", False)
    }
    counts = {
        "left_reverse_braking": 0,
        "right_reverse_braking": 0,
        "first_release_after_left": 0,
        "first_release_after_right": 0,
    }
    strict_rows = 0
    sources = []
    for path in paths:
        sources.append(
            {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": _sha256(path),
            }
        )
        if path.name in excluded_names:
            continue
        previous_action: int | None = None
        for row in _jsonl(path):
            before = player_state(row["observation"])
            after = player_state(row["next_observation"])
            dt = float(row["next_observation_timestamp"]) - float(
                row["observation_timestamp"]
            )
            action = int(row["action"])
            clean = bool(
                before["present"] > 0.5
                and after["present"] > 0.5
                and not row.get("events")
                and 0 < dt <= 0.25
                and 72.0 <= before["x"] <= 391.0
                and abs(before["motion"]) > 0.5
                and before["motion"] == after["motion"]
            )
            if clean:
                strict_rows += 1
                if action == 1 and before["vx"] > 20.0:
                    counts["left_reverse_braking"] += 1
                if action == 2 and before["vx"] < -20.0:
                    counts["right_reverse_braking"] += 1
                if action == 0 and previous_action == 1:
                    counts["first_release_after_left"] += 1
                if action == 0 and previous_action == 2:
                    counts["first_release_after_right"] += 1
            previous_action = action
    return (
        {
            "source_files": len(paths) - len(excluded_names),
            "source_files_total": len(paths),
            "excluded_files": sorted(excluded_names),
            "strict_continuous_rows": strict_rows,
            "counts": counts,
            "controller_context_available": False,
            "merge_into_primary_gate": False,
            "fixed_platform_qualification": review.get("qualification"),
            "fixed_platform_included_new_totals": review.get(
                "included_new_diagnostic_totals"
            ),
            "conclusion": (
                "Fixed-platform reversal rows are diagnostic-only; they do "
                "not repair natural landing-context coverage and lack "
                "controller sidecars."
            ),
        },
        sources,
    )


def _read_gate(run_path: Path) -> dict[str, Any]:
    path = run_path / "teacher_real_game_micro_gate.json"
    if not path.is_file():
        raise RuntimeError(f"primary run 缺少 Gate JSON：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _format(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _write(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise RuntimeError(f"拒絕覆寫既有報告；請明確加 --overwrite：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def dynamics_report(payload: dict[str, Any]) -> str:
    action = payload["action_dynamics"]
    held_out = action["held_out"]
    lines = [
        "# Action-Conditioned Dynamics Report",
        "",
        f"- generated at: {payload['generated_at']}",
        f"- real transitions read: {payload['transition_count']}",
        f"- strict normal-motion rows: {action['strict_sample_count']}",
        f"- held-out episodes: {held_out['episodes']}",
        f"- shadow model eligible: **{action['shadow_model_eligible']}**",
        "- live deployment approved: **False**",
        "",
        "This report is offline-only. It reuses the horizontal coefficient form already present in `CalibratedObservationModel`; it does not add a second live dynamics subsystem.",
        "",
        "## Episode-held-out one-step error",
        "",
        "| Regime | n | model x MAE | carry x MAE | model vx MAE | carry vx MAE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in [("OVERALL", held_out["overall"]), *held_out["by_action"].items()]:
        lines.append(
            f"| {name} | {metrics['samples']} | {_format(metrics['model_x_mae'])} | {_format(metrics['carry_x_mae'])} | {_format(metrics['model_vx_mae'])} | {_format(metrics['carry_vx_mae'])} |"
        )
    lines += [
        "",
        "## Action-history regimes",
        "",
        "| Regime | n | model x MAE | carry x MAE |",
        "|---|---:|---:|---:|",
    ]
    for name, metrics in held_out["by_regime"].items():
        lines.append(
            f"| {name} | {metrics['samples']} | {_format(metrics['model_x_mae'])} | {_format(metrics['carry_x_mae'])} |"
        )
    lines += [
        "",
        "## Actual-action rollout audit",
        "",
        "| Horizon | windows | model x MAE | carry x MAE |",
        "|---:|---:|---:|---:|",
    ]
    for horizon, metrics in held_out["rollouts"].items():
        lines.append(
            f"| {horizon} | {metrics['windows']} | {_format(metrics['model_x_mae'])} | {_format(metrics['carry_x_mae'])} |"
        )
    release = action["release_nonzero"]
    lines += [
        "",
        "## Release evidence",
        "",
        f"- non-zero release rows: {release['samples']}",
        f"- absolute displacement median / max: {_format(release['absolute_displacement_px']['median'])} / {_format(release['absolute_displacement_px']['maximum'])} px",
        f"- old `vx × 0.25 s` x MAE: {_format(release['old_vx_times_0_25_x_mae_px'])} px",
        f"- short `vx × 0.05 s` x MAE: {_format(release['short_vx_times_0_05_x_mae_px'])} px",
        "",
        "## Acceptance checks",
        "",
    ]
    lines += [
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in action["checks"].items()
    ]
    lines += [
        "",
        "Result: action-conditioned dynamics remains a supported research direction, but failed checks block live deployment. In particular, reverse-braking coverage and/or held-out sequence quality must be repaired before controller integration.",
    ]
    calibration = action["historical_calibration_coverage"]
    calibration_counts = calibration["counts"]
    lines += [
        "",
        "## Historical calibration coverage check",
        "",
        f"- files / strict continuous rows: {calibration['source_files']} / {calibration['strict_continuous_rows']}",
        f"- excluded interrupted files: {calibration['excluded_files']}",
        f"- reverse LEFT / RIGHT: {calibration_counts['left_reverse_braking']} / {calibration_counts['right_reverse_braking']}",
        f"- first release after LEFT / RIGHT: {calibration_counts['first_release_after_left']} / {calibration_counts['first_release_after_right']}",
        "- controller sidecar context: unavailable; these rows are not merged into the primary deployment Gate",
        "",
        "The fixed-platform archive confirms that action reversal changes short-horizon motion, but it cannot close the natural landing-context evidence gap. Further fixed-platform oscillation is stopped. The next representative source must be bounded natural Teacher trajectories with full controller sidecars; the candidate model remains offline and cannot affect those actions.",
    ]
    return "\n".join(lines)


def normal_gate_report(payload: dict[str, Any]) -> str:
    gate = payload["primary_gate"]
    metrics = gate.get("metrics") or {}
    episodes = gate.get("episodes") or []
    floors = [episode.get("floors") for episode in episodes]
    gate_result = gate.get("gate") or {}
    checks = gate_result.get("checks") or {}
    status = str(gate_result.get("status") or "UNKNOWN")
    if status == "PASS":
        conclusion = (
            "The completed bounded natural run passes the current semantic "
            "Gate. This clears the three-episode micro Gate only; the single "
            "floor-2 lower-tail episode still requires the planned 10-episode "
            "stability Gate before P4.0 Student training."
        )
    else:
        conclusion = (
            "The current primary Gate remains failed. Offline dynamics model "
            "quality does not substitute for closed-loop normal-landing "
            "evidence and cannot authorize live deployment."
        )
    return "\n".join(
        [
            "# Normal Landing Gate",
            "",
            f"- status: **{status}**",
            f"- primary evidence: `{payload['primary_run']}`",
            f"- primary Gate artifact: `{payload['primary_gate_artifact']}`",
            f"- episodes / floors: {len(episodes)} / `{floors}`",
            f"- mean / median / Q25 / CVaR25: {_format(metrics.get('mean_floors'))} / {_format(metrics.get('median_floors'))} / {_format(metrics.get('floor_q25'))} / {_format(metrics.get('floor_cvar25'))}",
            f"- reach floor 3: {metrics.get('reach_floor_3', 0)}/{len(episodes)}",
            f"- reach floor 5: {metrics.get('reach_floor_5', 0)}/{len(episodes)}",
            f"- reach-3 check: {checks.get('reach_floor_3_case')}",
            "",
            conclusion,
        ]
    )


def encounter_report(payload: dict[str, Any], kind: str) -> str:
    title = "Spring Escape Gate" if kind == "spring" else "Spike Escape Gate"
    encounters = [
        row for row in payload["special_encounters"] if row["kind"] == kind
    ]
    if kind == "spring":
        status = "INSUFFICIENT_EVIDENCE"
        conclusion = (
            "Contact/source IDs fragment in some multi-bounce encounters, but the latest complete Gate also records successful exit/progress. This authorizes encounter telemetry only, not a new Spring FSM."
        )
    else:
        status = "PROVISIONAL LOCAL PASS; NOT QUALIFIED"
        conclusion = (
            "The latest observed spike contacts are bounded, while later failures occur during landing/recovery. The sample is too small for global qualification and does not support a new Spike FSM."
        )
    lines = [
        f"# {title}",
        "",
        f"- status: **{status}**",
        f"- offline encounters across reviewed runs: {len(encounters)}",
        "",
        "An encounter bridges only short same-kind gaps. It is a diagnostic grouping and does not claim unstable detector IDs represent one physical platform.",
        "",
        "| Source | steps | contact/source IDs | contact steps | bounce | damage | health gain | normal landing | release | reversals | floor progress | exit | terminal nearby |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in encounters:
        ids = f"{row['contact_ids']} / {row['source_platform_ids']}"
        lines.append(
            f"| {row['source']} | {row['start_step']}-{row['end_step']} | {ids} | {row['contact_steps']} | {row['bounce_count']} | {row['spike_damage_count']} | {row['health_gain_count']} | {row['normal_landing_count']} | {row['release_count']} | {row['direction_reversal_count']} | {row['floor_progress']} | {row['exit_observed']} | {row['terminal_within_outcome']} |"
        )
    lines += ["", conclusion]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    run_paths = [_resolve(path) for path in (args.runs or DEFAULT_RUNS)]
    primary_run = _resolve(args.primary_run)
    samples, encounters, sources, transition_count = load_evidence(run_paths)
    if not samples:
        raise RuntimeError("嚴格篩選後沒有 normal transition，拒絕產生空白結論。")
    primary_gate_path = (
        _resolve(args.primary_gate)
        if args.primary_gate
        else primary_run / "teacher_real_game_micro_gate.json"
    )
    if not primary_gate_path.is_file():
        raise RuntimeError(f"找不到 primary Gate artifact：{primary_gate_path}")
    primary_gate = json.loads(primary_gate_path.read_text(encoding="utf-8"))
    action_dynamics = action_audit(samples)
    calibration_coverage, calibration_sources = calibration_regime_audit()
    action_dynamics["historical_calibration_coverage"] = calibration_coverage
    sources.extend(calibration_sources)
    payload = {
        "schema_version": "teacher-control-strategy-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "offline-read-only",
        "sends_game_input": False,
        "runs": [str(path.relative_to(PROJECT_ROOT)) for path in run_paths],
        "primary_run": str(primary_run.relative_to(PROJECT_ROOT)),
        "primary_gate_artifact": str(
            primary_gate_path.relative_to(PROJECT_ROOT)
        ),
        "transition_count": transition_count,
        "sources": sources,
        "action_dynamics": action_dynamics,
        "special_encounters": encounters,
        "primary_gate": primary_gate,
        "implementation_decisions": {
            "live_controller_changed": False,
            "spring_fsm_added": False,
            "spike_fsm_added": False,
            "active_stuck_watchdog_added": False,
            "p4_student_training_started": False,
        },
    }
    artifact_path = _resolve(args.artifact)
    _write(
        artifact_path,
        json.dumps(payload, ensure_ascii=False, indent=2),
        overwrite=args.overwrite,
    )
    report_contents = {
        PROJECT_ROOT / "reports/ACTION_CONDITIONED_DYNAMICS_REPORT.md": dynamics_report(payload),
        PROJECT_ROOT / "reports/NORMAL_LANDING_GATE.md": normal_gate_report(payload),
        PROJECT_ROOT / "reports/SPRING_ESCAPE_GATE.md": encounter_report(payload, "spring"),
        PROJECT_ROOT / "reports/SPIKE_ESCAPE_GATE.md": encounter_report(payload, "spikes"),
    }
    for path, content in report_contents.items():
        _write(path, content, overwrite=args.overwrite)
    print(json.dumps(payload["action_dynamics"], ensure_ascii=False, indent=2))
    print(f"artifact={artifact_path}")
    for path in report_contents:
        print(f"report={path}")


if __name__ == "__main__":
    run_main(main)
