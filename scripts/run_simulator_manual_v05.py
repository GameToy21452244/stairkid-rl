"""Run the normal-platform v0.5 responsive-control manual candidate.

This entry point is intentionally manual-only. It keeps the frozen v0.3 and
v0.4 profiles untouched, but samples keyboard state and advances the simulator
at the fixed 60 Hz physics cadence. Opposite-direction input clears the old
horizontal velocity before the new direction accelerates, removing the
multi-step reverse-braking delay observed in the v0.4 manual sessions.
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

V05_VERSION = "ns-shaft-sim-v0.5-responsive-manual-candidate"
V05_OUTPUT_ROOT = DEFAULT_OUTPUT_ROOT / "v05"


def _normal_scenarios() -> tuple[ManualScenario, ...]:
    return tuple(item for item in list_manual_scenarios() if not item.special_platform)


class ResponsiveManualSession(ManualSimulatorSession):
    """Manual-only 60 Hz controller with immediate direction reversal."""

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
        air_control_multiplier: float,
        max_horizontal_speed: float,
        release_deceleration: float,
        scroll_speed: float,
    ) -> None:
        self._v05_values = {
            "horizontal_acceleration": float(horizontal_acceleration),
            "air_control_multiplier": float(air_control_multiplier),
            "max_horizontal_speed": float(max_horizontal_speed),
            "release_deceleration": float(release_deceleration),
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
            reverse_brake_multiplier=1.0,
            **self._v05_values,
        )
        self.env.config = config
        simulator.config = config
        self.calibration_profile = "v05"
        self._event(
            "v05_responsive_profile_installed",
            environment_version=V05_VERSION,
            control_hz=config.fps,
            physics_hz=config.physics_hz,
            instant_direction_reversal=True,
            **self._v05_values,
        )

    def _replace_environment(self, scenario: ManualScenario) -> None:
        # The shared builder only knows the frozen before/after profiles. Build
        # the v0.4 normal environment first, then opt into this isolated v0.5
        # manual controller again.
        self.calibration_profile = "after"
        super()._replace_environment(scenario)
        self._install_v05_profile()

    def next_scenario(self) -> None:
        normal = _normal_scenarios()
        current_index = next(
            index for index, item in enumerate(normal) if item.name == self.scenario.name
        )
        next_definition = normal[(current_index + 1) % len(normal)]
        self._event("scenario_switch", next_scenario=next_definition.name)
        self._replace_environment(next_definition)

    def toggle_calibration_profile(self) -> None:
        # Keep the candidate isolated. Use run_simulator_manual_test.py for the
        # v0.3/v0.4 comparison instead of mutating this v0.5 session in place.
        self._event("v05_profile_toggle_ignored", reason="profile_locked")

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
        return super().step_once()


def _bounded_float(
    name: str,
    minimum: float,
    maximum: float,
):
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
        default=560.0,
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
        air_control_multiplier=args.air_control_multiplier,
        max_horizontal_speed=args.max_horizontal_speed,
        release_deceleration=args.release_deceleration,
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
