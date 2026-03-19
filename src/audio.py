from __future__ import annotations

import array
import math
from dataclasses import dataclass

import pygame


def _pcm16_from_samples(samples: list[float]) -> bytes:
    # Convert float -1..1 to int16 PCM little-endian.
    pcm = array.array("h")
    for s in samples:
        v = int(max(-1.0, min(1.0, s)) * 32767)
        pcm.append(v)
    return pcm.tobytes()


def _make_chirp(
    *,
    f0: float,
    f1: float,
    duration_s: float,
    volume: float,
    sample_rate: int = 44100,
) -> bytes:
    n = max(1, int(duration_s * sample_rate))
    out: list[float] = []
    for i in range(n):
        t = i / sample_rate
        k = t / duration_s if duration_s > 0 else 1.0
        freq = f0 + (f1 - f0) * k
        # Exponential-ish decay envelope.
        env = (1.0 - k) ** 1.6
        s = math.sin(2.0 * math.pi * freq * t) * env * volume
        out.append(s)
    return _pcm16_from_samples(out)


def _make_noise_burst(
    *,
    duration_s: float,
    volume: float,
    sample_rate: int = 44100,
) -> bytes:
    # Deterministic LCG noise (avoid Python random import).
    n = max(1, int(duration_s * sample_rate))
    x = 123456789
    out: list[float] = []
    for i in range(n):
        # LCG: x = (a*x + c) mod m
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        r = (x / 0x7FFFFFFF) * 2.0 - 1.0
        k = i / n
        env = (1.0 - k) ** 1.8
        s = r * env * volume
        out.append(s)
    return _pcm16_from_samples(out)


@dataclass
class SfxBank:
    flip: pygame.mixer.Sound
    death: pygame.mixer.Sound

    @staticmethod
    def create() -> "SfxBank":
        # If mixer can't init (no audio device), callers should catch.
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        sample_rate = 44100
        flip_bytes = _make_chirp(f0=420.0, f1=950.0, duration_s=0.08, volume=0.35, sample_rate=sample_rate)
        # “Death”: a noisy pop + low chirp layered by concatenation would be longer;
        # instead we keep it short and punchy.
        death_noise = _make_noise_burst(duration_s=0.26, volume=0.55, sample_rate=sample_rate)
        death_bytes = death_noise

        flip = pygame.mixer.Sound(buffer=flip_bytes)
        death = pygame.mixer.Sound(buffer=death_bytes)
        return SfxBank(flip=flip, death=death)

    def play_flip(self, volume: float) -> None:
        v = max(0.0, min(1.0, volume))
        self.flip.set_volume(v)
        self.flip.play()

    def play_death(self, volume: float) -> None:
        v = max(0.0, min(1.0, volume))
        self.death.set_volume(v)
        self.death.play()

