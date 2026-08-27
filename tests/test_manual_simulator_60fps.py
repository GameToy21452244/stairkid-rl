from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "play_simulator.py"
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def load_launcher():
    spec = importlib.util.spec_from_file_location("manual_simulator_60fps", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manual_action_mapping_releases_for_neither_or_both() -> None:
    module = load_launcher()
    assert module.manual_action(left=False, right=False) == 0
    assert module.manual_action(left=True, right=True) == 0
    assert module.manual_action(left=True, right=False) == 1
    assert module.manual_action(left=False, right=True) == 2


def test_manual_60hz_environment_reuses_r3_contract_and_v3_layout() -> None:
    module = load_launcher()
    env = module.build_manual_environment(seed=12345, control_hz=60)
    try:
        observation, info = env.reset()
        assert observation.shape == (268,)
        assert env.action_space.n == 3
        assert env.config.fps == 60
        assert env.config.physics_hz == 60
        assert env.config.allow_manual_60hz_control is True
        assert info["episode_seed"] == 12345
        assert info["cadence_hz"] == 60
        assert type(env.simulator).__name__ == "FidelityV3Simulator"
        assert env.simulator is not None
        assert len(env.simulator.platforms) > 0
        for action in (0, 1, 2):
            observation, _, _, _, _ = env.step(action)
            assert observation.shape == (268,)
    finally:
        env.close()


def test_training_cadence_preview_does_not_open_manual_60hz_gate() -> None:
    module = load_launcher()
    for control_hz in (8, 10, 12):
        env = module.build_manual_environment(seed=12345, control_hz=control_hz)
        try:
            env.reset()
            assert env.config.fps == control_hz
            assert env.config.physics_hz == 60
            assert env.config.allow_manual_60hz_control is False
        finally:
            env.close()


def test_headless_smoke_steps_all_actions_and_generates_platforms() -> None:
    module = load_launcher()
    result = module.headless_smoke(seed=12345, steps=90)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["training_performed"] is False
    assert result["real_game_executed"] is False


def test_corrected_flipping_contract_at_all_manual_control_rates() -> None:
    module = load_launcher()
    for control_hz in (8, 10, 12, 60):
        result = module.flipping_smoke(seed=12345, control_hz=control_hz)
        assert result["status"] == "PASS"
        assert result["control_hz"] == control_hz
        assert all(result["checks"].values())
        assert result["training_performed"] is False
        assert result["real_game_executed"] is False


def test_flipping_test_scene_and_hud_use_runtime_state() -> None:
    module = load_launcher()
    env = module.build_manual_environment(seed=12345, control_hz=60)
    try:
        env.reset()
        floor = module.configure_flipping_test_scene(env)
        assert module._nearest_flipping(env) == (str(floor), "READY", "True", "0.000")
        env.simulator.flipping_states[floor] = {"state": "INACTIVE", "elapsed": 0.5}
        env.simulator.elapsed_seconds = 100.0
        lines = module._hud_lines(
            env,
            measured_fps=60.0,
            action=0,
            landing="none",
            terminal="running",
        )
        assert any("state=INACTIVE" in line for line in lines)
        assert any("active=False" in line and "elapsed=0.500s" in line for line in lines)
    finally:
        env.close()


def test_dummy_sdl_draws_existing_renderer_with_human_hud() -> None:
    module = load_launcher()
    env = module.build_manual_environment(seed=12345, control_hz=60)
    module.pygame.init()
    try:
        env.reset()
        screen = module.pygame.display.set_mode((env.config.width, env.config.height))
        font = module.pygame.font.Font(None, 18)
        module._draw_frame(
            screen,
            font,
            env,
            measured_fps=60.0,
            action=0,
            landing="none",
            terminal="running",
        )
        assert screen.get_size() == (env.config.width, env.config.height)
    finally:
        env.close()
        module.pygame.quit()


def test_launcher_has_no_real_input_or_training_backend() -> None:
    text = LAUNCHER.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "inputcontroller",
        "pyautogui",
        "pydirectinput",
        "screen_capture",
        "stable_baselines3",
        "torch",
        ".learn(",
        "ppo.load",
    ):
        assert forbidden not in text
