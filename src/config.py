from __future__ import annotations

# Base logical resolution. We render to this surface and scale to the actual window size.
LOGICAL_WIDTH = 900
LOGICAL_HEIGHT = 600

FPS = 60
TITLE = "Gravity Runner"

# Player
PLAYER_RADIUS = 16
PLAYER_X = 240  # Screen space; camera moves instead of player.

# Physics
GRAVITY_PX_S2 = 2400.0
BOUNCE_DAMPING = 0.0  # For a clean Geometry-Dash-like feel.

# Input
FLIP_COOLDOWN_S = 0.09  # Prevents accidental double-flips.

# World / scrolling
START_SPEED_PX_S = 360.0
MAX_SPEED_PX_S = 620.0

SPAWN_AHEAD_PX = 1200  # How far ahead gates are generated.
DESPAWN_BEHIND_PX = 250

# Gates (obstacles)
GATE_WIDTH_PX = 58
GAP_HEIGHT_MIN = 170
GAP_HEIGHT_MAX = 270
GAP_CENTER_Y_PADDING = 80  # Keep gaps away from extreme edges.

# Score
SCORE_DIVISOR_PX = 10  # Higher divisor -> slower scoring.

# Visuals
NEON_ACCENT = (92, 255, 214)
NEON_PINK = (255, 74, 200)
NEON_BLUE = (92, 154, 255)
TEXT_MAIN = (230, 252, 255)
BG_DARK = (6, 8, 14)

