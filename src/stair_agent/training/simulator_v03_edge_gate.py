"""Bounded Gate for Simulator v0.3 moving-platform support semantics."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

import numpy as np

from ..baseline_policy import SafePlatformPolicy
from ..config import BaselineConfig
from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from ..policies.simulator_teachers import OracleFull
from ..policies.observable_route_intent import ObservableRouteIntentPolicy
from ..simulator.state import ShaftEnvConfig


DEVELOPMENT_SEEDS = tuple(range(13000, 13100))
HOLDOUT_SEEDS = tuple(range(14000, 14100))
MAX_EPISODE_STEPS = 600
TARGET_FLOOR = 10


@dataclass(frozen=True)
class EdgeEpisode:
    seed: int
    steps: int
    deepest_floor: int
    terminal_reason: str | None
    action_counts: dict[str, int]
    support_departures: int
    floor_descents: int
    minimum_departure_clearance: float | None
    invariant_violations: tuple[str, ...]


@dataclass(frozen=True)
class EdgeEvaluation:
    candidate: str
    episodes: int
    mean_deepest_floor: float
    reach_floor_3_rate: float
    reach_floor_10_rate: float
    max_action_share: float
    collapsed: bool
    action_counts: dict[str, int]
    support_departures: int
    floor_descents: int
    minimum_departure_clearance: float | None
    invariant_violation_count: int
    episodes_with_violations: int
    terminal_reasons: dict[str, int]
    episode_results: tuple[EdgeEpisode, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ActionChooser = Callable[[ShaftEnv], Action]


def edge_fidelity_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        enable_support_ownership=True,
    )


def evaluate_edge_candidate(
    candidate: str,
    chooser_factory: Callable[[], ActionChooser],
    *,
    seeds: Iterable[int],
    max_episode_steps: int = MAX_EPISODE_STEPS,
    target_floor: int = TARGET_FLOOR,
    config: ShaftEnvConfig | None = None,
) -> EdgeEvaluation:
    seed_list = tuple(int(seed) for seed in seeds)
    if not seed_list or len(seed_list) != len(set(seed_list)):
        raise ValueError("seeds 不可為空或重複。")
    if max_episode_steps <= 0 or target_floor <= 0:
        raise ValueError("step 與 target floor 必須大於 0。")

    episodes: list[EdgeEpisode] = []
    total_actions: Counter[str] = Counter()
    terminal_reasons: Counter[str] = Counter()
    for seed in seed_list:
        env = ShaftEnv(config=config or edge_fidelity_config())
        chooser = chooser_factory()
        env.reset(seed=seed)
        required_departure_floor = 0
        departed_floor: int | None = None
        action_counts: Counter[str] = Counter()
        violations: list[str] = []
        departure_clearances: list[float] = []
        support_departures = 0
        floor_descents = 0
        terminal_reason: str | None = None
        try:
            for step in range(1, max_episode_steps + 1):
                simulator = env.simulator
                source = simulator.supported_platform
                source_floor = (
                    None if source is None else source.floor_index
                )
                previous_deepest = simulator.deepest_floor
                action = Action(int(chooser(env)))
                action_counts[action.name] += 1
                total_actions[action.name] += 1
                _, _, terminated, truncated, info = env.step(int(action))
                current_source_floor = source_floor
                departure_records = iter(info["support_departures"])
                for event in info["events"]:
                    if event == "landed":
                        current_source_floor = (
                            env.simulator.last_landed_floor
                        )
                    elif event == "floor_descended":
                        floor_descents += 1
                        if departed_floor != required_departure_floor:
                            violations.append(
                                f"step {step}: floor "
                                f"{env.simulator.deepest_floor} without edge "
                                f"departure from {required_departure_floor}"
                            )
                        if env.simulator.deepest_floor <= previous_deepest:
                            violations.append(
                                f"step {step}: non-increasing floor_descended"
                            )
                        required_departure_floor = env.simulator.deepest_floor
                        departed_floor = None
                    elif event == "support_departed":
                        support_departures += 1
                        record = next(departure_records, None)
                        if record is None:
                            violations.append(
                                f"step {step}: support_departed without record"
                            )
                        else:
                            source_floor = int(record["source_floor"])
                            clearance = float(record["clearance"])
                            departure_clearances.append(clearance)
                            if clearance < -1e-6:
                                violations.append(
                                    f"step {step}: source {source_floor} "
                                    "departure clearance is negative"
                                )
                            if (
                                current_source_floor is not None
                                and current_source_floor != source_floor
                            ):
                                violations.append(
                                    f"step {step}: departure record source "
                                    f"{source_floor} != tracked source "
                                    f"{current_source_floor}"
                                )
                            departed_floor = source_floor
                        current_source_floor = None

                if env.simulator.deepest_floor >= target_floor:
                    terminal_reason = "target_reached"
                    break
                if terminated or truncated:
                    terminal_reason = str(info["terminal_reason"])
                    break
            terminal_reasons[str(terminal_reason)] += 1
            episodes.append(
                EdgeEpisode(
                    seed=seed,
                    steps=step,
                    deepest_floor=int(env.simulator.deepest_floor),
                    terminal_reason=terminal_reason,
                    action_counts={
                        name: int(action_counts.get(name, 0))
                        for name in ("RELEASE_ALL", "LEFT", "RIGHT")
                    },
                    support_departures=support_departures,
                    floor_descents=floor_descents,
                    minimum_departure_clearance=(
                        min(departure_clearances)
                        if departure_clearances
                        else None
                    ),
                    invariant_violations=tuple(violations),
                )
            )
        finally:
            env.close()

    floors = np.asarray(
        [episode.deepest_floor for episode in episodes],
        dtype=np.float64,
    )
    total_steps = sum(sum(ep.action_counts.values()) for ep in episodes)
    max_action_share = max(total_actions.values(), default=0) / max(
        1, total_steps
    )
    clearances = [
        episode.minimum_departure_clearance
        for episode in episodes
        if episode.minimum_departure_clearance is not None
    ]
    violation_count = sum(
        len(episode.invariant_violations) for episode in episodes
    )
    return EdgeEvaluation(
        candidate=candidate,
        episodes=len(episodes),
        mean_deepest_floor=float(floors.mean()),
        reach_floor_3_rate=float(np.mean(floors >= 3)),
        reach_floor_10_rate=float(np.mean(floors >= 10)),
        max_action_share=float(max_action_share),
        collapsed=max_action_share >= 0.98,
        action_counts={
            name: int(total_actions.get(name, 0))
            for name in ("RELEASE_ALL", "LEFT", "RIGHT")
        },
        support_departures=sum(ep.support_departures for ep in episodes),
        floor_descents=sum(ep.floor_descents for ep in episodes),
        minimum_departure_clearance=(min(clearances) if clearances else None),
        invariant_violation_count=violation_count,
        episodes_with_violations=sum(
            bool(episode.invariant_violations) for episode in episodes
        ),
        terminal_reasons=dict(terminal_reasons),
        episode_results=tuple(episodes),
    )


def oracle_factory() -> ActionChooser:
    oracle = OracleFull()
    return lambda env: oracle.choose(env.simulator).action


def route_planner_oracle_factory() -> ActionChooser:
    oracle = OracleFull(enable_route_planner=True)
    return lambda env: oracle.choose(env.simulator).action


def baseline_factory() -> ActionChooser:
    policy = SafePlatformPolicy(BaselineConfig())
    return lambda env: policy.choose(env.last_observation).action


def observable_route_intent_factory() -> ActionChooser:
    policy = ObservableRouteIntentPolicy(BaselineConfig())
    return lambda env: policy.choose(env.last_observation).action


def release_factory() -> ActionChooser:
    return lambda _env: Action.RELEASE_ALL


def oracle_checks(result: EdgeEvaluation) -> dict[str, bool]:
    return {
        "reach_floor_10_at_least_0.95": result.reach_floor_10_rate >= 0.95,
        "reach_floor_3_at_least_0.99": result.reach_floor_3_rate >= 0.99,
        "edge_invariant_violations_zero": result.invariant_violation_count == 0,
        "all_actions_used": all(result.action_counts.values()),
        "not_collapsed": not result.collapsed,
    }


def baseline_checks(result: EdgeEvaluation) -> dict[str, bool]:
    return {
        "mean_deepest_floor_at_least_5": result.mean_deepest_floor >= 5.0,
        "reach_floor_3_at_least_0.90": result.reach_floor_3_rate >= 0.90,
        "edge_invariant_violations_zero": result.invariant_violation_count == 0,
        "not_collapsed": not result.collapsed,
    }


__all__ = [
    "DEVELOPMENT_SEEDS",
    "HOLDOUT_SEEDS",
    "MAX_EPISODE_STEPS",
    "TARGET_FLOOR",
    "EdgeEpisode",
    "EdgeEvaluation",
    "baseline_checks",
    "baseline_factory",
    "edge_fidelity_config",
    "evaluate_edge_candidate",
    "oracle_checks",
    "oracle_factory",
    "observable_route_intent_factory",
    "release_factory",
    "route_planner_oracle_factory",
]
