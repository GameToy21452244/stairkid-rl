"""Analyse existing real-game data for normal-platform fidelity calibration.

This script reads committed artifacts (alignment audit JSON, calibration
summaries, etc.) and outputs a machine-readable summary of the evidence
available for v0.5 calibration.  It does NOT:
- Launch NS Shaft.exe or send keystrokes
- Use formal holdout seeds
- Access raw captures (which are gitignored and not pushed)
- Fabricate data when files are missing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow importing project modules when run from scripts/
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _analyze_alignment_audit(project_root: Path) -> dict:
    """Extract calibration-relevant data from the alignment audit artifact."""
    path = project_root / "artifacts" / "simulator_real_alignment_audit_v3.json"
    data = _load_json(path)
    if data is None:
        return {"status": "MISSING", "path": str(path)}

    result: dict = {"status": "FOUND", "path": str(path)}

    # --- Action response (delta_vx at 125ms cadence) ---
    primary = data.get("primary_real", {})
    secondary = data.get("secondary_real", {})
    simulator = data.get("simulator", {})

    result["real_cadence_ms"] = primary.get("cadence_ms", {}).get("median")
    result["simulator_cadence_ms"] = simulator.get("cadence_ms", {}).get("median")

    # Horizontal response
    action_resp = primary.get("action_response", {})
    result["real_left_delta_vx_median"] = action_resp.get("LEFT", {}).get(
        "delta_vx_median"
    )
    result["real_right_delta_vx_median"] = action_resp.get("RIGHT", {}).get(
        "delta_vx_median"
    )
    result["real_left_delta_x_median"] = action_resp.get("LEFT", {}).get(
        "delta_x_median"
    )
    result["real_right_delta_x_median"] = action_resp.get("RIGHT", {}).get(
        "delta_x_median"
    )
    result["real_release_delta_vx_median"] = action_resp.get(
        "RELEASE_ALL", {}
    ).get("delta_vx_median")

    # Secondary real data
    sec_resp = secondary.get("action_response", {})
    result["secondary_left_delta_vx_median"] = sec_resp.get("LEFT", {}).get(
        "delta_vx_median"
    )
    result["secondary_right_delta_vx_median"] = sec_resp.get("RIGHT", {}).get(
        "delta_vx_median"
    )

    # Simulator response
    sim_resp = simulator.get("action_response", {})
    result["sim_left_delta_vx_median"] = sim_resp.get("LEFT", {}).get(
        "delta_vx_median"
    )
    result["sim_right_delta_vx_median"] = sim_resp.get("RIGHT", {}).get(
        "delta_vx_median"
    )

    # Scale ratios
    ratios = data.get("action_response_scale_ratio_simulator_over_real", {})
    result["sim_over_real_left_ratio"] = ratios.get("LEFT_abs_delta_vx_median")
    result["sim_over_real_right_ratio"] = ratios.get(
        "RIGHT_abs_delta_vx_median"
    )

    # Motion / falling data
    result["real_motion_counts"] = primary.get("motion_counts")
    result["real_falling_records"] = primary.get("motion_counts", {}).get(
        "falling", 0
    )
    result["real_rising_records"] = primary.get("motion_counts", {}).get(
        "rising", 0
    )

    # Support phase data
    result["real_max_rising_support_streak"] = primary.get(
        "max_rising_support_persistence_streak"
    )
    result["sim_max_rising_support_streak"] = simulator.get(
        "max_rising_support_persistence_streak"
    )

    # Sample counts
    result["real_left_samples"] = action_resp.get("LEFT", {}).get("samples", 0)
    result["real_right_samples"] = action_resp.get("RIGHT", {}).get(
        "samples", 0
    )
    result["real_release_samples"] = action_resp.get("RELEASE_ALL", {}).get(
        "samples", 0
    )

    return result


def _analyze_calibration_summary(project_root: Path) -> dict:
    """Extract calibration candidate data."""
    path = (
        project_root
        / "artifacts"
        / "manual_simulator_calibration"
        / "calibration_summary.json"
    )
    data = _load_json(path)
    if data is None:
        return {"status": "MISSING", "path": str(path)}
    candidate = data.get("candidate", {})
    return {
        "status": "FOUND",
        "path": str(path),
        "v04_horizontal_acceleration": candidate.get("horizontal_acceleration"),
        "v04_scroll_speed": candidate.get("scroll_speed"),
        "v04_horizontal_shift_median": candidate.get("horizontal_shift_median"),
        "v04_horizontal_shift_q75": candidate.get("horizontal_shift_q75"),
        "v04_vertical_gap_median": candidate.get("vertical_gap_median"),
        "v04_swept_edge_collision": candidate.get("swept_edge_collision"),
    }


def _search_raw_data(project_root: Path) -> dict:
    """Search for raw real-game data files that might contain platform
    bounding boxes, falling trajectories, player tracking, etc."""
    raw_patterns = [
        "teacher_real_micro",
        "platform_detection",
        "platform_boxes",
        "frame_log",
        "player_track",
        "falling",
        "observation",
    ]
    found_files: list[str] = []
    missing_dirs: list[str] = []

    captures_dir = project_root / "captures"
    if captures_dir.exists():
        for f in captures_dir.rglob("*"):
            if f.is_file() and f.suffix in {".json", ".jsonl", ".csv", ".npz"}:
                found_files.append(str(f.relative_to(project_root)))
    else:
        missing_dirs.append("captures/")

    # Check for any data files matching patterns
    for pattern in raw_patterns:
        for ext in [".json", ".jsonl", ".csv", ".npz"]:
            for f in project_root.rglob(f"*{pattern}*{ext}"):
                rel = str(f.relative_to(project_root))
                if rel not in found_files:
                    found_files.append(rel)

    return {
        "found_data_files": sorted(found_files),
        "missing_directories": missing_dirs,
        "gitignore_excludes_captures": True,
        "gitignore_excludes_manual_sessions": True,
        "note": (
            "Raw real-game captures (teacher_real_micro_*, platform bounding "
            "boxes, falling trajectories) are excluded by .gitignore and not "
            "pushed to the repository. Only aggregated statistics in the "
            "alignment audit artifact are available."
        ),
    }


def _derive_physics_estimates(alignment: dict) -> dict:
    """Derive provisional physics estimates from available data.

    These are NOT from raw trajectory fitting. They are inferred from the
    aggregate statistics in the alignment audit and the calibration reports.
    """
    estimates: dict = {}

    # --- Platform width ---
    # No raw bounding box data available. Reports mention real playfield
    # width = 423 - 40 = 383 px. The visual ratio of platform to playfield
    # from the YouTube video suggests platforms are roughly 1/5 to 1/6 of
    # playfield width. 383/5 ≈ 76.6, 383/6 ≈ 63.8.
    # With player width 24 px, the ratio is roughly 3:1 for a 72px platform.
    estimates["platform_width"] = {
        "provisional_value": 72.0,
        "evidence_source": "VIDEO_VISUAL_RATIO",
        "playfield_width_px": 383.0,
        "estimated_ratio_to_playfield": 72.0 / 383.0,
        "player_to_platform_ratio": 24.0 / 72.0,
        "alternatives_for_comparison": [64.0, 72.0, 80.0],
        "note": (
            "No raw platform bounding box data in repo. 72 px is a visual "
            "estimate from video. User confirmed 96 px is too wide."
        ),
    }

    # --- Gravity and max fall speed ---
    # No raw falling trajectory data for proper second-derivative fitting.
    # The real cadence is 125ms. At 48px platform spacing:
    # Free-fall time for 48 px at g=320: t = sqrt(2*48/320) ≈ 0.548 s
    # Free-fall time for 48 px at g=192: t = sqrt(2*48/192) ≈ 0.707 s
    # Free-fall time for 48 px at g=400: t = sqrt(2*48/400) ≈ 0.490 s
    # User said 192 was too floaty. 320 is the current candidate.
    estimates["gravity"] = {
        "provisional_value": 320.0,
        "evidence_source": "USER_SUBJECTIVE_PLUS_ESTIMATE",
        "v03_value": 192.0,
        "fall_time_48px_at_192": 0.707,
        "fall_time_48px_at_320": 0.548,
        "fall_time_48px_at_400": 0.490,
        "alternatives_for_comparison": [270.0, 320.0, 380.0],
        "note": (
            "No raw falling trajectory data for proper g estimation. "
            "320 is provisional based on user feedback that 192 is too floaty. "
            "Video suggests brisk descent rhythm consistent with ~300-400 range."
        ),
    }

    estimates["max_fall_speed"] = {
        "provisional_value": 420.0,
        "evidence_source": "PROVISIONAL_ESTIMATE",
        "note": (
            "No data to identify terminal velocity from real game. "
            "420 px/s prevents unrealistic acceleration in deep falls."
        ),
    }

    # --- Scroll speed ---
    # The alignment audit reports real cadence 125ms and delta_x_median for
    # both LEFT and RIGHT around ±18 px per 125ms step. The calibration report
    # states "packet量測值其實是96" for scroll, but v0.4 used 80 subjectively.
    estimates["scroll_speed"] = {
        "data_measured_value": 96.0,
        "v04_subjective_candidate": 80.0,
        "evidence_source": "REAL_GAME_MEASUREMENT",
        "note": (
            "Real game measurement from alignment packet is 96 px/s. "
            "v0.4 used 80 px/s based on user subjective feedback. "
            "v0.5-r3 defaults to 96 (data-supported) with --scroll-speed 80 "
            "available for comparison."
        ),
    }

    # --- Horizontal control ---
    left_dvx = alignment.get("real_left_delta_vx_median")
    right_dvx = alignment.get("real_right_delta_vx_median")
    cadence = alignment.get("real_cadence_ms")

    if left_dvx is not None and right_dvx is not None and cadence:
        # At 125ms cadence, median delta_vx is the velocity change per step
        # LEFT: -44 px/s change per 125ms ≈ -352 px/s² equivalent
        # RIGHT: +63.27 px/s change per 125ms ≈ +506 px/s² equivalent
        left_equiv_accel = abs(left_dvx) / (cadence / 1000.0)
        right_equiv_accel = abs(right_dvx) / (cadence / 1000.0)
        avg_equiv_accel = (left_equiv_accel + right_equiv_accel) / 2.0

        estimates["horizontal_response"] = {
            "real_left_delta_vx_per_125ms": left_dvx,
            "real_right_delta_vx_per_125ms": right_dvx,
            "equivalent_left_acceleration": round(left_equiv_accel, 1),
            "equivalent_right_acceleration": round(right_equiv_accel, 1),
            "average_equivalent_acceleration": round(avg_equiv_accel, 1),
            "note": (
                "These equivalent accelerations include tracker noise, "
                "mixed phases (startup/sustained/release), and are not pure "
                "first-tick startup measurements. The asymmetry (LEFT weaker "
                "than RIGHT) may reflect game asymmetry or tracking bias."
            ),
            "v05_base_acceleration": 420.0,
            "v05_startup_effective": "420 × 2.4 = 1008 px/s²",
            "sim_over_real_left_ratio": alignment.get("sim_over_real_left_ratio"),
            "sim_over_real_right_ratio": alignment.get("sim_over_real_right_ratio"),
        }

    return estimates


def main() -> int:
    project_root = _PROJECT_ROOT

    print(f"Project root: {project_root}")
    print("Searching for real-game calibration data...\n")

    # 1. Alignment audit analysis
    alignment = _analyze_alignment_audit(project_root)
    print(f"Alignment audit: {alignment.get('status')}")

    # 2. Calibration summary
    calibration = _analyze_calibration_summary(project_root)
    print(f"Calibration summary: {calibration.get('status')}")

    # 3. Raw data search
    raw_data = _search_raw_data(project_root)
    print(f"Raw data files found: {len(raw_data['found_data_files'])}")

    # 4. Physics estimates
    estimates = _derive_physics_estimates(alignment)

    # Compile output
    output = {
        "schema_version": "real-normal-fidelity-analysis-v1",
        "project_root": str(project_root),
        "data_sources": {
            "alignment_audit": alignment,
            "calibration_summary": calibration,
            "raw_data_search": raw_data,
        },
        "physics_estimates": estimates,
        "missing_data_for_proper_calibration": [
            {
                "item": "Raw platform bounding boxes",
                "file_pattern": "captures/*/platform_detection*.json",
                "impact": "Cannot compute platform width statistics",
                "workaround": "Using video visual ratio estimate (72 px provisional)",
            },
            {
                "item": "Raw falling trajectory data",
                "file_pattern": "captures/*/player_track*.jsonl",
                "impact": "Cannot fit gravity from second-derivative",
                "workaround": "Using 320 px/s² from user feedback + video rhythm",
            },
            {
                "item": "Raw per-frame scroll measurements",
                "file_pattern": "captures/*/scroll_estimate*.json",
                "impact": "Cannot verify per-frame scroll speed consistency",
                "workaround": "Using 96 px/s from alignment audit aggregate",
            },
            {
                "item": "Per-step velocity time series",
                "file_pattern": "captures/*/frame_log*.csv",
                "impact": (
                    "Cannot analyse 125/250/375ms velocity buildup or "
                    "reversal crossing time"
                ),
                "workaround": "Using aggregate delta_vx medians only",
            },
        ],
        "v05_r3_defaults": {
            "horizontal_acceleration": 420.0,
            "startup_acceleration_multiplier": 2.4,
            "acceleration_curve_exponent": 2.0,
            "air_control_multiplier": 0.85,
            "max_horizontal_speed": 230.0,
            "release_deceleration": 960.0,
            "startup_impulse_speed": 60.0,
            "reversal_brake_speed": 30.0,
            "platform_width": 72.0,
            "gravity": 320.0,
            "max_fall_speed": 420.0,
            "scroll_speed": 96.0,
        },
        "evidence_classification": {
            "data_measured": [
                "real_cadence_125ms",
                "real_left_delta_vx_-44",
                "real_right_delta_vx_+63.27",
                "scroll_speed_96",
                "platform_spacing_48",
                "playfield_bounds_40_423_60_416",
            ],
            "video_visual_inference": [
                "platform_width_72_provisional",
                "fall_rhythm_brisk",
                "arcade_startup_response",
            ],
            "user_subjective": [
                "96px_platform_too_wide",
                "192_gravity_too_floaty",
                "linear_acceleration_wrong",
                "startup_feels_like_resistance",
            ],
            "provisional_unverified": [
                "gravity_320",
                "max_fall_speed_420",
                "startup_impulse_60",
                "reversal_brake_30",
                "scroll_speed_96_vs_80",
            ],
        },
    }

    # Write output
    output_dir = project_root / "artifacts" / "manual_simulator_calibration" / "v05"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "real_normal_fidelity_summary.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nOutput: {output_path}")
    print("\n=== Key findings ===")
    print(f"  Real LEFT delta-vx (125ms): {alignment.get('real_left_delta_vx_median')} px/s")
    print(f"  Real RIGHT delta-vx (125ms): {alignment.get('real_right_delta_vx_median')} px/s")
    print(f"  Sim/Real LEFT ratio: {alignment.get('sim_over_real_left_ratio'):.2f}x")
    print(f"  Sim/Real RIGHT ratio: {alignment.get('sim_over_real_right_ratio'):.2f}x")
    print(f"  Scroll speed (measured): 96 px/s")
    print(f"  Platform width: 72 px (PROVISIONAL - no bounding box data)")
    print(f"  Gravity: 320 px/s^2 (PROVISIONAL - no trajectory fitting)")
    print(f"\n=== Missing raw data ===")
    for item in output["missing_data_for_proper_calibration"]:
        print(f"  - {item['item']}: {item['file_pattern']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
