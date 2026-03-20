from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Tuple

import pygame

from .config import (
    PLAYER_RADIUS,
)


@dataclass
class Gate:
    """
    A vertical obstacle with a vertical gap.

    In screen space (after camera offset):
    - There's a "wall" region across the full height except the gap.
    - If the player circle touches the wall area, they die.
    """

    x_world: float
    width: float
    gap_center_y: float
    gap_height: float
    wall_color: Tuple[int, int, int]
    outline_color: Tuple[int, int, int]
    spike_color: Tuple[int, int, int]
    kind: Literal["static", "moving", "phase", "pulse"] = "static"
    move_amp: float = 0.0
    move_speed: float = 0.0
    move_phase: float = 0.0

    def screen_x(self, camera_x: float) -> float:
        return self.x_world - camera_x

    def gap_bounds(self) -> Tuple[float, float]:
        top = self.gap_center_y - self.gap_height / 2.0
        bottom = self.gap_center_y + self.gap_height / 2.0
        return top, bottom

    def _current_gap_center(self, camera_x: float) -> float:
        if self.kind != "moving" or self.move_amp <= 0.0 or self.move_speed <= 0.0:
            if self.kind != "phase" or self.move_amp <= 0.0 or self.move_speed <= 0.0:
                return self.gap_center_y
            phase = self.move_phase + ((camera_x + self.x_world) * self.move_speed * 0.0022)
            idx = int((phase * 1.45) % 4.0)
            pattern = (-1.0, -0.2, 1.0, 0.1)
            return self.gap_center_y + self.move_amp * pattern[idx]
        # Deterministic movement tied to world/camera progression.
        phase = self.move_phase + ((camera_x + self.x_world) * self.move_speed * 0.0025)
        return self.gap_center_y + self.move_amp * math.sin(phase)

    def _gap_height_at(self, camera_x: float) -> float:
        if self.kind != "pulse" or self.move_speed <= 0.0:
            return self.gap_height
        phase = self.move_phase + ((camera_x + self.x_world) * self.move_speed * 0.0032)
        pulse = 0.5 + 0.5 * math.sin(phase)
        return self.gap_height * (0.72 + 0.22 * pulse)

    def _gap_bounds_at(self, camera_x: float) -> Tuple[float, float]:
        center = self._current_gap_center(camera_x)
        current_gap_height = self._gap_height_at(camera_x)
        top = center - current_gap_height / 2.0
        bottom = center + current_gap_height / 2.0
        return top, bottom

    def collides_circle(
        self,
        player_x_screen: float,
        player_y_screen: float,
        player_radius: float = PLAYER_RADIUS,
        camera_x: float = 0.0,
    ) -> bool:
        # Simplified collision:
        # If the circle overlaps the wall x-range and overlaps outside the gap area => dead.
        sx = self.screen_x(camera_x)

        half_w = self.width / 2.0
        wall_left = sx - half_w
        wall_right = sx + half_w

        if player_x_screen + player_radius < wall_left:
            return False
        if player_x_screen - player_radius > wall_right:
            return False

        gap_top, gap_bottom = self._gap_bounds_at(camera_x)

        # Circle overlaps gap area?
        overlaps_gap = not (player_y_screen - player_radius > gap_bottom or player_y_screen + player_radius < gap_top)
        if overlaps_gap:
            return False

        # Circle overlaps wall in x and not overlapping gap in y.
        return True

    def draw(self, surf: pygame.Surface, camera_x: float, floor_y: float, ceiling_y: float) -> None:
        sx = self.screen_x(camera_x)
        half_w = self.width / 2.0
        wall_left = sx - half_w
        wall_right = sx + half_w
        gap_top, gap_bottom = self._gap_bounds_at(camera_x)

        # Wall rectangles
        # Top wall: ceiling -> gap_top
        if gap_top > ceiling_y + 1:
            top_rect = pygame.Rect(wall_left, ceiling_y, self.width, gap_top - ceiling_y)
            pygame.draw.rect(surf, (*self.wall_color, 34), top_rect.inflate(8, 8), border_radius=10)
            pygame.draw.rect(surf, self.wall_color, top_rect, border_radius=6)
            self._draw_spikes(surf, wall_left, gap_top, up=True)

        # Bottom wall: gap_bottom -> floor
        if gap_bottom < floor_y - 1:
            bot_rect = pygame.Rect(wall_left, gap_bottom, self.width, floor_y - gap_bottom)
            pygame.draw.rect(surf, (*self.wall_color, 34), bot_rect.inflate(8, 8), border_radius=10)
            pygame.draw.rect(surf, self.wall_color, bot_rect, border_radius=6)
            self._draw_spikes(surf, wall_left, gap_bottom, up=False)

        # Neon inner outline to look nicer.
        pygame.draw.rect(
            surf,
            self.outline_color,
            pygame.Rect(wall_left + 2, max(ceiling_y, 0), self.width - 4, (floor_y - max(ceiling_y, 0))),
            width=2,
            border_radius=6,
        )

        # Highlight moving gates with a subtle animated line in the gap.
        if self.kind == "moving":
            mid = int((gap_top + gap_bottom) * 0.5)
            pygame.draw.line(
                surf,
                self.outline_color,
                (int(wall_left) + 4, mid),
                (int(wall_right) - 4, mid),
                2,
            )
        elif self.kind == "phase":
            y0 = int(gap_top + 4)
            y1 = int(gap_bottom - 4)
            x = int((wall_left + wall_right) * 0.5)
            pygame.draw.line(surf, self.outline_color, (x, y0), (x, y1), 2)
        elif self.kind == "pulse":
            mid = int((gap_top + gap_bottom) * 0.5)
            pygame.draw.line(
                surf,
                self.outline_color,
                (int(wall_left) + 6, mid),
                (int(wall_right) - 6, mid),
                3,
            )
            for i in range(2):
                y = int(mid + (-1 if i == 0 else 1) * 10)
                pygame.draw.line(
                    surf,
                    (*self.spike_color,),
                    (int(wall_left) + 10, y),
                    (int(wall_right) - 10, y),
                    2,
                )

    def _draw_spikes(self, surf: pygame.Surface, wall_left: float, y_edge: float, up: bool) -> None:
        # Simple triangle spikes along the wall edge.
        # up=True means spikes point up from the top wall.
        step = 10
        count = int(self.width // step) + 2
        base_w = self.width / count
        for i in range(count):
            x0 = wall_left + i * base_w
            x1 = x0 + base_w * 0.85
            if up:
                tip_y = y_edge - 14
                base_y = y_edge
            else:
                tip_y = y_edge + 14
                base_y = y_edge

            pts = [(x0, base_y), (x1, base_y), ((x0 + x1) / 2.0, tip_y)]
            pygame.draw.polygon(surf, self.spike_color, pts)

