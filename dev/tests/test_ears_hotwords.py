"""Hotwords Whisper (banc 19 sept) câblés dans EARS, pas seulement le banc."""
from __future__ import annotations

import numpy as np

from test_hostagent_env_local import serve_hostagent
from src.ears.faster_whisper_asr import FasterWhisperASR

HOTWORDS = "Hyper Ambient"


class _Info:
    language = "fr"
    language_probability = 1.0


class _ModeleEspion:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    def transcribe(self, _audio, **kwargs):
        self.kwargs = kwargs
        return [], _Info()


def test_decode_passe_les_hotwords():
    asr = FasterWhisperASR(hotwords=HOTWORDS)
    asr.model = _ModeleEspion()
    asr._decode(np.zeros(1600, dtype=np.float32), beam_size=5)
    assert asr.model.kwargs["hotwords"] == HOTWORDS


def test_decode_sans_hotwords_n_envoie_pas_la_cle():
    asr = FasterWhisperASR()
    asr.model = _ModeleEspion()
    asr._decode(np.zeros(1600, dtype=np.float32), beam_size=5)
    assert "hotwords" not in asr.model.kwargs


class _Segment:
    start = 0.0
    end = 1.0
    text = "bonjour"
    no_speech_prob = 0.81
    avg_logprob = -1.4


class _ModeleAvecSignal(_ModeleEspion):
    def transcribe(self, _audio, **kwargs):
        self.kwargs = kwargs
        return [_Segment()], _Info()


def test_decode_remonte_no_speech_prob_et_avg_logprob():
    asr = FasterWhisperASR()
    asr.model = _ModeleAvecSignal()
    result = asr._decode(np.zeros(1600, dtype=np.float32), beam_size=5)
    assert result["segments"][0]["no_speech_prob"] == 0.81
    assert result["segments"][0]["avg_logprob"] == -1.4


def test_construire_ears_lit_ears_hotwords(monkeypatch):
    monkeypatch.setenv("EARS_BACKEND", "faster-whisper")
    monkeypatch.setenv("EARS_MODEL", "large-v3")
    monkeypatch.setenv("EARS_HOTWORDS", HOTWORDS)
    _backend, asr = serve_hostagent.construire_ears()
    assert asr.hotwords == HOTWORDS
