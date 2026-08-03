from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from stair_agent.learnability import learned_selector
from stair_agent.training.p41_sequence import (
    CAUSAL_ACTION_DIM,
    COMPACT_OBSERVATION_DIM,
    P41Dataset,
    P41Episode,
    P41Row,
    CausalActionState,
    FeedForwardAblationPolicy,
    RecurrentAblationPolicy,
    SequenceBehaviorCloningGRU,
    build_experiment_manifest,
    build_mlp_examples,
    build_sequence_chunks,
    compact_observation,
    load_p41_teacher_dataset,
)
from stair_agent.training.p41_ablation import (
    compare_to_s0_gate,
    load_p41_checkpoint,
    make_model,
    make_policy,
    save_p41_checkpoint,
    train_variant,
)


def _observation(value: float) -> np.ndarray:
    observation = np.zeros(268, dtype=np.float32)
    observation[-67:] = value
    return observation


def _episode(
    episode_id: str,
    *,
    split: str = "train",
    seed: int = 1,
    length: int = 10,
) -> P41Episode:
    rows = tuple(
        P41Row(
            episode_id=episode_id,
            split=split,
            seed=seed,
            step=step,
            observation=_observation(float(step)),
            action=step % 3,
            soft_target=np.eye(3, dtype=np.float32)[step % 3],
            teacher_reason="synthetic",
        )
        for step in range(length)
    )
    return P41Episode(episode_id=episode_id, split=split, seed=seed, rows=rows)


def _teacher_row(
    *,
    episode_id: str,
    seed: int,
    split: str,
    step: int,
    action: int,
    terminated: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": "ns-shaft-teacher-v1",
        "episode_id": episode_id,
        "seed": seed,
        "split": split,
        "platform_sequence_id": f"sequence-{seed}",
        "step": step,
        "observation": _observation(float(step)).tolist(),
        "action": action,
        "soft_target": np.eye(3, dtype=np.float32)[action].tolist(),
        "teacher_confidence": 1.0,
        "candidate_action_values": [0.0, 0.0, 0.0],
        "teacher_type": "teacher_observable",
        "verified": True,
        "target_platform_id": None,
        "target_platform_kind": "normal",
        "next_observation": _observation(float(step + 1)).tolist(),
        "reward": 0.0,
        "events": [],
        "terminated": terminated,
        "truncated": False,
        "environment_version": "test-sim-v1",
        "observation_schema_version": "stair-observation-v3-268",
        "failure_reason": None,
        "visible_platform_kinds": ["normal"],
        "health_segments": 12,
        "teacher_policy_version": "teacher-test-v1",
        "teacher_reason": "synthetic",
    }


def test_causal_action_state_contains_only_prior_actions_and_resets() -> None:
    state = CausalActionState()

    initial = state.snapshot()
    state.update(2)
    after_right = state.snapshot()
    state.update(0)
    after_release = state.snapshot()

    assert initial.shape == (CAUSAL_ACTION_DIM,)
    assert np.all(initial == 0.0)
    assert after_right[:3].tolist() == [0.0, 0.0, 1.0]
    assert after_right[3] == 1.0
    assert after_right[5] == 1.0
    assert after_release[:3].tolist() == [1.0, 0.0, 0.0]
    assert after_release[7] > 0.0

    state.reset()
    assert np.all(state.snapshot() == 0.0)


def test_compact_observation_uses_latest_frame_without_embedded_action() -> None:
    observation = np.arange(268, dtype=np.float32)

    compact = compact_observation(observation)

    assert compact.shape == (COMPACT_OBSERVATION_DIM,)
    assert compact.tolist() == observation[-67 : -67 + 22].tolist()


def test_mlp_s1_features_are_shifted_before_current_label() -> None:
    episode = _episode("episode-a", length=3)

    features, labels, _targets = build_mlp_examples((episode,), variant="S1")

    assert np.all(features[0, 268:] == 0.0)
    expected = CausalActionState()
    expected.update(episode.rows[0].action)
    assert np.allclose(features[1, 268:], expected.snapshot())
    assert labels.tolist() == [0, 1, 2]


def test_sequence_chunks_do_not_cross_episodes_and_train_each_row_once() -> None:
    episodes = (
        _episode("episode-a", seed=1, length=14),
        _episode("episode-b", seed=2, length=7),
    )

    chunks = build_sequence_chunks(
        episodes,
        variant="S3",
        sequence_length=8,
        burn_in=2,
    )

    assert chunks
    assert all(chunk.features.shape[1] == COMPACT_OBSERVATION_DIM + CAUSAL_ACTION_DIM for chunk in chunks)
    for episode in episodes:
        trained_steps = [
            int(step)
            for chunk in chunks
            if chunk.episode_id == episode.episode_id
            for step, selected in zip(chunk.steps, chunk.loss_mask)
            if selected
        ]
        assert trained_steps == list(range(len(episode.rows)))
    assert all(
        np.all(chunk.steps[~chunk.valid_mask] == -1)
        for chunk in chunks
    )


def test_teacher_loader_rejects_episode_split_leakage(tmp_path) -> None:
    path = tmp_path / "teacher.jsonl"
    rows = [
        _teacher_row(
            episode_id="episode-a",
            seed=1,
            split="train",
            step=0,
            action=0,
        ),
        _teacher_row(
            episode_id="episode-a",
            seed=1,
            split="test",
            step=1,
            action=1,
        ),
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    with pytest.raises(ValueError, match="split"):
        load_p41_teacher_dataset(path)


def test_teacher_loader_and_manifest_are_deterministic(tmp_path) -> None:
    path = tmp_path / "teacher.jsonl"
    rows = []
    for split, seed in (("train", 1), ("validation", 2), ("test", 3)):
        rows.extend(
            [
                _teacher_row(
                    episode_id=f"episode-{seed}",
                    seed=seed,
                    split=split,
                    step=0,
                    action=seed % 3,
                ),
                _teacher_row(
                    episode_id=f"episode-{seed}",
                    seed=seed,
                    split=split,
                    step=1,
                    action=(seed + 1) % 3,
                    terminated=True,
                ),
            ]
        )
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    dataset = load_p41_teacher_dataset(path)
    first = build_experiment_manifest(path, dataset)
    second = build_experiment_manifest(path, dataset)

    assert isinstance(dataset, P41Dataset)
    assert len(dataset.episodes) == 3
    assert first == second
    assert first["dataset"]["records"] == 6
    assert first["protocol"]["sequence_length"] == 24
    assert first["protocol"]["burn_in"] == 8
    assert first["protocol"]["mlp_batch_size"] == 112
    assert first["protocol"]["sequence_batch_chunks"] == 8
    assert set(first["models"]) == {"S0", "S1", "S2", "S3"}


def test_gru_policy_reset_clears_hidden_and_causal_state() -> None:
    torch.manual_seed(7)
    model = SequenceBehaviorCloningGRU(input_dim=COMPACT_OBSERVATION_DIM + CAUSAL_ACTION_DIM)
    policy = RecurrentAblationPolicy(model, variant="S3")
    observation = _observation(0.25)

    first_action, _ = policy.predict(observation)
    first_hidden = policy.hidden_state.clone()
    policy.predict(_observation(0.5))
    policy.reset()

    assert policy.hidden_state is None
    assert np.all(policy.causal_state.snapshot() == 0.0)
    repeated_action, _ = policy.predict(observation)
    assert repeated_action == first_action
    assert torch.allclose(policy.hidden_state, first_hidden)


def test_feed_forward_policy_and_learned_selector_propagate_reset() -> None:
    model = torch.nn.Sequential(torch.nn.Linear(268 + CAUSAL_ACTION_DIM, 3))
    policy = FeedForwardAblationPolicy(model, variant="S1")
    selector = learned_selector(policy)

    selector(_observation(0.0), None, np.random.default_rng(1))
    assert np.any(policy.causal_state.snapshot() != 0.0)
    selector.reset()
    assert np.all(policy.causal_state.snapshot() == 0.0)


@pytest.mark.parametrize("variant", ["S0", "S1", "S2", "S3"])
def test_all_variants_complete_bounded_training_and_policy_smoke(variant) -> None:
    dataset = P41Dataset(
        episodes=(
            _episode("train-a", split="train", seed=1, length=8),
            _episode("validation-a", split="validation", seed=2, length=5),
            _episode("test-a", split="test", seed=3, length=5),
        ),
        environment_versions=("test-sim-v1",),
        teacher_policy_versions=("teacher-test-v1",),
    )

    result = train_variant(
        dataset,
        variant=variant,
        initialization_seed=7,
        max_updates=2,
        candidate_updates=(1, 2),
        device="cpu",
    )

    assert result.variant == variant
    assert set(result.checkpoints) == {1, 2}
    assert len(result.update_label_counts) == 2
    assert all(count > 0 for count in result.update_label_counts)
    assert all(np.isfinite(item["validation_loss"]) for item in result.history)
    model = make_model(variant)
    model.load_state_dict(result.checkpoints[2])
    policy = make_policy(model, variant)
    action, _state = policy.predict(_observation(0.0))
    assert action in {0, 1, 2}


def test_p41_checkpoint_round_trip_rejects_variant_mismatch(tmp_path) -> None:
    model = make_model("S3")
    path = tmp_path / "s3.pt"
    save_p41_checkpoint(
        path,
        model=model,
        variant="S3",
        initialization_seed=2,
        update=10,
        dataset_sha256="a" * 64,
    )

    restored, metadata = load_p41_checkpoint(path, expected_variant="S3")

    assert isinstance(restored, SequenceBehaviorCloningGRU)
    assert metadata["update"] == 10
    with pytest.raises(ValueError, match="variant"):
        load_p41_checkpoint(path, expected_variant="S2")


def _rollout_summary(
    *,
    q25=5.0,
    cvar=4.0,
    reach=0.5,
    bottom=0.3,
    oscillation=2.0,
    health=0.0,
    collapsed=False,
) -> dict[str, object]:
    return {
        "deepest_floor_quantile_25": q25,
        "deepest_floor_cvar25": cvar,
        "reach_rate_floor_10": reach,
        "bottom_death_rate": bottom,
        "direction_switches_per_100_steps": oscillation,
        "health_death_rate": health,
        "collapsed": collapsed,
    }


def test_p41_gate_requires_tail_reach_bottom_and_oscillation_improvement() -> None:
    s0 = [_rollout_summary() for _ in range(3)]
    improved = [
        _rollout_summary(q25=6.5, cvar=5.0, reach=0.6, bottom=0.25, oscillation=1.8)
        for _ in range(3)
    ]
    mean_only = [
        {
            **_rollout_summary(),
            "mean_deepest_floor": 100.0,
        }
        for _ in range(3)
    ]

    assert compare_to_s0_gate(improved, s0)["passed"]
    failed = compare_to_s0_gate(mean_only, s0)
    assert not failed["passed"]
    assert not failed["checks"]["material_q25_improvement"]
