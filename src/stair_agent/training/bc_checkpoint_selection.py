from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def ensure_disjoint_seed_partitions(
    *,
    dataset_seeds: Iterable[int],
    selection_seeds: Iterable[int],
    final_seeds: Iterable[int],
) -> None:
    partitions = {
        "dataset": set(dataset_seeds),
        "selection": set(selection_seeds),
        "final": set(final_seeds),
    }
    for name, seeds in partitions.items():
        if not seeds:
            raise ValueError(f"{name} seeds 不可為空。")
    pairs = (("dataset", "selection"), ("dataset", "final"), ("selection", "final"))
    for left, right in pairs:
        overlap = sorted(partitions[left] & partitions[right])
        if overlap:
            raise ValueError(
                f"{left} 與 {right} seeds 重疊：{overlap}"
            )


def checkpoint_gate_passed(
    *,
    evaluation: Mapping[str, Any],
    baseline: Mapping[str, Any],
    random: Mapping[str, Any],
    release: Mapping[str, Any],
    curriculum: str,
) -> bool:
    health_deaths = int(
        evaluation.get("terminal_reasons", {}).get("health_depleted", 0)
    )
    bottom_deaths = int(
        evaluation.get("terminal_reasons", {}).get("bottom", 0)
    )
    baseline_bottom_deaths = int(
        baseline.get("terminal_reasons", {}).get("bottom", 0)
    )
    floor_10_reach = float(
        evaluation.get(
            "reach_rate_floor_10",
            evaluation.get("success_rate_floor_10", 0.0),
        )
    )
    baseline_floor_10_reach = float(
        baseline.get(
            "reach_rate_floor_10",
            baseline.get("success_rate_floor_10", 0.0),
        )
    )
    mean_deepest_floor = float(
        evaluation.get("mean_deepest_floor", evaluation["mean_floors"])
    )
    baseline_mean_deepest_floor = float(
        baseline.get("mean_deepest_floor", baseline["mean_floors"])
    )
    random_mean_deepest_floor = float(
        random.get("mean_deepest_floor", random["mean_floors"])
    )
    release_mean_deepest_floor = float(
        release.get("mean_deepest_floor", release["mean_floors"])
    )
    floor_quantile_25 = float(
        evaluation.get(
            "deepest_floor_quantile_25",
            evaluation.get("floor_quantile_25", 0.0),
        )
    )
    baseline_floor_quantile_25 = float(
        baseline.get(
            "deepest_floor_quantile_25",
            baseline.get("floor_quantile_25", 0.0),
        )
    )
    return bool(
        not evaluation["collapsed"]
        and mean_deepest_floor > random_mean_deepest_floor
        and mean_deepest_floor > release_mean_deepest_floor
        and mean_deepest_floor >= 0.8 * baseline_mean_deepest_floor
        and floor_10_reach >= 0.9 * baseline_floor_10_reach
        and bottom_deaths <= baseline_bottom_deaths
        and floor_quantile_25 >= 0.8 * baseline_floor_quantile_25
        and (curriculum != "spike-v0" or health_deaths == 0)
    )


def checkpoint_selection_key(
    *,
    epoch: int,
    validation_loss: float,
    evaluation: Mapping[str, Any],
    baseline: Mapping[str, Any],
    random: Mapping[str, Any],
    release: Mapping[str, Any],
    curriculum: str,
) -> tuple[bool, float, int, float, float, bool, float, float, int]:
    health_deaths = int(
        evaluation.get("terminal_reasons", {}).get("health_depleted", 0)
    )
    safe = not evaluation["collapsed"] and (
        curriculum != "spike-v0" or health_deaths == 0
    )
    passed = checkpoint_gate_passed(
        evaluation=evaluation,
        baseline=baseline,
        random=random,
        release=release,
        curriculum=curriculum,
    )
    bottom_deaths = int(
        evaluation.get("terminal_reasons", {}).get("bottom", 0)
    )
    return (
        safe,
        float(
            evaluation.get(
                "reach_rate_floor_10",
                evaluation.get("success_rate_floor_10", 0.0),
            )
        ),
        -bottom_deaths,
        float(
            evaluation.get(
                "deepest_floor_quantile_25",
                evaluation.get("floor_quantile_25", 0.0),
            )
        ),
        float(
            evaluation.get(
                "median_deepest_floor",
                evaluation.get("median_floors", 0.0),
            )
        ),
        passed,
        float(
            evaluation.get(
                "mean_deepest_floor",
                evaluation["mean_floors"],
            )
        ),
        -float(validation_loss),
        -int(epoch),
    )


__all__ = [
    "checkpoint_gate_passed",
    "checkpoint_selection_key",
    "ensure_disjoint_seed_partitions",
]
