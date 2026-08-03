"""Causal, deployable inputs for the bounded P4.1 model ablation.

The real-game controller sidecar is a post-decision snapshot, so feeding the
same-step values to a Student would leak its action label.  This module uses
only observations available at the decision and state reconstructed from
actions strictly before that decision.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Literal, Sequence

import numpy as np
import torch
from torch import nn

from ..data.schema import OBSERVATION_DIM, OBSERVATION_SCHEMA_VERSION
from ..data.teacher_dataset import TEACHER_SCHEMA_VERSION


P41_SCHEMA_VERSION = "p41-causal-sequence-v1"
P41_VARIANTS = ("S0", "S1", "S2", "S3")
Variant = Literal["S0", "S1", "S2", "S3"]

TEMPORAL_FRAMES = 4
RAW_FEATURE_DIM = 64
ACTION_HISTORY_DIM = 3
TEMPORAL_FRAME_DIM = RAW_FEATURE_DIM + ACTION_HISTORY_DIM

# Latest frame core features (16) plus the nearest ordered platform slot (6).
# Embedded action features are intentionally excluded; the causal state below
# is the single explicit action-memory contract for S1/S3.
COMPACT_OBSERVATION_DIM = 22
CAUSAL_ACTION_DIM = 9
S1_INPUT_DIM = OBSERVATION_DIM + CAUSAL_ACTION_DIM
S3_INPUT_DIM = COMPACT_OBSERVATION_DIM + CAUSAL_ACTION_DIM

SEQUENCE_LENGTH = 24
BURN_IN = 8
GRU_HIDDEN_SIZE = 128
MAX_UPDATES = 300
CANDIDATE_UPDATES = (100, 200, 300)
MLP_BATCH_SIZE = 112
SEQUENCE_BATCH_CHUNKS = 8
INITIALIZATION_SEEDS = (0, 1, 2)
SELECTION_SEEDS = tuple(range(4000, 4020))
FINAL_SEEDS = tuple(range(4100, 4140))
MAX_EPISODE_STEPS = 600


def _validate_variant(variant: str) -> Variant:
    if variant not in P41_VARIANTS:
        raise ValueError(f"未知 P4.1 variant：{variant!r}")
    return variant  # type: ignore[return-value]


class CausalActionState:
    """Small state that deployment can rebuild from its own past actions."""

    def __init__(self, *, streak_cap: int = 8, history_length: int = 8) -> None:
        if streak_cap <= 0 or history_length <= 1:
            raise ValueError("streak cap 必須大於 0，history length 必須大於 1。")
        self.streak_cap = int(streak_cap)
        self.history_length = int(history_length)
        self._recent_actions: deque[int] = deque(maxlen=self.history_length)
        self.reset()

    def reset(self) -> None:
        self.previous_action: int | None = None
        self.last_nonrelease_action: int | None = None
        self.same_action_streak = 0
        self.release_streak = 0
        self._recent_actions.clear()

    def snapshot(self) -> np.ndarray:
        values = np.zeros(CAUSAL_ACTION_DIM, dtype=np.float32)
        if self.previous_action is not None:
            values[self.previous_action] = 1.0
            values[3] = 1.0
        if self.last_nonrelease_action == 1:
            values[4] = 1.0
        elif self.last_nonrelease_action == 2:
            values[5] = 1.0
        values[6] = min(self.same_action_streak, self.streak_cap) / self.streak_cap
        values[7] = min(self.release_streak, self.streak_cap) / self.streak_cap
        directions = [action for action in self._recent_actions if action in {1, 2}]
        switches = sum(left != right for left, right in zip(directions, directions[1:]))
        values[8] = switches / max(1, self.history_length - 1)
        return values

    def update(self, action: int) -> None:
        action = int(action)
        if action not in {0, 1, 2}:
            raise ValueError(f"無效 action：{action}")
        if action == self.previous_action:
            self.same_action_streak += 1
        else:
            self.same_action_streak = 1
        if action == 0:
            self.release_streak += 1
        else:
            self.release_streak = 0
            self.last_nonrelease_action = action
        self.previous_action = action
        self._recent_actions.append(action)


def compact_observation(observation: np.ndarray | Sequence[float]) -> np.ndarray:
    values = np.asarray(observation, dtype=np.float32)
    if values.shape != (OBSERVATION_DIM,):
        raise ValueError(
            f"observation shape 必須為 {(OBSERVATION_DIM,)}，實際為 {values.shape}。"
        )
    if not np.isfinite(values).all():
        raise ValueError("observation 含 NaN 或 infinity。")
    latest = values.reshape(TEMPORAL_FRAMES, TEMPORAL_FRAME_DIM)[-1]
    return latest[:COMPACT_OBSERVATION_DIM].copy()


@dataclass(frozen=True)
class P41Row:
    episode_id: str
    split: str
    seed: int
    step: int
    observation: np.ndarray
    action: int
    soft_target: np.ndarray
    teacher_reason: str


@dataclass(frozen=True)
class P41Episode:
    episode_id: str
    split: str
    seed: int
    rows: tuple[P41Row, ...]


@dataclass(frozen=True)
class P41Dataset:
    episodes: tuple[P41Episode, ...]
    environment_versions: tuple[str, ...]
    teacher_policy_versions: tuple[str, ...]

    def episodes_for_split(self, split: str) -> tuple[P41Episode, ...]:
        return tuple(episode for episode in self.episodes if episode.split == split)

    @property
    def record_count(self) -> int:
        return sum(len(episode.rows) for episode in self.episodes)


@dataclass(frozen=True)
class SequenceChunk:
    episode_id: str
    split: str
    seed: int
    features: np.ndarray
    actions: np.ndarray
    soft_targets: np.ndarray
    valid_mask: np.ndarray
    loss_mask: np.ndarray
    steps: np.ndarray


def _require_number_array(
    value: object,
    *,
    shape: tuple[int, ...],
    label: str,
) -> np.ndarray:
    result = np.asarray(value, dtype=np.float32)
    if result.shape != shape:
        raise ValueError(f"{label} shape 必須為 {shape}，實際為 {result.shape}。")
    if not np.isfinite(result).all():
        raise ValueError(f"{label} 含 NaN 或 infinity。")
    return result


def load_p41_teacher_dataset(path: str | Path) -> P41Dataset:
    """Load a verified Teacher dataset and reject timing/split leakage."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    episode_payloads: dict[str, list[dict[str, object]]] = {}
    episode_order: list[str] = []
    closed_episodes: set[str] = set()
    active_episode: str | None = None
    sequence_splits: dict[str, str] = {}
    environment_versions: set[str] = set()
    teacher_versions: set[str] = set()

    with source.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{source}:{line_number} JSON 無效。") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{source}:{line_number} 必須是 JSON object。")
            episode_id = str(payload.get("episode_id", ""))
            if not episode_id:
                raise ValueError(f"{source}:{line_number} 缺少 episode_id。")
            if active_episode != episode_id:
                if active_episode is not None:
                    closed_episodes.add(active_episode)
                if episode_id in closed_episodes:
                    raise ValueError(f"episode {episode_id} 非連續寫入。")
                active_episode = episode_id
            if episode_id not in episode_payloads:
                episode_payloads[episode_id] = []
                episode_order.append(episode_id)
            episode_payloads[episode_id].append(payload)

            split = str(payload.get("split", ""))
            if split not in {"train", "validation", "test"}:
                raise ValueError(f"{source}:{line_number} split 無效。")
            sequence_id = str(payload.get("platform_sequence_id", ""))
            prior_split = sequence_splits.setdefault(sequence_id, split)
            if not sequence_id or prior_split != split:
                raise ValueError(f"{source}:{line_number} platform sequence split 洩漏。")
            environment_versions.add(str(payload.get("environment_version", "")))
            teacher_versions.add(str(payload.get("teacher_policy_version", "")))

    if not episode_payloads:
        raise ValueError("P4.1 teacher dataset 不可為空。")

    episodes: list[P41Episode] = []
    split_seeds: dict[str, set[int]] = {name: set() for name in ("train", "validation", "test")}
    for episode_id in episode_order:
        payloads = episode_payloads[episode_id]
        first = payloads[0]
        split = str(first["split"])
        seed = int(first["seed"])
        rows: list[P41Row] = []
        previous_terminal = False
        for expected_step, payload in enumerate(payloads):
            if payload.get("schema_version") != TEACHER_SCHEMA_VERSION:
                raise ValueError(f"{episode_id}: teacher schema version 不符。")
            if payload.get("observation_schema_version") != OBSERVATION_SCHEMA_VERSION:
                raise ValueError(f"{episode_id}: observation schema version 不符。")
            if payload.get("teacher_type") != "teacher_observable":
                raise ValueError(f"{episode_id}: privileged teacher 不可用於 P4.1。")
            if payload.get("verified") is not True:
                raise ValueError(f"{episode_id}: 未 verified 的 Teacher row。")
            if str(payload.get("split")) != split or int(payload.get("seed", -1)) != seed:
                raise ValueError(f"{episode_id}: episode split 或 seed 不一致。")
            step = int(payload.get("step", -1))
            if step != expected_step:
                raise ValueError(f"{episode_id}: step 不連續，預期 {expected_step}，實際 {step}。")
            if previous_terminal:
                raise ValueError(f"{episode_id}: terminal 後仍有資料。")
            action = int(payload.get("action", -1))
            if action not in {0, 1, 2}:
                raise ValueError(f"{episode_id}:{step} action 無效。")
            soft_target = _require_number_array(
                payload.get("soft_target"), shape=(3,), label=f"{episode_id}:{step} soft_target"
            )
            if not np.isclose(float(soft_target.sum()), 1.0, atol=1e-6):
                raise ValueError(f"{episode_id}:{step} soft_target 總和不為 1。")
            rows.append(
                P41Row(
                    episode_id=episode_id,
                    split=split,
                    seed=seed,
                    step=step,
                    observation=_require_number_array(
                        payload.get("observation"),
                        shape=(OBSERVATION_DIM,),
                        label=f"{episode_id}:{step} observation",
                    ),
                    action=action,
                    soft_target=soft_target,
                    teacher_reason=str(payload.get("teacher_reason", "unknown")),
                )
            )
            previous_terminal = bool(payload.get("terminated")) or bool(payload.get("truncated"))
        split_seeds[split].add(seed)
        episodes.append(P41Episode(episode_id, split, seed, tuple(rows)))

    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        overlap = sorted(split_seeds[left] & split_seeds[right])
        if overlap:
            raise ValueError(f"{left}/{right} seed split 洩漏：{overlap}")
    if any(not split_seeds[name] for name in split_seeds):
        raise ValueError("train/validation/test 三個 split 都必須存在。")
    if "" in environment_versions or "" in teacher_versions:
        raise ValueError("environment/teacher policy version 不可為空。")
    return P41Dataset(
        episodes=tuple(episodes),
        environment_versions=tuple(sorted(environment_versions)),
        teacher_policy_versions=tuple(sorted(teacher_versions)),
    )


def _episode_features(episode: P41Episode, variant: Variant) -> np.ndarray:
    state = CausalActionState()
    features: list[np.ndarray] = []
    for row in episode.rows:
        if variant in {"S0", "S2"}:
            current = row.observation
        elif variant == "S1":
            current = np.concatenate((row.observation, state.snapshot()))
        else:
            current = np.concatenate((compact_observation(row.observation), state.snapshot()))
        features.append(np.asarray(current, dtype=np.float32))
        state.update(row.action)
    return np.vstack(features)


def build_mlp_examples(
    episodes: Iterable[P41Episode], *, variant: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    selected = _validate_variant(variant)
    if selected not in {"S0", "S1"}:
        raise ValueError("MLP examples 只支援 S0/S1。")
    episode_list = tuple(episodes)
    if not episode_list:
        raise ValueError("episodes 不可為空。")
    features = np.vstack([_episode_features(episode, selected) for episode in episode_list])
    labels = np.asarray(
        [row.action for episode in episode_list for row in episode.rows], dtype=np.int64
    )
    targets = np.vstack([row.soft_target for episode in episode_list for row in episode.rows])
    return features, labels, targets.astype(np.float32, copy=False)


def build_sequence_chunks(
    episodes: Iterable[P41Episode],
    *,
    variant: str,
    sequence_length: int = SEQUENCE_LENGTH,
    burn_in: int = BURN_IN,
) -> tuple[SequenceChunk, ...]:
    selected = _validate_variant(variant)
    if selected not in {"S2", "S3"}:
        raise ValueError("sequence chunks 只支援 S2/S3。")
    if sequence_length <= 0 or burn_in < 0 or burn_in >= sequence_length:
        raise ValueError("sequence length 必須大於 burn-in，且 burn-in 不可為負。")
    target_capacity = sequence_length - burn_in
    chunks: list[SequenceChunk] = []
    for episode in episodes:
        episode_features = _episode_features(episode, selected)
        feature_dim = episode_features.shape[1]
        row_count = len(episode.rows)
        for target_start in range(0, row_count, target_capacity):
            target_end = min(row_count, target_start + target_capacity)
            context_start = max(0, target_start - burn_in)
            selected_rows = episode.rows[context_start:target_end]
            count = len(selected_rows)
            features = np.zeros((sequence_length, feature_dim), dtype=np.float32)
            actions = np.zeros(sequence_length, dtype=np.int64)
            soft_targets = np.zeros((sequence_length, 3), dtype=np.float32)
            valid_mask = np.zeros(sequence_length, dtype=bool)
            loss_mask = np.zeros(sequence_length, dtype=bool)
            steps = np.full(sequence_length, -1, dtype=np.int64)
            features[:count] = episode_features[context_start:target_end]
            actions[:count] = [row.action for row in selected_rows]
            soft_targets[:count] = [row.soft_target for row in selected_rows]
            valid_mask[:count] = True
            steps[:count] = [row.step for row in selected_rows]
            loss_offset = target_start - context_start
            loss_mask[loss_offset:count] = True
            chunks.append(
                SequenceChunk(
                    episode_id=episode.episode_id,
                    split=episode.split,
                    seed=episode.seed,
                    features=features,
                    actions=actions,
                    soft_targets=soft_targets,
                    valid_mask=valid_mask,
                    loss_mask=loss_mask,
                    steps=steps,
                )
            )
    if not chunks:
        raise ValueError("episodes 不可為空。")
    return tuple(chunks)


class SequenceBehaviorCloningGRU(nn.Module):
    def __init__(self, input_dim: int, hidden_size: int = GRU_HIDDEN_SIZE) -> None:
        super().__init__()
        if input_dim <= 0 or hidden_size <= 0:
            raise ValueError("GRU input/hidden dimensions 必須大於 0。")
        self.input_dim = int(input_dim)
        self.hidden_size = int(hidden_size)
        self.gru = nn.GRU(self.input_dim, self.hidden_size, batch_first=True)
        self.action_head = nn.Linear(self.hidden_size, 3)

    def forward(
        self,
        features: torch.Tensor,
        hidden: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if features.ndim != 3 or features.shape[-1] != self.input_dim:
            raise ValueError(
                f"GRU features shape 應為 (batch,time,{self.input_dim})，"
                f"實際為 {tuple(features.shape)}。"
            )
        output, next_hidden = self.gru(features, hidden)
        return self.action_head(output), next_hidden


class FeedForwardAblationPolicy:
    def __init__(self, model: nn.Module, *, variant: str) -> None:
        selected = _validate_variant(variant)
        if selected not in {"S0", "S1"}:
            raise ValueError("FeedForward policy 只支援 S0/S1。")
        self.model = model.eval()
        self.variant = selected
        self.causal_state = CausalActionState()

    def reset(self) -> None:
        self.causal_state.reset()

    def predict(self, observation: np.ndarray, deterministic: bool = True):
        del deterministic
        values = np.asarray(observation, dtype=np.float32)
        if self.variant == "S1":
            values = np.concatenate((values, self.causal_state.snapshot()))
        parameter = next(self.model.parameters())
        tensor = torch.as_tensor(values, dtype=torch.float32, device=parameter.device).unsqueeze(0)
        with torch.no_grad():
            action = int(self.model(tensor).argmax(dim=1).item())
        self.causal_state.update(action)
        return action, None


class RecurrentAblationPolicy:
    def __init__(self, model: SequenceBehaviorCloningGRU, *, variant: str) -> None:
        selected = _validate_variant(variant)
        if selected not in {"S2", "S3"}:
            raise ValueError("Recurrent policy 只支援 S2/S3。")
        self.model = model.eval()
        self.variant = selected
        self.causal_state = CausalActionState()
        self.hidden_state: torch.Tensor | None = None

    def reset(self) -> None:
        self.hidden_state = None
        self.causal_state.reset()

    def predict(self, observation: np.ndarray, deterministic: bool = True):
        del deterministic
        values = np.asarray(observation, dtype=np.float32)
        if self.variant == "S3":
            values = np.concatenate((compact_observation(values), self.causal_state.snapshot()))
        parameter = next(self.model.parameters())
        tensor = torch.as_tensor(values, dtype=torch.float32, device=parameter.device).reshape(1, 1, -1)
        hidden = None if self.hidden_state is None else self.hidden_state.to(parameter.device)
        with torch.no_grad():
            logits, next_hidden = self.model(tensor, hidden)
            action = int(logits[:, -1].argmax(dim=1).item())
        self.hidden_state = next_hidden.detach()
        self.causal_state.update(action)
        return action, self.hidden_state


def build_experiment_manifest(path: str | Path, dataset: P41Dataset) -> dict[str, object]:
    source = Path(path)
    digest = sha256(source.read_bytes()).hexdigest()
    try:
        logical_path = source.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        logical_path = source.name
    split_records: Counter[str] = Counter()
    split_episodes: Counter[str] = Counter()
    split_seeds: dict[str, list[int]] = {}
    actions: Counter[int] = Counter()
    for split in ("train", "validation", "test"):
        episodes = dataset.episodes_for_split(split)
        split_episodes[split] = len(episodes)
        split_records[split] = sum(len(episode.rows) for episode in episodes)
        split_seeds[split] = sorted({episode.seed for episode in episodes})
        actions.update(row.action for episode in episodes for row in episode.rows)
    return {
        "schema_version": P41_SCHEMA_VERSION,
        "status": "FROZEN_LOCAL_PREFLIGHT",
        "dataset": {
            "path": logical_path,
            "sha256": digest,
            "records": dataset.record_count,
            "episodes": len(dataset.episodes),
            "records_by_split": dict(split_records),
            "episodes_by_split": dict(split_episodes),
            "seeds_by_split": split_seeds,
            "action_counts": {str(action): actions[action] for action in (0, 1, 2)},
            "environment_versions": list(dataset.environment_versions),
            "teacher_policy_versions": list(dataset.teacher_policy_versions),
        },
        "models": {
            "S0": {"type": "MLP", "input_dim": OBSERVATION_DIM},
            "S1": {"type": "MLP", "input_dim": S1_INPUT_DIM, "causal_state_dim": CAUSAL_ACTION_DIM},
            "S2": {"type": "GRU", "input_dim": OBSERVATION_DIM, "hidden_size": GRU_HIDDEN_SIZE},
            "S3": {"type": "GRU", "input_dim": S3_INPUT_DIM, "hidden_size": GRU_HIDDEN_SIZE},
        },
        "protocol": {
            "loss": "hard_cross_entropy",
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "mlp_batch_size": MLP_BATCH_SIZE,
            "sequence_batch_chunks": SEQUENCE_BATCH_CHUNKS,
            "train_updates_per_full_dataset_pass": 21,
            "train_labels_per_full_dataset_pass": 2327,
            "sequence_length": SEQUENCE_LENGTH,
            "burn_in": BURN_IN,
            "max_updates": MAX_UPDATES,
            "candidate_updates": list(CANDIDATE_UPDATES),
            "initialization_seeds": list(INITIALIZATION_SEEDS),
            "selection_environment_seeds": list(SELECTION_SEEDS),
            "final_environment_seeds": list(FINAL_SEEDS),
            "max_episode_steps": MAX_EPISODE_STEPS,
            "physics_frequency_hz": 60,
            "policy_frequency_hz": 10,
            "checkpoint_selection": "closed_loop_selection_seeds_only",
            "final_evaluation": "single_use_after_architecture_and_checkpoint_freeze",
            "causal_timing": "state from actions < t; reset at episode boundary",
        },
        "gate_priority": [
            "safety_events",
            "health_death",
            "bottom_death",
            "deepest_floor_q25",
            "deepest_floor_cvar25",
            "reach_floor_10",
            "oscillation",
            "median",
            "mean",
        ],
        "forbidden_inputs": [
            "same_step_post_decision_controller_sidecar",
            "future_observation",
            "simulator_privileged_state",
            "raw_platform_or_track_id",
        ],
    }


__all__ = [
    "BURN_IN",
    "CAUSAL_ACTION_DIM",
    "CANDIDATE_UPDATES",
    "COMPACT_OBSERVATION_DIM",
    "CausalActionState",
    "FINAL_SEEDS",
    "FeedForwardAblationPolicy",
    "GRU_HIDDEN_SIZE",
    "INITIALIZATION_SEEDS",
    "MAX_EPISODE_STEPS",
    "MAX_UPDATES",
    "MLP_BATCH_SIZE",
    "P41Dataset",
    "P41Episode",
    "P41Row",
    "P41_SCHEMA_VERSION",
    "P41_VARIANTS",
    "RecurrentAblationPolicy",
    "S1_INPUT_DIM",
    "S3_INPUT_DIM",
    "SELECTION_SEEDS",
    "SEQUENCE_BATCH_CHUNKS",
    "SEQUENCE_LENGTH",
    "SequenceBehaviorCloningGRU",
    "SequenceChunk",
    "build_experiment_manifest",
    "build_mlp_examples",
    "build_sequence_chunks",
    "compact_observation",
    "load_p41_teacher_dataset",
]
