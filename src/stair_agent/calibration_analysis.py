from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable


REFERENCE_WIDTH = 634.0
REFERENCE_HEIGHT = 431.0
VELOCITY_SCALE = 500.0
FRAME_WIDTH = 67
LATEST = 3 * FRAME_WIDTH
PLAYER_HALF_WIDTH_PX = 12.0
LANDING_GAP_PX = 17.25


def player_state(values: list[float]) -> dict[str, float]:
    """Decode the latest frame in the v1 temporal feature vector."""
    return {
        "present": values[LATEST],
        "x": values[LATEST + 1] * REFERENCE_WIDTH,
        "y": values[LATEST + 2] * REFERENCE_HEIGHT,
        "vx": values[LATEST + 3] * VELOCITY_SCALE,
        "vy": values[LATEST + 4] * VELOCITY_SCALE,
        "motion": values[LATEST + 5],
    }


def is_continuous_motion_transition(row: dict[str, Any]) -> bool:
    """Reject contacts and unlabelled motion-boundary discontinuities."""
    before = player_state(row["observation"])
    after = player_state(row["next_observation"])
    dt = row["next_observation_timestamp"] - row["observation_timestamp"]
    return bool(
        before["present"] > 0.5
        and after["present"] > 0.5
        and not row["events"]
        and dt > 0
        and abs(before["motion"]) > 0.5
        and before["motion"] == after["motion"]
    )


def predicts_landing(values: list[float]) -> bool:
    """Geometry-only landing prediction from the pre-action observation."""
    player = player_state(values)
    if player["present"] <= 0.5 or player["motion"] <= 0.5:
        return False
    for slot in range(8):
        base = LATEST + 16 + slot * 6
        if values[base] <= 0.5:
            continue
        relative_x_px = abs(values[base + 1] * REFERENCE_WIDTH)
        relative_top_px = values[base + 2] * REFERENCE_HEIGHT
        half_platform_width_px = values[base + 3] * REFERENCE_WIDTH / 2
        if (
            0 <= relative_top_px <= LANDING_GAP_PX
            and relative_x_px
            <= half_platform_width_px + PLAYER_HALF_WIDTH_PX
        ):
            return True
    return False


@dataclass(frozen=True)
class LandingMetrics:
    true_positive: int
    false_positive: int
    false_negative: int
    death_misclassifications: int

    @property
    def precision(self) -> float:
        total = self.true_positive + self.false_positive
        return self.true_positive / total if total else 0.0

    @property
    def recall(self) -> float:
        total = self.true_positive + self.false_negative
        return self.true_positive / total if total else 0.0


def landing_metrics(rows: Iterable[dict[str, Any]]) -> LandingMetrics:
    tp = fp = fn = death_errors = 0
    for row in rows:
        predicted = predicts_landing(row["observation"])
        actual = any(
            event.get("type") == "landed" for event in row["events"]
        )
        tp += int(predicted and actual)
        fp += int(predicted and not actual)
        fn += int(actual and not predicted)
        death_errors += int(predicted and bool(row["terminated"]))
    return LandingMetrics(tp, fp, fn, death_errors)


def two_proportion_z(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> float:
    if total_a <= 0 or total_b <= 0:
        raise ValueError("兩組比例的樣本數都必須大於 0。")
    if not 0 <= successes_a <= total_a or not 0 <= successes_b <= total_b:
        raise ValueError("成功次數必須介於 0 與樣本數之間。")
    pooled = (successes_a + successes_b) / (total_a + total_b)
    variance = pooled * (1 - pooled) * (1 / total_a + 1 / total_b)
    if variance == 0:
        return 0.0
    return (
        successes_a / total_a - successes_b / total_b
    ) / math.sqrt(variance)
