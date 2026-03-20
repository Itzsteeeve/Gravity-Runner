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
    contact_release_s: float = 0.0
    contact_boundary: int = 0  # -1 ceiling, +1 floor, 0 none

    def flip_gravity(self) -> None:
        self.gravity_sign *= -1.0

    def reset(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.vy = 0.0
        self.gravity_sign = 1.0
        self.contact_release_s = 0.0
        self.contact_boundary = 0

    def update(self, dt: float, ceiling_y: float, floor_y: float, gravity_scale: float = 1.0) -> None:
        if self.contact_release_s > 0.0:
            self.contact_release_s = max(0.0, self.contact_release_s - dt)
        # Gravity acceleration in screen coordinates.
        self.vy += GRAVITY_PX_S2 * self.gravity_sign * max(0.2, gravity_scale) * dt
        self.y += self.vy * dt

        # Collide with bounds (simple "ground" and "ceiling").
        # If gravity points down, the relevant boundary is the floor; if up, ceiling.
        if self.gravity_sign > 0.0:
            # Floor is at larger y.
            if self.y + PLAYER_RADIUS > floor_y:
                penetration = (self.y + PLAYER_RADIUS) - floor_y
                self.y = floor_y - PLAYER_RADIUS - max(0.0, penetration)
                # Avoid sticky contact: enforce outward velocity for a short grace period.
                rebound = -self.vy * BOUNCE_DAMPING
                self.vy = min(rebound, -125.0)
                self.contact_release_s = 0.055
                self.contact_boundary = 1
            elif self.contact_boundary == 1 and self.contact_release_s > 0.0 and self.y + PLAYER_RADIUS >= floor_y - 0.75:
                self.vy = min(self.vy, -125.0)
        else:
            if self.y - PLAYER_RADIUS < ceiling_y:
                penetration = ceiling_y - (self.y - PLAYER_RADIUS)
                self.y = ceiling_y + PLAYER_RADIUS + max(0.0, penetration)
                # Avoid sticky contact: enforce outward velocity for a short grace period.
                rebound = -self.vy * BOUNCE_DAMPING
                self.vy = max(rebound, 125.0)
                self.contact_release_s = 0.055
                self.contact_boundary = -1
            elif self.contact_boundary == -1 and self.contact_release_s > 0.0 and self.y - PLAYER_RADIUS <= ceiling_y + 0.75:
                self.vy = max(self.vy, 125.0)
        if self.contact_release_s <= 0.0:
            self.contact_boundary = 0

        # Keep y in hard bounds even if something goes odd.
        self.y = clamp(self.y, ceiling_y + PLAYER_RADIUS, floor_y - PLAYER_RADIUS)

