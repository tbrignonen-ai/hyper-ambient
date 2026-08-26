"""Trames audio 16 kHz / 20 ms et tampon circulaire entre périphérique et bus.

16 kHz mono float32 est ce que EARS (faster-whisper) et TURN (Silero VAD)
consomment. Une conversion implicite (int16 → float32) masquerait une
erreur de configuration du périphérique, et on ne s'en apercevrait qu'à
l'oreille : le dtype est donc exigé à la construction, jamais corrigé.

La trame de 20 ms (FRAME_SAMPLES = 320 à 16 kHz) vient d'ADR-016
« flux de trames de 20 ms ». Le tampon circulaire absorbe la gigue entre
le fil audio du périphérique, qui ne doit jamais attendre, et la boucle
événementielle qui consomme. Une perte est un fait à compter et à
remonter, pas un incident à masquer : NFR-01 (p95 mic_to_audible) se
mesure, et un tampon qui perd en silence rend la mesure fausse.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

SAMPLE_RATE = 16000
FRAME_SAMPLES = 320

# Même principe que EventBus._next_stamp (src.core.bus.event_bus) :
# time.monotonic, et math.nextafter si deux lectures tombent dans la
# même graduation. Non factorisé : ce module n'a pas le droit de
# modifier le bus, et extraire l'horloge ailleurs casserait le périmètre
# d'un seul fichier.
_last_stamp: float = float("-inf")


def _next_stamp() -> float:
    """Prochain stamp monotone, strictement supérieur au précédent."""
    global _last_stamp
    now = time.monotonic()
    if now <= _last_stamp:
        now = math.nextafter(_last_stamp, math.inf)
    _last_stamp = now
    return now


class InvalidFrameSizeError(Exception):
    """La trame n'a pas exactement FRAME_SAMPLES échantillons."""


class InvalidSampleDtypeError(Exception):
    """Les échantillons ne sont pas exactement numpy float32."""


@dataclass(frozen=True)
class AudioFrame:
    """Trame immuable : FRAME_SAMPLES float32 et stamp monotone."""

    samples: np.ndarray
    stamp: float = field(default_factory=_next_stamp)

    def __post_init__(self) -> None:
        if self.samples.dtype != np.float32:
            raise InvalidSampleDtypeError(self.samples.dtype)
        if self.samples.shape != (FRAME_SAMPLES,):
            raise InvalidFrameSizeError(self.samples.shape)


class FrameRing:
    """Tampon circulaire de capacité fixe entre le fil audio et le consommateur.

    push écrase la plus ancienne trame quand le tampon est plein et
    incrémente drop_count. pop_all rend les trames dans l'ordre
    chronologique puis vide le tampon. collections.deque(maxlen) écrase
    tout seul ; le compteur de pertes, lui, est tenu explicitement.
    """

    def __init__(self, capacity: int) -> None:
        self._buffer: deque[AudioFrame] = deque(maxlen=capacity)
        self.drop_count = 0

    def push(self, frame: AudioFrame) -> None:
        """Empile une trame ; si plein, écrase la plus ancienne et compte la perte."""
        if len(self._buffer) == self._buffer.maxlen:
            self.drop_count += 1
        self._buffer.append(frame)

    def pop_all(self) -> list[AudioFrame]:
        """Rend les trames dans l'ordre chronologique et vide le tampon."""
        frames = list(self._buffer)
        self._buffer.clear()
        return frames
