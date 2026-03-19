from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame

from .config import BG_DARK


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    life: float
    max_life: float
    color: Tuple[int, int, int]

    def update(self, dt: float) -> None:
        self.life -= dt
        # Light gravity to make it feel "alive"
        self.vy += 900.0 * dt * 0.15
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surf: pygame.Surface) -> None:
        if self.life <= 0:
            return
        t = max(0.0, min(1.0, self.life / self.max_life))
        a = int(255 * t)

        # Alpha requires a per-particle temporary surface; keep it minimal.
        r = max(1.0, self.radius)
        size = int(2 * r + 2)
        tmp = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (*self.color, a), (size // 2, size // 2), int(r))
        surf.blit(tmp, (self.x - r, self.y - r))


class ParticleSystem:
    def __init__(self) -> None:
        self._particles: List[Particle] = []

    def emit_flip(self, x: float, y: float, base_color: Tuple[int, int, int]) -> None:
        # Small burst indicating direction change.
        for _ in range(26):
            ang = random.uniform(0, math.tau)
            speed = random.uniform(120.0, 420.0)
            vx = math.cos(ang) * speed
            vy = math.sin(ang) * speed
            self._particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    radius=random.uniform(1.2, 3.2),
                    life=random.uniform(0.18, 0.35),
                    max_life=0.35,
                    color=base_color,
                )
            )

    def emit_death(self, x: float, y: float, base_color: Tuple[int, int, int]) -> None:
        for _ in range(85):
            ang = random.uniform(0, math.tau)
            speed = random.uniform(150.0, 780.0)
            vx = math.cos(ang) * speed
            vy = math.sin(ang) * speed
            radius = random.uniform(1.4, 4.2)
            life = random.uniform(0.25, 0.65)
            self._particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    radius=radius,
                    life=life,
                    max_life=life,
                    color=base_color,
                )
            )

    def update(self, dt: float) -> None:
        for p in self._particles:
            p.update(dt)
        self._particles = [p for p in self._particles if p.life > 0]

    def draw(self, surf: pygame.Surface) -> None:
        for p in self._particles:
            p.draw(surf)

