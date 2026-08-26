"""Shared, side-effect-free preparation for the canonical Real PPO runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from stair_agent.actions import Action
from stair_agent.config import AppConfig
from stair_agent.core.model_registry import LoadedCanonicalModel, load_canonical_model
from stair_agent.hud_detection import HudDetector
from stair_agent.object_detection import ObjectDetector
from stair_agent.real_observation_pipeline import RealFrameObservationPipeline


@dataclass(frozen=True)
class RealDryRunResult:
    """Objects validated without capture or keyboard/controller construction."""

    loaded_model: LoadedCanonicalModel
    config_path: Path
    frame_pipeline: RealFrameObservationPipeline
    actions_sent: int = 0
    capture_constructed: bool = False
    controller_constructed: bool = False


@dataclass(frozen=True)
class RealRunResult:
    model_id: str
    mode: str
    steps: int
    actions_sent: int
    elapsed_seconds: float
    terminal_reason: str


def resolve_real_config(project_root: Path, config_path: Path | None = None) -> Path:
    root = project_root.resolve()
    selected = (config_path or Path("config.yaml"))
    candidate = selected if selected.is_absolute() else root / selected
    if not candidate.is_file() and config_path is None:
        candidate = root / "config.example.yaml"
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise RuntimeError(f"REAL_CONFIG_OUTSIDE_PROJECT:{candidate}")
    if not candidate.is_file():
        raise RuntimeError(f"REAL_CONFIG_REQUIRED:{candidate}")
    return candidate


def prepare_real_dry_run(
    project_root: Path,
    model_id: str,
    *,
    config_path: Path | None = None,
    device: str = "cpu",
) -> RealDryRunResult:
    """Validate the model and perception graph while guaranteeing zero actions.

    This deliberately does not import or instantiate ``ScreenCapture``,
    ``WindowManager``, ``InputController``, ``SafetyMonitor``, or a live game
    adapter.  It is therefore suitable for CI and source-level safety audits.
    """

    root = project_root.resolve()
    selected_config = resolve_real_config(root, config_path)
    config = AppConfig.load(selected_config)
    loaded = load_canonical_model(root, model_id, device=device)
    pipeline = RealFrameObservationPipeline(
        object_detector=ObjectDetector.from_config(config.vision, root),
        hud_detector=HudDetector(config.hud),
        landing_contact_gap=config.events.landing_contact_gap,
        spring_contact_gap=config.events.spring_contact_gap,
        correlation_frames=config.events.correlation_frames,
    )
    return RealDryRunResult(
        loaded_model=loaded,
        config_path=selected_config,
        frame_pipeline=pipeline,
    )


def run_live_real(
    project_root: Path,
    loaded_model: LoadedCanonicalModel,
    *,
    config_path: Path | None = None,
    control: bool = False,
    max_steps: int = 1800,
    max_seconds: float = 180.0,
) -> RealRunResult:
    """Run one bounded shadow or explicitly authorized control episode.

    Live-only imports remain inside this function, so dry-run cannot construct
    capture or input backends. The caller owns interactive authorization for
    ``control=True``. Automatic menu/reset input is disabled; the game must
    already be in PLAYING state.
    """

    if not 1 <= max_steps <= 3600:
        raise ValueError("REAL_MAX_STEPS_OUT_OF_RANGE")
    if not 1.0 <= max_seconds <= 600.0:
        raise ValueError("REAL_MAX_SECONDS_OUT_OF_RANGE")

    from stair_agent.game_state import GamePhase
    from stair_agent.live_env import create_live_environment

    root = project_root.resolve()
    selected_config = resolve_real_config(root, config_path)
    config = AppConfig.load(selected_config)
    env, _target = create_live_environment(
        config,
        root,
        allow_single_enter_reset=False,
    )
    started = time.monotonic()
    steps = 0
    actions_sent = 0
    terminal_reason = "limit"
    try:
        structured = env.adapter.observe()
        observation, _ = env.initialize_from_observation(structured)
        while steps < max_steps and time.monotonic() - started < max_seconds:
            action = loaded_model.predict(observation)
            if control:
                observation, _, terminated, truncated, info = env.step(action)
                actions_sent += 1
                steps += 1
                if terminated or truncated:
                    terminal_reason = str(
                        info.get("phase", "terminated" if terminated else "truncated")
                    )
                    break
            else:
                time.sleep(config.controls.action_duration_ms / 1000.0)
                structured = env.adapter.observe()
                if structured.phase != GamePhase.PLAYING.value:
                    terminal_reason = structured.phase
                    break
                features = env.encoder.encode(structured)
                observation = env.temporal_stack.append(
                    features, Action.RELEASE_ALL
                )
                steps += 1
    finally:
        env.close()
    return RealRunResult(
        model_id=loaded_model.spec.id,
        mode="CONTROL" if control else "SHADOW",
        steps=steps,
        actions_sent=actions_sent,
        elapsed_seconds=time.monotonic() - started,
        terminal_reason=terminal_reason,
    )
