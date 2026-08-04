"""Diagnostic-only Spring curriculum failure tracing."""

from __future__ import annotations

from collections import Counter, deque
from pathlib import Path
import json
from typing import Any, Iterable, Mapping

from ..envs.shaft_env import ShaftEnv
from ..learnability import ACTION_NAMES
from ..policies.simulator_teachers import OracleFull
from ..simulator.state import ShaftEnvConfig


def _has_kind(observation: Mapping[str, Any], kind: str) -> bool:
    nearest = observation.get("nearest_platform") or {}
    if str(nearest.get("kind", "")) == kind:
        return True
    return any(
        str(platform.get("kind", "")) == kind
        for platform in observation.get("platforms", [])
        if isinstance(platform, Mapping)
    )


def analyze_real_spring_evidence(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = list(records)
    visible = 0
    target = 0
    confirmed = 0
    confirmed_velocity_pairs = 0
    for row in rows:
        observation = row.get("observation") or {}
        next_observation = row.get("next_observation") or {}
        if _has_kind(observation, "spring") or _has_kind(
            next_observation, "spring"
        ):
            visible += 1
        teacher = row.get("teacher") or {}
        if str(teacher.get("target_platform_kind", "")) == "spring":
            target += 1
        events = [
            event
            for event in row.get("events", [])
            if isinstance(event, Mapping)
        ]
        spring_events = [
            event
            for event in events
            if "spring" in str(event.get("type", ""))
            or str(event.get("source_platform_kind", "")) == "spring"
        ]
        if spring_events:
            confirmed += 1
            player = observation.get("player") or {}
            next_player = next_observation.get("player") or {}
            if (
                isinstance(player.get("velocity_y"), (int, float))
                and isinstance(next_player.get("velocity_y"), (int, float))
            ):
                confirmed_velocity_pairs += 1
    eligible = confirmed >= 5 and confirmed_velocity_pairs >= 5
    return {
        "records": len(rows),
        "spring_visible_records": visible,
        "spring_target_records": target,
        "confirmed_spring_event_records": confirmed,
        "confirmed_vertical_response_pairs": confirmed_velocity_pairs,
        "minimum_required_confirmed_pairs": 5,
        "physics_calibration_eligible": eligible,
        "status": "PASS" if eligible else "INSUFFICIENT_EVIDENCE",
    }


def load_alignment_records(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}不是JSON object。")
                records.append(value)
    return records


def trace_oracle_spring_failures(
    seeds: Iterable[int],
    *,
    config: ShaftEnvConfig,
    max_episode_steps: int,
    enable_spring_escape: bool = False,
) -> dict[str, Any]:
    frozen_seeds = tuple(int(seed) for seed in seeds)
    if not frozen_seeds or len(set(frozen_seeds)) != len(frozen_seeds):
        raise ValueError("trace seeds不可為空或重複。")
    episodes: list[dict[str, Any]] = []
    for seed in frozen_seeds:
        env = ShaftEnv(config=config)
        oracle = OracleFull(enable_spring_escape=enable_spring_escape)
        observation, _ = env.reset(seed=seed)
        spring_contact_steps: list[int] = []
        spring_contact_snapshots: list[dict[str, Any]] = []
        post_first_actions: Counter[str] = Counter()
        recent_after_contact: deque[dict[str, Any]] = deque(maxlen=16)
        min_top_margin: float | None = None
        terminal_reason: str | None = None
        try:
            for step in range(max_episode_steps):
                simulator = env.simulator
                decision = oracle.choose(simulator)
                action_name = ACTION_NAMES[int(decision.action)]
                if spring_contact_steps:
                    post_first_actions[action_name] += 1
                before = {
                    "step": step,
                    "action": action_name,
                    "target_floor": decision.target_platform_id,
                    "target_kind": decision.target_platform_kind,
                    "target_center_x": decision.target_center_x,
                    "player_x": float(simulator.player.body.position.x),
                    "player_y": float(simulator.player.body.position.y),
                    "player_vx": float(simulator.player.body.velocity.x),
                    "player_vy": float(simulator.player.body.velocity.y),
                    "deepest_floor": int(simulator.deepest_floor),
                }
                observation, _, terminated, truncated, info = env.step(
                    int(decision.action)
                )
                player_bottom = (
                    float(simulator.player.body.position.y)
                    - simulator.player.height / 2
                )
                top_margin = float(config.height - player_bottom)
                min_top_margin = (
                    top_margin
                    if min_top_margin is None
                    else min(min_top_margin, top_margin)
                )
                before["events"] = list(info["events"])
                before["top_margin_after_step"] = top_margin
                before["terminal_reason"] = info["terminal_reason"]
                if spring_contact_steps:
                    recent_after_contact.append(before)
                if "spring_contact" in info["events"]:
                    spring_contact_steps.append(step)
                    spring_contact_snapshots.append(before)
                    if len(spring_contact_steps) == 1:
                        recent_after_contact.append(before)
                if terminated or truncated:
                    terminal_reason = info["terminal_reason"]
                    break
                if simulator.deepest_floor >= 10:
                    terminal_reason = "target_reached"
                    break
            episodes.append(
                {
                    "seed": seed,
                    "steps": step + 1,
                    "deepest_floor": int(env.simulator.deepest_floor),
                    "terminal_reason": terminal_reason,
                    "spring_contact_count": len(spring_contact_steps),
                    "spring_contact_steps": spring_contact_steps,
                    "top_on_first_spring_bounce": (
                        terminal_reason == "top"
                        and len(spring_contact_steps) == 1
                    ),
                    "post_first_contact_action_counts": {
                        name: int(post_first_actions.get(name, 0))
                        for name in ACTION_NAMES.values()
                    },
                    "minimum_top_margin": min_top_margin,
                    "spring_contact_snapshots": spring_contact_snapshots,
                    "terminal_context": list(recent_after_contact),
                }
            )
        finally:
            env.close()

    spring_episodes = [
        episode for episode in episodes if episode["spring_contact_count"] > 0
    ]
    top_spring_episodes = [
        episode
        for episode in spring_episodes
        if episode["terminal_reason"] == "top"
    ]
    no_spring_episodes = [
        episode for episode in episodes if episode["spring_contact_count"] == 0
    ]
    repeated_before_top = bool(top_spring_episodes) and all(
        episode["spring_contact_count"] >= 2
        for episode in top_spring_episodes
    )
    direct_first_bounce_top = any(
        episode["top_on_first_spring_bounce"]
        for episode in top_spring_episodes
    )
    return {
        "seeds": list(frozen_seeds),
        "episodes": episodes,
        "summary": {
            "episode_count": len(episodes),
            "spring_episode_count": len(spring_episodes),
            "spring_target_reached_count": sum(
                episode["deepest_floor"] >= 10
                for episode in spring_episodes
            ),
            "spring_top_death_count": len(top_spring_episodes),
            "no_spring_episode_count": len(no_spring_episodes),
            "no_spring_target_reached_count": sum(
                episode["deepest_floor"] >= 10
                for episode in no_spring_episodes
            ),
        },
        "hypotheses": {
            "single_bounce_direct_top_death": direct_first_bounce_top,
            "repeated_contact_before_top_death": repeated_before_top,
            "oracle_escape_candidate_supported": (
                repeated_before_top and not direct_first_bounce_top
            ),
        },
    }


__all__ = [
    "analyze_real_spring_evidence",
    "load_alignment_records",
    "trace_oracle_spring_failures",
]
