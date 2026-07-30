from __future__ import annotations

from dataclasses import dataclass

import pymunk


@dataclass
class SimulatorPlatform:
    floor_index: int
    body: pymunk.Body
    shape: pymunk.Poly
    width: float
    height: float

    @classmethod
    def create(
        cls,
        *,
        floor_index: int,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
    ) -> "SimulatorPlatform":
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = (center_x, center_y)
        shape = pymunk.Poly.create_box(body, (width, height))
        # v0 uses an explicit one-way crossing test. Sensor shapes keep Pymunk
        # state inspectable without creating a two-way floor collision.
        shape.sensor = True
        return cls(floor_index, body, shape, width, height)

    @property
    def center_x(self) -> float:
        return float(self.body.position.x)

    @property
    def center_y(self) -> float:
        return float(self.body.position.y)

    @property
    def left(self) -> float:
        return self.center_x - self.width / 2

    @property
    def right(self) -> float:
        return self.center_x + self.width / 2

    @property
    def top(self) -> float:
        return self.center_y + self.height / 2
