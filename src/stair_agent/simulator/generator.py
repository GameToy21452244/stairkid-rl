from __future__ import annotations

import numpy as np

from .platform import SimulatorPlatform
from .state import ShaftEnvConfig


def generate_platforms(
    config: ShaftEnvConfig,
    rng: np.random.Generator,
) -> list[SimulatorPlatform]:
    platforms: list[SimulatorPlatform] = []
    starting_y = 96.0
    center_x = config.width / 2
    for floor_index in range(config.platform_count):
        if floor_index:
            center_x += float(
                rng.uniform(
                    -config.max_platform_shift,
                    config.max_platform_shift,
                )
            )
            margin = config.platform_width / 2 + 8
            center_x = float(np.clip(center_x, margin, config.width - margin))
        platforms.append(
            SimulatorPlatform.create(
                floor_index=floor_index,
                center_x=center_x,
                center_y=starting_y
                - floor_index * config.platform_spacing,
                width=config.platform_width,
                height=config.platform_height,
            )
        )
    return platforms
