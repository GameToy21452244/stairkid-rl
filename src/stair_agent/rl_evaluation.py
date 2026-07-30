from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


class PredictiveModel(Protocol):
    def predict(
        self,
        observation,
        *,
        deterministic: bool,
    ) -> tuple[Any, Any]: ...


class EvaluationEnvironment(Protocol):
    def reset(self) -> tuple[Any, dict[str, Any]]: ...

    def step(
        self,
        action: int,
    ) -> tuple[Any, float, bool, bool, dict[str, Any]]: ...


@dataclass(frozen=True)
class EvaluationResult:
    stop_reason: str
    steps: int
    completed_episodes: int
    total_reward: float
    elapsed_seconds: float
    episode_lengths: list[int]
    episode_rewards: list[float]
    action_counts: dict[str, int]
    longest_same_action_streak: int
    direction_switches: int
    reward_component_totals: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_policy(
    env: EvaluationEnvironment,
    model: PredictiveModel,
    *,
    max_steps: int,
    max_episodes: int,
    max_seconds: float,
    clock: Callable[[], float] = time.monotonic,
) -> EvaluationResult:
    """以 deterministic 動作評估，且不超過任一核准上限。"""
    if max_steps <= 0 or max_episodes <= 0 or max_seconds <= 0:
        raise ValueError("評估步數、回合數與秒數上限都必須大於 0。")

    started_at = clock()
    observation, _info = env.reset()
    steps = 0
    completed = 0
    total_reward = 0.0
    current_reward = 0.0
    current_length = 0
    episode_rewards: list[float] = []
    episode_lengths: list[int] = []
    action_names = {0: "RELEASE_ALL", 1: "LEFT", 2: "RIGHT"}
    action_counts = {name: 0 for name in action_names.values()}
    previous_action: int | None = None
    current_action_streak = 0
    longest_same_action_streak = 0
    previous_direction: int | None = None
    direction_switches = 0
    reward_component_totals: dict[str, float] = {}
    stop_reason = "step_limit"

    while steps < max_steps:
        if clock() - started_at >= max_seconds:
            stop_reason = "time_limit"
            break

        action, _state = model.predict(
            observation,
            deterministic=True,
        )
        action_value = int(action)
        action_name = action_names.get(action_value, f"UNKNOWN_{action_value}")
        action_counts[action_name] = action_counts.get(action_name, 0) + 1
        if action_value == previous_action:
            current_action_streak += 1
        else:
            previous_action = action_value
            current_action_streak = 1
        longest_same_action_streak = max(
            longest_same_action_streak,
            current_action_streak,
        )
        if action_value in (1, 2):
            if previous_direction is not None and action_value != previous_direction:
                direction_switches += 1
            previous_direction = action_value

        observation, reward, terminated, truncated, step_info = env.step(
            action_value
        )
        for name, value in (
            step_info.get("reward_components") or {}
        ).items():
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and (
                    name.endswith("_reward")
                    or name.endswith("_penalty")
                )
            ):
                reward_component_totals[name] = (
                    reward_component_totals.get(name, 0.0)
                    + float(value)
                )
        steps += 1
        current_length += 1
        current_reward += float(reward)
        total_reward += float(reward)

        if terminated or truncated:
            completed += 1
            episode_lengths.append(current_length)
            episode_rewards.append(current_reward)
            if completed >= max_episodes:
                stop_reason = "episode_limit"
                break
            if steps >= max_steps:
                stop_reason = "step_limit"
                break
            if clock() - started_at >= max_seconds:
                stop_reason = "time_limit"
                break
            observation, _info = env.reset()
            current_reward = 0.0
            current_length = 0

    return EvaluationResult(
        stop_reason=stop_reason,
        steps=steps,
        completed_episodes=completed,
        total_reward=total_reward,
        elapsed_seconds=max(0.0, clock() - started_at),
        episode_lengths=episode_lengths,
        episode_rewards=episode_rewards,
        action_counts=action_counts,
        longest_same_action_streak=longest_same_action_streak,
        direction_switches=direction_switches,
        reward_component_totals=reward_component_totals,
    )


def resolve_evaluation_model(
    project_root: str | Path,
    requested_path: str | Path | None,
) -> Path:
    """只允許載入專案 models/ 下的 zip，避免開啟任意模型檔。"""
    root = Path(project_root).resolve()
    models_root = (root / "models").resolve()
    if requested_path is None:
        candidates = list(models_root.glob("ppo/*/final_model.zip"))
        if not candidates:
            raise FileNotFoundError(
                "models/ppo/ 下找不到可評估的 final_model.zip。"
            )
        target = max(
            candidates,
            key=lambda path: (path.stat().st_mtime_ns, str(path)),
        ).resolve()
    else:
        raw = Path(requested_path)
        target = (
            raw.resolve()
            if raw.is_absolute()
            else (root / raw).resolve()
        )

    try:
        target.relative_to(models_root)
    except ValueError as exc:
        raise ValueError("評估模型必須位於專案 models/ 之下。") from exc
    if target.suffix.casefold() != ".zip":
        raise ValueError("評估模型必須是 .zip 檔。")
    if not target.is_file():
        raise FileNotFoundError(f"找不到評估模型：{target}")
    return target
