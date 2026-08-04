from __future__ import annotations

import numpy as np

from .physics import ShaftSimulator


class SimulatorRenderer:
    def __init__(self) -> None:
        self._screen = None
        self._clock = None

    @staticmethod
    def rgb_array(
        simulator: ShaftSimulator,
        diagnostics: dict[str, object] | None = None,
    ) -> np.ndarray:
        config = simulator.config
        frame = np.full((config.height, config.width, 3), 12, dtype=np.uint8)
        play_left = int(round(config.effective_playfield_left))
        play_right = int(round(config.effective_playfield_right))
        play_top = int(round(config.effective_playfield_top))
        play_bottom = int(round(config.effective_playfield_bottom))
        frame[play_top:play_bottom, play_left:play_right] = (8, 18, 54)
        wall_color = (150, 185, 205)
        frame[play_top:play_bottom, play_left : play_left + 4] = wall_color
        frame[play_top:play_bottom, play_right - 4 : play_right] = wall_color
        frame[play_bottom - 4 : play_bottom, play_left:play_right] = wall_color
        hazard_bottom = int(round(config.effective_top_hazard_bottom))
        if hazard_bottom > play_top:
            frame[play_top : play_top + 4, play_left:play_right] = wall_color
            tooth_width = 16
            for x in range(play_left, play_right):
                phase = (x - play_left) % tooth_width
                tooth_height = int(
                    round(
                        (hazard_bottom - play_top)
                        * (1.0 - abs(phase - tooth_width / 2) / (tooth_width / 2))
                    )
                )
                if tooth_height > 0:
                    frame[play_top : play_top + tooth_height, x] = wall_color
        for platform in simulator.platforms:
            left = max(0, int(round(platform.left)))
            right = min(config.width, int(round(platform.right)))
            top = max(0, int(round(config.height - platform.top)))
            bottom = min(
                config.height,
                top + max(1, int(round(platform.height))),
            )
            if left < right and top < bottom:
                colors = {
                    "spikes": (205, 55, 65),
                    "conveyor_left": (55, 145, 215),
                    "conveyor_right": (125, 85, 215),
                    "spring": (235, 155, 45),
                    "flipping": (
                        (45, 190, 190)
                        if simulator.platform_is_active(platform)
                        else (70, 70, 82)
                    ),
                }
                color = colors.get(platform.kind, (80, 190, 110))
                frame[top:bottom, left:right] = color
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
        if config.enable_health:
            segment_width = 8
            gap = 2
            total_width = (
                config.max_health_segments * segment_width
                + (config.max_health_segments - 1) * gap
            )
            start_x = max(4, config.width - total_width - 6)
            start_y = config.height - 14
            for index in range(config.max_health_segments):
                left = start_x + index * (segment_width + gap)
                color = (
                    (220, 55, 70)
                    if index < simulator.health_segments
                    else (65, 35, 40)
                )
                frame[start_y : start_y + 8, left : left + segment_width] = color
        if diagnostics:
            import pygame

            if not pygame.font.get_init():
                pygame.font.init()
            surface = pygame.surfarray.make_surface(
                np.transpose(frame, (1, 0, 2))
            )
            font = pygame.font.Font(None, 17)
            lines = [
                f"action={diagnostics.get('action')} "
                f"p/q={diagnostics.get('action_values')}",
                f"target={diagnostics.get('target')} "
                f"floor={diagnostics.get('floor')} "
                f"reward={diagnostics.get('reward')}",
                f"x/y={diagnostics.get('x_y')} "
                f"vx/vy={diagnostics.get('vx_vy')}",
                f"hz={diagnostics.get('control_hz')} "
                f"terminal={diagnostics.get('terminal_reason')}",
                f"components={diagnostics.get('reward_components')}",
            ]
            pygame.draw.rect(surface, (0, 0, 0), (4, 4, 626, 78))
            for index, line in enumerate(lines):
                surface.blit(font.render(line, True, (240, 240, 240)), (8, 7 + index * 14))
            frame = np.transpose(pygame.surfarray.array3d(surface), (1, 0, 2))
        return frame

    def human(
        self,
        simulator: ShaftSimulator,
        diagnostics: dict[str, object] | None = None,
    ) -> None:
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
        frame = self.rgb_array(simulator, diagnostics)
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
