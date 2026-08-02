from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Iterable

import numpy as np

from .baseline_policy import SafePlatformPolicy
from .config import BaselineConfig
from .envs.shaft_env import ShaftEnv, ShaftEnvConfig


ACTION_NAMES = {
    0: "RELEASE_ALL",
    1: "LEFT",
    2: "RIGHT",
}
ActionSelector = Callable[[np.ndarray, ShaftEnv, np.random.Generator], int]


@dataclass(frozen=True)
class ProbeEpisode:
    seed: int
    length: int
    total_return: float
    floors: int
    deepest_floor: int
    landings: int
    terminal_reason: str | None


@dataclass(frozen=True)
class ProbeEvaluation:
    candidate: str
    episodes: int
    total_steps: int
    mean_length: float
    mean_return: float
    mean_floors: float
    mean_landings: float
    action_counts: dict[str, int]
    max_action_share: float
    collapsed: bool
    longest_same_action_streak: int
    direction_switches: int
    terminal_reasons: dict[str, int]
    episode_results: list[ProbeEpisode]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["episode_results"] = [
            asdict(result) for result in self.episode_results
        ]
        return payload


def learned_selector(model: Any) -> ActionSelector:
    def choose(
        observation: np.ndarray,
        _env: ShaftEnv,
        _rng: np.random.Generator,
    ) -> int:
        action, _state = model.predict(observation, deterministic=True)
        return int(action)

    return choose


def release_selector(
    _observation: np.ndarray,
    _env: ShaftEnv,
    _rng: np.random.Generator,
) -> int:
    return 0


def random_selector(
    _observation: np.ndarray,
    _env: ShaftEnv,
    rng: np.random.Generator,
) -> int:
    return int(rng.integers(0, 3))


def baseline_selector(config: BaselineConfig | None = None) -> ActionSelector:
    policy = SafePlatformPolicy(config or BaselineConfig())

    def choose(
        _observation: np.ndarray,
        env: ShaftEnv,
        _rng: np.random.Generator,
    ) -> int:
        if env.last_observation is None:
            raise RuntimeError("baseline evaluation 缺少 structured observation。")
        return int(policy.choose(env.last_observation).action)

    setattr(choose, "reset", policy.reset)
    return choose


def evaluate_candidate(
    candidate: str,
    selector: ActionSelector,
    *,
    seeds: Iterable[int],
    max_episode_steps: int,
    config: ShaftEnvConfig | None = None,
    success_floor: int | None = None,
) -> ProbeEvaluation:
    seed_list = list(seeds)
    if not seed_list or max_episode_steps <= 0:
        raise ValueError("評估 seeds 不可為空，episode step 上限必須大於 0。")
    action_counts: Counter[str] = Counter()
    terminal_reasons: Counter[str] = Counter()
    episode_results: list[ProbeEpisode] = []
    longest_same_action_streak = 0
    direction_switches = 0
    for seed in seed_list:
        reset_selector = getattr(selector, "reset", None)
        if callable(reset_selector):
            reset_selector()
        env_config = replace(
            config or ShaftEnvConfig(),
            max_episode_steps=max_episode_steps,
        )
        env = ShaftEnv(config=env_config)
        observation, _info = env.reset(seed=seed)
        rng = np.random.default_rng(seed + 90_000)
        total_return = 0.0
        floors = 0
        landings = 0
        terminal_reason = None
        previous_action: int | None = None
        current_streak = 0
        try:
            for length in range(1, max_episode_steps + 1):
                action = int(selector(observation, env, rng))
                if action not in ACTION_NAMES:
                    raise ValueError(
                        f"{candidate} 產生無效 simulator action：{action}"
                    )
                action_counts[ACTION_NAMES[action]] += 1
                if action == previous_action:
                    current_streak += 1
                else:
                    current_streak = 1
                    if (
                        previous_action in {1, 2}
                        and action in {1, 2}
                        and previous_action != action
                    ):
                        direction_switches += 1
                previous_action = action
                longest_same_action_streak = max(
                    longest_same_action_streak, current_streak
                )
                (
                    observation,
                    reward,
                    terminated,
                    truncated,
                    info,
                ) = env.step(action)
                total_return += float(reward)
                floors += int("floor_descended" in info["events"])
                landings += int("landed" in info["events"])
                if (
                    success_floor is not None
                    and env.simulator.deepest_floor >= success_floor
                ):
                    terminal_reason = "target_reached"
                    break
                if terminated or truncated:
                    terminal_reason = info["terminal_reason"]
                    break
            terminal_reasons[str(terminal_reason)] += 1
            episode_results.append(
                ProbeEpisode(
                    seed=seed,
                    length=length,
                    total_return=total_return,
                    floors=floors,
                    deepest_floor=env.simulator.deepest_floor,
                    landings=landings,
                    terminal_reason=terminal_reason,
                )
            )
        finally:
            env.close()
    total_steps = sum(result.length for result in episode_results)
    max_share = max(action_counts.values(), default=0) / max(1, total_steps)
    return ProbeEvaluation(
        candidate=candidate,
        episodes=len(episode_results),
        total_steps=total_steps,
        mean_length=float(
            np.mean([result.length for result in episode_results])
        ),
        mean_return=float(
            np.mean([result.total_return for result in episode_results])
        ),
        mean_floors=float(
            np.mean([result.floors for result in episode_results])
        ),
        mean_landings=float(
            np.mean([result.landings for result in episode_results])
        ),
        action_counts={
            name: int(action_counts.get(name, 0))
            for name in ACTION_NAMES.values()
        },
        max_action_share=max_share,
        collapsed=max_share >= 0.98,
        longest_same_action_streak=longest_same_action_streak,
        direction_switches=direction_switches,
        terminal_reasons=dict(terminal_reasons),
        episode_results=episode_results,
    )
