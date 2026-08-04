"""Coverage and provenance audit for the proposed P4.1 Teacher Dataset v2."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np


BRANCH_NAMES = (
    "normal_move",
    "direction_brake",
    "launch_escape",
    "recovery",
    "support_departure",
    "wall_guard",
    "special_escape",
    "no_reachable",
    "spike_target",
    "spike_visible",
    "damage_event",
    "health_recovery_event",
    "bottom_context",
)


def _branches(row: Mapping[str, object], *, bottom_context: bool) -> set[str]:
    reason = str(row.get("teacher_reason") or "")
    events = {str(value) for value in row.get("events", [])}
    visible = {str(value) for value in row.get("visible_platform_kinds", [])}
    result: set[str] = set()
    if "safe_platform" in reason or "deeper_safe_platform" in reason:
        result.add("normal_move")
    if "brake" in reason:
        result.add("direction_brake")
    if "launch" in reason:
        result.add("launch_escape")
    if "recovery" in reason:
        result.add("recovery")
    if "depart_support" in reason:
        result.add("support_departure")
    if "wall_guard" in reason:
        result.add("wall_guard")
    if "special_contact" in reason:
        result.add("special_escape")
    if reason == "no_reachable_landing":
        result.add("no_reachable")
    if str(row.get("target_platform_kind") or "") == "spikes":
        result.add("spike_target")
    if "spikes" in visible:
        result.add("spike_visible")
    if "damage" in events:
        result.add("damage_event")
    if "health_gained" in events:
        result.add("health_recovery_event")
    if bottom_context:
        result.add("bottom_context")
    return result


def _quantiles(values: list[int]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(array.min()),
        "q25": float(np.quantile(array, 0.25)),
        "median": float(np.median(array)),
        "q75": float(np.quantile(array, 0.75)),
        "maximum": float(array.max()),
        "mean": float(array.mean()),
    }


def analyze_teacher_dataset(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    digest = sha256(source.read_bytes()).hexdigest()
    episodes: dict[str, list[dict[str, object]]] = {}
    episode_order: list[str] = []
    with source.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{source}:{line_number} 必須是object。")
            episode_id = str(payload.get("episode_id", ""))
            if not episode_id:
                raise ValueError(f"{source}:{line_number} 缺少episode_id。")
            if episode_id not in episodes:
                episodes[episode_id] = []
                episode_order.append(episode_id)
            episodes[episode_id].append(payload)
    if not episodes:
        raise ValueError("Teacher dataset不可為空。")

    actions: Counter[int] = Counter()
    events: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    policy_versions: set[str] = set()
    environment_versions: set[str] = set()
    outcome_counts: Counter[str] = Counter()
    branch_rows: Counter[str] = Counter()
    branch_episodes: dict[str, set[str]] = defaultdict(set)
    branch_split_rows: dict[str, Counter[str]] = defaultdict(Counter)
    branch_split_episodes: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    episode_details: dict[str, dict[str, object]] = {}
    reversals = 0
    longest_streak = 0
    total_records = 0
    for episode_id in episode_order:
        rows = episodes[episode_id]
        for expected_step, row in enumerate(rows):
            if int(row.get("step", -1)) != expected_step:
                raise ValueError(f"{episode_id} step不連續。")
        seed = int(rows[0].get("seed", -1))
        split = str(rows[0].get("split", ""))
        if seed < 0 or split not in {"train", "validation", "test"}:
            raise ValueError(f"{episode_id} seed/split無效。")
        last = rows[-1]
        if bool(last.get("terminated")):
            outcome = str(last.get("failure_reason") or "terminated")
            if outcome == "bottom_death":
                outcome = "bottom"
        elif bool(last.get("truncated")):
            outcome = "truncated"
        else:
            outcome = "target_reached"
        outcome_counts[outcome] += 1
        floor_events = sum(
            "floor_descended" in {str(value) for value in row.get("events", [])}
            for row in rows
        )
        bottom_start = max(0, len(rows) - 8) if outcome == "bottom" else len(rows)
        previous_action: int | None = None
        previous_direction: int | None = None
        streak = 0
        episode_actions: list[int] = []
        episode_reasons: list[str] = []
        for index, row in enumerate(rows):
            action = int(row.get("action", -1))
            if action not in {0, 1, 2}:
                raise ValueError(f"{episode_id}:{index} action無效。")
            actions[action] += 1
            splits[split] += 1
            total_records += 1
            episode_actions.append(action)
            reason = str(row.get("teacher_reason") or "unknown")
            episode_reasons.append(reason)
            reasons[reason] += 1
            policy_versions.add(str(row.get("teacher_policy_version") or ""))
            environment_versions.add(str(row.get("environment_version") or ""))
            events.update(str(value) for value in row.get("events", []))
            if action == previous_action:
                streak += 1
            else:
                streak = 1
            longest_streak = max(longest_streak, streak)
            previous_action = action
            if action in {1, 2}:
                if previous_direction is not None and action != previous_direction:
                    reversals += 1
                previous_direction = action
            for branch in _branches(row, bottom_context=index >= bottom_start):
                branch_rows[branch] += 1
                branch_episodes[branch].add(episode_id)
                branch_split_rows[branch][split] += 1
                branch_split_episodes[branch][split].add(episode_id)
        episode_details[str(seed)] = {
            "episode_id": episode_id,
            "seed": seed,
            "split": split,
            "records": len(rows),
            "outcome": outcome,
            "floor_descended_events": floor_events,
            "actions": episode_actions,
            "teacher_reasons": episode_reasons,
        }

    action_rates = {
        str(action): actions[action] / total_records for action in (0, 1, 2)
    }
    return {
        "path": source.as_posix(),
        "sha256": digest,
        "records": total_records,
        "episodes": len(episodes),
        "policy_versions": sorted(policy_versions),
        "environment_versions": sorted(environment_versions),
        "split_records": dict(sorted(splits.items())),
        "action_counts": {str(action): actions[action] for action in (0, 1, 2)},
        "action_rates": action_rates,
        "event_counts": dict(sorted(events.items())),
        "teacher_reason_counts": dict(reasons.most_common()),
        "outcomes": dict(sorted(outcome_counts.items())),
        "outcome_rates": {
            name: count / len(episodes) for name, count in sorted(outcome_counts.items())
        },
        "episode_length": _quantiles([len(rows) for rows in episodes.values()]),
        "release_bridged_reversals": reversals,
        "release_bridged_reversals_per_100_steps": 100.0 * reversals / total_records,
        "longest_same_action_streak": longest_streak,
        "branches": {
            branch: {
                "rows": branch_rows[branch],
                "episodes": len(branch_episodes[branch]),
                "split_rows": {
                    split: branch_split_rows[branch][split]
                    for split in ("train", "validation", "test")
                },
                "split_episodes": {
                    split: len(branch_split_episodes[branch][split])
                    for split in ("train", "validation", "test")
                },
            }
            for branch in BRANCH_NAMES
        },
        "episode_details": episode_details,
    }


def compare_same_seed_datasets(
    frozen: Mapping[str, object],
    current: Mapping[str, object],
) -> dict[str, Any]:
    frozen_episodes = frozen["episode_details"]
    current_episodes = current["episode_details"]
    common = sorted(set(frozen_episodes) & set(current_episodes), key=int)
    if not common:
        raise ValueError("兩份dataset沒有共同seed。")
    transitions: Counter[str] = Counter()
    regressed: list[int] = []
    improved: list[int] = []
    first_divergence: dict[str, int | None] = {}
    first_action_transitions: Counter[str] = Counter()
    first_reason_transitions: Counter[str] = Counter()
    length_deltas: dict[str, int] = {}
    for seed in common:
        left = frozen_episodes[seed]
        right = current_episodes[seed]
        left_outcome = str(left["outcome"])
        right_outcome = str(right["outcome"])
        transitions[f"{left_outcome}->{right_outcome}"] += 1
        if left_outcome == "target_reached" and right_outcome != "target_reached":
            regressed.append(int(seed))
        if left_outcome != "target_reached" and right_outcome == "target_reached":
            improved.append(int(seed))
        left_actions = list(left["actions"])
        right_actions = list(right["actions"])
        mismatch = next(
            (
                index
                for index, (first, second) in enumerate(zip(left_actions, right_actions))
                if first != second
            ),
            None,
        )
        if mismatch is None and len(left_actions) != len(right_actions):
            mismatch = min(len(left_actions), len(right_actions))
        first_divergence[seed] = mismatch
        if mismatch is not None and mismatch < min(len(left_actions), len(right_actions)):
            first_action_transitions[
                f"{left_actions[mismatch]}->{right_actions[mismatch]}"
            ] += 1
            left_reasons = list(left["teacher_reasons"])
            right_reasons = list(right["teacher_reasons"])
            first_reason_transitions[
                f"{left_reasons[mismatch]}->{right_reasons[mismatch]}"
            ] += 1
        length_deltas[seed] = len(right_actions) - len(left_actions)
    frozen_rates = frozen["action_rates"]
    current_rates = current["action_rates"]
    action_tv = 0.5 * sum(
        abs(float(frozen_rates[str(action)]) - float(current_rates[str(action)]))
        for action in (0, 1, 2)
    )
    finite_divergences = [value for value in first_divergence.values() if value is not None]
    return {
        "common_seeds": len(common),
        "outcome_transitions": dict(sorted(transitions.items())),
        "regressed_seeds": regressed,
        "improved_seeds": improved,
        "unchanged_outcome_seeds": len(common) - len(regressed) - len(improved),
        "action_distribution_total_variation": action_tv,
        "first_action_divergence_by_seed": first_divergence,
        "first_action_transitions": dict(first_action_transitions.most_common()),
        "first_reason_transitions": dict(first_reason_transitions.most_common()),
        "first_action_divergence_step": (
            _quantiles([int(value) for value in finite_divergences])
            if finite_divergences
            else None
        ),
        "episode_length_delta_by_seed": length_deltas,
    }


def evaluate_v2_readiness(
    frozen: Mapping[str, object],
    current: Mapping[str, object],
    comparison: Mapping[str, object],
    *,
    source_fingerprint_embedded: bool,
    fresh_reliability_evaluated: bool,
    fresh_reliability_passed: bool = False,
) -> dict[str, Any]:
    frozen_target = float(frozen["outcome_rates"].get("target_reached", 0.0))
    current_target = float(current["outcome_rates"].get("target_reached", 0.0))
    frozen_bottom = float(frozen["outcome_rates"].get("bottom", 0.0))
    current_bottom = float(current["outcome_rates"].get("bottom", 0.0))
    target_floor = max(0.90, frozen_target - 0.02)
    bottom_ceiling = min(0.10, frozen_bottom + 0.02)
    policy_bumped = set(current["policy_versions"]) != set(frozen["policy_versions"])
    critical_branches = ("direction_brake", "recovery", "spike_target")
    all_split_coverage = all(
        all(int(current["branches"][branch]["split_rows"][split]) > 0 for split in ("train", "validation", "test"))
        for branch in critical_branches
    )
    branch_episode_minimums = {
        "direction_brake": 20,
        "recovery": 10,
        "spike_target": 10,
    }
    checks = {
        "policy_version_bumped": policy_bumped,
        "source_fingerprint_embedded": bool(source_fingerprint_embedded),
        "same_seed_target_reliability": current_target >= target_floor,
        "same_seed_bottom_reliability": current_bottom <= bottom_ceiling,
        "no_health_death": int(current["outcomes"].get("health_depleted", 0)) == 0,
        "action_distribution_tv_bounded": float(
            comparison["action_distribution_total_variation"]
        )
        <= 0.10,
        "critical_branches_all_splits": all_split_coverage,
        "critical_branch_episode_minimums": all(
            int(current["branches"][branch]["episodes"]) >= minimum
            for branch, minimum in branch_episode_minimums.items()
        ),
        "fresh_reliability_evaluated": bool(fresh_reliability_evaluated),
        "fresh_reliability_passed": bool(fresh_reliability_passed),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "criteria": {
            "same_seed_target_reached_rate_minimum": target_floor,
            "same_seed_bottom_rate_maximum": bottom_ceiling,
            "action_distribution_total_variation_maximum": 0.10,
            "branch_episode_minimums": branch_episode_minimums,
            "critical_branches_required_in_every_split": list(critical_branches),
            "fresh_reliability": (
                "100 new seeds; reach-10 >=90%; bottom <=10%; health death=0; "
                "Q25/CVaR reported before dataset generation"
            ),
        },
        "observed": {
            "frozen_target_reached_rate": frozen_target,
            "current_target_reached_rate": current_target,
            "frozen_bottom_rate": frozen_bottom,
            "current_bottom_rate": current_bottom,
            "action_distribution_total_variation": comparison[
                "action_distribution_total_variation"
            ],
        },
    }


def evaluate_v2_same_seed_readiness(
    frozen: Mapping[str, object],
    current: Mapping[str, object],
    comparison: Mapping[str, object],
    *,
    source_fingerprint_embedded: bool,
    config_fingerprint_embedded: bool,
) -> dict[str, Any]:
    """Evaluate only the blocking 60-seed Gate before fresh evaluation."""

    frozen_target = float(frozen["outcome_rates"].get("target_reached", 0.0))
    current_target = float(current["outcome_rates"].get("target_reached", 0.0))
    frozen_bottom = float(frozen["outcome_rates"].get("bottom", 0.0))
    current_bottom = float(current["outcome_rates"].get("bottom", 0.0))
    target_floor = max(0.90, frozen_target - 0.02)
    bottom_ceiling = min(0.10, frozen_bottom + 0.02)
    critical_branches = ("direction_brake", "recovery", "spike_target")
    branch_episode_minimums = {
        "direction_brake": 20,
        "recovery": 10,
        "spike_target": 10,
    }
    checks = {
        "policy_version_bumped": (
            set(current["policy_versions"]) != set(frozen["policy_versions"])
        ),
        "source_fingerprint_embedded": bool(source_fingerprint_embedded),
        "config_fingerprint_embedded": bool(config_fingerprint_embedded),
        "same_seed_target_reliability": current_target >= target_floor,
        "same_seed_bottom_reliability": current_bottom <= bottom_ceiling,
        "no_health_death": (
            int(current["outcomes"].get("health_depleted", 0)) == 0
        ),
        "action_distribution_tv_bounded": (
            float(comparison["action_distribution_total_variation"]) <= 0.10
        ),
        "critical_branches_all_splits": all(
            all(
                int(current["branches"][branch]["split_rows"][split]) > 0
                for split in ("train", "validation", "test")
            )
            for branch in critical_branches
        ),
        "critical_branch_episode_minimums": all(
            int(current["branches"][branch]["episodes"]) >= minimum
            for branch, minimum in branch_episode_minimums.items()
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "criteria": {
            "same_seed_target_reached_rate_minimum": target_floor,
            "same_seed_bottom_rate_maximum": bottom_ceiling,
            "action_distribution_total_variation_maximum": 0.10,
            "branch_episode_minimums": branch_episode_minimums,
            "critical_branches_required_in_every_split": list(
                critical_branches
            ),
        },
        "observed": {
            "frozen_target_reached_rate": frozen_target,
            "candidate_target_reached_rate": current_target,
            "frozen_bottom_rate": frozen_bottom,
            "candidate_bottom_rate": current_bottom,
            "action_distribution_total_variation": comparison[
                "action_distribution_total_variation"
            ],
        },
    }


__all__ = [
    "BRANCH_NAMES",
    "analyze_teacher_dataset",
    "compare_same_seed_datasets",
    "evaluate_v2_same_seed_readiness",
    "evaluate_v2_readiness",
]
