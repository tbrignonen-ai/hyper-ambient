"""La transposition de la voix.

Les seules voix Piper francaises exploitables (siwis, upmc) sont claires — 235 Hz
mesures — la ou le cahier des charges demande grave et pose. Le corpus MLS offrait
des locutrices graves mais son synthetiseur multi-locuteur est inexploitable : 50 a
300 % d'erreur de transcription. Descendre une voix native est donc la seule route
qui garde le francais natif ET le timbre demande.

On descend par rééchantillonnage plutot que par vocodeur de phase : c'est sans
artefact, et l'allongement qui en decoule sert le cahier des charges, qui veut une
diction lente. Le débit de synthèse est compensé en amont pour que la durée finale
ne bouge pas.
"""
import numpy as np
import pytest

from src.mouth.voice_design import transposer, facteur_transposition


def _fondamentale(x: np.ndarray, taux: int) -> float:
    x = x.astype(np.float32) - float(np.mean(x))
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    lo, hi = int(taux / 400), int(taux / 70)
    return float(taux / (lo + int(np.argmax(ac[lo:hi]))))


def test_facteur_est_le_rapport_de_demi_tons():
    assert facteur_transposition(0.0) == pytest.approx(1.0)
    assert facteur_transposition(-12.0) == pytest.approx(0.5)
    assert facteur_transposition(12.0) == pytest.approx(2.0)


def test_descendre_de_quatre_demi_tons_baisse_la_fondamentale():
    taux = 22050
    t = np.arange(taux) / taux
    source = (np.sin(2 * np.pi * 220.0 * t) * 12000).astype(np.int16)

    sortie = transposer(source, demi_tons=-4.0)

    assert _fondamentale(sortie, taux) == pytest.approx(174.6, rel=0.02)


def test_descendre_allonge_la_duree_dans_le_meme_rapport():
    source = np.zeros(22050, dtype=np.int16)
    source[::100] = 8000

    sortie = transposer(source, demi_tons=-4.0)

    assert len(sortie) == pytest.approx(22050 / facteur_transposition(-4.0), rel=0.01)


def test_transposition_nulle_rend_le_signal_intact():
    source = (np.random.default_rng(0).normal(0, 3000, 4096)).astype(np.int16)

    assert np.array_equal(transposer(source, demi_tons=0.0), source)


def test_la_sortie_reste_en_entier_seize_bits_sans_saturer():
    source = np.full(8192, 32000, dtype=np.int16)

    sortie = transposer(source, demi_tons=-5.0)

    assert sortie.dtype == np.int16
    assert np.abs(sortie).max() <= 32767
