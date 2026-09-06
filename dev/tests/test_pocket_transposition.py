"""PocketTTS doit pouvoir descendre la voix.

pocket-tts n'expose ni vitesse ni hauteur. `voice_design.transposer` regle les
deux d'un seul geste : relire l'onde plus lentement descend la fondamentale et
allonge le bloc dans le meme rapport. C'est exactement ce que demande une voix
jugee trop aigue *et* trop rapide, et contrairement au vocodeur de phase le
procede n'introduit aucun artefact de fenetre aux bornes de chunk.

Ces tests ne chargent pas le modele : ils portent sur le contrat de
`PocketTTS` (l'attribut existe, il est lu depuis l'environnement) et sur la
transposition elle-meme.
"""
import numpy as np
import pytest

from src.mouth.pocket_tts import PocketTTS
from src.mouth.voice_design import facteur_transposition, transposer

SR = 24000
F0 = 220.0


def _sinus(secondes: float = 1.0, frequence: float = F0) -> np.ndarray:
    t = np.arange(int(secondes * SR), dtype=np.float32) / np.float32(SR)
    return (0.5 * np.sin(2.0 * np.pi * frequence * t) * 32767.0).astype(np.int16)


def _hauteur_dominante(pcm16: np.ndarray) -> float:
    x = pcm16.astype(np.float64) / 32768.0
    spectre = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return float(np.fft.rfftfreq(x.size, 1.0 / SR)[int(np.argmax(spectre))])


def test_pocket_accepte_demi_tons():
    """Le constructeur expose la poignee, a zero par defaut."""
    assert PocketTTS().demi_tons == 0.0
    assert PocketTTS(demi_tons=-3.0).demi_tons == -3.0


def test_transposition_descend_la_hauteur():
    """-3 demi-tons doit descendre la fondamentale d'une tierce mineure."""
    sortie = transposer(_sinus(), -3.0)
    attendu = F0 * facteur_transposition(-3.0)
    assert _hauteur_dominante(sortie) == pytest.approx(attendu, rel=0.03)


def test_transposition_ralentit_dans_le_meme_rapport():
    """Descendre allonge le bloc — c'est le ralentissement recherche."""
    entree = _sinus()
    sortie = transposer(entree, -3.0)
    ratio = sortie.size / entree.size
    assert ratio == pytest.approx(1.0 / facteur_transposition(-3.0), rel=0.01)


def test_transposition_nulle_ne_touche_a_rien():
    """Garde-fou : le reglage par defaut doit etre un passe-plat exact."""
    entree = _sinus()
    assert np.array_equal(transposer(entree, 0.0), entree)


def test_appliquer_transposition_sur_un_chunk_vide():
    """Un chunk vide ne doit pas faire tomber la chaine."""
    vide = np.zeros(0, dtype=np.int16)
    assert PocketTTS(demi_tons=-3.0)._transposer(vide).size == 0
