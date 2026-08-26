"""Capture audio native du host-agent, sur l'hôte Windows.

Ce module vit ici, pas dans le conteneur, parce que Docker Desktop
Windows n'expose aucun périphérique audio : le conteneur tourne dans une
VM, sans ``/dev/snd`` et sans ALSA. ADR-006 en tire l'architecture à
deux composants — le cœur dans le conteneur, le host-agent sur l'hôte,
seul à toucher le micro et le haut-parleur.

Il n'a le droit de faire que ``audio.capture`` et ``audio.render``.
ADR-016 règle 2 : aucune primitive d'exécution, pas de shell, pas de
spawn, pas d'accès fichier arbitraire.

Asymétrie int16 / float32, intentionnelle
-----------------------------------------
Cette couche est au contact du matériel, qui rend typiquement de l'int16.
La conversion vers float32 normalisé dans [-1, 1] (division par 32768.0)
est donc légitime, et d'elle seule. ``AudioFrame``, en aval, refuse cette
conversion : un int16 qui arriverait jusqu'à lui ne peut être qu'une
erreur de configuration, et une conversion implicite la masquerait.
"""
from __future__ import annotations

import math
import time

import numpy as np

from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

# Même principe que src.hostagent.audio._next_stamp : time.monotonic, et
# math.nextafter si deux lectures tombent dans la même graduation.
_last_stamp: float = float("-inf")


def _next_stamp() -> float:
    """Prochain stamp monotone, strictement supérieur au précédent."""
    global _last_stamp
    now = time.monotonic()
    if now <= _last_stamp:
        now = math.nextafter(_last_stamp, math.inf)
    _last_stamp = now
    return now


def _vers_float32(echantillons) -> np.ndarray:
    """Convertit int16 → float32 ∈ [-1, 1] ; laisse le float32 intact."""
    arr = np.asarray(echantillons).reshape(-1)
    if arr.dtype == np.int16:
        return arr.astype(np.float32) / np.float32(32768.0)
    return np.ascontiguousarray(arr, dtype=np.float32)


def frames_from_samples(samples, stamper=None, leftover=None):
    """Découpe en trames de FRAME_SAMPLES. Un reste incomplet n'est pas émis.

    Le reliquat est conservé dans ``leftover`` (liste d'un tableau) pour
    le tour suivant. Sans ``leftover``, il est simplement écarté — jamais
    émis tronqué, ``AudioFrame`` le refuserait et une trame courte
    désalignerait le flux.
    """
    if stamper is None:
        stamper = _next_stamp
    convertis = _vers_float32(samples)
    if leftover:
        convertis = np.concatenate([leftover[0], convertis])
    n_complet = (convertis.size // FRAME_SAMPLES) * FRAME_SAMPLES
    trames = []
    for debut in range(0, n_complet, FRAME_SAMPLES):
        chunk = np.array(
            convertis[debut : debut + FRAME_SAMPLES],
            dtype=np.float32,
            copy=True,
        )
        trames.append(AudioFrame(samples=chunk, stamp=stamper()))
    reste = np.array(convertis[n_complet:], dtype=np.float32, copy=True)
    if leftover is not None:
        leftover[:] = [reste]
    return trames


def _default_stream_factory(callback):
    """Fabrique le flux d'entrée réel. Import paresseux de sounddevice."""
    import sounddevice as sd

    return sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        callback=callback,
    )


class PushToTalkCapture:
    """Capture appuyer-pour-parler : ne retient que ce qui arrive entre start et stop.

    Le matériel n'est jamais atteint depuis la logique : ``stream_factory``
    est injectable. Les tests y branchent une source synthétique.
    """

    def __init__(self, stream_factory=None) -> None:
        self._stream_factory = (
            stream_factory if stream_factory is not None else _default_stream_factory
        )
        self._stream = None
        self._trames: list[AudioFrame] = []
        self._leftover: list = [np.zeros(0, dtype=np.float32)]
        self._actif = False

    def _on_audio(self, indata, frames, time_info, status) -> None:
        if not self._actif:
            return
        self._trames.extend(
            frames_from_samples(indata, stamper=_next_stamp, leftover=self._leftover)
        )

    def start(self) -> None:
        """Ouvre le flux et commence à retenir les échantillons."""
        self._trames = []
        self._leftover = [np.zeros(0, dtype=np.float32)]
        self._actif = True
        self._stream = self._stream_factory(self._on_audio)
        self._stream.start()

    def stop(self) -> list[AudioFrame]:
        """Arrête le flux et rend les trames capturées depuis start()."""
        self._actif = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return self._trames


def _lister_peripheriques_entree() -> None:
    """Liste les périphériques d'entrée et celui qui serait choisi.

    N'ouvre aucun flux, ne capture rien, ne se connecte à rien :
    lecture de l'inventaire PortAudio seulement. Échoue proprement
    si sounddevice est absent.
    """
    try:
        import sounddevice as sd
    except ImportError:
        print(
            "sounddevice est absent : ce programme liste le matériel "
            "audio de l'hôte Windows et ne peut pas s'exécuter là où "
            "le paquet n'est pas installé (conteneur, CI)."
        )
        raise SystemExit(1)

    try:
        peripheriques = sd.query_devices()
        choisi = sd.query_devices(kind="input")
    except Exception as exc:
        print(f"Impossible d'interroger les périphériques audio : {exc}")
        raise SystemExit(1)

    print("Périphériques d'entrée disponibles :")
    for indice, peripherique in enumerate(peripheriques):
        if peripherique["max_input_channels"] > 0:
            print(f"  [{indice}] {peripherique['name']}")
    print(f"Périphérique qui serait choisi : {choisi['name']}")


if __name__ == "__main__":
    _lister_peripheriques_entree()
