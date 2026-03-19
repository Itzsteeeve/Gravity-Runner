from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class SkinTheme:
    # Player colors
    player_down: Color  # gravity points down
    player_up: Color  # gravity points up
    accent: Color

    # Gate colors
    gate_wall: Color
    gate_outline: Color
    spike_a: Color
    spike_b: Color


@dataclass(frozen=True)
class SkinDef:
    id: str
    name: str
    description: str
    price_credits: int
    theme: SkinTheme


SKINS: List[SkinDef] = [
    SkinDef(
        id="neo_core",
        name="Neo Core",
        description="Default neon setup.",
        price_credits=0,
        theme=SkinTheme(
            player_down=(92, 154, 255),  # NEON_BLUE
            player_up=(255, 74, 200),  # NEON_PINK
            accent=(92, 255, 214),  # NEON_ACCENT
            gate_wall=(92, 154, 255),
            gate_outline=(92, 255, 214),
            spike_a=(255, 74, 200),
            spike_b=(92, 154, 255),
        ),
    ),
    SkinDef(
        id="aqua_pulse",
        name="Aqua Pulse",
        description="Cold gates, hotter glow.",
        price_credits=10_000,
        theme=SkinTheme(
            player_down=(80, 220, 255),
            player_up=(255, 110, 210),
            accent=(92, 255, 214),
            gate_wall=(80, 220, 255),
            gate_outline=(92, 255, 214),
            spike_a=(255, 110, 210),
            spike_b=(80, 220, 255),
        ),
    ),
    SkinDef(
        id="magenta_rift",
        name="Magenta Rift",
        description="More contrast, heavier punch.",
        price_credits=20_000,
        theme=SkinTheme(
            player_down=(145, 90, 255),
            player_up=(255, 74, 200),
            accent=(180, 255, 100),
            gate_wall=(145, 90, 255),
            gate_outline=(180, 255, 100),
            spike_a=(255, 74, 200),
            spike_b=(145, 90, 255),
        ),
    ),
    SkinDef(
        id="sunset_chrome",
        name="Sunset Chrome",
        description="Golden speed, neon fire.",
        price_credits=50_000,
        theme=SkinTheme(
            player_down=(255, 170, 70),
            player_up=(255, 74, 200),
            accent=(92, 255, 214),
            gate_wall=(255, 170, 70),
            gate_outline=(92, 255, 214),
            spike_a=(255, 74, 200),
            spike_b=(255, 170, 70),
        ),
    ),
    SkinDef(
        id="void_prism",
        name="Void Prism",
        description="Premium high-contrast legendary neon.",
        price_credits=100_000,
        theme=SkinTheme(
            player_down=(158, 244, 255),
            player_up=(255, 124, 230),
            accent=(255, 234, 120),
            gate_wall=(128, 102, 255),
            gate_outline=(255, 234, 120),
            spike_a=(255, 124, 230),
            spike_b=(158, 244, 255),
        ),
    ),
]


def skins_by_id() -> Dict[str, SkinDef]:
    return {s.id: s for s in SKINS}


def default_skin_id() -> str:
    return "neo_core"

