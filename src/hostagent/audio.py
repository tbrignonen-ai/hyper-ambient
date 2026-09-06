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


class RechantillonneurContinu:
    """Convertit un flux d'un taux à l'autre en portant son état d'un bloc au suivant.

    MOUTH sort à 24 kHz par blocs de 80 ms ; le canal host-agent transporte du
    16 kHz. La conversion se faisait bloc par bloc avec ``librosa.resample``,
    qui est écrit pour un signal **complet** : il suppose du silence avant le
    premier échantillon et après le dernier, donc il remet ses bords à zéro à
    chaque appel. Appliqué à un flux découpé, il pose un transitoire à chaque
    couture. Mesuré le 6 septembre 2026 sur des chunks de 1920 échantillons :
    l'écart au signal de référence vaut 0,016 au bord d'un bloc contre 0,000 au
    milieu — un rapport de 237 000 — et culmine à 13 % du pic sur une phrase
    d'estelle. Douze coutures et demie par seconde, ce qui s'entend comme un
    hachurage : « des fois comme de la jitter, entrecoupé ».

    ``soxr.ResampleStream`` est fait pour ça : il garde la queue du filtre
    polyphase entre deux appels, si bien que la sortie concaténée est
    indiscernable du rechantillonnage du signal entier. C'est le contrat que
    fixe ``dev/tests/test_resample_continu.py``.

    Un rechantillonneur par flux, jamais partagé : l'état est la mémoire du
    filtre, et deux voix qui se le partageraient s'entendraient l'une l'autre.
    """

    def __init__(self, taux_entree: int, taux_sortie: int) -> None:
        self.taux_entree = int(taux_entree)
        self.taux_sortie = int(taux_sortie)
        self._flux = None
        if self.taux_entree != self.taux_sortie:
            self._ouvrir()

    def _ouvrir(self) -> None:
        import soxr

        # « HQ » est la qualité que librosa emploie par défaut ; on ne change
        # pas la couleur du rendu en même temps qu'on répare les coutures.
        self._flux = soxr.ResampleStream(
            self.taux_entree, self.taux_sortie, 1, dtype="float32", quality="HQ"
        )

    def pousser(self, pcm: np.ndarray) -> np.ndarray:
        """Convertit un bloc. La queue du filtre reste pour le bloc suivant."""
        if self._flux is None:
            return pcm
        bloc = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if bloc.size == 0:
            return np.zeros(0, dtype=np.float32)
        return np.asarray(self._flux.resample_chunk(bloc), dtype=np.float32).reshape(-1)

    def vider(self) -> np.ndarray:
        """Sort la queue retenue dans le filtre. À appeler en fin de flux.

        Sans ça, les derniers millisecondes d'une phrase restent dans le filtre
        et la fin de mot est coupée — le défaut inverse de celui qu'on répare.
        """
        if self._flux is None:
            return np.zeros(0, dtype=np.float32)
        reste = self._flux.resample_chunk(np.zeros(0, dtype=np.float32), last=True)
        return np.asarray(reste, dtype=np.float32).reshape(-1)

    def reinitialiser(self) -> None:
        """Repart d'un filtre vierge : un tour de parole ne colore pas le suivant."""
        if self.taux_entree != self.taux_sortie:
            self._ouvrir()
