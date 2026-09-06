"""Rechantillonnage continu : les coutures de chunk ne doivent pas s'entendre.

MOUTH (Pocket TTS) sort a 24 kHz par blocs de 80 ms ; le canal host-agent
transporte du 16 kHz. La conversion se faisait bloc par bloc avec
`librosa.resample`, qui est concu pour un signal *complet* : il remet ses bords
a zero a chaque appel. Mesure du 6 septembre 2026, chunks de 1920 echantillons :

    |erreur| au debut d'un chunk  0.01632
    |erreur| au milieu           0.00000   -> rapport 237 000x
    erreur crete sur estelle     13 % du pic

Autrement dit un transitoire a chaque couture, douze fois et demie par seconde.
C'est ce que Thomas a decrit a l'oreille : « des fois comme de la jitter,
entrecoupe ». Ces tests fixent le contrat inverse : un rechantillonneur qui
porte son etat d'un bloc au suivant, dont la sortie concatenee est
indiscernable du rechantillonnage du signal entier.

Aucun materiel, aucun modele : du signal et de l'arithmetique.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.hostagent.audio import SAMPLE_RATE, RechantillonneurContinu

SR_MOUTH = 24000
CHUNK = 1920  # 80 ms a 24 kHz, la taille reelle d'un chunk Pocket


def _signal(duree_s: float = 2.0, sr: int = SR_MOUTH) -> np.ndarray:
    """Deux sinus purs : n'importe quelle discontinuite s'y voit sans ambiguite."""
    t = np.arange(int(sr * duree_s)) / sr
    return (0.5 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 1800 * t)).astype(
        np.float32
    )


def _reference(x: np.ndarray) -> np.ndarray:
    """Le signal entier converti d'un seul tenant — la verite terrain."""
    import soxr

    return soxr.resample(x, SR_MOUTH, SAMPLE_RATE).astype(np.float32)


def _par_blocs(x: np.ndarray, taille: int = CHUNK) -> np.ndarray:
    r = RechantillonneurContinu(SR_MOUTH, SAMPLE_RATE)
    morceaux = [r.pousser(x[i : i + taille]) for i in range(0, x.size, taille)]
    morceaux.append(r.vider())
    return np.concatenate([m for m in morceaux if m.size])


def test_sortie_par_blocs_egale_le_signal_entier():
    """Contrat central : decouper l'entree ne change pas la sortie."""
    x = _signal()
    ref = _reference(x)
    obtenu = _par_blocs(x)

    n = min(ref.size, obtenu.size)
    assert abs(ref.size - obtenu.size) <= 2, (
        f"longueurs trop differentes : {obtenu.size} contre {ref.size}"
    )
    crete = np.abs(obtenu[:n] - ref[:n]).max()
    assert crete < 0.01 * np.abs(ref[:n]).max(), (
        f"erreur crete {crete:.5f} — les coutures s'entendent encore"
    )


def test_pas_de_transitoire_aux_coutures():
    """L'erreur ne doit pas se concentrer au debut des blocs.

    C'est la signature exacte du bug : au milieu d'un bloc l'erreur est nulle,
    au bord elle explose. On exige que le bord ne depasse pas dix fois le
    milieu, la ou le rechantillonnage sans etat en faisait 237 000.
    """
    x = _signal()
    ref = _reference(x)
    obtenu = _par_blocs(x)
    n = min(ref.size, obtenu.size)
    err = np.abs(obtenu[:n] - ref[:n])

    pas = CHUNK * SAMPLE_RATE // SR_MOUTH  # 1280 echantillons en sortie
    utilisable = (err.size // pas) * pas
    profil = err[:utilisable].reshape(-1, pas).mean(axis=0)

    bord = profil[:8].mean()
    milieu = profil[pas // 2 - 4 : pas // 2 + 4].mean()
    assert bord <= 10 * milieu + 1e-6, (
        f"bord {bord:.6f} contre milieu {milieu:.6f} — transitoire de couture"
    )


def test_taille_de_bloc_indifferente():
    """Pocket ne garantit pas un chunk de taille constante."""
    x = _signal(1.0)
    ref = _reference(x)

    r = RechantillonneurContinu(SR_MOUTH, SAMPLE_RATE)
    tailles = [1920, 960, 2880, 1920, 480]
    morceaux, i, k = [], 0, 0
    while i < x.size:
        t = tailles[k % len(tailles)]
        morceaux.append(r.pousser(x[i : i + t]))
        i += t
        k += 1
    morceaux.append(r.vider())
    obtenu = np.concatenate([m for m in morceaux if m.size])

    n = min(ref.size, obtenu.size)
    assert np.abs(obtenu[:n] - ref[:n]).max() < 0.01 * np.abs(ref[:n]).max()


def test_meme_taux_rend_le_signal_tel_quel():
    """16 kHz vers 16 kHz : aucun filtre, aucune copie deformee."""
    r = RechantillonneurContinu(SAMPLE_RATE, SAMPLE_RATE)
    x = _signal(0.1, sr=SAMPLE_RATE)
    assert np.array_equal(r.pousser(x), x)
    assert r.vider().size == 0


def test_bloc_vide_ne_casse_rien():
    r = RechantillonneurContinu(SR_MOUTH, SAMPLE_RATE)
    assert r.pousser(np.zeros(0, dtype=np.float32)).size == 0
    sortie = r.pousser(_signal(0.1))
    assert sortie.size > 0


def test_reinitialiser_repart_a_zero():
    """Deux tours de parole successifs ne doivent pas se contaminer."""
    x = _signal(0.5)
    r = RechantillonneurContinu(SR_MOUTH, SAMPLE_RATE)

    premier = np.concatenate(
        [r.pousser(x[i : i + CHUNK]) for i in range(0, x.size, CHUNK)] + [r.vider()]
    )
    r.reinitialiser()
    second = np.concatenate(
        [r.pousser(x[i : i + CHUNK]) for i in range(0, x.size, CHUNK)] + [r.vider()]
    )
    assert np.array_equal(premier, second)


@pytest.mark.parametrize("duree", [0.02, 0.08, 0.5])
def test_rien_n_est_perdu(duree):
    """La duree restituee suit la duree fournie, a un echantillon pres."""
    x = _signal(duree)
    obtenu = _par_blocs(x)
    attendu = x.size * SAMPLE_RATE / SR_MOUTH
    assert abs(obtenu.size - attendu) <= 2, f"{obtenu.size} contre {attendu:.0f}"
