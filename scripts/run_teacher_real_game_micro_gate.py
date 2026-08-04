from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.data.real_alignment import (
    REAL_ALIGNMENT_SCHEMA_VERSION,
    RealAlignmentPacketWriter,
    audit_real_alignment_records,
)
from stair_agent.data.schema import PolicySource
from stair_agent.data.writer import TransitionJsonlWriter, extract_reward_terms
from stair_agent.live_env import LiveGameAdapter, create_live_environment
from stair_agent.hud_detection import FloorCounterTracker
from stair_agent.input_controller import Action, InputError
from stair_agent.real_game_gate import (
    DirectionOscillationTracker,
    DropoutForensicRecorder,
    PhysicalResponseLatencyTracker,
    RealGameMicroLimits,
    SupportDepartureTracker,
    classify_terminal_reason,
    dry_run_manifest,
    observation_confidence,
    outward_wall_push_side,
    playing_telemetry_required,
    reclassify_real_micro_episode,
    safe_unapplied_terminal,
    summarize_real_micro_gate,
)
from stair_agent.object_detection import player_color_diagnostics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Teacher 真實遊戲微型 Gate；預設只 dry-run，不尋找視窗、不載入輸入後端。"
        )
    )
    parser.add_argument("--execute", action="store_true", help="明確允許受限真機 smoke。")
    parser.add_argument(
        "--focus-target",
        action="store_true",
        help="倒數後嘗試將唯一已驗證的遊戲視窗切到前景。",
    )
    parser.add_argument(
        "--dismiss-name-entry",
        action="store_true",
        help=(
            "只對唯一、同程序、owned #32770 且標題符合的姓名視窗"
            "送一次 Enter；不輸入任何文字。"
        ),
    )
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--max-steps-per-episode", type=int, default=300)
    parser.add_argument("--max-seconds-per-episode", type=float, default=60.0)
    parser.add_argument("--max-total-steps", type=int, default=900)
    parser.add_argument("--max-total-seconds", type=float, default=180.0)
    parser.add_argument(
        "--dry-run-output",
        type=Path,
        default=(
            PROJECT_ROOT
            / "artifacts"
            / "teacher_real_alignment_packet_dry_run.json"
        ),
    )
    return parser.parse_args()


def _write_new_json(
    path: Path,
    payload: dict[str, Any],
    *,
    allow_identical: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if allow_identical:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == payload:
                return
        raise RuntimeError(f"拒絕覆寫既有 Gate artifact：{path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _video_writer(path: Path, frame: Any, fps: float) -> cv2.VideoWriter:
    height, width = frame.shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        writer.release()
        raise RuntimeError(f"無法建立 Gate MP4：{path}")
    return writer


def _run_episode(
    *,
    env: Any,
    adapter: LiveGameAdapter,
    policy: SafePlatformPolicy,
    episode_index: int,
    run_dir: Path,
    limits: RealGameMicroLimits,
    remaining_steps: int,
    total_deadline: float,
    reference_height: float,
    diagnose_player: Any,
    hud_config: Any,
) -> dict[str, Any]:
    features, info = env.reset()
    policy.reset()
    decision_observation = env.last_observation
    if decision_observation is None:
        raise RuntimeError("reset 後缺少真實觀測。")
    prefix = run_dir / f"episode_{episode_index:02d}"
    transition_path = prefix.with_suffix(".transitions.jsonl")
    controller_path = prefix.with_suffix(".controller.jsonl")
    alignment_path = prefix.with_suffix(".alignment.jsonl")
    video_path = prefix.with_suffix(".mp4")
    dropout_dir = run_dir / f"episode_{episode_index:02d}.dropout"
    dropout_forensics = DropoutForensicRecorder(
        dropout_dir,
        diagnose_player=diagnose_player,
    )
    episode_id = f"teacher-real-{run_dir.name}-{episode_index:02d}"
    transition_writer = TransitionJsonlWriter(
        transition_path,
        policy_source=PolicySource.BASELINE,
        episode_id=episode_id,
    )
    transition_writer.begin(
        features,
        observation_timestamp=float(decision_observation.timestamp),
    )
    controller_file = controller_path.open("x", encoding="utf-8")
    alignment_writer = RealAlignmentPacketWriter(
        alignment_path,
        episode_id=episode_id,
        landing_margin_pixels=policy.config.landing_margin_pixels,
    )
    frame = adapter.latest_frame()
    if frame is None:
        alignment_writer.close()
        controller_file.close()
        transition_writer.close()
        raise RuntimeError("reset 後缺少錄影 frame。")
    video = _video_writer(video_path, frame, fps=8.0)
    video_floor_tracker = FloorCounterTracker(hud_config)
    video_max_floor: int | None = None

    def write_video_frame(video_frame: Any) -> None:
        nonlocal video_max_floor
        video.write(video_frame)
        floor_update = video_floor_tracker.update(video_frame)
        if floor_update.value is not None:
            value = int(floor_update.value)
            video_max_floor = (
                value
                if video_max_floor is None
                else max(video_max_floor, value)
            )

    write_video_frame(frame)
    actions: Counter[str] = Counter()
    initial_floor = (
        None
        if decision_observation.floor is None
        else decision_observation.floor.get("value")
    )
    max_floor = None if initial_floor is None else int(initial_floor)
    floor_counter_available = initial_floor is not None
    floor_counter_unstable_steps = 0
    physical_tracker = PhysicalResponseLatencyTracker()
    physical_response_samples: list[dict[str, Any]] = []
    physical_response_timeouts = 0
    outward_wall_push_count = 0
    outward_wall_push_streak = 0
    max_outward_wall_push_streak = 0
    player_missing_step_count = 0
    current_player_missing_streak = 0
    max_player_missing_streak = 0
    oscillation_tracker = DirectionOscillationTracker(max_step_gap=3)
    wall_oscillation_tracker = DirectionOscillationTracker(max_step_gap=3)
    departure_tracker = SupportDepartureTracker(edge_threshold_pixels=20.0)
    wall_reentry_cycle_count = 0
    wall_was_active = False
    last_wall_side: str | None = None
    last_wall_end_step: int | None = None
    aligned_release_streak = 0
    max_aligned_release_streak = 0
    support_aligned_release_streak = 0
    max_support_aligned_release_streak = 0
    steps = 0
    target_lock_seen = False
    observation_valid = True
    controller_records_buffer: list[dict[str, Any]] = []
    forced_reason: str | None = None
    name_entry_dialog: dict[str, Any] | None = None
    last_playing_observation = decision_observation
    episode_deadline = min(
        total_deadline,
        time.monotonic() + limits.max_seconds_per_episode,
    )
    try:
        step_cap = min(limits.max_steps_per_episode, remaining_steps)
        for step in range(step_cap):
            if adapter.emergency_stopped:
                forced_reason = "emergency_stop"
                break
            if not adapter.is_foreground():
                try:
                    verified_dialog = adapter.verified_name_entry_dialog()
                except Exception:
                    verified_dialog = None
                if verified_dialog is None:
                    forced_reason = "focus_lost_or_related_window"
                else:
                    forced_reason = "verified_name_entry_dialog"
                    name_entry_dialog = {
                        "hwnd": int(verified_dialog.hwnd),
                        "title": str(verified_dialog.title),
                        "class_name": str(verified_dialog.class_name),
                        "owner_hwnd": int(verified_dialog.owner_hwnd),
                        "process_id": int(verified_dialog.process_id),
                    }
                break
            if time.monotonic() >= episode_deadline:
                forced_reason = "time_limit"
                break
            loop_start = time.monotonic()
            pre_decision_memory = policy.memory_snapshot()
            decision = policy.choose(decision_observation)
            memory = policy.memory_snapshot()
            confidence = observation_confidence(decision_observation)
            player_payload = decision_observation.player or {}
            player_source = str(
                player_payload.get("detection_source", "missing")
            )
            if player_source != "raw":
                player_missing_step_count += 1
                reported_streak = int(
                    player_payload.get("missing_streak", 0) or 0
                )
                current_player_missing_streak = max(
                    current_player_missing_streak + 1,
                    reported_streak,
                )
            else:
                current_player_missing_streak = 0
            max_player_missing_streak = max(
                max_player_missing_streak,
                current_player_missing_streak,
            )
            diagnostic_frame = adapter.latest_frame()
            if diagnostic_frame is not None:
                dropout_forensics.observe(
                    step=step,
                    detection_source=player_source,
                    missing_streak=current_player_missing_streak,
                    frame=diagnostic_frame,
                    metadata={
                        "teacher_reason": decision.reason,
                        "action": decision.action.name,
                        "controller_phase": memory["controller_phase"],
                        "observation_confidence": confidence,
                        "floor": decision_observation.floor,
                    },
                )

            wall_active = bool(memory["wall_evacuation_active"])
            wall_side = memory["wall_guard_side"]
            if wall_active and not wall_was_active:
                if (
                    last_wall_end_step is not None
                    and wall_side == last_wall_side
                    and step - last_wall_end_step <= 8
                ):
                    wall_reentry_cycle_count += 1
                last_wall_side = None if wall_side is None else str(wall_side)
            elif not wall_active and wall_was_active:
                last_wall_end_step = step - 1
            wall_was_active = wall_active

            if (
                decision.action is Action.RELEASE_ALL
                and decision.reason.startswith("aligned")
            ):
                aligned_release_streak += 1
            else:
                aligned_release_streak = 0
            max_aligned_release_streak = max(
                max_aligned_release_streak,
                aligned_release_streak,
            )
            if (
                decision.action is Action.RELEASE_ALL
                and decision.reason.startswith("aligned")
                and bool(memory["support_contact_active"])
            ):
                support_aligned_release_streak += 1
            else:
                support_aligned_release_streak = 0
            max_support_aligned_release_streak = max(
                max_support_aligned_release_streak,
                support_aligned_release_streak,
            )
            target_lock_seen = target_lock_seen or memory["target_platform_id"] is not None
            observation_valid = observation_valid and confidence > 0.0
            try:
                next_features, reward, terminated, truncated, info = env.step(
                    int(decision.action)
                )
            except InputError:
                try:
                    verified_dialog = adapter.verified_name_entry_dialog()
                except Exception:
                    verified_dialog = None
                if verified_dialog is None:
                    raise
                forced_reason = "verified_name_entry_dialog"
                name_entry_dialog = {
                    "hwnd": int(verified_dialog.hwnd),
                    "title": str(verified_dialog.title),
                    "class_name": str(verified_dialog.class_name),
                    "owner_hwnd": int(verified_dialog.owner_hwnd),
                    "process_id": int(verified_dialog.process_id),
                }
                break
            next_observation = env.last_observation
            timing = adapter.last_action_timing
            if next_observation is None or timing is None:
                raise RuntimeError("step 後缺少 observation 或 action timing。")
            if not timing.action_applied:
                if not safe_unapplied_terminal(
                    next_observation,
                    action_applied=timing.action_applied,
                    terminated=terminated,
                    truncated=truncated,
                ):
                    raise RuntimeError(
                        "遊戲仍在 PLAYING，但本控制步驟未實際套用 action。"
                    )
                # The phase probe intentionally suppressed input after a
                # terminal/dialog transition.  Preserve the terminal frame,
                # but do not fabricate a transition for an unsent action.
                frame = adapter.latest_frame()
                if frame is not None:
                    write_video_frame(frame)
                forced_reason = "terminal_phase_before_action"
                break
            actions[decision.action.name] += 1
            departure_tracker.update(
                memory,
                action=decision.action,
                reason=decision.reason,
            )
            oscillation_tracker.update(decision.action, step=step)
            decision_player = decision_observation.player or {}
            player_x_raw = decision_player.get("center_x")
            player_x = (
                None if player_x_raw is None else float(player_x_raw)
            )
            in_wall_corridor = (
                player_x is not None
                and (
                    player_x
                    <= policy.config.playfield_left_pixels
                    + policy.config.wall_evacuation_exit_margin_pixels
                    or player_x
                    >= policy.config.playfield_right_pixels
                    - policy.config.wall_evacuation_exit_margin_pixels
                )
            )
            if in_wall_corridor:
                wall_oscillation_tracker.update(decision.action, step=step)
            else:
                wall_oscillation_tracker.reset_burst()
            outward_side = outward_wall_push_side(
                decision.action,
                player_x=player_x,
                playfield_left=policy.config.playfield_left_pixels,
                playfield_right=policy.config.playfield_right_pixels,
                margin=policy.config.wall_guard_margin_pixels,
            )
            if outward_side is None:
                outward_wall_push_streak = 0
            else:
                outward_wall_push_count += 1
                outward_wall_push_streak += 1
                max_outward_wall_push_streak = max(
                    max_outward_wall_push_streak,
                    outward_wall_push_streak,
                )
            physical_response = physical_tracker.update(
                decision.action,
                command_timestamp=timing.action_command_timestamp,
                observation=next_observation,
                prior_observation=decision_observation,
            )
            if physical_response.latency_ms is not None:
                physical_response_samples.append(
                    {
                        "direction": physical_response.direction,
                        "latency_ms": physical_response.latency_ms,
                        "step": step,
                    }
                )
            physical_response_timeouts += int(physical_response.timed_out)
            reward_terms = extract_reward_terms(info.get("reward_components", {}))
            transition_writer.write_step(
                action=int(decision.action),
                reward=reward,
                reward_components=reward_terms,
                next_observation=next_features,
                terminated=terminated,
                truncated=truncated,
                events=next_observation.events,
                timing=timing,
                target_platform_id=decision.target_platform_id,
                target_platform_kind=decision.target_platform_kind,
                target_signed_offset=decision.horizontal_delta,
            )
            alignment_writer.write_step(
                observation=decision_observation,
                next_observation=next_observation,
                pre_decision_memory=pre_decision_memory,
                post_decision_memory=memory,
                decision=decision,
                timing=timing,
                terminated=terminated,
                truncated=truncated,
                events=next_observation.events,
            )
            loop_seconds = max(1e-9, time.monotonic() - loop_start)
            controller_record = {
                        "step": step,
                        "teacher_reason": decision.reason,
                        "action": decision.action.name,
                        "observation_confidence": confidence,
                        "floor": next_observation.floor,
                        "controller_memory": memory,
                        "wall_guard_active": memory["wall_guard_active"],
                        "wall_guard_side": memory["wall_guard_side"],
                        "wall_guard_original_action": memory[
                            "wall_guard_original_action"
                        ],
                        "wall_evacuation_active": memory[
                            "wall_evacuation_active"
                        ],
                        "wall_evacuation_cooldown_steps": memory[
                            "wall_evacuation_cooldown_steps"
                        ],
                        "player_detection_source": player_source,
                        "player_missing_streak": (
                            current_player_missing_streak
                        ),
                        "rapid_direction_reversal_count": (
                            oscillation_tracker.reversal_count
                        ),
                        "rapid_direction_reversal_burst": (
                            oscillation_tracker.max_burst
                        ),
                        "wall_direction_reversal_burst": (
                            wall_oscillation_tracker.max_burst
                        ),
                        "wall_reentry_cycle_count": wall_reentry_cycle_count,
                        "aligned_release_streak": aligned_release_streak,
                        "support_aligned_release_streak": (
                            support_aligned_release_streak
                        ),
                        "support_contact_active": memory[
                            "support_contact_active"
                        ],
                        "support_platform_id": memory[
                            "support_platform_id"
                        ],
                        "support_edge_distance": memory[
                            "support_edge_distance"
                        ],
                        "support_departure_active": memory[
                            "support_departure_active"
                        ],
                        "support_departure_source_id": memory[
                            "support_departure_source_id"
                        ],
                        "support_departure_destination_id": memory[
                            "support_departure_destination_id"
                        ],
                        "support_departure_direction": memory[
                            "support_departure_direction"
                        ],
                        "support_departure_steps": memory[
                            "support_departure_steps"
                        ],
                        "same_support_departure_cycle_count": (
                            departure_tracker.same_support_departure_cycle_count
                        ),
                        "support_departure_target_switch_count": (
                            departure_tracker.support_departure_target_switch_count
                        ),
                        "support_edge_release_count": (
                            departure_tracker.support_edge_release_count
                        ),
                        "support_edge_opportunity_count": (
                            departure_tracker.support_edge_opportunity_count
                        ),
                        "generic_support_edge_release_count": (
                            departure_tracker.generic_support_edge_release_count
                        ),
                        "generic_support_edge_opportunity_count": (
                            departure_tracker.generic_support_edge_opportunity_count
                        ),
                        "outward_wall_push": outward_side is not None,
                        "outward_wall_push_side": outward_side,
                        "outward_wall_push_streak": outward_wall_push_streak,
                        "action_command_timestamp": timing.action_command_timestamp,
                        "action_effective_timestamp": timing.action_effective_timestamp,
                        "next_observation_timestamp": timing.next_observation_timestamp,
                        "action_latency_ms": 1000.0 * (
                            timing.action_effective_timestamp - timing.action_command_timestamp
                        ),
                        "command_dispatch_latency_ms": 1000.0 * (
                            timing.action_effective_timestamp
                            - timing.action_command_timestamp
                        ),
                        "physical_response_latency_ms": (
                            physical_response.latency_ms
                        ),
                        "physical_response_direction": (
                            physical_response.direction
                        ),
                        "physical_response_pending": physical_response.pending,
                        "physical_response_timed_out": physical_response.timed_out,
                        "physical_response_preexisting_motion": (
                            physical_response.preexisting_motion
                        ),
                        "control_loop_hz": 1.0 / loop_seconds,
                        "events": next_observation.events,
                    }
            controller_records_buffer.append(controller_record)
            controller_file.write(
                json.dumps(
                    controller_record,
                    ensure_ascii=False,
                )
                + "\n"
            )
            controller_file.flush()
            frame = adapter.latest_frame()
            if frame is None:
                raise RuntimeError("step 後缺少錄影 frame。")
            write_video_frame(frame)
            steps += 1
            if playing_telemetry_required(
                next_observation,
                terminated=terminated,
                truncated=truncated,
            ):
                floor_payload = next_observation.floor or {}
                floor_value = floor_payload.get("value")
                floor_counter_available = (
                    floor_counter_available and floor_value is not None
                )
                if floor_value is not None:
                    normalized_floor = int(floor_value)
                    max_floor = (
                        normalized_floor
                        if max_floor is None
                        else max(max_floor, normalized_floor)
                    )
                if not bool(floor_payload.get("stable", False)):
                    floor_counter_unstable_steps += 1
            if next_observation.player is not None:
                last_playing_observation = next_observation
            features = next_features
            decision_observation = next_observation
            if terminated or truncated:
                break
        else:
            forced_reason = "step_limit"
    finally:
        transition_writer.close()
        controller_file.close()
        alignment_writer.close()
        video.release()
        adapter.release_all()
        dropout_forensic_manifest = dropout_forensics.finalize()
    terminal_reason = classify_terminal_reason(
        last_playing_observation,
        forced_reason=forced_reason,
        reference_height=reference_height,
    )
    sidecar_max_floor = max_floor
    if video_max_floor is not None:
        max_floor = (
            video_max_floor
            if max_floor is None
            else max(max_floor, video_max_floor)
        )
    episode_result = {
        "episode": episode_index,
        "steps": steps,
        "floors": 0 if max_floor is None else max_floor,
        "floor_start": initial_floor,
        "floor_max": max_floor,
        "floor_max_sidecar": sidecar_max_floor,
        "floor_max_video": video_max_floor,
        "floor_video_corrected": (
            video_max_floor is not None
            and (
                sidecar_max_floor is None
                or video_max_floor > sidecar_max_floor
            )
        ),
        "floor_counter_available": floor_counter_available,
        "floor_counter_unstable_steps": floor_counter_unstable_steps,
        "physical_response_samples": physical_response_samples,
        "physical_response_timeouts": physical_response_timeouts,
        "wall_telemetry_available": True,
        "outward_wall_push_count": outward_wall_push_count,
        "max_outward_wall_push_streak": max_outward_wall_push_streak,
        "player_telemetry_available": True,
        "player_missing_step_count": player_missing_step_count,
        "max_player_missing_streak": max_player_missing_streak,
        "wall_reentry_cycle_count": wall_reentry_cycle_count,
        "rapid_direction_reversal_count": (
            oscillation_tracker.reversal_count
        ),
        "max_rapid_direction_reversal_burst": oscillation_tracker.max_burst,
        "max_wall_direction_reversal_burst": (
            wall_oscillation_tracker.max_burst
        ),
        "max_aligned_release_streak": max_aligned_release_streak,
        "max_support_aligned_release_streak": (
            max_support_aligned_release_streak
        ),
        "support_departure_telemetry_available": True,
        "support_edge_actionable_telemetry_available": True,
        "same_support_departure_cycle_count": (
            departure_tracker.same_support_departure_cycle_count
        ),
        "support_departure_target_switch_count": (
            departure_tracker.support_departure_target_switch_count
        ),
        "support_departure_timeout_count": (
            departure_tracker.support_departure_timeout_count
        ),
        "support_edge_release_count": (
            departure_tracker.support_edge_release_count
        ),
        "support_edge_opportunity_count": (
            departure_tracker.support_edge_opportunity_count
        ),
        "generic_support_edge_release_count": (
            departure_tracker.generic_support_edge_release_count
        ),
        "generic_support_edge_opportunity_count": (
            departure_tracker.generic_support_edge_opportunity_count
        ),
        "support_departure_exit_samples": (
            departure_tracker.support_departure_exit_samples
        ),
        "max_support_departure_steps": (
            departure_tracker.max_support_departure_steps
        ),
        "action_counts": dict(sorted(actions.items())),
        "terminal_reason": terminal_reason,
        "forced_reason": forced_reason,
        "name_entry_dialog_detected": name_entry_dialog is not None,
        "name_entry_dialog_dismissed": False,
        "name_entry_dialog": name_entry_dialog,
        "observation_valid": observation_valid,
        "target_lock_seen": target_lock_seen,
        "transition_records": steps,
        "controller_records": steps,
        "alignment_records": alignment_writer.records,
        "alignment_schema_version": REAL_ALIGNMENT_SCHEMA_VERSION,
        "alignment_episode_id": episode_id,
        "video_complete": video_path.exists() and video_path.stat().st_size > 0,
        "transition_path": str(transition_path),
        "controller_path": str(controller_path),
        "alignment_path": str(alignment_path),
        "video_path": str(video_path),
        "dropout_forensic_manifest_path": str(
            dropout_dir / "manifest.json"
        ),
        "dropout_forensic_snapshot_count": (
            dropout_forensic_manifest["snapshot_count"]
        ),
        "dropout_forensic_dropped_snapshot_count": (
            dropout_forensic_manifest["dropped_snapshot_count"]
        ),
        "dropout_forensic_telemetry_available": (
            (dropout_dir / "manifest.json").is_file()
        ),
    }
    return reclassify_real_micro_episode(
        episode_result,
        controller_records_buffer,
    )


def main() -> None:
    args = parse_args()
    limits = RealGameMicroLimits(
        episodes=args.episodes,
        max_steps_per_episode=args.max_steps_per_episode,
        max_seconds_per_episode=args.max_seconds_per_episode,
        max_total_steps=args.max_total_steps,
        max_total_seconds=args.max_total_seconds,
    )
    try:
        limits.validate()
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    if not args.execute:
        payload = dry_run_manifest(
            limits,
            dismiss_name_entry=args.dismiss_name_entry,
        )
        payload["alignment_packet"] = {
            "schema_version": REAL_ALIGNMENT_SCHEMA_VERSION,
            "status": "PENDING",
            "diagnostic_only": True,
            "training_eligible": False,
            "records_structured_observation": True,
            "records_pre_and_post_decision_memory": True,
            "records_video_frame_indices": True,
        }
        payload["actual_artifacts"].insert(
            2,
            "episode_XX.alignment.jsonl",
        )
        _write_new_json(
            args.dry_run_output,
            payload,
            allow_identical=True,
        )
        print(f"Dry-run PASS：{args.dry_run_output}")
        print("沒有尋找遊戲、沒有載入輸入 backend、沒有送出任何按鍵。")
        print("Teacher Real Gate 仍為 PENDING；dry-run 不算真機通過。")
        return

    config = load_config()
    if config.game.auto_launch:
        raise RuntimeError("Teacher Real Gate 要求 game.auto_launch=false。")
    env, target = create_live_environment(
        config,
        PROJECT_ROOT,
        allow_single_enter_reset=True,
    )
    adapter = env.adapter
    if not isinstance(adapter, LiveGameAdapter):
        env.close()
        raise RuntimeError("實機 adapter 類型不符。")
    print(f"唯一目標：{target.title!r}，client={target.client_rect.width}x{target.client_rect.height}")
    print(f"將執行 {limits.episodes} 回合；限制：{limits.to_dict()}")
    print(
        "每回合保存 transition、controller sidecar、alignment packet、MP4 "
        "與 bounded raw-dropout forensics。"
    )
    if input("輸入大寫 TEACHER REAL MICRO 才執行：").strip() != "TEACHER REAL MICRO":
        env.close()
        print("未確認，已安全取消。")
        return
    print("看到 3... 後立即點選遊戲並保持前景；F8 可隨時停止。")
    for value in (3, 2, 1):
        print(f"{value}...")
        time.sleep(1)
    if args.focus_target:
        adapter.controller.window_manager.focus(target.hwnd)
        time.sleep(0.2)
        if not adapter.is_foreground():
            env.close()
            raise RuntimeError("嘗試切換後遊戲仍不是前景視窗；已停止。")
        print("遊戲前景切換與驗證通過。")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = PROJECT_ROOT / "logs" / f"teacher_real_micro_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    episodes: list[dict[str, Any]] = []
    safety_events: list[dict[str, Any]] = []
    total_deadline = time.monotonic() + limits.max_total_seconds
    total_steps = 0
    policy = SafePlatformPolicy(config.baseline)

    def dismiss_name_entry_for_episode(
        episode: dict[str, Any],
    ) -> bool:
        if not args.dismiss_name_entry:
            return False
        try:
            dialog = adapter.dismiss_verified_name_entry_dialog(
                focus_target=args.focus_target,
            )
        except Exception:
            return False
        if dialog is None:
            return False
        episode["name_entry_dialog_detected"] = True
        episode["name_entry_dialog_dismissed"] = True
        episode["name_entry_dialog"] = {
            "hwnd": int(dialog.hwnd),
            "title": str(dialog.title),
            "class_name": str(dialog.class_name),
            "owner_hwnd": int(dialog.owner_hwnd),
            "process_id": int(dialog.process_id),
        }
        print("已驗證姓名輸入 modal；只送一次 Enter 跳過，未輸入文字。")
        return True

    try:
        for episode_index in range(1, limits.episodes + 1):
            if time.monotonic() >= total_deadline or total_steps >= limits.max_total_steps:
                break
            for reset_attempt in range(2):
                try:
                    result = _run_episode(
                        env=env,
                        adapter=adapter,
                        policy=policy,
                        episode_index=episode_index,
                        run_dir=run_dir,
                        limits=limits,
                        remaining_steps=limits.max_total_steps - total_steps,
                        total_deadline=total_deadline,
                        reference_height=float(target.client_rect.height),
                        hud_config=config.hud,
                        diagnose_player=lambda frame: player_color_diagnostics(
                            frame,
                            config.vision,
                        ),
                    )
                    break
                except InputError:
                    episode_files_started = any(
                        (run_dir / f"episode_{episode_index:02d}{suffix}").exists()
                        for suffix in (
                            ".transitions.jsonl",
                            ".controller.jsonl",
                            ".alignment.jsonl",
                            ".mp4",
                        )
                    )
                    if (
                        reset_attempt > 0
                        or episode_files_started
                        or not episodes
                        or not dismiss_name_entry_for_episode(episodes[-1])
                    ):
                        raise
            else:  # pragma: no cover - loop always breaks or raises
                raise RuntimeError("姓名視窗 reset retry 未完成。")
            episodes.append(result)
            total_steps += int(result["steps"])
            if result.get("forced_reason") == "verified_name_entry_dialog":
                if not dismiss_name_entry_for_episode(result):
                    safety_events.append(
                        {
                            "episode": episode_index,
                            "reason": "verified_name_entry_dialog_not_dismissed",
                        }
                    )
                    break
                continue
            if result.get("forced_reason") in {
                "emergency_stop",
                "focus_lost_or_related_window",
            }:
                safety_events.append(
                    {"episode": episode_index, "reason": result["forced_reason"]}
                )
                break
    except Exception as exc:
        safety_events.append({"episode": len(episodes) + 1, "reason": "exception", "detail": str(exc)})
        raise
    finally:
        env.close()
        summary = summarize_real_micro_gate(
            episodes,
            safety_events=safety_events,
            dry_run=False,
            expected_episodes=limits.episodes,
        )
        summary["limits"] = limits.to_dict()
        alignment_records: list[dict[str, Any]] = []
        expected_alignment_counts: dict[str, int] = {}
        for episode in episodes:
            alignment_path = Path(str(episode["alignment_path"]))
            with alignment_path.open("r", encoding="utf-8") as stream:
                alignment_records.extend(
                    json.loads(line) for line in stream if line.strip()
                )
            expected_alignment_counts[str(episode["alignment_episode_id"])] = int(
                episode["transition_records"]
            )
        summary["alignment_packet"] = audit_real_alignment_records(
            alignment_records,
            expected_episodes=limits.episodes,
            safety_events=safety_events,
            expected_record_counts=expected_alignment_counts,
        )
        _write_new_json(run_dir / "teacher_real_game_micro_gate.json", summary)
        print(f"Gate artifact：{run_dir / 'teacher_real_game_micro_gate.json'}")


if __name__ == "__main__":
    run_main(main)
