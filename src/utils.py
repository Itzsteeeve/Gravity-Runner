from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any


def resource_path(relative_path: str) -> str:
    """
    Return path to bundled resource for PyInstaller.
    - When running from source, it returns path relative to current working dir.
    - When running from PyInstaller, it uses sys._MEIPASS.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _highscore_storage_dir() -> str:
    if os.name == "nt":
        # Windows packaged apps: for simplicity and to avoid env-taint warnings,
        # store under user's home directory.
        root = os.path.expanduser("~")
        return os.path.join(root, "GravityRunner")
    # Linux/macOS: use ~/.config
    return os.path.join(os.path.expanduser("~"), ".config", "GravityRunner")


def highscore_path() -> str:
    return os.path.join(_highscore_storage_dir(), "highscore.json")


def load_highscore() -> int:
    # Ephemeral mode: keep runtime-only values, do not persist between launches.
    return 0


def save_highscore(score: int) -> None:
    # Ephemeral mode: intentionally no-op.
    return


def profile_path() -> str:
    return os.path.join(_highscore_storage_dir(), "profile.json")


def load_profile() -> dict:
    """
    Lightweight local profile persistence for credits, skin ownership, and UI settings.
    """
    default = {
        "credits": 0,
        "owned_skin_ids": ["neo_core"],
        "equipped_skin_id": "neo_core",
        "settings": {
            "sound_enabled": True,
            "sfx_volume": 0.7,
            "fx_intensity": 1.0,
        },
    }
    # Ephemeral mode: always start from defaults, no disk reads.
    return default


def save_profile(profile: dict) -> None:
    # Ephemeral mode: intentionally no-op.
    return


@dataclass(frozen=True)
class Difficulty:
    speed_px_s: float
    gap_height_min: float
    gap_height_max: float
    gate_width: float
    gate_spacing_px: float


def difficulty_from_progress(progress: float) -> Difficulty:
    """
    progress: 0..1-ish (we clamp internally)
    Uses linear ramps so it stays predictable.
    """
    p = clamp(progress, 0.0, 1.0)
    speed = 360.0 + (620.0 - 360.0) * (p ** 1.15)
    gap_min = 270.0 - (270.0 - 170.0) * p
    gap_max = 330.0 - (330.0 - 270.0) * p
    gate_w = 52.0 + (58.0 - 52.0) * p
    spacing = 320.0 - (320.0 - 260.0) * p
    return Difficulty(
        speed_px_s=speed,
        gap_height_min=gap_min,
        gap_height_max=gap_max,
        gate_width=gate_w,
        gate_spacing_px=spacing,
    )

