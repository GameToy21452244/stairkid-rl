from __future__ import annotations

import numpy as np

from .physics import ShaftSimulator


class SimulatorRenderer:
    def __init__(self) -> None:
        self._screen = None
        self._clock = None

    @staticmethod
    def rgb_array(simulator: ShaftSimulator) -> np.ndarray:
        config = simulator.config
        frame = np.full((config.height, config.width, 3), 18, dtype=np.uint8)
        for platform in simulator.platforms:
            left = max(0, int(round(platform.left)))
            right = min(config.width, int(round(platform.right)))
            top = max(0, int(round(config.height - platform.top)))
            bottom = min(
                config.height,
                top + max(1, int(round(platform.height))),
            )
            if left < right and top < bottom:
                frame[top:bottom, left:right] = (80, 190, 110)
        player = simulator.player
        left = max(0, int(round(player.body.position.x - player.width / 2)))
        right = min(
            config.width,
            int(round(player.body.position.x + player.width / 2)),
        )
        top = max(
            0,
            int(
                round(
                    config.height
                    - (player.body.position.y + player.height / 2)
                )
            ),
        )
        bottom = min(
            config.height,
            top + max(1, int(round(player.height))),
        )
        if left < right and top < bottom:
            frame[top:bottom, left:right] = (235, 205, 70)
        return frame

    def human(self, simulator: ShaftSimulator) -> None:
        import pygame

        if self._screen is None:
            pygame.init()
            self._screen = pygame.display.set_mode(
                (simulator.config.width, simulator.config.height)
            )
            pygame.display.set_caption("NS-SHAFT Simulator v0")
            self._clock = pygame.time.Clock()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        frame = self.rgb_array(simulator)
        surface = pygame.surfarray.make_surface(np.transpose(frame, (1, 0, 2)))
        self._screen.blit(surface, (0, 0))
        pygame.display.flip()
        self._clock.tick(simulator.config.fps)

    def close(self) -> None:
        if self._screen is not None:
            import pygame

            pygame.display.quit()
            pygame.quit()
        self._screen = None
        self._clock = None
