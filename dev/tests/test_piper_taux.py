"""Tom sort à 44 100 Hz ; siwis et upmc à 22 050. Le pipeline MOUTH doit
annoncer un seul taux, sinon un chemin qui oublie `tts.sample_rate` lit
le PCM deux fois trop lent — haché, entrecoupé.

Aucun modèle ONNX : sinus et arithmétique.
"""
from __future__ import annotations

import asyncio

import numpy as np
import pytest

from src.mouth.piper_tts import PIPELINE_RATE, PiperTTS, ramener_au_taux_pipeline

TAUX_TOM = 44100


def _sinus(duree_s: float, taux: int, freq: float = 440.0) -> np.ndarray:
    t = np.arange(int(taux * duree_s), dtype=np.float64) / taux
    return (np.sin(2 * np.pi * freq * t) * 12000).astype(np.int16)


def test_taux_identique_ne_touche_pas_le_signal():
    source = _sinus(0.2, PIPELINE_RATE)
    assert np.array_equal(ramener_au_taux_pipeline(source, PIPELINE_RATE), source)


def test_tableau_vide_reste_vide():
    vide = np.zeros(0, dtype=np.int16)
    assert ramener_au_taux_pipeline(vide, TAUX_TOM).size == 0


def test_tom_44100_dure_pareil_a_22050():
    duree = 0.5
    source = _sinus(duree, TAUX_TOM)
    sortie = ramener_au_taux_pipeline(source, TAUX_TOM)
    assert sortie.dtype == np.int16
    assert abs(len(sortie) / PIPELINE_RATE - duree) < 0.01


def test_tom_44100_garde_la_fondamentale():
    source = _sinus(1.0, TAUX_TOM, freq=220.0)
    sortie = ramener_au_taux_pipeline(source, TAUX_TOM)
    x = sortie.astype(np.float32) - float(np.mean(sortie))
    ac = np.correlate(x, x, "full")[len(x) - 1 :]
    lo, hi = int(PIPELINE_RATE / 400), int(PIPELINE_RATE / 70)
    fondamentale = float(PIPELINE_RATE / (lo + int(np.argmax(ac[lo:hi]))))
    assert fondamentale == pytest.approx(220.0, rel=0.03)


class _Chunk:
    def __init__(self, audio: np.ndarray):
        self.audio_int16_array = audio


class _VoixTom:
    """Piper à 44 100 Hz : une seconde de 220 Hz, un seul chunk."""

    class config:
        sample_rate = TAUX_TOM

    def synthesize(self, text, syn_config=None):
        yield _Chunk(_sinus(1.0, TAUX_TOM, freq=220.0))


def test_piper_annonce_22050_quand_la_voix_est_a_44100():
    tts = PiperTTS(model_path="tom-fake.onnx", profile="flat")
    tts.voice = _VoixTom()
    tts.native_sample_rate = TAUX_TOM
    tts.sample_rate = PIPELINE_RATE
    tts._treatment = None

    out = asyncio.run(tts.synthesize("bonjour"))
    assert out["sample_rate"] == PIPELINE_RATE
    assert out["audio"].dtype == np.int16
    assert abs(out["duration_s"] - 1.0) < 0.02
    assert abs(len(out["audio"]) / PIPELINE_RATE - 1.0) < 0.02
