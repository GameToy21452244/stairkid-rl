from __future__ import annotations

from ..simulator.state import ShaftEnvConfig, SimulatorStep


class SimulatorRewardCalculator:
    def __init__(self, config: ShaftEnvConfig) -> None:
        self.config = config
        self.last_components: dict[str, float] = {}

    def calculate(self, result: SimulatorStep) -> float:
        components = {
            "step_penalty": -self.config.step_penalty,
            "landing_reward": 0.0,
            "floor_reward": 0.0,
            "death_penalty": 0.0,
        }
        if "landed" in result.events:
            components["landing_reward"] = self.config.landing_reward
        if "floor_descended" in result.events:
            components["floor_reward"] = self.config.floor_reward
        if result.terminated:
            components["death_penalty"] = -self.config.death_penalty
        self.last_components = components
        return float(sum(components.values()))
