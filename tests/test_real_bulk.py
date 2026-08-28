from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import numpy as np
import pytest

from stair_agent.actions import Action
from stair_agent.config import AppConfig
import stair_agent.real.bulk as bulk_module
from stair_agent.real.bulk import (
    AuthorizationGatedController,
    BulkEvaluationConfig,
    EpisodeVideoRetention,
    active_safety_failure,
    build_bulk_summary,
    create_verified_session_zip,
    has_verified_reset_calibration,
    run_live_episode,
    run_passive_preflight,
    render_bulk_overlay,
    request_control_authorization,
    select_best_episode,
    write_episode_jsonl,
)


class FakeController:
    def __init__(self) -> None:
        self.actions: list[Action] = []
        self.release_count = 0
        self.emergency_stopped = False
        self.active = True

    def apply(self, action: Action) -> None:
        self.actions.append(action)

    def release_all(self) -> None:
        self.release_count += 1

    def emergency_stop(self) -> None:
        self.emergency_stopped = True
        self.release_all()

    def is_target_active(self) -> bool:
        return self.active


class FailingController(FakeController):
    def apply(self, action: Action) -> None:
        del action
        raise RuntimeError("backend failed")


def _observation(phase: str = "playing", floor: int = 1):
    return SimpleNamespace(
        phase=phase,
        player={"center_x": 10} if phase == "playing" else None,
        platforms=[{"track_id": 1}] if phase == "playing" else [],
        floor={"value": floor},
        health={"segments": 10},
        events=[],
    )


class FakeAdapter:
    action_duration_ms = 0

    def __init__(self, observations) -> None:
        self.observations = iter(observations)
        self.emergency_stopped = False
        self.release_count = 0
        self.controller = SimpleNamespace(actions_sent=0)

    def observe(self):
        return next(self.observations)

    def latest_frame(self):
        return None

    def is_foreground(self) -> bool:
        return True

    def release_all(self) -> None:
        self.release_count += 1


class FakeEnv:
    def __init__(self, observations) -> None:
        self.adapter = FakeAdapter(observations)
        self.last_observation = None
        self.encoder = SimpleNamespace(encode=lambda _observation: np.zeros(67, dtype=np.float32))
        self.temporal_stack = SimpleNamespace(
            append=lambda _features, _action: np.zeros(268, dtype=np.float32)
        )

    def initialize_from_observation(self, observation):
        self.last_observation = observation
        return np.zeros(268, dtype=np.float32), {}


class FakeLoadedModel:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def predict(self, _observation) -> int:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return int(Action.LEFT)


@pytest.mark.parametrize("episodes", [1, 20, 100])
def test_bulk_episode_bounds_accept_real20_and_real100(episodes: int) -> None:
    assert BulkEvaluationConfig(episodes=episodes).episodes == episodes


@pytest.mark.parametrize("episodes", [0, 101, -1])
def test_bulk_episode_bounds_fail_closed(episodes: int) -> None:
    with pytest.raises(ValueError, match="EPISODES_OUT_OF_RANGE"):
        BulkEvaluationConfig(episodes=episodes)


def test_video_modes_are_historically_confirmed() -> None:
    for mode in ("none", "best", "all"):
        assert BulkEvaluationConfig(video_mode=mode).video_mode == mode
    with pytest.raises(ValueError, match="VIDEO_MODE_INVALID"):
        BulkEvaluationConfig(video_mode="latest")


def test_verified_reset_requires_every_focus_coordinate() -> None:
    names = (
        "reference_width",
        "reference_height",
        "menu_start_button_left",
        "menu_start_button_top",
        "menu_start_button_width",
        "menu_start_button_height",
        "menu_two_player_button_left",
        "menu_two_player_button_top",
        "menu_two_player_button_width",
        "menu_two_player_button_height",
        "menu_exit_button_left",
        "menu_exit_button_top",
        "menu_exit_button_width",
        "menu_exit_button_height",
    )
    detection = SimpleNamespace(**{name: 1 for name in names})
    config = SimpleNamespace(detection=detection)
    assert has_verified_reset_calibration(config) is True
    detection.menu_exit_button_left = None
    assert has_verified_reset_calibration(config) is False


def test_example_config_uses_safe_manual_reset_fallback() -> None:
    root = Path(__file__).resolve().parents[1]
    config = AppConfig.load(root / "config.example.yaml")
    assert has_verified_reset_calibration(config) is False


def test_control_cannot_bypass_authorization_and_releases_on_exception() -> None:
    raw = FakeController()
    gate = AuthorizationGatedController(raw, model_id="v3", episode_limit=1)
    with pytest.raises(RuntimeError, match="REAL_CONTROL_NOT_AUTHORIZED"):
        gate.apply(Action.LEFT)
    assert gate.authorize("wrong") is False
    assert gate.authorize("AUTHORIZE_V3_REAL_CONTROL") is True
    gate.arm_episode(1)
    gate.apply(Action.LEFT)
    assert raw.actions == [Action.LEFT]
    gate.emergency_stop()
    assert gate.emergency_stopped is True
    assert raw.release_count >= 1
    with pytest.raises(RuntimeError, match="REAL_CONTROL_NOT_ARMED"):
        gate.apply(Action.RIGHT)


def test_controller_backend_exception_disarms_and_releases() -> None:
    raw = FailingController()
    gate = AuthorizationGatedController(raw, model_id="r4", episode_limit=1)
    assert gate.authorize("AUTHORIZE_R4_REAL_CONTROL")
    gate.arm_episode(1)
    with pytest.raises(RuntimeError, match="backend failed"):
        gate.apply(Action.RIGHT)
    assert raw.release_count == 1
    with pytest.raises(RuntimeError, match="REAL_CONTROL_NOT_ARMED"):
        gate.apply(Action.LEFT)


def test_control_authorization_prompt_displays_exact_model_phrase() -> None:
    raw = FakeController()
    gate = AuthorizationGatedController(raw, model_id="r4", episode_limit=20)
    output: list[str] = []
    prompts: list[str] = []

    request_control_authorization(
        gate,
        output_fn=output.append,
        input_fn=lambda prompt: prompts.append(prompt) or "AUTHORIZE_R4_REAL_CONTROL",
    )

    assert gate.session_authorized is True
    assert any("TYPE EXACTLY" in line for line in output)
    assert any("AUTHORIZE_R4_REAL_CONTROL" in line for line in output)
    assert prompts == ["Authorization [AUTHORIZE_R4_REAL_CONTROL]: "]
    assert output[-1] == "REAL_CONTROL_AUTHORIZATION=PASS"


def test_control_authorization_prompt_rejects_mismatch_and_releases() -> None:
    raw = FakeController()
    gate = AuthorizationGatedController(raw, model_id="v3", episode_limit=1)
    output: list[str] = []
    with pytest.raises(RuntimeError, match="REAL_CONTROL_AUTHORIZATION_REJECTED"):
        request_control_authorization(
            gate,
            output_fn=output.append,
            input_fn=lambda _prompt: "authorize_v3_real_control",
        )
    assert gate.session_authorized is False
    assert raw.release_count == 1
    assert output[-1].startswith("REAL_CONTROL_AUTHORIZATION=REJECTED")


def test_shadow_contract_sends_zero_actions() -> None:
    raw = FakeController()
    gate = AuthorizationGatedController(raw, model_id="r4", episode_limit=20)
    gate.release_all()
    assert gate.actions_sent == 0
    assert raw.actions == []


def test_passive_preflight_observes_without_inference_or_input() -> None:
    env = FakeEnv([_observation(), _observation(), _observation()])
    result = run_passive_preflight(env)
    assert result == {
        "status": "PASS",
        "frames": 3,
        "phases": ["playing", "playing", "playing"],
        "actions_sent": 0,
    }


def test_passive_preflight_rejects_preexisting_held_keys() -> None:
    env = FakeEnv([_observation(), _observation(), _observation()])
    env.adapter.controller.held_keys = {"left"}
    with pytest.raises(RuntimeError, match="PREFLIGHT_HELD_KEYS_PRESENT"):
        run_passive_preflight(env)
    assert env.adapter.release_count == 1


def test_shadow_episode_writes_jsonl_and_sends_zero_actions(tmp_path: Path) -> None:
    initial = _observation(floor=2)
    env = FakeEnv([_observation("dialog", floor=5)])
    loaded = FakeLoadedModel()
    output = tmp_path / "episode.jsonl"
    record = run_live_episode(
        env,
        loaded,  # type: ignore[arg-type]
        episode_id=1,
        config=BulkEvaluationConfig(
            episodes=1, mode="shadow", video_mode="none", max_episode_seconds=10
        ),
        step_jsonl=output,
        video_path=None,
        capture_fps=10,
        initial_observation=initial,
    )
    assert loaded.calls == 1
    assert record["actions_sent"] == 0
    assert record["deepest_floor"] == 5
    assert json.loads(output.read_text(encoding="utf-8").strip())["action_sent"] is False
    assert env.adapter.release_count == 1


def test_episode_exception_always_releases_keys(tmp_path: Path) -> None:
    env = FakeEnv([])
    loaded = FakeLoadedModel(error=RuntimeError("policy failure"))
    output = tmp_path / "failed.jsonl"
    with pytest.raises(RuntimeError, match="policy failure"):
        run_live_episode(
            env,
            loaded,  # type: ignore[arg-type]
            episode_id=1,
            config=BulkEvaluationConfig(
                episodes=1, mode="shadow", video_mode="none", max_episode_seconds=10
            ),
            step_jsonl=output,
            video_path=None,
            capture_fps=10,
            initial_observation=_observation(),
        )
    assert env.adapter.release_count == 1
    assert output.is_file()


def test_focus_emergency_and_tracking_fail_closed() -> None:
    adapter = SimpleNamespace(emergency_stopped=False, is_foreground=lambda: True)
    good = SimpleNamespace(phase="playing", player={"center_x": 1}, platforms=[{}])
    assert active_safety_failure(adapter, good) is None
    adapter.emergency_stopped = True
    assert active_safety_failure(adapter, good) == "F8_EMERGENCY_STOP"
    adapter.emergency_stopped = False
    adapter.is_foreground = lambda: False
    assert active_safety_failure(adapter, good) == "FOCUS_LOST"
    adapter.is_foreground = lambda: True
    missing = SimpleNamespace(phase="playing", player=None, platforms=[{}])
    assert active_safety_failure(adapter, missing) == "PLAYER_TRACKING_LOST"
    missing_platforms = SimpleNamespace(
        phase="playing", player={"center_x": 1}, platforms=[]
    )
    assert active_safety_failure(adapter, missing_platforms) == "PLATFORM_TRACKING_LOST"


def test_summary_metrics_and_best_episode_are_stable() -> None:
    episodes = [
        {"episode_id": 1, "valid": True, "deepest_floor": 2, "duration_seconds": 5},
        {"episode_id": 2, "valid": True, "deepest_floor": 8, "duration_seconds": 4},
        {"episode_id": 3, "valid": True, "deepest_floor": 8, "duration_seconds": 7},
        {"episode_id": 4, "valid": True, "deepest_floor": 4, "duration_seconds": 3},
    ]
    assert select_best_episode(episodes)["episode_id"] == 2
    summary = build_bulk_summary(episodes)
    assert summary["episodes_completed"] == 4
    assert summary["mean_floor"] == pytest.approx(5.5)
    assert summary["median_floor"] == pytest.approx(6.0)
    assert summary["q25_floor"] == pytest.approx(3.5)
    assert summary["q75_floor"] == pytest.approx(8.0)
    assert summary["floor_le_4_rate"] == pytest.approx(0.5)
    assert summary["best_episode"] == 2
    assert summary["best_floor"] == 8


def test_jsonl_and_verified_zip_contain_provenance(tmp_path: Path) -> None:
    session = tmp_path / "session"
    session.mkdir()
    records = [{"episode_id": 1, "model_sha256": "a" * 64, "deepest_floor": 3}]
    jsonl = session / "episodes.jsonl"
    write_episode_jsonl(jsonl, records)
    assert json.loads(jsonl.read_text(encoding="utf-8").strip()) == records[0]
    (session / "session_manifest.json").write_text(
        json.dumps({"model_id": "v3", "git_commit": "abc"}), encoding="utf-8"
    )
    archive = create_verified_session_zip(session)
    with zipfile.ZipFile(archive) as handle:
        assert handle.testzip() is None
        assert {Path(name).name for name in handle.namelist()} >= {
            "episodes.jsonl",
            "session_manifest.json",
        }


def test_failure_diagnostic_writes_machine_readable_reason(tmp_path: Path) -> None:
    env = SimpleNamespace(adapter=SimpleNamespace(latest_frame=lambda: None))
    bulk_module._write_failure_diagnostic(tmp_path, 7, env, "TRACKING_LOST")
    payload = json.loads(
        (tmp_path / "failure_diagnostics/episode_007.json").read_text(encoding="utf-8")
    )
    assert payload["episode_id"] == 7
    assert payload["reason"] == "TRACKING_LOST"


def test_video_none_and_all_semantics(tmp_path: Path) -> None:
    none = EpisodeVideoRetention(tmp_path, "episode", "none")
    assert none.candidate_path(1) is None
    all_mode = EpisodeVideoRetention(tmp_path, "episode", "all")
    candidate = all_mode.candidate_path(1)
    assert candidate is not None
    candidate.write_bytes(b"video")
    assert all_mode.finalize(1, 3, candidate).path == candidate


def test_best_video_uses_highest_floor_and_earlier_tie(tmp_path: Path) -> None:
    retention = EpisodeVideoRetention(tmp_path, "episode", "best")
    first = retention.candidate_path(1)
    assert first is not None
    first.write_bytes(b"one")
    chosen = retention.finalize(1, 5, first)
    assert chosen.selected_as_best
    tie = retention.candidate_path(2)
    assert tie is not None
    tie.write_bytes(b"two")
    assert retention.finalize(2, 5, tie).path is None
    better = retention.candidate_path(3)
    assert better is not None
    better.write_bytes(b"three")
    replacement = retention.finalize(3, 6, better)
    assert replacement.selected_as_best
    assert replacement.replaced_episode == 1
    assert retention.summary()["best_video_episode"] == 3


def test_video_retention_refuses_outside_session(tmp_path: Path) -> None:
    session = tmp_path / "session"
    session.mkdir()
    retention = EpisodeVideoRetention(session, "episode", "best")
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="VIDEO_PATH_OUTSIDE_SESSION"):
        retention.finalize(1, 1, outside)


def test_recorded_overlay_is_diagnostic_only() -> None:
    frame = np.zeros((120, 320, 3), dtype=np.uint8)
    rendered = render_bulk_overlay(
        frame,
        model_id="r4",
        mode="shadow",
        episode=1,
        episode_total=20,
        step=3,
        predicted_action=int(Action.RIGHT),
        action_sent=False,
        observation=_observation(floor=4),
    )
    assert rendered.shape == frame.shape
    assert np.count_nonzero(rendered) > 0
    assert np.count_nonzero(frame) == 0
