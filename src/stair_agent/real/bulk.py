"""Guarded, bounded Real bulk evaluation primitives.

This module recovers the audited Real evaluation behavior as inference-only
code.  Live imports stay inside :func:`run_bulk_session`, allowing unit tests
and source verification to execute without constructing Windows capture or
keyboard backends.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Iterable, Iterator, Mapping
import zipfile

import numpy as np

from stair_agent.actions import Action
from stair_agent.core.model_registry import (
    LoadedCanonicalModel,
    load_canonical_model,
    sha256_file,
)
from stair_agent.evaluation.metrics import floor_metrics


VIDEO_MODES = ("none", "best", "all")
MIN_EPISODES = 1
MAX_EPISODES = 100
MIN_EPISODE_SECONDS = 10.0
MAX_EPISODE_SECONDS = 600.0
POLICY_PERIOD_SECONDS = 0.10
ACTION_HISTORY_SOURCE = "ACTUALLY_EXECUTED_POLICY_ACTION"


@dataclass(frozen=True)
class BulkEvaluationConfig:
    episodes: int = 20
    mode: str = "shadow"
    video_mode: str = "best"
    failure_diagnostics: bool = False
    max_episode_seconds: float = 180.0
    max_episode_steps: int = 3600

    def __post_init__(self) -> None:
        if not MIN_EPISODES <= int(self.episodes) <= MAX_EPISODES:
            raise ValueError("EPISODES_OUT_OF_RANGE: expected 1..100")
        if self.mode not in {"shadow", "control"}:
            raise ValueError("REAL_MODE_INVALID: expected shadow or control")
        if self.video_mode not in VIDEO_MODES:
            raise ValueError("VIDEO_MODE_INVALID: expected none, best, or all")
        if not MIN_EPISODE_SECONDS <= float(self.max_episode_seconds) <= MAX_EPISODE_SECONDS:
            raise ValueError("MAX_EPISODE_SECONDS_OUT_OF_RANGE: expected 10..600")
        if not 1 <= int(self.max_episode_steps) <= 10000:
            raise ValueError("MAX_EPISODE_STEPS_OUT_OF_RANGE")


@dataclass(frozen=True)
class VideoFinalizeResult:
    path: Path | None
    selected_as_best: bool = False
    replaced_episode: int | None = None


class EpisodeVideoRetention:
    """Historical none/best/all retention; highest floor wins, ties stay early."""

    def __init__(self, output_dir: Path, prefix: str, mode: str) -> None:
        if mode not in VIDEO_MODES:
            raise ValueError(f"VIDEO_MODE_INVALID:{mode}")
        self.output_dir = Path(output_dir).resolve()
        self.prefix = prefix
        self.mode = mode
        self.best_floor: int | None = None
        self.best_episode: int | None = None
        self.best_path: Path | None = None

    def candidate_path(self, episode: int) -> Path | None:
        if self.mode == "none":
            return None
        if self.mode == "all":
            return self.output_dir / f"{self.prefix}_{episode:03d}.mp4"
        return self.output_dir / f".{self.prefix}_{episode:03d}.candidate.mp4"

    def _managed(self, path: Path) -> Path:
        candidate = Path(path)
        if candidate.resolve().parent != self.output_dir:
            raise RuntimeError(f"VIDEO_PATH_OUTSIDE_SESSION:{candidate}")
        return candidate

    def _unlink(self, path: Path | None) -> None:
        if path is None:
            return
        managed = self._managed(path)
        if managed.exists() or managed.is_symlink():
            managed.unlink()

    def finalize(
        self,
        episode: int,
        floor: int | None,
        candidate_path: Path | None,
        *,
        eligible: bool = True,
    ) -> VideoFinalizeResult:
        if self.mode == "none" or candidate_path is None:
            return VideoFinalizeResult(None)
        candidate = self._managed(candidate_path)
        if self.mode == "all":
            return VideoFinalizeResult(candidate if candidate.exists() else None)
        if not candidate.exists():
            return VideoFinalizeResult(None)
        score = -1 if floor is None else int(floor)
        if not eligible or (self.best_floor is not None and score <= self.best_floor):
            self._unlink(candidate)
            return VideoFinalizeResult(None)
        replaced = self.best_episode
        destination = self.output_dir / (
            f"{self.prefix}_best_floor_{score}_episode_{episode:03d}.mp4"
        )
        self._unlink(self.best_path)
        os.replace(candidate, destination)
        self.best_floor = score
        self.best_episode = int(episode)
        self.best_path = destination
        return VideoFinalizeResult(destination, True, replaced)

    def summary(self) -> dict[str, Any]:
        return {
            "video_mode": self.mode,
            "best_video_episode": self.best_episode,
            "best_video_floor": self.best_floor,
            "best_video": None if self.best_path is None else str(self.best_path),
        }


class AuthorizationGatedController:
    """Narrow capability wrapper around the existing guarded controller.

    ``apply`` is impossible until both the model-specific session phrase and a
    numbered episode arm are present.  Menu reset is a separate scope and only
    permits the configured restart/focus-correction keys.
    """

    def __init__(
        self,
        controller: Any,
        *,
        model_id: str,
        episode_limit: int,
        allowed_menu_keys: Iterable[str] = (),
    ) -> None:
        if model_id not in {"v3", "r4"}:
            raise ValueError(f"UNKNOWN_MODEL_ID:{model_id}")
        if not MIN_EPISODES <= episode_limit <= MAX_EPISODES:
            raise ValueError("EPISODES_OUT_OF_RANGE")
        self._controller = controller
        self.model_id = model_id
        self.episode_limit = int(episode_limit)
        self.allowed_menu_keys = frozenset(str(key) for key in allowed_menu_keys)
        self.session_authorized = False
        self.episode_armed = False
        self.menu_reset_enabled = False
        self.actions_sent = 0

    @property
    def expected_phrase(self) -> str:
        return f"AUTHORIZE_{self.model_id.upper()}_REAL_CONTROL"

    def authorize(self, phrase: str) -> bool:
        self.session_authorized = phrase == self.expected_phrase
        if not self.session_authorized:
            self.release_all()
        return self.session_authorized

    def arm_episode(self, episode: int) -> None:
        if not self.session_authorized:
            raise RuntimeError("REAL_CONTROL_NOT_AUTHORIZED")
        if not 1 <= int(episode) <= self.episode_limit:
            raise RuntimeError("REAL_EPISODE_OUT_OF_AUTHORIZED_RANGE")
        self.menu_reset_enabled = False
        self.episode_armed = True

    def disarm_episode(self) -> None:
        self.episode_armed = False
        self.menu_reset_enabled = False
        self.release_all()

    @contextmanager
    def menu_reset_scope(self) -> Iterator[None]:
        if not self.session_authorized or self.episode_armed:
            raise RuntimeError("REAL_MENU_RESET_NOT_AUTHORIZED")
        self.menu_reset_enabled = True
        try:
            yield
        finally:
            self.menu_reset_enabled = False
            self.release_all()

    def apply(self, action: Action) -> None:
        if not self.session_authorized:
            raise RuntimeError("REAL_CONTROL_NOT_AUTHORIZED")
        if not self.episode_armed:
            raise RuntimeError("REAL_CONTROL_NOT_ARMED")
        try:
            self._controller.apply(action)
            self.actions_sent += 1
        except BaseException:
            self.episode_armed = False
            self.release_all()
            raise

    def tap(self, key: str, duration_ms: int | None = None) -> None:
        if not self.session_authorized or not self.menu_reset_enabled:
            raise RuntimeError("REAL_MENU_RESET_NOT_AUTHORIZED")
        if key not in self.allowed_menu_keys:
            raise RuntimeError(f"REAL_MENU_KEY_NOT_ALLOWED:{key}")
        self._controller.tap(key, duration_ms)

    def release_all(self) -> None:
        self._controller.release_all()

    def emergency_stop(self) -> None:
        self.episode_armed = False
        self.menu_reset_enabled = False
        self._controller.emergency_stop()

    @property
    def emergency_stopped(self) -> bool:
        return bool(self._controller.emergency_stopped)

    @property
    def held_keys(self) -> set[str]:
        return set(getattr(self._controller, "held_keys", set()))

    def is_target_active(self) -> bool:
        return bool(self._controller.is_target_active())

    def focus_target(self) -> None:
        """Focus is not a game action; held keys are released before forwarding."""

        self.release_all()
        self._controller.focus_target()

    def verified_name_entry_dialog(self):
        return self._controller.verified_name_entry_dialog()

    def dismiss_verified_name_entry_dialog(self):
        if not self.session_authorized or not self.menu_reset_enabled:
            raise RuntimeError("REAL_MENU_RESET_NOT_AUTHORIZED")
        return self._controller.dismiss_verified_name_entry_dialog()

    def resume_after_related_window(self) -> bool:
        return bool(self._controller.resume_after_related_window())


def request_control_authorization(
    gate: AuthorizationGatedController,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Show the exact second-layer phrase and fail closed on any mismatch."""

    phrase = gate.expected_phrase
    output_fn("")
    output_fn("CONTROL MODE - SECOND SAFETY AUTHORIZATION")
    output_fn("Real keyboard actions remain disabled until this exact phrase is entered.")
    output_fn("F8 remains the emergency stop; keep the game focused and supervised.")
    output_fn(f"TYPE EXACTLY (case-sensitive): {phrase}")
    entered = input_fn(f"Authorization [{phrase}]: ").strip()
    if not gate.authorize(entered):
        output_fn("REAL_CONTROL_AUTHORIZATION=REJECTED (no policy action was enabled)")
        raise RuntimeError("REAL_CONTROL_AUTHORIZATION_REJECTED")
    output_fn("REAL_CONTROL_AUTHORIZATION=PASS")


def install_authorization_gate(env: Any, gate: AuthorizationGatedController) -> None:
    """Route gameplay and the existing resetter through one capability gate."""

    env.adapter.controller = gate
    resetter = getattr(env.adapter, "episode_resetter", None)
    if resetter is not None:
        resetter.controller = gate
        resetter.handler.controller = gate


def has_verified_reset_calibration(app_config: Any) -> bool:
    """Return true only when every coordinate required by the reset guard exists."""

    detection = app_config.detection
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
    return all(getattr(detection, name, None) is not None for name in names)


def active_safety_failure(adapter: Any, observation: Any) -> str | None:
    if bool(adapter.emergency_stopped):
        return "F8_EMERGENCY_STOP"
    if not bool(adapter.is_foreground()):
        return "FOCUS_LOST"
    if getattr(observation, "phase", None) != "playing":
        return f"PHASE_{str(getattr(observation, 'phase', 'unknown')).upper()}"
    if getattr(observation, "player", None) is None:
        return "PLAYER_TRACKING_LOST"
    if not getattr(observation, "platforms", None):
        return "PLATFORM_TRACKING_LOST"
    return None


def validate_policy_observation(observation: Any) -> np.ndarray:
    """Validate the frozen V3/R4 Real policy input contract."""

    array = np.asarray(observation, dtype=np.float32)
    if tuple(array.shape) != (268,):
        raise RuntimeError(f"OBSERVATION_SHAPE_MISMATCH:{tuple(array.shape)}!=(268,)")
    if not np.isfinite(array).all():
        raise RuntimeError("OBSERVATION_NONFINITE")
    return array


def assert_causal_history_contract(
    env: Any,
    *,
    resulting_observation: Any,
    executed_action: Action,
) -> None:
    """Prove the newest temporal entry is (features(O_t+1), executed A_t)."""

    stack = env.temporal_stack
    if not bool(stack.include_action_history) or int(stack.history_frames) != 4:
        raise RuntimeError("CAUSAL_TEMPORAL_STACK_CONFIGURATION_VIOLATION")
    expected_features = env.encoder.encode(resulting_observation)
    expected_action = stack._action_features(executed_action)
    if not np.array_equal(stack._frames[-1], expected_features):
        raise RuntimeError("CAUSAL_RESULTING_OBSERVATION_MISMATCH")
    if not np.array_equal(stack._actions[-1], expected_action):
        raise RuntimeError("CAUSAL_EXECUTED_ACTION_HISTORY_MISMATCH")


def select_best_episode(records: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
    eligible = [
        row for row in records
        if bool(row.get("valid")) and row.get("deepest_floor") is not None
    ]
    if not eligible:
        raise ValueError("NO_VALID_REAL_EPISODES")
    # Highest floor wins; stable ordering deliberately preserves the earlier tie.
    return max(eligible, key=lambda row: int(row["deepest_floor"]))


def build_bulk_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    valid = [
        row for row in rows
        if bool(row.get("valid")) and row.get("deepest_floor") is not None
    ]
    floors = [int(row["deepest_floor"]) for row in valid]
    if not floors:
        raise ValueError("NO_VALID_REAL_EPISODES")
    metrics = floor_metrics(floors)
    best = select_best_episode(valid)
    action_counts = {
        name: sum(int(row.get("action_counts", {}).get(name, 0)) for row in valid)
        for name in (Action.RELEASE_ALL.name, Action.LEFT.name, Action.RIGHT.name)
    }
    total_actions = sum(action_counts.values())
    total_duration = sum(float(row.get("duration_seconds", 0.0)) for row in valid)
    return {
        "episodes_requested": len(rows),
        "episodes_completed": len(valid),
        "mean_floor": metrics["mean"],
        "median_floor": metrics["median"],
        "q25_floor": metrics["q25"],
        "q75_floor": metrics["q75"],
        "min_floor": metrics["min"],
        "max_floor": metrics["max"],
        "floor_le_4_rate": metrics["floor_le_threshold_rate"],
        "best_episode": int(best["episode_id"]),
        "best_floor": int(best["deepest_floor"]),
        "invalid_technical": len(rows) - len(valid),
        "total_policy_steps": total_actions,
        "effective_policy_hz": total_actions / max(total_duration, 1e-9),
        "action_counts": action_counts,
        "action_rates": {
            name: count / max(total_actions, 1) for name, count in action_counts.items()
        },
    }


def write_episode_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(
                json.dumps(dict(row), ensure_ascii=False, default=_json_default) + "\n"
            )


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    raise TypeError(f"NOT_JSON_SERIALIZABLE:{type(value).__name__}")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, default=_json_default)
        + "\n",
        encoding="utf-8",
    )


def create_verified_session_zip(session_dir: Path) -> Path:
    session = Path(session_dir).resolve()
    if not session.is_dir():
        raise RuntimeError(f"SESSION_DIR_REQUIRED:{session}")
    archive = session.with_suffix(".zip")
    temporary = archive.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(session.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(session.parent))
    with zipfile.ZipFile(temporary) as handle:
        bad = handle.testzip()
        if bad is not None:
            raise RuntimeError(f"SESSION_ZIP_CRC_FAILURE:{bad}")
    temporary.replace(archive)
    return archive


def _git_value(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return completed.stdout.strip()


def _floor_value(observation: Any) -> int | None:
    floor = getattr(observation, "floor", None)
    if not isinstance(floor, dict) or floor.get("value") is None:
        return None
    return int(floor["value"])


def _open_video(path: Path | None, frame: Any, fps: float):
    if path is None or frame is None:
        return None
    import cv2

    height, width = frame.shape[:2]
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), max(1.0, fps), (width, height)
    )
    if not writer.isOpened():
        writer.release()
        raise RuntimeError(f"VIDEO_WRITER_OPEN_FAILED:{path}")
    return writer


def render_bulk_overlay(
    frame: Any,
    *,
    model_id: str,
    mode: str,
    episode: int,
    episode_total: int,
    step: int,
    predicted_action: int,
    action_sent: bool,
    observation: Any,
):
    """Render the audited diagnostic overlay onto the recorded frame only."""

    import cv2

    output = frame.copy()
    action_name = Action(int(predicted_action)).name
    floor = _floor_value(observation)
    health = getattr(observation, "health", {}) or {}
    lines = [
        f"STAIRKID REAL BULK | MODEL={model_id} MODE={mode.upper()}",
        "F8 = EMERGENCY STOP",
        f"EP={episode}/{episode_total} STEP={step} POLICY={action_name} SENT={'YES' if action_sent else 'NO'}",
        f"PHASE={observation.phase} TRACK={'YES' if observation.player else 'NO'} PLATFORM={'YES' if observation.platforms else 'NO'}",
        f"FLOOR={floor} HEALTH={health.get('segments')}",
    ]
    cv2.rectangle(output, (0, 0), (output.shape[1], 88), (0, 0, 125), -1)
    for index, line in enumerate(lines):
        cv2.putText(
            output,
            line,
            (8, 16 + index * 17),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
        )
    return output


def run_live_episode(
    env: Any,
    loaded: LoadedCanonicalModel,
    *,
    episode_id: int,
    config: BulkEvaluationConfig,
    step_jsonl: Path,
    video_path: Path | None,
    capture_fps: float,
    initial_observation: Any | None = None,
    initial_policy_observation: Any | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run one bounded inference episode with the audited R4 Real20 contract."""

    started = monotonic()
    steps = 0
    deepest: int | None = None
    terminal_reason = "LIMIT"
    valid = True
    writer = None
    records: list[dict[str, Any]] = []
    previous_step: float | None = None
    try:
        if initial_observation is None:
            vector, _ = env.reset()
            structured = env.last_observation
        else:
            structured = initial_observation
            if initial_policy_observation is None:
                vector, _ = env.initialize_from_observation(structured)
            else:
                vector = initial_policy_observation
                env.last_observation = structured
        vector = validate_policy_observation(vector)
        deepest = _floor_value(structured)
        frame = env.adapter.latest_frame()
        writer = _open_video(video_path, frame, capture_fps)
        while (
            steps < config.max_episode_steps
            and monotonic() - started < config.max_episode_seconds
        ):
            step_started = monotonic()
            failure = active_safety_failure(env.adapter, structured)
            if failure is not None:
                terminal_reason = failure
                valid = failure.startswith("PHASE_") and steps > 0
                break
            policy_input = validate_policy_observation(vector)
            action, probabilities = loaded.predict_with_probabilities(policy_input)
            predicted = Action(int(action))
            observation_timestamp = getattr(structured, "timestamp", None)
            timing = None
            if config.mode == "control":
                vector, _reward, terminated, truncated, info = env.step(action)
                structured = env.last_observation
                timing = env.adapter.last_action_timing
                if timing is None or not bool(timing.action_applied):
                    raise RuntimeError("ACTION_NOT_ACTUALLY_APPLIED")
                assert_causal_history_contract(
                    env,
                    resulting_observation=structured,
                    executed_action=predicted,
                )
                vector = validate_policy_observation(vector)
                steps += 1
                if terminated or truncated:
                    terminal_reason = (
                        "EPISODE_TERMINATED" if terminated else "EPISODE_TRUNCATED"
                    )
            else:
                sleeper(env.adapter.action_duration_ms / 1000.0)
                structured = env.adapter.observe()
                features = env.encoder.encode(structured)
                vector = env.temporal_stack.append(features, Action.RELEASE_ALL)
                vector = validate_policy_observation(vector)
                terminated = structured.phase != "playing"
                truncated = False
                info = {}
                steps += 1
                if terminated:
                    terminal_reason = str(structured.phase).upper()
            floor = _floor_value(structured)
            if floor is not None:
                deepest = floor if deepest is None else max(deepest, floor)
            frame = env.adapter.latest_frame()
            if writer is not None and frame is not None:
                writer.write(
                    render_bulk_overlay(
                        frame,
                        model_id=loaded.spec.id,
                        mode=config.mode,
                        episode=episode_id,
                        episode_total=config.episodes,
                        step=steps,
                        predicted_action=action,
                        action_sent=config.mode == "control",
                        observation=structured,
                    )
                )
            records.append(
                {
                    "episode_id": episode_id,
                    "step": steps,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "predicted_action": int(action),
                    "predicted_action_name": predicted.name,
                    "action_probabilities": probabilities,
                    "action_sent": config.mode == "control",
                    "actually_executed_action": (
                        predicted.name if config.mode == "control" else "NONE_SHADOW"
                    ),
                    "action_applied": bool(
                        config.mode == "control"
                        and timing is not None
                        and timing.action_applied
                    ),
                    "observation_shape": list(policy_input.shape),
                    "observation_finite": bool(np.isfinite(policy_input).all()),
                    "next_observation_shape": list(vector.shape),
                    "next_observation_finite": bool(np.isfinite(vector).all()),
                    "phase": structured.phase,
                    "floor": floor,
                    "health": getattr(structured, "health", None),
                    "events": getattr(structured, "events", None),
                    "player_detected": getattr(structured, "player", None) is not None,
                    "player": getattr(structured, "player", None),
                    "platform_context": bool(getattr(structured, "platforms", None)),
                    "platform_count": len(getattr(structured, "platforms", []) or []),
                    "nearest_platform": getattr(structured, "nearest_platform", None),
                    "observation_timestamp": observation_timestamp,
                    "action_command_timestamp": (
                        None if timing is None else timing.action_command_timestamp
                    ),
                    "action_effective_timestamp": (
                        None if timing is None else timing.action_effective_timestamp
                    ),
                    "next_observation_timestamp": (
                        None if timing is None else timing.next_observation_timestamp
                    ),
                    "policy_loop_period_ms": (
                        None
                        if previous_step is None
                        else 1000.0 * (step_started - previous_step)
                    ),
                    "ACTION_HISTORY_SOURCE": ACTION_HISTORY_SOURCE,
                    "info": info,
                }
            )
            previous_step = step_started
            if terminated or truncated:
                break
            failure = active_safety_failure(env.adapter, structured)
            if failure is not None:
                terminal_reason = failure
                valid = False
                break
            sleeper(max(0.0, POLICY_PERIOD_SECONDS - (monotonic() - step_started)))
        else:
            terminal_reason = "TIME_OR_STEP_LIMIT"
    except BaseException as exc:
        valid = False
        terminal_reason = f"INVALID_TECHNICAL:{type(exc).__name__}:{exc}"
        raise
    finally:
        if writer is not None:
            writer.release()
        env.adapter.release_all()
        write_episode_jsonl(step_jsonl, records)
    duration = monotonic() - started
    action_counts = {
        action.name: sum(
            row.get("predicted_action_name") == action.name for row in records
        )
        for action in (Action.RELEASE_ALL, Action.LEFT, Action.RIGHT)
    }
    return {
        "episode_id": int(episode_id),
        "valid": bool(valid and deepest is not None),
        "deepest_floor": deepest,
        "steps": steps,
        "duration_seconds": duration,
        "policy_hz": steps / max(duration, 1e-9),
        "action_counts": action_counts,
        "release_rate": action_counts[Action.RELEASE_ALL.name] / max(steps, 1),
        "termination_reason": terminal_reason,
        "actions_sent": steps if config.mode == "control" else 0,
        "jsonl": str(step_jsonl),
        "video": None if video_path is None else str(video_path),
    }


def _write_failure_diagnostic(session: Path, episode: int, env: Any, reason: str) -> None:
    diagnostic = session / "failure_diagnostics"
    diagnostic.mkdir(exist_ok=True)
    _write_json(
        diagnostic / f"episode_{episode:03d}.json",
        {"episode_id": episode, "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()},
    )
    frame = env.adapter.latest_frame()
    if frame is not None:
        import cv2

        cv2.imwrite(str(diagnostic / f"episode_{episode:03d}.png"), frame)


def run_passive_preflight(env: Any, *, frames: int = 3) -> dict[str, Any]:
    """Observe only; inference and keyboard input are deliberately absent."""

    if frames < 1:
        raise ValueError("PREFLIGHT_FRAMES_INVALID")
    phases: list[str] = []
    for _ in range(frames):
        observation = env.adapter.observe()
        phases.append(str(observation.phase))
        if env.adapter.emergency_stopped:
            raise RuntimeError("PREFLIGHT_F8_EMERGENCY_STOP")
        if not env.adapter.is_foreground():
            raise RuntimeError("PREFLIGHT_FOCUS_UNSAFE")
        if observation.phase not in {"playing", "dialog"}:
            raise RuntimeError(f"PREFLIGHT_PHASE_UNSAFE:{observation.phase}")
    controller = env.adapter.controller
    if getattr(controller, "actions_sent", 0) != 0:
        raise RuntimeError("PREFLIGHT_INPUT_WAS_SENT")
    if getattr(controller, "held_keys", set()):
        env.adapter.release_all()
        raise RuntimeError("PREFLIGHT_HELD_KEYS_PRESENT")
    return {"status": "PASS", "frames": frames, "phases": phases, "actions_sent": 0}


def prepare_supervised_episode(
    env: Any,
    *,
    episode_id: int,
    output_fn: Callable[[str], None] = print,
    sleeper: Callable[[float], None] = time.sleep,
    settle_seconds: float = 0.75,
) -> Any:
    """Refocus after terminal READY, then revalidate without sending game input."""

    env.adapter.release_all()
    output_fn(
        f"EPISODE_{episode_id}_READY_ACCEPTED: focusing the verified NS-SHAFT window..."
    )
    env.adapter.controller.focus_target()
    sleeper(max(0.0, settle_seconds))
    observation = env.adapter.observe()
    failure = active_safety_failure(env.adapter, observation)
    if failure is not None:
        env.adapter.release_all()
        raise RuntimeError(f"SUPERVISED_EPISODE_UNSAFE:{failure}")
    output_fn(f"EPISODE_{episode_id}_FOCUS_TRACKING_PREFLIGHT=PASS")
    return observation


def prepare_verified_menu_episode(
    env: Any,
    gate: AuthorizationGatedController,
    *,
    episode_id: int,
    countdown_seconds: int = 0,
    output_fn: Callable[[str], None] = print,
    sleeper: Callable[[float], None] = time.sleep,
    return_policy_observation: bool = False,
) -> Any:
    """Focus and execute the historical guarded one-Enter menu reset."""

    env.adapter.release_all()
    output_fn(f"EPISODE_{episode_id}_VERIFIED_MENU_RESET=ARMED")
    if countdown_seconds > 0:
        output_fn("The verified NS-SHAFT window will be focused after this countdown:")
        for remaining in range(int(countdown_seconds), 0, -1):
            output_fn(f"STARTING_IN={remaining}")
            sleeper(1.0)
    gate.focus_target()
    sleeper(0.5)
    with gate.menu_reset_scope():
        policy_observation, _info = env.reset()
    policy_observation = validate_policy_observation(policy_observation)
    observation = env.last_observation
    failure = active_safety_failure(env.adapter, observation)
    if failure is not None:
        env.adapter.release_all()
        raise RuntimeError(f"VERIFIED_MENU_RESET_UNSAFE:{failure}")
    output_fn(f"EPISODE_{episode_id}_VERIFIED_MENU_RESET=PASS")
    if return_policy_observation:
        return observation, policy_observation
    return observation


def run_bulk_session(
    project_root: Path,
    *,
    model_id: str,
    bulk_config: BulkEvaluationConfig,
    output_root: Path,
    config_path: Path | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Execute a supervised Real session after passive preflight and auth."""

    from stair_agent.config import AppConfig
    from stair_agent.live_env import create_live_environment
    from stair_agent.real.runtime import resolve_real_config

    root = Path(project_root).resolve()
    loaded = load_canonical_model(root, model_id, device="cpu")
    model_before = sha256_file(loaded.path)
    selected_config = resolve_real_config(root, config_path, allow_example=False)
    app_config = AppConfig.load(selected_config)
    verified_reset = (
        bulk_config.mode == "control"
        and has_verified_reset_calibration(app_config)
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session = (Path(output_root).resolve() / f"{timestamp}_{model_id}_{bulk_config.mode}")
    session.mkdir(parents=True, exist_ok=False)
    env = None
    gate = None
    episodes: list[dict[str, Any]] = []
    retention = EpisodeVideoRetention(session, "episode", bulk_config.video_mode)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "session_id": session.name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git_branch": _git_value(root, "branch", "--show-current"),
        "git_commit": _git_value(root, "rev-parse", "HEAD"),
        "model_id": loaded.spec.id,
        "model_display_name": loaded.spec.display_name,
        "model_sha256": loaded.spec.sha256,
        "model_status": loaded.spec.status,
        "observation_shape": list(loaded.spec.observation_shape),
        "action_count": loaded.spec.action_count,
        "configuration": asdict(bulk_config),
        "real_config": str(selected_config),
        "capture_fps": app_config.capture.target_fps,
        "action_duration_ms": app_config.controls.action_duration_ms,
        "policy_period_seconds": POLICY_PERIOD_SECONDS,
        "action_history_source": ACTION_HISTORY_SOURCE,
        "max_continuous_hold_ms": app_config.controls.max_continuous_hold_ms,
        "emergency_stop_key": app_config.safety.emergency_stop_key,
        "episode_reset_mode": (
            "VERIFIED_SINGLE_ENTER" if verified_reset else "MANUAL_USER_SUPERVISED"
        ),
        "real_game_evaluation": True,
        "training_performed": False,
    }
    _write_json(session / "session_manifest.json", manifest)
    try:
        env, _target = create_live_environment(
            app_config, root, allow_single_enter_reset=verified_reset
        )
        raw_controller = env.adapter.controller
        gate = AuthorizationGatedController(
            raw_controller,
            model_id=model_id,
            episode_limit=bulk_config.episodes,
            allowed_menu_keys={
                app_config.controls.restart_key,
                app_config.controls.menu_focus_correction_key,
            },
        )
        install_authorization_gate(env, gate)
        preflight = run_passive_preflight(env)
        output_fn("R4/V3 REAL BULK PASSIVE PREFLIGHT=PASS")
        output_fn(f"EPISODE_RESET_MODE={manifest['episode_reset_mode']}")
        if bulk_config.mode == "control":
            request_control_authorization(
                gate,
                input_fn=input_fn,
                output_fn=output_fn,
            )
        for episode_id in range(1, bulk_config.episodes + 1):
            initial = None
            initial_policy_observation = None
            if bulk_config.mode == "control":
                assert gate is not None
                if verified_reset:
                    initial, initial_policy_observation = prepare_verified_menu_episode(
                        env,
                        gate,
                        episode_id=episode_id,
                        countdown_seconds=3 if episode_id == 1 else 0,
                        output_fn=output_fn,
                        return_policy_observation=True,
                    )
                else:
                    answer = input_fn(
                        f"Episode {episode_id}: manually reset/start the game, "
                        "return here, then type READY "
                        "(the runner will refocus the game): "
                    ).strip()
                    if answer != "READY":
                        raise RuntimeError("CONTROL_EPISODE_READY_NOT_CONFIRMED")
                    initial = prepare_supervised_episode(
                        env,
                        episode_id=episode_id,
                        output_fn=output_fn,
                    )
                gate.arm_episode(episode_id)
            else:
                answer = input_fn(
                    f"Episode {episode_id}: manually start/reset the game, return here, "
                    "then type READY (the runner will refocus the game): "
                ).strip()
                if answer != "READY":
                    raise RuntimeError("SHADOW_EPISODE_READY_NOT_CONFIRMED")
                initial = prepare_supervised_episode(
                    env,
                    episode_id=episode_id,
                    output_fn=output_fn,
                )
            candidate = retention.candidate_path(episode_id)
            try:
                record = run_live_episode(
                    env,
                    loaded,
                    episode_id=episode_id,
                    config=bulk_config,
                    step_jsonl=session / f"episode_{episode_id:03d}.jsonl",
                    video_path=candidate,
                    capture_fps=float(app_config.capture.target_fps),
                    initial_observation=initial,
                    initial_policy_observation=initial_policy_observation,
                )
            except BaseException as exc:
                record = {
                    "episode_id": episode_id,
                    "valid": False,
                    "deepest_floor": None,
                    "steps": 0,
                    "duration_seconds": 0.0,
                    "termination_reason": f"INVALID_TECHNICAL:{type(exc).__name__}:{exc}",
                    "actions_sent": 0,
                }
                if bulk_config.failure_diagnostics:
                    _write_failure_diagnostic(session, episode_id, env, record["termination_reason"])
                retention.finalize(
                    episode_id,
                    None,
                    candidate,
                    eligible=False,
                )
                episodes.append(record)
                write_episode_jsonl(session / "episodes.jsonl", episodes)
                _write_json(session / f"episode_{episode_id:03d}.json", record)
                raise
            finally:
                if gate is not None:
                    gate.disarm_episode()
            finalized = retention.finalize(
                episode_id,
                record.get("deepest_floor"),
                candidate,
                eligible=bool(record.get("valid")),
            )
            record["video"] = None if finalized.path is None else str(finalized.path)
            if bulk_config.failure_diagnostics and not record.get("valid"):
                _write_failure_diagnostic(
                    session,
                    episode_id,
                    env,
                    str(record.get("termination_reason", "INVALID_TECHNICAL")),
                )
            episodes.append(record)
            write_episode_jsonl(session / "episodes.jsonl", episodes)
            _write_json(session / f"episode_{episode_id:03d}.json", record)
            output_fn(
                f"EPISODE={episode_id} VALID={record['valid']} FLOOR={record['deepest_floor']} "
                f"REASON={record['termination_reason']}"
            )
            if not record.get("valid"):
                raise RuntimeError(
                    f"REAL_BULK_SAFETY_STOP:{record['termination_reason']}"
                )
        summary = build_bulk_summary(episodes)
        summary.update(retention.summary())
        summary["model_id"] = model_id
        summary["model_sha256"] = loaded.spec.sha256
        summary["git_commit"] = manifest["git_commit"]
        summary["mode"] = bulk_config.mode
        summary["failure_diagnostics"] = bulk_config.failure_diagnostics
        _write_json(session / "summary.json", summary)
        (session / "summary.md").write_text(
            "# Real Bulk Evaluation Summary\n\n"
            + "\n".join(f"- {key}: {value}" for key, value in summary.items())
            + "\n",
            encoding="utf-8",
        )
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["summary"] = summary
        manifest["actions_sent"] = 0 if gate is None else gate.actions_sent
        model_after = sha256_file(loaded.path)
        manifest["model_sha256_after"] = model_after
        manifest["model_unchanged"] = model_before == model_after == loaded.spec.sha256
        if not manifest["model_unchanged"]:
            raise RuntimeError("CANONICAL_MODEL_CHANGED_DURING_REAL_EVALUATION")
        _write_json(session / "session_manifest.json", manifest)
        archive = create_verified_session_zip(session)
        return {
            "session_dir": str(session),
            "archive": str(archive),
            "manifest": manifest,
            "summary": summary,
            "preflight": preflight,
        }
    except BaseException as exc:
        # Preserve an auditable partial session even when a safety or technical
        # failure stops the batch.  The original exception remains the result.
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["aborted"] = True
        manifest["abort_reason"] = f"{type(exc).__name__}:{exc}"
        manifest["episodes"] = episodes
        manifest["actions_sent"] = 0 if gate is None else gate.actions_sent
        model_after = sha256_file(loaded.path)
        manifest["model_sha256_after"] = model_after
        manifest["model_unchanged"] = model_before == model_after == loaded.spec.sha256
        _write_json(session / "session_manifest.json", manifest)
        write_episode_jsonl(session / "episodes.jsonl", episodes)
        create_verified_session_zip(session)
        if not manifest["model_unchanged"]:
            raise RuntimeError("CANONICAL_MODEL_CHANGED_DURING_REAL_EVALUATION") from exc
        raise
    finally:
        if gate is not None:
            gate.disarm_episode()
        if env is not None:
            env.close()


__all__ = [
    "AuthorizationGatedController",
    "BulkEvaluationConfig",
    "EpisodeVideoRetention",
    "VIDEO_MODES",
    "active_safety_failure",
    "build_bulk_summary",
    "create_verified_session_zip",
    "install_authorization_gate",
    "has_verified_reset_calibration",
    "prepare_supervised_episode",
    "prepare_verified_menu_episode",
    "run_bulk_session",
    "run_live_episode",
    "run_passive_preflight",
    "render_bulk_overlay",
    "request_control_authorization",
    "select_best_episode",
    "write_episode_jsonl",
]
