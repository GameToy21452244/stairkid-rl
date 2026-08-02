from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.game_events import GameplayEventDetector
from stair_agent.game_state import GamePhase, GameStateDetector
from stair_agent.hud_detection import FloorCounterTracker, HealthTracker, HudDetector
from stair_agent.input_controller import Action
from stair_agent.object_detection import ObjectDetector, PlatformKind
from stair_agent.object_tracking import (
    PlatformStabilizer,
    PlatformTracker,
    PlatformTrackingState,
    PlayerTracker,
)
from stair_agent.observation import ObservationBuilder
from stair_agent.real_game_gate import (
    DirectionOscillationTracker,
    SupportDepartureTracker,
    outward_wall_push_side,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "離線重播 Teacher 真機 MP4，稽核 vision、wall、phase-aware aligned "
            "release 與 support-departure latch；不載入輸入 backend。"
        )
    )
    parser.add_argument(
        "--logs-glob",
        default="logs/teacher_real_micro_20260801_04*/episode_*.mp4",
    )
    parser.add_argument(
        "--output",
        default="artifacts/p36_repair_v5_offline_replay.json",
    )
    parser.add_argument("--expected-videos", type=int, default=18)
    return parser.parse_args()


def _replay_video(path: Path) -> dict[str, object]:
    config = load_config()
    detector = ObjectDetector.from_config(config.vision, PROJECT_ROOT)
    state_detector = GameStateDetector.from_config(
        config.detection,
        PROJECT_ROOT,
    )
    hud = HudDetector(config.hud)
    health_tracker = HealthTracker()
    floor_tracker = FloorCounterTracker(config.hud)
    player_tracker = PlayerTracker(max_missing_frames=2)
    platform_tracker = PlatformTracker()
    platform_stabilizer = PlatformStabilizer(
        persistent_kinds={
            PlatformKind.CONVEYOR,
            PlatformKind.FLIPPING,
            PlatformKind.SPRING,
        },
        persistence_frames=2,
    )
    event_detector = GameplayEventDetector(
        landing_contact_gap=config.events.landing_contact_gap,
        spring_contact_gap=config.events.spring_contact_gap,
        correlation_frames=config.events.correlation_frames,
    )
    builder = ObservationBuilder()
    policy = SafePlatformPolicy(config.baseline)
    oscillation = DirectionOscillationTracker(max_step_gap=3)
    wall_oscillation = DirectionOscillationTracker(max_step_gap=3)
    departure_tracker = SupportDepartureTracker(edge_threshold_pixels=20.0)

    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 8.0)
    raw_detected = 0
    tracked_steps = 0
    effective_missing_steps = 0
    max_missing_streak = 0
    outward_count = 0
    wall_reentry_cycles = 0
    wall_was_active = False
    last_wall_side: str | None = None
    last_wall_end_step: int | None = None
    max_aligned_release_streak = 0
    support_aligned_release_streak = 0
    max_support_aligned_release_streak = 0
    action_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    playing_frames = 0
    total_frames = 0
    wall_trace: list[dict[str, object]] = []
    departure_trace: list[dict[str, object]] = []
    aligned_trace: list[dict[str, object]] = []
    special_trace: list[dict[str, object]] = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index = total_frames
            total_frames += 1
            phase = state_detector.detect(frame)
            if phase is not GamePhase.PLAYING:
                continue
            timestamp = frame_index / max(fps, 1.0)
            raw_objects = detector.detect(frame)
            raw_detected += raw_objects.player is not None
            platform_state = platform_tracker.update(raw_objects, timestamp)
            stable_objects = platform_stabilizer.update(platform_state.objects)
            platform_state = PlatformTrackingState(
                stable_objects,
                platform_state.scroll_velocity_y,
                platform_state.matched_platforms,
            )
            player_state = player_tracker.update(stable_objects, timestamp)
            health = health_tracker.update(hud.detect_health(frame).segments)
            floor = floor_tracker.update(frame)
            events = event_detector.update(
                player_state,
                health,
                floor=floor,
            )
            observation = builder.build(
                timestamp=timestamp,
                phase=phase,
                player_state=player_state,
                platform_state=platform_state,
                health=health,
                events=events,
                floor=floor,
            )
            playing_frames += 1
            if player_state.detection_source == "tracked":
                tracked_steps += 1
            if player_state.player is None:
                effective_missing_steps += 1
            max_missing_streak = max(
                max_missing_streak,
                player_state.missing_streak,
            )

            decision = policy.choose(observation)
            memory = policy.memory_snapshot()
            action_counts[decision.action.name] += 1
            reason_counts[decision.reason] += 1
            if memory.get("special_contact_episode_id") is not None:
                special_trace.append(
                    {
                        "step": playing_frames - 1,
                        "player": observation.player,
                        "action": decision.action.name,
                        "reason": decision.reason,
                        "contact_id": memory[
                            "special_contact_episode_id"
                        ],
                        "source_id": memory[
                            "special_source_platform_id"
                        ],
                        "source_kind": memory[
                            "special_source_platform_kind"
                        ],
                        "direction": memory[
                            "special_escape_direction"
                        ],
                        "direction_source": memory[
                            "special_escape_direction_source"
                        ],
                        "destination_id": memory[
                            "special_escape_destination_platform_id"
                        ],
                        "escape_steps": memory[
                            "special_escape_steps"
                        ],
                        "candidate_stability_steps": memory[
                            "special_escape_candidate_stability_steps"
                        ],
                        "replan_count": memory[
                            "special_escape_replan_count"
                        ],
                        "forced_exit": memory[
                            "special_escape_forced_exit_active"
                        ],
                        "platforms": observation.platforms,
                    }
                )
            departure_tracker.update(
                memory,
                action=decision.action,
                reason=decision.reason,
            )
            oscillation.update(decision.action, step=playing_frames - 1)
            max_aligned_release_streak = max(
                max_aligned_release_streak,
                int(memory["aligned_release_streak"]),
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
            if decision.reason.startswith("aligned"):
                aligned_trace.append(
                    {
                        "step": playing_frames - 1,
                        "reason": decision.reason,
                        "target_id": decision.target_platform_id,
                        "support_contact_active": memory[
                            "support_contact_active"
                        ],
                        "support_platform_id": memory[
                            "support_platform_id"
                        ],
                        "support_edge_distance": memory[
                            "support_edge_distance"
                        ],
                        "departure_active": memory[
                            "support_departure_active"
                        ],
                    }
                )
            player_x = (
                None
                if observation.player is None
                else float(observation.player["center_x"])
            )
            outward_count += outward_wall_push_side(
                decision.action,
                player_x=player_x,
                playfield_left=config.baseline.playfield_left_pixels,
                playfield_right=config.baseline.playfield_right_pixels,
                margin=config.baseline.wall_guard_margin_pixels,
            ) is not None
            in_wall_corridor = (
                player_x is not None
                and (
                    player_x
                    <= config.baseline.playfield_left_pixels
                    + config.baseline.wall_evacuation_exit_margin_pixels
                    or player_x
                    >= config.baseline.playfield_right_pixels
                    - config.baseline.wall_evacuation_exit_margin_pixels
                )
            )
            if in_wall_corridor:
                wall_oscillation.update(
                    decision.action,
                    step=playing_frames - 1,
                )
                wall_trace.append(
                    {
                        "step": playing_frames - 1,
                        "player_x": player_x,
                        "velocity_x": (
                            None
                            if observation.player is None
                            else float(observation.player["velocity_x"])
                        ),
                        "action": decision.action.name,
                        "reason": decision.reason,
                        "wall_side": memory["wall_guard_side"],
                        "wall_evacuation_active": memory[
                            "wall_evacuation_active"
                        ],
                        "wall_evacuation_cooldown_steps": memory[
                            "wall_evacuation_cooldown_steps"
                        ],
                    }
                )
            else:
                wall_oscillation.reset_burst()

            if bool(memory["support_contact_active"]) or bool(
                memory["support_departure_active"]
            ):
                departure_trace.append(
                    {
                        "step": playing_frames - 1,
                        "support_platform_id": memory[
                            "support_platform_id"
                        ],
                        "support_edge_distance": memory[
                            "support_edge_distance"
                        ],
                        "departure_active": memory[
                            "support_departure_active"
                        ],
                        "source_id": memory[
                            "support_departure_source_id"
                        ],
                        "destination_id": memory[
                            "support_departure_destination_id"
                        ],
                        "direction": memory[
                            "support_departure_direction"
                        ],
                        "departure_steps": memory[
                            "support_departure_steps"
                        ],
                        "action": decision.action.name,
                        "reason": decision.reason,
                    }
                )

            wall_active = bool(memory["wall_evacuation_active"])
            wall_side = memory["wall_guard_side"]
            if wall_active and not wall_was_active:
                if (
                    last_wall_end_step is not None
                    and wall_side == last_wall_side
                    and playing_frames - 1 - last_wall_end_step <= 8
                ):
                    wall_reentry_cycles += 1
                last_wall_side = None if wall_side is None else str(wall_side)
            elif not wall_active and wall_was_active:
                last_wall_end_step = playing_frames - 2
            wall_was_active = wall_active
    finally:
        cap.release()

    raw_missing = max(0, playing_frames - raw_detected)
    return {
        "video": str(path),
        "total_frames": total_frames,
        "playing_frames": playing_frames,
        "raw_player_detected_steps": raw_detected,
        "raw_player_missing_steps": raw_missing,
        "tracked_bridge_steps": tracked_steps,
        "effective_player_missing_steps": effective_missing_steps,
        "max_player_missing_streak": max_missing_streak,
        "outward_wall_push_count": outward_count,
        "wall_reentry_cycle_count": wall_reentry_cycles,
        "rapid_direction_reversal_count": oscillation.reversal_count,
        "max_rapid_direction_reversal_burst": oscillation.max_burst,
        "max_wall_direction_reversal_burst": wall_oscillation.max_burst,
        "max_aligned_release_streak": max_aligned_release_streak,
        "max_support_aligned_release_streak": (
            max_support_aligned_release_streak
        ),
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
        "support_departure_exit_samples": (
            departure_tracker.support_departure_exit_samples
        ),
        "max_support_departure_steps": (
            departure_tracker.max_support_departure_steps
        ),
        "support_departure_active_step_count": reason_counts[
            "depart_support_platform"
        ],
        "action_counts": dict(sorted(action_counts.items())),
        "reason_counts": dict(reason_counts.most_common()),
        "wall_trace": wall_trace,
        "departure_trace": departure_trace,
        "aligned_trace": aligned_trace,
        "special_trace": special_trace,
    }


def main() -> None:
    args = parse_args()
    paths = sorted(PROJECT_ROOT.glob(args.logs_glob))
    if not paths:
        raise RuntimeError(f"找不到 replay MP4：{args.logs_glob}")
    rows = [_replay_video(path) for path in paths]
    totals: Counter[str] = Counter()
    maximums: Counter[str] = Counter()
    for row in rows:
        for key in (
            "total_frames",
            "playing_frames",
            "raw_player_detected_steps",
            "raw_player_missing_steps",
            "tracked_bridge_steps",
            "effective_player_missing_steps",
            "outward_wall_push_count",
            "wall_reentry_cycle_count",
            "rapid_direction_reversal_count",
            "same_support_departure_cycle_count",
            "support_departure_target_switch_count",
            "support_departure_timeout_count",
            "support_edge_release_count",
            "support_edge_opportunity_count",
            "support_departure_active_step_count",
        ):
            totals[key] += int(row[key])
        for key in (
            "max_player_missing_streak",
            "max_rapid_direction_reversal_burst",
            "max_wall_direction_reversal_burst",
            "max_aligned_release_streak",
            "max_support_aligned_release_streak",
            "max_support_departure_steps",
        ):
            maximums[key] = max(maximums[key], int(row[key]))

    checks = {
        "all_videos_parsed": len(rows) == args.expected_videos,
        "effective_missing_streak_bounded": (
            maximums["max_player_missing_streak"] <= 2
            and totals["effective_player_missing_steps"] == 0
        ),
        "outward_wall_push_zero": totals["outward_wall_push_count"] == 0,
        "wall_reentry_cycles_zero": totals["wall_reentry_cycle_count"] == 0,
        "wall_direction_oscillation_bounded": (
            maximums["max_wall_direction_reversal_burst"] <= 2
        ),
        "support_aligned_release_bounded": (
            maximums["max_support_aligned_release_streak"] <= 3
        ),
        "departure_latch_activated": (
            totals["support_departure_active_step_count"] > 0
        ),
        "same_support_departure_cycles_zero": (
            totals["same_support_departure_cycle_count"] == 0
        ),
        "support_departure_target_stable": (
            totals["support_departure_target_switch_count"] == 0
        ),
    }
    payload = {
        "experiment": "p36-support-departure-offline-replay-v1",
        "input": {
            "glob": args.logs_glob,
            "video_count": len(rows),
            "evidence_limit": (
                "MP4 是壓縮後 counterfactual replay；可拒絕明顯失敗，"
                "不能驗證新 action 是否真的造成 support-lost，亦不能取代"
                "全新真機 Gate。timeout／edge ratio 只列 telemetry，不作"
                "此離線 Gate 的 blocking check。"
            ),
        },
        "videos": rows,
        "totals": dict(totals),
        "maximums": dict(maximums),
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "real_game_gate": "PENDING_RETEST",
    }
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError(f"拒絕覆寫既有 replay artifact：{output}")
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Support-departure offline replay {payload['status']}：{output}")
    print(json.dumps({"totals": payload["totals"], "maximums": payload["maximums"], "checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_main(main)
