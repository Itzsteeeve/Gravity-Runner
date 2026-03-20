from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from .config import (
    SPAWN_AHEAD_PX,
    DESPAWN_BEHIND_PX,
)
from .obstacles import Gate
from .utils import Difficulty, difficulty_from_progress
from .skins import SkinTheme


@dataclass
class LevelGenerator:
    seed: int
    gates: List[Gate]
    next_gate_x: float
    skin: SkinTheme
    difficulty_mode: str = "normal"
    last_lane: int = 0  # -1 top, +1 bottom, 0 unknown.
    difficulty_progress_multiplier: float = 1.0

    @staticmethod
    def create(seed: int, skin: SkinTheme, difficulty_progress_multiplier: float, difficulty_mode: str) -> "LevelGenerator":
        return LevelGenerator(
            seed=seed,
            gates=[],
            next_gate_x=900.0,
            last_lane=0,
            skin=skin,
            difficulty_progress_multiplier=difficulty_progress_multiplier,
            difficulty_mode=difficulty_mode,
        )

    def reset(self) -> None:
        self.gates.clear()
        self.next_gate_x = 900.0
        self.last_lane = 0

    def _choose_lane(self, rng: random.Random) -> int:
        # Alternate with a bias; keeps it learnable but varied.
        if self.last_lane == 0:
            lane = 1 if rng.random() < 0.5 else -1
        else:
            # 60% chance to alternate, 40% to stay.
            lane = -self.last_lane if rng.random() < 0.6 else self.last_lane
        self.last_lane = lane
        return lane

    def update(
        self,
        camera_x: float,
        ceiling_y: float,
        floor_y: float,
        event_name: str | None = None,
        event_strength: float = 0.0,
    ) -> None:
        progress = max(0.0, camera_x / 22000.0) * self.difficulty_progress_multiplier
        diff = difficulty_from_progress(progress)

        # Remove old gates.
        min_x_keep = camera_x - DESPAWN_BEHIND_PX
        self.gates = [g for g in self.gates if g.x_world >= min_x_keep]

        # Spawn ahead.
        max_x_want = camera_x + SPAWN_AHEAD_PX
        while self.next_gate_x < max_x_want:
            self._spawn_pattern(
                camera_x=self.next_gate_x,
                diff=diff,
                ceiling_y=ceiling_y,
                floor_y=floor_y,
                event_name=event_name,
                event_strength=event_strength,
            )

    def _spawn_pattern(
        self,
        camera_x: float,
        diff: Difficulty,
        ceiling_y: float,
        floor_y: float,
        event_name: str | None = None,
        event_strength: float = 0.0,
    ) -> None:
        rng = random.Random(self.seed + int(camera_x // 1))
        lane = self._choose_lane(rng)
        start_gate_i = len(self.gates)

        # Choose gap height based on current difficulty.
        gap_height = rng.uniform(diff.gap_height_min, diff.gap_height_max)

        # Keep gap center within safe bounds (with padding).
        padding = 70.0
        min_center = ceiling_y + padding + gap_height / 2.0
        max_center = floor_y - padding - gap_height / 2.0
        if min_center > max_center:
            # Fallback for very small spaces (shouldn't happen with our tuned config).
            center = (ceiling_y + floor_y) / 2.0
        else:
            upper_target = min_center
            lower_target = max_center
            # Bias lane toward the chosen lane target, but keep some randomness.
            if lane < 0:
                center = rng.uniform(min_center, (min_center + max_center) / 2.0)
            else:
                center = rng.uniform((min_center + max_center) / 2.0, max_center)

        gate_width = diff.gate_width
        event_strength = max(0.0, min(1.0, event_strength))
        if event_name == "pulse_gates":
            pulse = 0.76 + 0.18 * (0.5 + 0.5 * rng.random()) * (0.7 + 0.6 * event_strength)
            gap_height *= pulse
        if event_name == "pulse_gates":
            gate_width *= 1.08

        def spike_pick() -> tuple[int, int, int]:
            return self.skin.spike_a if rng.random() < 0.5 else self.skin.spike_b

        pattern_roll = rng.random()
        # Fair obstacle mixes by chosen difficulty.
        if self.difficulty_mode == "easy":
            # Mostly standard gates, occasional wide double gates.
            if pattern_roll < 0.20:
                g1 = Gate(
                    x_world=self.next_gate_x,
                    width=gate_width * 0.95,
                    gap_center_y=center,
                    gap_height=gap_height * 1.08,
                    wall_color=self.skin.gate_wall,
                    outline_color=self.skin.gate_outline,
                    spike_color=spike_pick(),
                )
                g2 = Gate(
                    x_world=self.next_gate_x + diff.gate_spacing_px * 0.42,
                    width=gate_width * 0.92,
                    gap_center_y=center + rng.uniform(-24.0, 24.0),
                    gap_height=gap_height * 1.10,
                    wall_color=self.skin.gate_wall,
                    outline_color=self.skin.gate_outline,
                    spike_color=spike_pick(),
                )
                self.gates.extend([g1, g2])
                spacing = rng.uniform(diff.gate_spacing_px * 1.25, diff.gate_spacing_px * 1.45)
            else:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width,
                        gap_center_y=center,
                        gap_height=gap_height,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.95, diff.gate_spacing_px * 1.18)

        elif self.difficulty_mode == "hard":
            # Frequent moving/tighter tunnel-like variants.
            if pattern_roll < 0.45:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width * 1.02,
                        gap_center_y=center,
                        gap_height=gap_height * rng.uniform(0.84, 0.92),
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                        kind="moving",
                        move_amp=rng.uniform(18.0, 34.0),
                        move_speed=rng.uniform(1.8, 2.6),
                        move_phase=rng.uniform(0.0, 6.28),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.78, diff.gate_spacing_px * 0.96)
            elif pattern_roll < 0.58:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width * 1.0,
                        gap_center_y=center,
                        gap_height=gap_height * 0.92,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                        kind="phase",
                        move_amp=rng.uniform(18.0, 28.0),
                        move_speed=rng.uniform(1.7, 2.4),
                        move_phase=rng.uniform(0.0, 6.28),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.84, diff.gate_spacing_px * 0.98)
            elif pattern_roll < 0.72:
                # Tunnel-like pair.
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width * 1.10,
                        gap_center_y=center,
                        gap_height=gap_height * 0.86,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x + diff.gate_spacing_px * 0.34,
                        width=gate_width * 1.05,
                        gap_center_y=center + rng.uniform(-18.0, 18.0),
                        gap_height=gap_height * 0.84,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.92, diff.gate_spacing_px * 1.05)
            else:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width,
                        gap_center_y=center,
                        gap_height=gap_height * 0.94,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.82, diff.gate_spacing_px * 1.0)
        else:
            # Normal: balanced set with conservative moving gates.
            if pattern_roll < 0.28:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width,
                        gap_center_y=center,
                        gap_height=gap_height,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                        kind="moving",
                        move_amp=rng.uniform(10.0, 24.0),
                        move_speed=rng.uniform(1.2, 1.8),
                        move_phase=rng.uniform(0.0, 6.28),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.9, diff.gate_spacing_px * 1.08)
            elif pattern_roll < 0.40:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width * 1.0,
                        gap_center_y=center,
                        gap_height=gap_height * 0.96,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                        kind="phase",
                        move_amp=rng.uniform(12.0, 22.0),
                        move_speed=rng.uniform(1.3, 1.9),
                        move_phase=rng.uniform(0.0, 6.28),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.95, diff.gate_spacing_px * 1.1)
            elif pattern_roll < 0.45:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width * 0.98,
                        gap_center_y=center,
                        gap_height=gap_height * 0.96,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x + diff.gate_spacing_px * 0.38,
                        width=gate_width * 0.96,
                        gap_center_y=center + rng.uniform(-20.0, 20.0),
                        gap_height=gap_height * 0.98,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 1.08, diff.gate_spacing_px * 1.24)
            else:
                self.gates.append(
                    Gate(
                        x_world=self.next_gate_x,
                        width=gate_width,
                        gap_center_y=center,
                        gap_height=gap_height,
                        wall_color=self.skin.gate_wall,
                        outline_color=self.skin.gate_outline,
                        spike_color=spike_pick(),
                    )
                )
                spacing = rng.uniform(diff.gate_spacing_px * 0.88, diff.gate_spacing_px * 1.1)

        if event_name == "pulse_gates":
            spacing *= 0.86 + 0.06 * (1.0 - event_strength)
            # Convert newly spawned gates into pulse gates for strong visual/gameplay identity.
            for g in self.gates[start_gate_i:]:
                if g.kind == "moving":
                    continue
                g.kind = "pulse"
                g.move_speed = rng.uniform(2.2, 3.4)
                g.move_phase = rng.uniform(0.0, 6.28)
        self.next_gate_x += spacing

