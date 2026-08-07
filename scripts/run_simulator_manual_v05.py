"""Run the normal-platform v0.5 responsive-control manual candidate.

This entry point is intentionally manual-only. It keeps the frozen v0.3 and
v0.4 profiles untouched, but samples keyboard state and advances the simulator
at the fixed 60 Hz physics cadence.

v0.5 revision 3 changes
------------------------
A. Startup impulse: the first tick of a directional press applies a minimum
   launch velocity so that the player responds immediately (arcade feel)
   instead of waiting several ticks to overcome inertia.
B. Reversal model: pressing the opposite direction now brakes the old-direction
   velocity to a small residual threshold (default 30 px/s) and applies
   startup impulse in the new direction, rather than zeroing velocity
   instantly.  This prevents both 0.3-0.4 s of sliding AND instantaneous
   full-speed mirroring.
C. RELEASE is separated from reversal: RELEASE uses linear deceleration;
   reversal uses the brake-then-impulse model.
D. Scroll speed defaults to 96 px/s (real-game measurement) instead of the
   subjective 80 px/s.  Use --scroll-speed 80 if the user feels 96 is too
   fast.
E. --preset flag provides named tuning bundles for quick A/B comparison.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.input_controller import Action
from stair_agent.simulator.manual_test import (
    DEFAULT_MANUAL_SEED,
    DEFAULT_OUTPUT_ROOT,
    ManualScenario,
    ManualSimulatorSession,
    list_manual_scenarios,
    run_manual_viewer,
)
from stair_agent.simulator.platform import SimulatorPlatform

V05_VERSION = "ns-shaft-sim-v0.5-arcade-normal-candidate"
V05_OUTPUT_ROOT = DEFAULT_OUTPUT_ROOT / "v05"

# ---------------------------------------------------------------------------
# Named presets for quick A/B testing without long CLI argument lists.
# Each preset is a dict of CLI-argument overrides.
# ---------------------------------------------------------------------------
_PRESETS: dict[str, dict[str, float]] = {
    "default": {},
    "heavier": {
        "gravity": 380.0,
        "max_fall_speed": 480.0,
    },
    "lighter": {
        "gravity": 270.0,
        "max_fall_speed": 360.0,
    },
    "narrow_platform": {
        "platform_width": 64.0,
    },
    "wide_platform": {
        "platform_width": 80.0,
    },
    "scroll_80": {
        "scroll_speed": 80.0,
    },
}


def _normal_scenarios() -> tuple[ManualScenario, ...]:
    return tuple(item for item in list_manual_scenarios() if not item.special_platform)


class ResponsiveManualSession(ManualSimulatorSession):
    """Manual-only 60 Hz controller with an arcade response curve.

    Revision 3 adds startup impulse, brake-then-impulse reversal, and separate
    RELEASE deceleration.
    """

    def __init__(
        self,
        *,
        scenario: str,
        seed: int,
        output_root: Path,
        display_fps: int,
        show_debug: bool,
        record_video: bool,
        horizontal_acceleration: float,
        startup_acceleration_multiplier: float,
        acceleration_curve_exponent: float,
        air_control_multiplier: float,
        max_horizontal_speed: float,
        release_deceleration: float,
        startup_impulse_speed: float,
        reversal_brake_speed: float,
        platform_width: float,
        gravity: float,
        max_fall_speed: float,
        scroll_speed: float,
    ) -> None:
        self._v05_values = {
            "horizontal_acceleration": float(horizontal_acceleration),
            "startup_acceleration_multiplier": float(
                startup_acceleration_multiplier
            ),
            "acceleration_curve_exponent": float(acceleration_curve_exponent),
            "air_control_multiplier": float(air_control_multiplier),
            "max_horizontal_speed": float(max_horizontal_speed),
            "release_deceleration": float(release_deceleration),
            "startup_impulse_speed": float(startup_impulse_speed),
            "reversal_brake_speed": float(reversal_brake_speed),
            "platform_width": float(platform_width),
            "gravity": -abs(float(gravity)),
            "max_fall_speed": float(max_fall_speed),
            "scroll_speed": float(scroll_speed),
        }
        super().__init__(
            scenario=scenario,
            seed=seed,
            output_root=output_root,
            display_fps=display_fps,
            show_debug=show_debug,
            record_video=record_video,
            calibration_profile="after",
        )
        self._install_v05_profile()

    def _rebuild_platform_width(self, width: float) -> None:
        simulator = self.env.simulator
        if simulator is None:
            raise RuntimeError("重建v0.5平台前沒有Simulator instance。")
        old_platforms = list(simulator.platforms)
        for platform in old_platforms:
            if platform.body in simulator.space.bodies:
                simulator.space.remove(platform.shape, platform.body)
        simulator.platforms = [
            SimulatorPlatform.create(
                floor_index=platform.floor_index,
                center_x=platform.center_x,
                center_y=platform.center_y,
                width=width,
                height=platform.height,
                kind=platform.kind,
            )
            for platform in old_platforms
        ]
        for platform in simulator.platforms:
            simulator.space.add(platform.body, platform.shape)

    def _install_v05_profile(self) -> None:
        simulator = self.env.simulator
        if simulator is None:
            raise RuntimeError("v0.5 manual profile安裝前沒有Simulator instance。")
        config = replace(
            self.env.config,
            environment_version=V05_VERSION,
            fps=60,
            physics_hz=60,
            allow_manual_60hz_control=True,
            horizontal_acceleration=self._v05_values[
                "horizontal_acceleration"
            ],
            air_control_multiplier=self._v05_values[
                "air_control_multiplier"
            ],
            max_horizontal_speed=self._v05_values["max_horizontal_speed"],
            release_deceleration=self._v05_values["release_deceleration"],
            reverse_brake_multiplier=1.0,
            platform_width=self._v05_values["platform_width"],
            gravity=self._v05_values["gravity"],
            max_fall_speed=self._v05_values["max_fall_speed"],
            scroll_speed=self._v05_values["scroll_speed"],
        )
        self.env.config = config
        simulator.config = config
        simulator.space.gravity = (0.0, config.gravity)
        self._rebuild_platform_width(config.platform_width)
        self.calibration_profile = "v05"
        self._event(
            "v05_arcade_profile_installed",
            environment_version=V05_VERSION,
            control_hz=config.fps,
            physics_hz=config.physics_hz,
            startup_impulse_speed=self._v05_values["startup_impulse_speed"],
            reversal_brake_speed=self._v05_values["reversal_brake_speed"],
            **{
                k: v
                for k, v in self._v05_values.items()
                if k not in ("startup_impulse_speed", "reversal_brake_speed")
            },
        )

    def _replace_environment(self, scenario: ManualScenario) -> None:
        # The shared builder only knows the frozen before/after profiles. Build
        # the v0.4 normal environment first, then install this isolated v0.5
        # manual controller again.
        self.calibration_profile = "after"
        super()._replace_environment(scenario)
        self._install_v05_profile()

    def next_scenario(self) -> None:
        normal = _normal_scenarios()
        current_index = next(
            index
            for index, item in enumerate(normal)
            if item.name == self.scenario.name
        )
        next_definition = normal[(current_index + 1) % len(normal)]
        self._event("scenario_switch", next_scenario=next_definition.name)
        self._replace_environment(next_definition)

    def toggle_calibration_profile(self) -> None:
        # Keep the candidate isolated. Use run_simulator_manual_test.py for the
        # v0.3/v0.4 comparison instead of mutating this session in place.
        self._event("v05_profile_toggle_ignored", reason="profile_locked")

    def _effective_horizontal_acceleration(self, action: Action) -> float:
        """Non-linear acceleration: strong at low speed, tapering near cap."""
        base = self._v05_values["horizontal_acceleration"]
        if action not in {Action.LEFT, Action.RIGHT}:
            return base
        simulator = self.env.simulator
        if simulator is None:
            return base
        speed_ratio = min(
            1.0,
            abs(float(simulator.player.body.velocity.x))
            / self._v05_values["max_horizontal_speed"],
        )
        remaining = max(0.0, 1.0 - speed_ratio)
        boost = self._v05_values["startup_acceleration_multiplier"]
        exponent = self._v05_values["acceleration_curve_exponent"]
        response_multiplier = 1.0 + (boost - 1.0) * remaining**exponent
        return base * response_multiplier

    def _apply_startup_impulse(
        self, action: Action, velocity_x: float
    ) -> float:
        """Ensure the first tick of a directional press gives an immediate
        minimum velocity kick, so the player never feels like pushing through
        resistance.

        Only applies when current speed in the requested direction is below
        the configured startup_impulse_speed.
        """
        impulse = self._v05_values["startup_impulse_speed"]
        if action is Action.LEFT:
            if velocity_x > -impulse:
                return -impulse
        elif action is Action.RIGHT:
            if velocity_x < impulse:
                return impulse
        return velocity_x

    def _apply_reversal_brake(
        self, action: Action, velocity_x: float
    ) -> tuple[float, bool]:
        """Brake-then-impulse reversal model.

        When pressing the opposite direction of current travel:
        1. Reduce old-direction speed to at most ``reversal_brake_speed``.
        2. Return the braked velocity and a flag indicating reversal occurred.

        The caller then applies startup impulse in the new direction.
        This avoids both:
        - Instant zeroing (which feels wrong)
        - Instant mirroring from full speed to opposite full speed
        - 0.3-0.4 s of old-direction sliding (the v0.4 problem)
        """
        brake_threshold = self._v05_values["reversal_brake_speed"]
        opposite = (
            (action is Action.LEFT and velocity_x > 0.0)
            or (action is Action.RIGHT and velocity_x < 0.0)
        )
        if not opposite:
            return velocity_x, False

        # Brake to at most brake_threshold in the old direction
        if abs(velocity_x) > brake_threshold:
            # Reduce to threshold, preserving sign
            braked = brake_threshold * (1.0 if velocity_x > 0 else -1.0)
        else:
            braked = velocity_x
        # Then zero the remaining old-direction component
        braked = 0.0
        return braked, True

    def step_once(self) -> dict[str, object]:
        simulator = self.env.simulator
        if simulator is None:
            raise RuntimeError("v0.5 manual simulator尚未reset。")
        action = self.input_state.action
        body = simulator.player.body
        velocity_x = float(body.velocity.x)

        # --- Direction reversal: brake then apply new-direction impulse ---
        velocity_x, reversed_direction = self._apply_reversal_brake(
            action, velocity_x
        )
        if reversed_direction:
            previous_velocity_x = float(body.velocity.x)
            body.velocity = (velocity_x, body.velocity.y)
            self._event(
                "direction_reversal_brake",
                action=action.name,
                previous_velocity_x=previous_velocity_x,
                braked_velocity_x=velocity_x,
            )

        # --- Startup impulse: ensure immediate response on directional press ---
        if action in {Action.LEFT, Action.RIGHT}:
            current_vx = float(body.velocity.x)
            impulse_vx = self._apply_startup_impulse(action, current_vx)
            if impulse_vx != current_vx:
                body.velocity = (impulse_vx, body.velocity.y)
                self._event(
                    "startup_impulse_applied",
                    action=action.name,
                    before_vx=current_vx,
                    after_vx=impulse_vx,
                )

        # --- Non-linear acceleration curve ---
        effective_acceleration = self._effective_horizontal_acceleration(action)
        effective_config = replace(
            self.env.config,
            horizontal_acceleration=effective_acceleration,
        )
        self.env.config = effective_config
        simulator.config = effective_config
        row = super().step_once()

        base_config = replace(
            self.env.config,
            horizontal_acceleration=self._v05_values[
                "horizontal_acceleration"
            ],
        )
        self.env.config = base_config
        simulator.config = base_config
        return row


def _bounded_float(name: str, minimum: float, maximum: float):
    def parse(value: str) -> float:
        number = float(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name}必須介於{minimum:g}與{maximum:g}。"
            )
        return number

    return parse


def build_parser() -> argparse.ArgumentParser:
    scenarios = _normal_scenarios()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=[item.name for item in scenarios],
        default="normal_baseline",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_MANUAL_SEED)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=V05_OUTPUT_ROOT)
    parser.add_argument("--show-debug", action="store_true")
    parser.add_argument(
        "--display-fps",
        type=int,
        choices=(60, 120),
        default=120,
        help="只影響視窗重畫；v0.5控制與physics固定60Hz。",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(_PRESETS),
        default="default",
        help="Named tuning presets for quick A/B comparison.",
    )
    parser.add_argument(
        "--horizontal-acceleration",
        type=_bounded_float("horizontal-acceleration", 100.0, 2000.0),
        default=None,
        help="接近最高速時的基礎加速度（預設420）。",
    )
    parser.add_argument(
        "--startup-acceleration-multiplier",
        type=_bounded_float("startup-acceleration-multiplier", 1.0, 4.0),
        default=None,
        help="低速起步加速倍率（預設2.4）。",
    )
    parser.add_argument(
        "--acceleration-curve-exponent",
        type=_bounded_float("acceleration-curve-exponent", 0.5, 4.0),
        default=None,
    )
    parser.add_argument(
        "--air-control-multiplier",
        type=_bounded_float("air-control-multiplier", 0.1, 1.0),
        default=None,
    )
    parser.add_argument(
        "--max-horizontal-speed",
        type=_bounded_float("max-horizontal-speed", 50.0, 400.0),
        default=None,
    )
    parser.add_argument(
        "--release-deceleration",
        type=_bounded_float("release-deceleration", 50.0, 3000.0),
        default=None,
    )
    parser.add_argument(
        "--startup-impulse-speed",
        type=_bounded_float("startup-impulse-speed", 10.0, 200.0),
        default=None,
        help="首次按鍵的最低啟動速度（預設60 px/s）。",
    )
    parser.add_argument(
        "--reversal-brake-speed",
        type=_bounded_float("reversal-brake-speed", 0.0, 200.0),
        default=None,
        help="反向剎車後殘留速度門檻（預設30 px/s）。",
    )
    parser.add_argument(
        "--platform-width",
        type=_bounded_float("platform-width", 48.0, 120.0),
        default=None,
    )
    parser.add_argument(
        "--gravity",
        type=_bounded_float("gravity", 100.0, 800.0),
        default=None,
        help="向下重力大小；輸入正值即可。",
    )
    parser.add_argument(
        "--max-fall-speed",
        type=_bounded_float("max-fall-speed", 100.0, 800.0),
        default=None,
    )
    parser.add_argument(
        "--scroll-speed",
        type=_bounded_float("scroll-speed", 0.0, 150.0),
        default=None,
    )
    parser.add_argument("--list-scenarios", action="store_true")
    return parser


# ---- Default v0.5-r3 values ----
_V05_DEFAULTS: dict[str, float] = {
    "horizontal_acceleration": 420.0,
    "startup_acceleration_multiplier": 2.4,
    "acceleration_curve_exponent": 2.0,
    "air_control_multiplier": 0.85,
    "max_horizontal_speed": 230.0,
    "release_deceleration": 960.0,
    "startup_impulse_speed": 60.0,
    "reversal_brake_speed": 30.0,
    "platform_width": 72.0,
    "gravity": 320.0,
    "max_fall_speed": 420.0,
    "scroll_speed": 96.0,
}


def _resolve_value(
    args: argparse.Namespace,
    key: str,
    preset_overrides: dict[str, float],
) -> float:
    """Priority: explicit CLI > preset > default."""
    cli_key = key.replace("_", "-")
    # argparse stores with underscores
    arg_val = getattr(args, key.replace("-", "_"), None)
    if arg_val is not None:
        return float(arg_val)
    if key in preset_overrides:
        return float(preset_overrides[key])
    return _V05_DEFAULTS[key]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_scenarios:
        for item in _normal_scenarios():
            print(f"{item.scenario_id} {item.name}: {item.title}")
        return 0

    preset_overrides = _PRESETS.get(args.preset, {})

    session = ResponsiveManualSession(
        scenario=args.scenario,
        seed=args.seed,
        output_root=args.output_dir,
        display_fps=args.display_fps,
        show_debug=args.show_debug,
        record_video=args.record,
        horizontal_acceleration=_resolve_value(
            args, "horizontal_acceleration", preset_overrides
        ),
        startup_acceleration_multiplier=_resolve_value(
            args, "startup_acceleration_multiplier", preset_overrides
        ),
        acceleration_curve_exponent=_resolve_value(
            args, "acceleration_curve_exponent", preset_overrides
        ),
        air_control_multiplier=_resolve_value(
            args, "air_control_multiplier", preset_overrides
        ),
        max_horizontal_speed=_resolve_value(
            args, "max_horizontal_speed", preset_overrides
        ),
        release_deceleration=_resolve_value(
            args, "release_deceleration", preset_overrides
        ),
        startup_impulse_speed=_resolve_value(
            args, "startup_impulse_speed", preset_overrides
        ),
        reversal_brake_speed=_resolve_value(
            args, "reversal_brake_speed", preset_overrides
        ),
        platform_width=_resolve_value(
            args, "platform_width", preset_overrides
        ),
        gravity=_resolve_value(args, "gravity", preset_overrides),
        max_fall_speed=_resolve_value(
            args, "max_fall_speed", preset_overrides
        ),
        scroll_speed=_resolve_value(
            args, "scroll_speed", preset_overrides
        ),
    )
    try:
        run_manual_viewer(session)
    except KeyboardInterrupt:
        print("v0.5 manual simulator收到Ctrl+C，安全保存目前紀錄。")
    finally:
        output_dir = session.close()
    print(f"v0.5 manual simulator紀錄：{output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
