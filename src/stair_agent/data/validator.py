from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .schema import (
    OBSERVATION_DIM,
    OBSERVATION_SCHEMA_VERSION,
    REWARD_VERSION,
    SCHEMA_VERSION,
    TransitionRecord,
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    line: int | None
    message: str


@dataclass
class DatasetValidationReport:
    path: str
    records: int = 0
    episodes: int = 0
    action_counts: dict[int, int] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def valid(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "valid": self.valid,
            "records": self.records,
            "episodes": self.episodes,
            "action_counts": self.action_counts,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "line": issue.line,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


class DatasetValidator:
    """Strict structural checks plus warnings for suspicious trajectories."""

    def __init__(
        self,
        *,
        expected_observation_dim: int = OBSERVATION_DIM,
        action_collapse_ratio: float = 0.98,
        duplicate_ratio: float = 0.50,
        minimum_distribution_records: int = 50,
        observation_jump_threshold: float = 0.25,
    ) -> None:
        self.expected_observation_dim = int(expected_observation_dim)
        self.action_collapse_ratio = float(action_collapse_ratio)
        self.duplicate_ratio = float(duplicate_ratio)
        self.minimum_distribution_records = int(
            minimum_distribution_records
        )
        self.observation_jump_threshold = float(
            observation_jump_threshold
        )

    @staticmethod
    def _finite(values: Any) -> bool:
        if isinstance(values, bool) or values is None:
            return True
        if isinstance(values, (int, float)):
            return math.isfinite(float(values))
        if isinstance(values, dict):
            return all(DatasetValidator._finite(value) for value in values.values())
        if isinstance(values, (list, tuple)):
            return all(DatasetValidator._finite(value) for value in values)
        return True

    @staticmethod
    def _add(
        report: DatasetValidationReport,
        severity: str,
        code: str,
        line: int | None,
        message: str,
    ) -> None:
        report.issues.append(ValidationIssue(severity, code, line, message))

    def _check_raw(
        self,
        payload: dict[str, Any],
        line: int,
        report: DatasetValidationReport,
    ) -> None:
        if payload.get("schema_version") != SCHEMA_VERSION:
            self._add(
                report,
                "error",
                "schema_version",
                line,
                f"schema_version 必須是 {SCHEMA_VERSION!r}。",
            )
        if (
            payload.get("observation_schema_version")
            != OBSERVATION_SCHEMA_VERSION
        ):
            self._add(
                report,
                "error",
                "observation_schema_version",
                line,
                "觀測版本不符。",
            )
        if payload.get("reward_version") != REWARD_VERSION:
            self._add(
                report,
                "error",
                "reward_version",
                line,
                "reward 版本不符。",
            )
        for name in ("observation", "next_observation"):
            value = payload.get(name)
            if (
                not isinstance(value, list)
                or len(value) != self.expected_observation_dim
            ):
                actual = len(value) if isinstance(value, list) else None
                self._add(
                    report,
                    "error",
                    "observation_dimension",
                    line,
                    f"{name} 維度應為 {self.expected_observation_dim}，"
                    f"實際為 {actual!r}。",
                )
        if payload.get("action") not in {0, 1, 2}:
            self._add(
                report,
                "error",
                "invalid_action",
                line,
                "action 只允許 0、1、2。",
            )
        numeric_payload = {
            name: payload.get(name)
            for name in (
                "observation",
                "next_observation",
                "reward",
                "reward_components",
                "target_signed_offset",
                "observation_timestamp",
                "action_command_timestamp",
                "action_effective_timestamp",
                "next_observation_timestamp",
                "action_duration_ms",
            )
        }
        if not self._finite(numeric_payload):
            self._add(
                report,
                "error",
                "nonfinite",
                line,
                "數值欄位包含 NaN 或 Infinity。",
            )

    def validate_file(self, path: str | Path) -> DatasetValidationReport:
        source = Path(path)
        report = DatasetValidationReport(path=str(source))
        try:
            lines = source.open(encoding="utf-8")
        except OSError as exc:
            self._add(report, "error", "file_error", None, str(exc))
            return report
        with lines:
            return self._validate_lines(lines, report)

    def _validate_lines(
        self,
        lines: Iterable[str],
        report: DatasetValidationReport,
    ) -> DatasetValidationReport:
        action_counts: Counter[int] = Counter()
        signatures: Counter[str] = Counter()
        episode_ids: set[str] = set()
        closed_episode_ids: set[str] = set()
        current_episode: str | None = None
        previous: TransitionRecord | None = None

        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except (json.JSONDecodeError, TypeError) as exc:
                self._add(
                    report,
                    "error",
                    "invalid_json",
                    line_number,
                    str(exc),
                )
                continue
            if not isinstance(payload, dict):
                self._add(
                    report,
                    "error",
                    "invalid_record",
                    line_number,
                    "每行必須是 JSON object。",
                )
                continue
            report.records += 1
            self._check_raw(payload, line_number, report)
            try:
                record = TransitionRecord.from_dict(payload)
            except (TypeError, ValueError) as exc:
                self._add(
                    report,
                    "error",
                    "schema_error",
                    line_number,
                    str(exc),
                )
                continue

            episode_ids.add(record.episode_id)
            action_counts[record.action] += 1
            signatures[
                json.dumps(
                    [
                        record.observation,
                        record.action,
                        record.next_observation,
                    ],
                    separators=(",", ":"),
                )
            ] += 1

            component_total = float(sum(record.reward_components.values()))
            if (
                math.isfinite(record.reward)
                and math.isfinite(component_total)
                and not math.isclose(
                    record.reward,
                    component_total,
                    rel_tol=1e-6,
                    abs_tol=1e-6,
                )
            ):
                self._add(
                    report,
                    "error",
                    "reward_component_mismatch",
                    line_number,
                    f"reward={record.reward}，components={component_total}。",
                )

            if current_episode != record.episode_id:
                if current_episode is not None:
                    closed_episode_ids.add(current_episode)
                if record.episode_id in closed_episode_ids:
                    self._add(
                        report,
                        "error",
                        "episode_reappeared",
                        line_number,
                        f"episode {record.episode_id!r} 跨界後重新出現。",
                    )
                current_episode = record.episode_id
                previous = None
                if record.step != 0:
                    self._add(
                        report,
                        "error",
                        "episode_start_step",
                        line_number,
                        f"新 episode 必須從 step 0 開始，實際為 {record.step}。",
                    )

            timestamps = (
                record.observation_timestamp,
                record.action_command_timestamp,
                record.action_effective_timestamp,
                record.next_observation_timestamp,
            )
            if any(
                later < earlier
                for earlier, later in zip(timestamps, timestamps[1:])
            ):
                self._add(
                    report,
                    "error",
                    "timestamp_order",
                    line_number,
                    "單筆 transition 的時間戳順序錯誤。",
                )

            if previous is not None:
                if previous.terminated or previous.truncated:
                    self._add(
                        report,
                        "error",
                        "transition_after_terminal",
                        line_number,
                        "terminal/truncated 後仍有同 episode transition。",
                    )
                if record.step != previous.step + 1:
                    self._add(
                        report,
                        "error",
                        "step_discontinuity",
                        line_number,
                        f"step 應為 {previous.step + 1}，實際為 {record.step}。",
                    )
                if (
                    record.observation_timestamp
                    < previous.next_observation_timestamp
                ):
                    self._add(
                        report,
                        "error",
                        "timestamp_regression",
                        line_number,
                        "episode 內 observation timestamp 倒退。",
                    )
                if (
                    len(record.observation) == self.expected_observation_dim
                    and len(previous.next_observation)
                    == self.expected_observation_dim
                ):
                    jump = float(
                        np.max(
                            np.abs(
                                np.asarray(record.observation)
                                - np.asarray(previous.next_observation)
                            )
                        )
                    )
                    if jump > self.observation_jump_threshold:
                        self._add(
                            report,
                            "warning",
                            "observation_jump",
                            line_number,
                            f"相鄰 transition 觀測跳變 {jump:.3f}。",
                        )
            previous = record

        report.episodes = len(episode_ids)
        report.action_counts = dict(sorted(action_counts.items()))
        if report.records >= self.minimum_distribution_records:
            dominant = max(action_counts.values(), default=0)
            if dominant / report.records >= self.action_collapse_ratio:
                self._add(
                    report,
                    "warning",
                    "action_collapse",
                    None,
                    "單一動作比例超過門檻，資料可能動作塌縮。",
                )
            duplicate_records = sum(
                count for count in signatures.values() if count > 1
            )
            if duplicate_records / report.records >= self.duplicate_ratio:
                self._add(
                    report,
                    "warning",
                    "duplicate_transitions",
                    None,
                    "高度重複 transition 比例超過門檻。",
                )
        return report
