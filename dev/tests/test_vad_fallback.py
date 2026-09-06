"""Tests pour src/turn/vad_fallback.py (TURN-L1 VAD Fallback).

Couvre le calcul d'énergie RMS, les seuils de silence, l'accumulation de trames,
la détection d'endpoint et la réinitialisation d'état sans matériel audio réel.
"""
from __future__ import annotations

import asyncio
import functools
import numpy as np
import pytest

from src.turn.vad_fallback import VADEndpointDetector


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


def test_vad_init_default_parameters():
    vad = VADEndpointDetector()
    assert vad.silence_threshold_db == -40.0
    assert vad.silence_duration_ms == 800
    assert vad.sample_rate == 16000
    assert vad.silent_frame_count == 0
    assert vad.total_frames == 0


def test_vad_compute_rms_empty():
    vad = VADEndpointDetector()
    rms = vad._compute_rms(np.zeros(0, dtype=np.float32))
    assert rms == -100.0


def test_vad_compute_rms_silence_and_signal():
    vad = VADEndpointDetector()
    # Zéro absolu
    silence = np.zeros(320, dtype=np.float32)
    assert vad._compute_rms(silence) == -100.0
    
    # Signal sinusoïdal d'amplitude 0.5 (RMS = 0.5 / sqrt(2) ≈ 0.3535 -> 20*log10(0.3535) ≈ -9.03 dB)
    t = np.linspace(0, 0.02, 320, endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    rms_db = vad._compute_rms(signal)
    assert -10.0 < rms_db < -8.0


@runs_async
async def test_vad_detect_endpoint_on_continuous_silence():
    # Avec silence_duration_ms=60 (3 trames de 20ms)
    vad = VADEndpointDetector(silence_threshold_db=-40.0, silence_duration_ms=60)
    silent_frame = np.zeros(320, dtype=np.float32)
    
    # Trame 1 (20ms)
    res1 = await vad.detect_endpoint(silent_frame)
    assert res1["is_silent"] is True
    assert res1["endpoint_detected"] is False
    assert res1["silence_duration_ms"] == 20

    # Trame 2 (40ms)
    res2 = await vad.detect_endpoint(silent_frame)
    assert res2["is_silent"] is True
    assert res2["endpoint_detected"] is False
    assert res2["silence_duration_ms"] == 40

    # Trame 3 (60ms -> Endpoint atteint)
    res3 = await vad.detect_endpoint(silent_frame)
    assert res3["is_silent"] is True
    assert res3["endpoint_detected"] is True
    assert res3["silence_duration_ms"] == 60


@runs_async
async def test_vad_resets_silence_count_on_speech():
    vad = VADEndpointDetector(silence_threshold_db=-40.0, silence_duration_ms=60)
    silent_frame = np.zeros(320, dtype=np.float32)
    speech_frame = np.full(320, 0.2, dtype=np.float32)  # RMS = 0.2 -> -14 dB (> -40 dB)
    
    # 2 trames de silence (40ms)
    await vad.detect_endpoint(silent_frame)
    await vad.detect_endpoint(silent_frame)
    assert vad.silent_frame_count == 2
    
    # 1 trame de parole -> réinitialisation du compteur de silence
    res_speech = await vad.detect_endpoint(speech_frame)
    assert not res_speech["is_silent"]
    assert res_speech["endpoint_detected"] is False
    assert res_speech["silence_duration_ms"] == 0
    assert vad.silent_frame_count == 0


@runs_async
async def test_vad_manual_reset():
    vad = VADEndpointDetector(silence_threshold_db=-40.0, silence_duration_ms=60)
    silent_frame = np.zeros(320, dtype=np.float32)
    
    await vad.detect_endpoint(silent_frame)
    await vad.detect_endpoint(silent_frame)
    assert vad.silent_frame_count == 2
    
    await vad.reset()
    assert vad.silent_frame_count == 0
