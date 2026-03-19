from __future__ import annotations

from dataclasses import dataclass

from .config import (
    BOUNCE_DAMPING,
    GRAVITY_PX_S2,
    PLAYER_RADIUS,
)
from .utils import clamp


@dataclass
class Player:
    x: float
    y: float
    vy: float = 0.0
    gravity_sign: float = 1.0  # +1 means down, -1 means up.

    def flip_gravity(self) -> None:
        self.gravity_sign *= -1.0

    def reset(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.vy = 0.0
        self.gravity_sign = 1.0

    def update(self, dt: float, ceiling_y: float, floor_y: float) -> None:
        # Gravity acceleration in screen coordinates.
        self.vy += GRAVITY_PX_S2 * self.gravity_sign * dt
        self.y += self.vy * dt

        # Collide with bounds (simple "ground" and "ceiling").
        # If gravity points down, the relevant boundary is the floor; if up, ceiling.
        if self.gravity_sign > 0.0:
            # Floor is at larger y.
            if self.y + PLAYER_RADIUS > floor_y:
                self.y = floor_y - PLAYER_RADIUS
                # Avoid "sticky" contact: push velocity slightly away from the boundary.
                rebound = -self.vy * BOUNCE_DAMPING
                self.vy = min(rebound, -35.0)
        else:
            if self.y - PLAYER_RADIUS < ceiling_y:
                self.y = ceiling_y + PLAYER_RADIUS
                # Avoid "sticky" contact: push velocity slightly away from the boundary.
                rebound = -self.vy * BOUNCE_DAMPING
                self.vy = max(rebound, 35.0)

        # Keep y in hard bounds even if something goes odd.
        self.y = clamp(self.y, ceiling_y + PLAYER_RADIUS, floor_y - PLAYER_RADIUS)

