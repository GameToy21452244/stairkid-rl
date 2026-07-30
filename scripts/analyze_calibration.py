from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from _common import PROJECT_ROOT, run_main
from stair_agent.calibration_analysis import (
    landing_metrics,
    player_state,
)

WIDTH = 634.0
HEIGHT = 431.0
VELOCITY_SCALE = 500.0


def state(values: list[float]) -> dict[str, float]:
    return player_state(values)


def median(values: list[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def main() -> None:
    paths = sorted((PROJECT_ROOT / "logs").glob("calibration_v1*.jsonl"))
    if not paths:
        raise RuntimeError("找不到 calibration_v1 JSONL。")
    rows = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            payload["_source"] = path.name
            rows.append(payload)

    clean = []
    continuous = []
    for row in rows:
        before = state(row["observation"])
        after = state(row["next_observation"])
        events = {event.get("type") for event in row["events"]}
        dt = row["next_observation_timestamp"] - row["observation_timestamp"]
        if (
            before["present"] > 0.5
            and after["present"] > 0.5
            and not events
            and dt > 0
        ):
            clean.append((row, before, after, dt))
            if (
                abs(before["motion"]) > 0.5
                and before["motion"] == after["motion"]
            ):
                continuous.append((row, before, after, dt))

    acceleration = {}
    counts = {}
    for action, name in ((1, "left"), (2, "right")):
        samples = [
            (after["vx"] - before["vx"]) / dt
            for row, before, after, dt in clean
            if row["action"] == action and 55 <= before["x"] <= 410
        ]
        counts[f"{name}_clean"] = len(samples)
        acceleration[name] = median(samples)
    drag_samples = [
        after["vx"] / before["vx"]
        for row, before, after, _dt in clean
        if row["action"] == 0
        and abs(before["vx"]) >= 30
        and before["vx"] * after["vx"] >= 0
    ]
    gravity_samples = [
        (after["vy"] - before["vy"]) / dt
        for row, before, after, dt in continuous
        if row["action"] == 0 and before["motion"] != 0
    ]
    counts["release_nonzero"] = len(drag_samples)
    counts["free_motion"] = len(gravity_samples)

    latency = [
        (row["next_observation_timestamp"] - row["action_effective_timestamp"])
        * 1000
        for row in rows
    ]
    event_counts = {}
    for row in rows:
        for event in row["events"]:
            name = str(event.get("type", "unknown"))
            event_counts[name] = event_counts.get(name, 0) + 1

    # Current v0 one-step model error, excluding discontinuous event steps.
    x_errors = []
    y_errors = []
    vx_errors = []
    vy_errors = []
    for row, before, after, dt in continuous:
        vx = before["vx"]
        if row["action"] == 1:
            vx = max(-230.0, vx - 760.0 * dt)
        elif row["action"] == 2:
            vx = min(230.0, vx + 760.0 * dt)
        else:
            vx *= 0.78
        vy = before["vy"] + 950.0 * dt
        predicted_x = before["x"] + vx * dt
        predicted_y = before["y"] + vy * dt
        x_errors.append(abs(predicted_x - after["x"]))
        y_errors.append(abs(predicted_y - after["y"]))
        vx_errors.append(abs(vx - after["vx"]))
        vy_errors.append(abs(vy - after["vy"]))

    current_errors = {
        "one_step_x_mae_px": float(np.mean(x_errors)),
        "one_step_y_mae_px": float(np.mean(y_errors)),
        "one_step_vx_mae_px_s": float(np.mean(vx_errors)),
        "one_step_vy_mae_px_s": float(np.mean(vy_errors)),
    }
    grouped = {
        path.name: [
            row for row in rows if row["_source"] == path.name
        ]
        for path in paths
    }
    rollout_errors: dict[int, tuple[float | None, float | None, int]] = {}
    for horizon in (10, 30):
        horizon_x = []
        horizon_y = []
        for source_rows in grouped.values():
            for start in range(0, len(source_rows) - horizon + 1):
                window = source_rows[start : start + horizon]
                if any(row["events"] for row in window):
                    continue
                predicted = state(window[0]["observation"])
                for row in window:
                    dt = (
                        row["next_observation_timestamp"]
                        - row["observation_timestamp"]
                    )
                    if row["action"] == 1:
                        predicted["vx"] = max(
                            -230.0, predicted["vx"] - 760.0 * dt
                        )
                    elif row["action"] == 2:
                        predicted["vx"] = min(
                            230.0, predicted["vx"] + 760.0 * dt
                        )
                    else:
                        predicted["vx"] *= 0.78
                    predicted["vy"] += 950.0 * dt
                    predicted["x"] += predicted["vx"] * dt
                    predicted["y"] += predicted["vy"] * dt
                actual = state(window[-1]["next_observation"])
                horizon_x.append(abs(predicted["x"] - actual["x"]))
                horizon_y.append(abs(predicted["y"] - actual["y"]))
        rollout_errors[horizon] = (
            float(np.mean(horizon_x)) if horizon_x else None,
            float(np.mean(horizon_y)) if horizon_y else None,
            len(horizon_x),
        )
        current_errors[f"{horizon}_step_x_mae_px"] = rollout_errors[horizon][0]
        current_errors[f"{horizon}_step_y_mae_px"] = rollout_errors[horizon][1]
        current_errors[f"{horizon}_step_windows"] = rollout_errors[horizon][2]

    fitted_left = abs(acceleration["left"] or -760.0)
    fitted_right = acceleration["right"] or 760.0
    fitted_drag = median(drag_samples) or 0.78
    fitted_gravity = median(gravity_samples) or 950.0
    fx: list[float] = []
    fy: list[float] = []
    fvx: list[float] = []
    fvy: list[float] = []
    for row, before, after, dt in continuous:
        vx = before["vx"]
        if row["action"] == 1:
            vx = max(-230.0, vx - fitted_left * dt)
        elif row["action"] == 2:
            vx = min(230.0, vx + fitted_right * dt)
        else:
            vx *= fitted_drag
        vy = before["vy"] + fitted_gravity * dt
        fx.append(abs(before["x"] + vx * dt - after["x"]))
        fy.append(
            abs(before["y"] + (before["vy"] + vy) * 0.5 * dt - after["y"])
        )
        fvx.append(abs(vx - after["vx"]))
        fvy.append(abs(vy - after["vy"]))
    fitted_errors = {
        "one_step_x_mae_px": float(np.mean(fx)),
        "one_step_y_mae_px": float(np.mean(fy)),
        "one_step_vx_mae_px_s": float(np.mean(fvx)),
        "one_step_vy_mae_px_s": float(np.mean(fvy)),
    }
    landing = landing_metrics(rows)
    landing_gate = bool(
        event_counts.get("landed", 0) >= 20
        and landing.precision >= 0.80
        and landing.recall >= 0.80
        and landing.death_misclassifications == 0
    )
    gates = {
        "left_clean_samples_30": counts["left_clean"] >= 30,
        "right_clean_samples_30": counts["right_clean"] >= 30,
        "release_nonzero_samples_20": counts["release_nonzero"] >= 20,
        "free_motion_samples_30": counts["free_motion"] >= 30,
        "landing_events_20": event_counts.get("landed", 0) >= 20,
        "one_step_x_mae_le_6": fitted_errors["one_step_x_mae_px"] <= 6,
        "one_step_y_mae_le_8": fitted_errors["one_step_y_mae_px"] <= 8,
        "one_step_vx_mae_le_50": fitted_errors["one_step_vx_mae_px_s"] <= 50,
        "one_step_vy_mae_le_60": fitted_errors["one_step_vy_mae_px_s"] <= 60,
        "landing_precision_recall_measured": landing_gate,
        "ten_step_rollout_threshold": bool(
            rollout_errors[10][2]
            and rollout_errors[10][0] <= 25
            and rollout_errors[10][1] <= 30
        ),
        "thirty_step_rollout_threshold": bool(
            rollout_errors[30][2]
            and rollout_errors[30][0] <= 60
            and rollout_errors[30][1] <= 70
        ),
    }
    payload = {
        "schema_version": "calibration-profile-v0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in paths
        ],
        "records": len(rows),
        "clean_records": len(clean),
        "sample_counts": counts,
        "event_counts": event_counts,
        "landing_metrics": {
            "true_positive": landing.true_positive,
            "false_positive": landing.false_positive,
            "false_negative": landing.false_negative,
            "precision": landing.precision,
            "recall": landing.recall,
            "death_misclassifications": landing.death_misclassifications,
        },
        "estimates": {
            "left_acceleration_px_s2": acceleration["left"],
            "right_acceleration_px_s2": acceleration["right"],
            "release_velocity_ratio_per_step": median(drag_samples),
            "screen_gravity_px_s2": median(gravity_samples),
            "effective_to_next_observation_ms_median": median(latency),
        },
        "current_simulator_errors": current_errors,
        "fitted_one_step_errors": fitted_errors,
        "gates": gates,
        "gate_pass": all(gates.values()),
    }
    analysis_revision = "MODEL_V1"
    profile = (
        PROJECT_ROOT
        / "reports"
        / f"CALIBRATION_PROFILE_R{len(paths)}_{analysis_revision}.json"
    )
    report = (
        PROJECT_ROOT
        / "reports"
        / f"CALIBRATION_GATE_REPORT_R{len(paths)}_{analysis_revision}.md"
    )
    for output in (profile, report):
        if output.exists():
            raise FileExistsError(f"拒絕覆寫既有校正結果：{output}")
    profile.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Calibration Gate Report",
        "",
        f"- records: {len(rows)}",
        f"- clean records: {len(clean)}",
        f"- gate pass: **{payload['gate_pass']}**",
        "",
        "## Estimates",
        "",
    ]
    lines += [
        f"- {key}: {value}" for key, value in payload["estimates"].items()
    ]
    lines += ["", "## Current simulator one-step error", ""]
    lines += [
        f"- {key}: {value:.3f}" if isinstance(value, float) else f"- {key}: {value}"
        for key, value in current_errors.items()
    ]
    lines += ["", "## Fitted one-step error", ""]
    lines += [f"- {key}: {value:.3f}" for key, value in fitted_errors.items()]
    lines += ["", "## Landing classifier", ""]
    lines += [
        f"- {key}: {value}"
        for key, value in payload["landing_metrics"].items()
    ]
    lines += ["", "## Gates", ""]
    lines += [
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in gates.items()
    ]
    lines += [
        "",
        "未通過全部門檻前，不開始 learnability probe、BC 或 RL 長訓。",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"profile={profile}")
    print(f"report={report}")


if __name__ == "__main__":
    run_main(main)
