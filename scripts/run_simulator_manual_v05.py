"""Run the normal-platform v0.5 responsive-control manual candidate.

This entry point is intentionally manual-only. It keeps the frozen v0.3 and
v0.4 profiles untouched, but samples keyboard state and advances the simulator
at the fixed 60 Hz physics cadence.

The candidate uses an arcade-style horizontal response: strong acceleration at
low speed that eases near the cap, immediate opposite-direction response, a
narrower normal platform, and stronger downward gravity. These changes are
isolated from formal simulator/training profiles.
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


def _normal_scenarios() -> tuple[ManualScenario, ...]:
    return tuple(item for item in list_manual_scenarios() if not item.special_platform)


class ResponsiveManualSession(ManualSimulatorSession):
    """Manual-only 60 Hz controller with an arcade response curve."""

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
            instant_direction_reversal=True,
            **self._v05_values,
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

    def step_once(self) -> dict[str, object]:
        simulator = self.env.simulator
        if simulator is None:
            raise RuntimeError("v0.5 manual simulator尚未reset。")
        action = self.input_state.action
        body = simulator.player.body
        velocity_x = float(body.velocity.x)
        opposite = (
            (action is Action.LEFT and velocity_x > 0.0)
            or (action is Action.RIGHT and velocity_x < 0.0)
        )
        if opposite:
            previous_velocity_x = velocity_x
            body.velocity = (0.0, body.velocity.y)
            self._event(
                "instant_direction_reversal",
                action=action.name,
                previous_velocity_x=previous_velocity_x,
            )

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
        "--horizontal-acceleration",
        type=_bounded_float("horizontal-acceleration", 100.0, 2000.0),
        default=420.0,
        help="接近最高速時的基礎加速度。",
    )
    parser.add_argument(
        "--startup-acceleration-multiplier",
        type=_bounded_float("startup-acceleration-multiplier", 1.0, 4.0),
        default=2.4,
        help="低速起步加速倍率；速度提高後會平滑衰減。",
    )
    parser.add_argument(
        "--acceleration-curve-exponent",
        type=_bounded_float("acceleration-curve-exponent", 0.5, 4.0),
        default=2.0,
    )
    parser.add_argument(
        "--air-control-multiplier",
        type=_bounded_float("air-control-multiplier", 0.1, 1.0),
        default=0.85,
    )
    parser.add_argument(
        "--max-horizontal-speed",
        type=_bounded_float("max-horizontal-speed", 50.0, 400.0),
        default=230.0,
    )
    parser.add_argument(
        "--release-deceleration",
        type=_bounded_float("release-deceleration", 50.0, 3000.0),
        default=960.0,
    )
    parser.add_argument(
        "--platform-width",
        type=_bounded_float("platform-width", 48.0, 120.0),
        default=72.0,
    )
    parser.add_argument(
        "--gravity",
        type=_bounded_float("gravity", 100.0, 800.0),
        default=320.0,
        help="向下重力大小；輸入正值即可。",
    )
    parser.add_argument(
        "--max-fall-speed",
        type=_bounded_float("max-fall-speed", 100.0, 800.0),
        default=420.0,
    )
    parser.add_argument(
        "--scroll-speed",
        type=_bounded_float("scroll-speed", 0.0, 150.0),
        default=80.0,
    )
    parser.add_argument("--list-scenarios", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_scenarios:
        for item in _normal_scenarios():
            print(f"{item.scenario_id} {item.name}: {item.title}")
        return 0

    session = ResponsiveManualSession(
        scenario=args.scenario,
        seed=args.seed,
        output_root=args.output_dir,
        display_fps=args.display_fps,
        show_debug=args.show_debug,
        record_video=args.record,
        horizontal_acceleration=args.horizontal_acceleration,
        startup_acceleration_multiplier=(
            args.startup_acceleration_multiplier
        ),
        acceleration_curve_exponent=args.acceleration_curve_exponent,
        air_control_multiplier=args.air_control_multiplier,
        max_horizontal_speed=args.max_horizontal_speed,
        release_deceleration=args.release_deceleration,
        platform_width=args.platform_width,
        gravity=args.gravity,
        max_fall_speed=args.max_fall_speed,
        scroll_speed=args.scroll_speed,
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
