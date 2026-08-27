"""60 FPS human player for the final corrected V3.5 simulator.

This tool deliberately keeps 60 Hz control outside the formal PPO environment.
It reuses the R4 profile, Fresh V3 sampling/layout, simulator physics, collision,
special platforms, observation contract, and existing renderer.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

from stair_agent.envs.fidelity_v3_5 import (
    FidelityV35Env,
    V35Profile,
    load_fidelity_v3_5_profile,
)
from stair_agent.simulator.scenarios import configure_flipping_landing


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "configs" / "fidelity_v3_5.yaml"
DISPLAY_FPS = 60
SUPPORTED_CONTROL_HZ = (8, 10, 12, 60)
ACTION_NAMES = {0: "RELEASE_ALL", 1: "LEFT", 2: "RIGHT"}


class ManualV35SimulatorEnv(FidelityV35Env):
    """Manual-only cadence wrapper; never imported by formal training code."""

    def __init__(
        self,
        *,
        profile: V35Profile,
        base_seed: int = 12345,
        control_hz: int = 60,
    ) -> None:
        if control_hz not in SUPPORTED_CONTROL_HZ:
            raise ValueError(f"MANUAL_CONTROL_HZ_UNSUPPORTED:{control_hz}")
        self.manual_control_hz = int(control_hz)
        super().__init__(
            profile=profile,
            base_seed=base_seed,
            forced_fps=None,
            render_mode=None,
        )

    def _choose_cadence(self) -> int:
        return self.manual_control_hz

    def _sample_config(self, fps: int) -> Any:
        # V3 sampling is cadence-independent, but the formal builder correctly
        # rejects 60 Hz policy control. Materialize the same seeded R4 sample at
        # a supported policy cadence, then enable the existing manual-only gate.
        policy_fps = 8 if fps == 60 else fps
        config = super()._sample_config(policy_fps)
        if fps != 60:
            return config
        return replace(
            config,
            fps=60,
            physics_hz=60,
            allow_manual_60hz_control=True,
        )


def build_manual_environment(
    *,
    profile_path: Path = DEFAULT_PROFILE,
    seed: int = 12345,
    control_hz: int = 60,
) -> ManualV35SimulatorEnv:
    return ManualV35SimulatorEnv(
        profile=load_fidelity_v3_5_profile(profile_path),
        base_seed=seed,
        control_hz=control_hz,
    )


def manual_action(*, left: bool, right: bool) -> int:
    if left == right:
        return 0
    return 1 if left else 2


def keyboard_action(*, focused: bool) -> int:
    if not focused:
        return 0
    keys = pygame.key.get_pressed()
    return manual_action(
        left=bool(keys[pygame.K_LEFT] or keys[pygame.K_a]),
        right=bool(keys[pygame.K_RIGHT] or keys[pygame.K_d]),
    )


def _reset(
    env: ManualV35SimulatorEnv,
    *,
    current_seed: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    if current_seed:
        return env.reset(seed=env.episode_seed)
    return env.reset()


def configure_flipping_test_scene(env: ManualV35SimulatorEnv) -> int:
    """Use the real simulator scenario helper to stage a quick flipping landing."""
    if env.simulator is None:
        raise RuntimeError("MANUAL_FLIPPING_TEST_REQUIRES_RESET")
    return configure_flipping_landing(env.simulator, active=True)


def _nearest_flipping(env: ManualV35SimulatorEnv) -> tuple[str, str, str, str]:
    simulator = env.simulator
    if simulator is None:
        return ("none", "none", "False", "0.000")
    flipping = [item for item in simulator.platforms if item.kind == "flipping"]
    if not flipping:
        return ("none", "none", "False", "0.000")
    platform = min(
        flipping,
        key=lambda item: abs(item.center_y - simulator.player.body.position.y),
    )
    runtime = simulator.flipping_states.get(platform.floor_index)
    state = simulator.get_flipping_status(platform)
    elapsed = float(runtime["elapsed"]) if runtime is not None else 0.0
    return (
        str(platform.floor_index),
        state,
        str(simulator.platform_is_active(platform)),
        f"{elapsed:.3f}",
    )


def _hud_lines(
    env: ManualV35SimulatorEnv,
    *,
    measured_fps: float,
    action: int,
    landing: str,
    terminal: str,
) -> list[str]:
    simulator = env.simulator
    if simulator is None:
        return ["Human Simulator (not reset)"]
    body = simulator.player.body
    flip_floor, flip_state, flip_active, flip_elapsed = _nearest_flipping(env)
    return [
        "Human Simulator (local only; not PPO training)",
        f"Render FPS: {measured_fps:5.1f} / {DISPLAY_FPS}",
        f"Physics Hz: {env.config.physics_hz}",
        f"Manual Control Hz: {env.config.fps}",
        f"Seed: {env.episode_seed}",
        f"Floor: {simulator.deepest_floor}    Health: {simulator.health_segments}",
        f"Action: {ACTION_NAMES[action]}",
        f"Player: x={body.position.x:7.2f} y={body.position.y:7.2f}",
        f"        vx={body.velocity.x:7.2f} vy={body.velocity.y:7.2f}",
        f"Nearest Flipping: floor={flip_floor} state={flip_state}",
        f"                  active={flip_active} elapsed={flip_elapsed}s",
        f"Landing: {landing}    Terminal: {terminal}",
        "A/Left  D/Right  R reset  N next seed  ESC exit",
    ]


def _draw_frame(
    screen: pygame.Surface,
    font: pygame.font.Font,
    env: ManualV35SimulatorEnv,
    *,
    measured_fps: float,
    action: int,
    landing: str,
    terminal: str,
) -> None:
    if env.simulator is None:
        return
    frame = env.renderer.rgb_array(env.simulator)
    surface = pygame.surfarray.make_surface(np.transpose(frame, (1, 0, 2)))
    screen.blit(surface, (0, 0))

    lines = _hud_lines(
        env,
        measured_fps=measured_fps,
        action=action,
        landing=landing,
        terminal=terminal,
    )
    overlay = pygame.Surface((475, 215), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 205))
    for index, line in enumerate(lines):
        overlay.blit(font.render(line, True, (245, 245, 245)), (8, 6 + index * 16))
    screen.blit(overlay, (5, 5))
    pygame.display.flip()


def run_human_simulator(
    env: ManualV35SimulatorEnv,
    *,
    flipping_test: bool = False,
) -> None:
    observation, _ = env.reset()
    if observation.shape != (268,) or int(env.action_space.n) != 3:
        raise RuntimeError("MANUAL_SIMULATOR_SPACE_CONTRACT_FAILED")
    if flipping_test:
        configure_flipping_test_scene(env)

    pygame.init()
    screen = pygame.display.set_mode((env.config.width, env.config.height))
    pygame.display.set_caption("StairKid RL - 60 FPS Human Simulator")
    font = pygame.font.Font(None, 18)
    clock = pygame.time.Clock()
    accumulator = 0.0
    focused = True
    running = True
    action = 0
    landing = "none"
    terminal = "running"
    flipping_seen_inactive = False
    flipping_replay_at: float | None = None

    try:
        while running:
            elapsed = min(clock.tick(DISPLAY_FPS) / 1000.0, 0.25)
            accumulator += elapsed
            reset_mode: str | None = None
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.WINDOWFOCUSLOST:
                    focused = False
                    action = 0
                elif event.type == pygame.WINDOWFOCUSGAINED:
                    focused = True
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        reset_mode = "current"
                    elif event.key == pygame.K_n:
                        reset_mode = "next"

            if not running:
                break
            if reset_mode is not None:
                observation, _ = _reset(env, current_seed=reset_mode == "current")
                if flipping_test:
                    configure_flipping_test_scene(env)
                accumulator = 0.0
                action = 0
                landing = "none"
                terminal = "running"
                flipping_seen_inactive = False
                flipping_replay_at = None

            control_period = 1.0 / env.config.fps
            while accumulator >= control_period:
                action = keyboard_action(focused=focused)
                observation, _, terminated, truncated, info = env.step(action)
                if flipping_test and env.simulator is not None:
                    _floor, state, _active, _state_elapsed = _nearest_flipping(env)
                    if state == "INACTIVE":
                        flipping_seen_inactive = True
                    elif flipping_seen_inactive and state == "READY":
                        if flipping_replay_at is None:
                            flipping_replay_at = env.simulator.elapsed_seconds + 0.35
                        elif env.simulator.elapsed_seconds >= flipping_replay_at:
                            configure_flipping_test_scene(env)
                            flipping_seen_inactive = False
                            flipping_replay_at = None
                landing_info = info.get("landing_safety")
                if isinstance(landing_info, dict):
                    landing = str(landing_info.get("classification", "unknown"))
                if terminated or truncated:
                    terminal = str(info.get("terminal_reason") or "unknown")
                    print(
                        f"episode_seed={info.get('episode_seed')} "
                        f"floor={env.simulator.deepest_floor if env.simulator else None} "
                        f"health={info.get('health_segments')} terminal={terminal}",
                        flush=True,
                    )
                    observation, _ = _reset(env, current_seed=False)
                    if flipping_test:
                        configure_flipping_test_scene(env)
                    action = 0
                    landing = "none"
                    flipping_seen_inactive = False
                    flipping_replay_at = None
                accumulator -= control_period

            _draw_frame(
                screen,
                font,
                env,
                measured_fps=clock.get_fps(),
                action=action,
                landing=landing,
                terminal=terminal,
            )
    finally:
        env.close()
        pygame.quit()


def headless_smoke(*, seed: int = 12345, steps: int = 90) -> dict[str, Any]:
    env = build_manual_environment(seed=seed, control_hz=60)
    actions_seen: set[int] = set()
    platform_count = 0
    try:
        observation, info = env.reset()
        platform_count = len(env.simulator.platforms) if env.simulator else 0
        for index in range(max(steps, 3)):
            action = (0, 1, 2)[index % 3]
            actions_seen.add(action)
            observation, _, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                observation, info = env.reset()
                platform_count = max(
                    platform_count,
                    len(env.simulator.platforms) if env.simulator else 0,
                )
        checks = {
            "observation_268": observation.shape == (268,),
            "action_space_3": int(env.action_space.n) == 3,
            "fps_60": env.config.fps == 60,
            "physics_hz_60": env.config.physics_hz == 60,
            "manual_60hz_gate": env.config.allow_manual_60hz_control is True,
            "platforms_generated": platform_count > 0,
            "release_left_right": actions_seen == {0, 1, 2},
        }
        if not all(checks.values()):
            raise RuntimeError(f"MANUAL_SIMULATOR_SMOKE_FAILED:{checks}")
        return {
            "status": "PASS",
            "steps": max(steps, 3),
            "episode_seed": info.get("episode_seed"),
            "checks": checks,
            "training_performed": False,
            "real_game_executed": False,
        }
    finally:
        env.close()


def flipping_smoke(*, seed: int = 12345, control_hz: int = 60) -> dict[str, Any]:
    """Exercise corrected flipping physics through the manual environment."""
    env = build_manual_environment(seed=seed, control_hz=control_hz)
    try:
        env.reset()
        floor = configure_flipping_test_scene(env)
        simulator = env.simulator
        if simulator is None:
            raise RuntimeError("MANUAL_FLIPPING_SMOKE_NO_SIMULATOR")
        platform = min(simulator.platforms, key=lambda item: item.floor_index)
        state = simulator.flipping_states[floor]
        checks: dict[str, bool] = {
            "render_fps_60": DISPLAY_FPS == 60,
            "physics_hz_60": env.config.physics_hz == 60,
            "control_hz": env.config.fps == control_hz,
            "manual_60hz_gate": (
                env.config.allow_manual_60hz_control is (control_hz == 60)
            ),
            "ready_active": state["state"] == "READY"
            and simulator.platform_is_active(platform),
        }

        simulator.supported_floor = floor
        simulator.trigger_flipping_platform(floor)
        checks["triggered_active"] = state["state"] == "TRIGGERED" and (
            simulator.platform_is_active(platform)
        )
        active_tick_limit = int(
            env.config.flipping_active_seconds / env.config.physics_dt
        ) + 2
        for _ in range(active_tick_limit):
            if state["state"] == "INACTIVE":
                break
            simulator._update_flipping_states(env.config.physics_dt)
        checks["inactive_entered"] = state["state"] == "INACTIVE"
        checks["inactive_not_active"] = not simulator.platform_is_active(platform)
        checks["inactive_no_support"] = simulator.supported_floor is None

        simulator.elapsed_seconds = 10.0
        inactive_at_10 = not simulator.platform_is_active(platform)
        simulator.elapsed_seconds = 100.0
        inactive_at_100 = not simulator.platform_is_active(platform)
        checks["global_elapsed_override_prevented"] = inactive_at_10 and inactive_at_100

        frame = env.renderer.rgb_array(simulator)
        checks["inactive_renderer_gray"] = bool(
            np.all(frame == (70, 70, 82), axis=2).sum()
            >= int(platform.width * platform.height * 0.8)
        )

        floor = configure_flipping_landing(simulator, active=False)
        all_events: list[str] = []
        for _ in range(5):
            _observation, _reward, _terminated, _truncated, info = env.step(0)
            all_events.extend(info["events"])
        checks["inactive_collision_pass_through"] = (
            "flipping_contact" not in all_events
            and simulator.last_landed_floor != floor
        )

        state = simulator.flipping_states[floor]
        inactive_tick_limit = int(
            env.config.flipping_inactive_seconds / env.config.physics_dt
        ) + 2
        for _ in range(inactive_tick_limit):
            if state["state"] == "READY":
                break
            simulator._update_flipping_states(env.config.physics_dt)
        checks["ready_after_inactive"] = state["state"] == "READY" and (
            simulator.platform_is_active(platform)
        )

        floor = configure_flipping_landing(simulator, active=True)
        restored_events: list[str] = []
        for _ in range(30):
            _observation, _reward, terminated, truncated, info = env.step(0)
            restored_events.extend(info["events"])
            if "flipping_contact" in info["events"] or terminated or truncated:
                break
        checks["collision_restored"] = (
            "flipping_contact" in restored_events
            and simulator.last_landed_floor == floor
        )
        if not all(checks.values()):
            raise RuntimeError(f"MANUAL_FLIPPING_SMOKE_FAILED:{checks}")
        return {
            "status": "PASS",
            "control_hz": control_hz,
            "checks": checks,
            "training_performed": False,
            "real_game_executed": False,
        }
    finally:
        env.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument(
        "--control-hz",
        type=int,
        choices=SUPPORTED_CONTROL_HZ,
        default=60,
        help="Human action sampling rate; rendering always stays at 60 FPS.",
    )
    parser.add_argument("--headless-smoke", action="store_true")
    parser.add_argument(
        "--flipping-test",
        action="store_true",
        help="Stage and continuously replay the real deterministic flipping scenario.",
    )
    parser.add_argument("--steps", type=int, default=90)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.headless_smoke:
        result = (
            flipping_smoke(seed=args.seed, control_hz=args.control_hz)
            if args.flipping_test
            else headless_smoke(seed=args.seed, steps=args.steps)
        )
        print(json.dumps(result, indent=2))
        return 0
    env = build_manual_environment(seed=args.seed, control_hz=args.control_hz)
    run_human_simulator(env, flipping_test=args.flipping_test)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
