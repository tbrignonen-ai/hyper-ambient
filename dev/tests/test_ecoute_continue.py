"""Capture continue segmentée (mains libres vrai) : VAD local, sans périphérique.

Patron repris de ``test_windows_audio.py`` : ``stream_factory`` injectable,
blocs int16 synthétiques. Aucun ``sounddevice``, aucun micro.
"""
from __future__ import annotations

import numpy as np

from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE


class _FluxSynthetique:
    """Même surface minimale qu'un InputStream : start / stop / close / pousser."""

    def __init__(self) -> None:
        self._callback = None
        self._demarre = False
        self.stops = 0
        self.closes = 0

    def __call__(self, callback):
        self._callback = callback
        return self

    def start(self) -> None:
        self._demarre = True

    def stop(self) -> None:
        self._demarre = False
        self.stops += 1

    def close(self) -> None:
        self.closes += 1

    def pousser(self, echantillons) -> None:
        if self._demarre and self._callback is not None:
            data = np.asarray(echantillons).reshape(-1)
            self._callback(data, data.size, None, None)


def _silence(ms: int) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    return np.zeros(n, dtype=np.int16)


def _parole(ms: int, amplitude: int = 8000) -> np.ndarray:
    """Signal voisé : 150 Hz + harmoniques, enveloppe variable (pas du DC)."""
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


def _duree_ms(trames) -> float:
    return 1000.0 * len(trames) * FRAME_SAMPLES / SAMPLE_RATE


def _energie(trames) -> float:
    if not trames:
        return 0.0
    return float(
        max(np.sqrt(np.mean(np.square(t.samples.astype(np.float64)))) for t in trames)
    )


def _nouvelle_capture(monkeypatch):
    monkeypatch.setenv("TURN_SILENCE_MS", "700")
    from native.hostagent.windows_audio import CaptureContinue

    flux = _FluxSynthetique()
    capture = CaptureContinue(stream_factory=flux)
    capture.start()
    flux.pousser(_silence(500))
    return capture, flux


def test_silence_continu_aucun_segment(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_silence(2000))
    assert capture.segment_pret() is False
    assert capture.prendre_segment() == []
    capture.stop()


def test_parole_puis_silence_un_segment_contenant_la_parole(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_parole(800))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    segment = capture.prendre_segment()
    assert capture.segment_pret() is False
    assert _energie(segment) > 0.05
    assert 700.0 <= _duree_ms(segment) <= 2000.0
    capture.stop()


def test_silence_court_300ms_ne_coupe_pas_le_tour(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_parole(500))
    flux.pousser(_silence(300))
    flux.pousser(_parole(500))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    premier = capture.prendre_segment()
    assert capture.segment_pret() is False
    assert capture.prendre_segment() == []
    assert _energie(premier) > 0.05
    assert _duree_ms(premier) >= 1000.0
    capture.stop()


def test_salve_100ms_jetee(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_parole(100))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is False
    assert capture.prendre_segment() == []
    capture.stop()


def test_suspendre_n_accumule_pas_reprendre_repart_propre(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_parole(300))
    capture.suspendre()
    flux.pousser(_parole(1200))
    capture.reprendre()
    flux.pousser(_silence(700))
    assert capture.segment_pret() is False
    flux.pousser(_parole(800))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    segment = capture.prendre_segment()
    assert 700.0 <= _duree_ms(segment) <= 2000.0
    capture.stop()


def test_segment_de_plus_de_15s_est_coupe(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_parole(16_000))
    assert capture.segment_pret() is True
    segment = capture.prendre_segment()
    duree = _duree_ms(segment)
    assert duree <= 15_020.0
    assert duree >= 14_900.0
    capture.stop()


def test_push_to_talk_start_stop_inchange(monkeypatch):
    """Le chemin PTT ne doit rien perdre : avant start / après stop ignorés."""
    from native.hostagent.windows_audio import PushToTalkCapture

    avant = np.full(FRAME_SAMPLES, 0.5, dtype=np.float32)
    pendant = np.full(SAMPLE_RATE, 0.25, dtype=np.float32)
    apres = np.full(FRAME_SAMPLES, -0.5, dtype=np.float32)

    flux = _FluxSynthetique()
    capture = PushToTalkCapture(stream_factory=flux)

    flux.pousser(avant)
    capture.start()
    flux.pousser(pendant)
    trames = capture.stop()
    flux.pousser(apres)

    assert flux.stops == 1
    assert flux.closes == 1
    assert len(trames) == SAMPLE_RATE // FRAME_SAMPLES
    attendu = np.full(FRAME_SAMPLES, 0.25, dtype=np.float32)
    for trame in trames:
        assert np.allclose(trame.samples, attendu)
        assert not np.allclose(trame.samples, 0.5)
        assert not np.allclose(trame.samples, -0.5)


def test_prendre_segment_ne_ferme_pas_le_flux(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    flux.pousser(_parole(800))
    flux.pousser(_silence(700))
    _ = capture.prendre_segment()
    assert flux.stops == 0
    assert flux.closes == 0
    flux.pousser(_parole(800))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    capture.stop()
