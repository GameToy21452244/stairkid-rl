from __future__ import annotations

import pymunk


class SimulatorPlayer:
    def __init__(
        self,
        *,
        width: float,
        height: float,
        position: tuple[float, float],
    ) -> None:
        self.width = float(width)
        self.height = float(height)
        mass = 1.0
        moment = pymunk.moment_for_box(mass, (self.width, self.height))
        self.body = pymunk.Body(mass, moment)
        self.body.position = position
        self.shape = pymunk.Poly.create_box(
            self.body,
            (self.width, self.height),
        )
        self.shape.friction = 0.0
        self.shape.elasticity = 0.0
