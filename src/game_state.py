from __future__ import annotations

from enum import Enum, auto


class GamePhase(Enum):
    menu = auto()
    paused = auto()
    running = auto()
    game_over = auto()

