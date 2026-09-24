"""VAD bande de voix : RMS + concentration spectrale. Aucun périphérique."""
from __future__ import annotations

import numpy as np

from src.hostagent.audio import SAMPLE_RATE


class _FluxSynthetique:
    """Même surface minimale qu'un InputStream : start / stop / close / pousser."""

    def __init__(self) -> None:
        self._callback = None
        self._demarre = False

    def __call__(self, callback):
        self._callback = callback
        return self

    def start(self) -> None:
        self._demarre = True

    def stop(self) -> None:
        self._demarre = False

    def close(self) -> None:
        pass

    def pousser(self, echantillons) -> None:
        if self._demarre and self._callback is not None:
            data = np.asarray(echantillons).reshape(-1)
            self._callback(data, data.size, None, None)


def _rms(echantillons: np.ndarray) -> float:
    arr = np.asarray(echantillons, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(arr))))


def _au_rms(signal: np.ndarray, cible: float) -> np.ndarray:
    actuel = _rms(signal)
    if actuel <= 0.0:
        return np.zeros(signal.size, dtype=np.int16)
    scaled = signal.astype(np.float64) * (cible / actuel)
    return np.clip(scaled, -32767, 32767).astype(np.int16)


def _voix(ms: int, amplitude: int = 8000) -> np.ndarray:
    """Sinusoïde 150 Hz + harmoniques, enveloppe variable (signal voisé)."""
    n = int(SAMPLE_RATE * ms / 1000.0)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    signal = np.zeros(n, dtype=np.float64)
    for harm in range(1, 12):
        signal += (1.0 / harm) * np.sin(2.0 * np.pi * 150.0 * harm * t)
    enveloppe = 0.65 + 0.35 * np.sin(2.0 * np.pi * 3.0 * t)
    signal *= enveloppe
    pic = np.max(np.abs(signal)) or 1.0
    scaled = np.clip(signal / pic * amplitude, -32767, 32767)
    return scaled.astype(np.int16)


def _bruit_blanc(ms: int, rms_cible: float) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    brut = np.random.default_rng(0).standard_normal(n)
    return _au_rms(brut, rms_cible)


def _sinus(ms: int, hz: float, rms_cible: float) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    return _au_rms(np.sin(2.0 * np.pi * hz * t), rms_cible)


def _silence(ms: int) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    return np.zeros(n, dtype=np.int16)


def _nouvelle_capture(monkeypatch):
    monkeypatch.setenv("TURN_SILENCE_MS", "700")
    from native.hostagent.windows_audio import CaptureContinue

    flux = _FluxSynthetique()
    capture = CaptureContinue(stream_factory=flux)
    capture.start()
    flux.pousser(_silence(500))
    return capture, flux


def test_sinusoide_voisee_compte_comme_parole(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_voix(1200))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    assert capture.prendre_segment()
    capture.stop()


def test_bruit_blanc_meme_rms_ne_compte_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    voix = _voix(1200)
    flux.pousser(_bruit_blanc(1200, _rms(voix)))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is False
    capture.stop()


def test_sinusoide_50hz_meme_rms_ne_compte_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    voix = _voix(1200)
    flux.pousser(_sinus(1200, 50.0, _rms(voix)))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is False
    capture.stop()


def test_sinusoide_6000hz_meme_rms_ne_compte_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    voix = _voix(1200)
    flux.pousser(_sinus(1200, 6000.0, _rms(voix)))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is False
    capture.stop()


def test_silence_ne_compte_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_silence(2000))
    assert capture.segment_pret() is False
    capture.stop()


def test_segment_voise_300ms_rejete_sous_plancher(monkeypatch):
    # Plancher ramené de 700 à 400 ms le 24/09 : « Hyper ambiant » seul dure
    # 480 ms et doit passer. Une salve de 300 ms reste jetée.
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_voix(300))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is False
    capture.stop()


def test_segment_voise_1200ms_puis_silence_un_segment(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_voix(1200))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    premier = capture.prendre_segment()
    assert premier
    assert capture.segment_pret() is False
    assert capture.prendre_segment() == []
    capture.stop()
