"""
Tests du type AudioFrame et du tampon circulaire partagé.

Le tampon porte le budget NFR-01 (p95 mic_to_audible <= 1200 ms) : trames
de 20 ms à 16 kHz, numpy float32, horodatage monotone. Une trame de mauvaise
taille ou d'un dtype implicite désalignerait EARS et TURN en aval.
"""
import time

import numpy as np
import pytest


def test_ring_overwrites_oldest_and_reports_drop_count():
    """Écrire 3 fois la capacité : seules les N plus récentes restent, drop_count = pertes."""
    from src.hostagent.audio import (
        FRAME_SAMPLES,
        SAMPLE_RATE,
        AudioFrame,
        FrameRing,
    )

    assert SAMPLE_RATE == 16000
    assert FRAME_SAMPLES == 320

    capacite = 4
    ring = FrameRing(capacity=capacite)
    total = 3 * capacite
    for indice in range(total):
        echantillons = np.full(FRAME_SAMPLES, float(indice), dtype=np.float32)
        ring.push(AudioFrame(samples=echantillons))

    perdues = total - capacite
    assert ring.drop_count == perdues

    conservees = ring.pop_all()
    assert len(conservees) == capacite
    assert [float(trame.samples[0]) for trame in conservees] == [
        float(indice) for indice in range(perdues, total)
    ]


def test_une_audio_frame_refuse_une_taille_qui_n_est_pas_frame_samples():
    """319 ou 321 échantillons lèvent une erreur nommée : la taille n'est pas négociable."""
    from src.hostagent.audio import FRAME_SAMPLES, AudioFrame, InvalidFrameSizeError

    assert FRAME_SAMPLES == 320
    for taille in (FRAME_SAMPLES - 1, FRAME_SAMPLES + 1):
        echantillons = np.zeros(taille, dtype=np.float32)
        with pytest.raises(InvalidFrameSizeError) as captured:
            AudioFrame(samples=echantillons)
        assert type(captured.value) is InvalidFrameSizeError


def test_une_audio_frame_refuse_un_dtype_autre_que_float32():
    """Un int16 (sortie brute de carte son) lève une erreur nommée, sans conversion silencieuse."""
    from src.hostagent.audio import FRAME_SAMPLES, AudioFrame, InvalidSampleDtypeError

    echantillons = np.zeros(FRAME_SAMPLES, dtype=np.int16)
    with pytest.raises(InvalidSampleDtypeError) as captured:
        AudioFrame(samples=echantillons)
    assert type(captured.value) is InvalidSampleDtypeError


def test_les_horodatages_de_trames_successives_sont_strictement_croissants():
    """Les stamps sont strictement croissants, même poussés dans la même graduation d'horloge."""
    from src.hostagent.audio import FRAME_SAMPLES, AudioFrame, FrameRing

    monotone_avant = time.monotonic()
    posix_avant = time.time()
    ring = FrameRing(capacity=200)
    for _ in range(100):
        ring.push(AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32)))
    trames = ring.pop_all()
    monotone_apres = time.monotonic()
    posix_apres = time.time()

    stamps = [trame.stamp for trame in trames]
    assert len(stamps) == 100
    assert all(stamps[i] < stamps[i + 1] for i in range(len(stamps) - 1))
    assert monotone_avant <= stamps[0] <= monotone_apres
    assert monotone_avant <= stamps[-1] <= monotone_apres
    assert not (posix_avant <= stamps[0] <= posix_apres)
    assert not (posix_avant <= stamps[-1] <= posix_apres)


def test_le_tampon_vide_rend_une_liste_vide_et_un_drop_count_a_zero():
    """Un tampon tout juste créé rend [] et drop_count 0, sans lever."""
    from src.hostagent.audio import FrameRing

    ring = FrameRing(capacity=8)
    assert ring.pop_all() == []
    assert ring.drop_count == 0


def test_pop_all_vide_le_tampon():
    """Deux appels successifs à pop_all ne rendent pas deux fois les mêmes trames."""
    from src.hostagent.audio import FRAME_SAMPLES, AudioFrame, FrameRing

    ring = FrameRing(capacity=8)
    for indice in range(3):
        echantillons = np.full(FRAME_SAMPLES, float(indice), dtype=np.float32)
        ring.push(AudioFrame(samples=echantillons))

    premier = ring.pop_all()
    second = ring.pop_all()
    assert len(premier) == 3
    assert [float(trame.samples[0]) for trame in premier] == [0.0, 1.0, 2.0]
    assert second == []
