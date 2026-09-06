"""Le debit de MOUTH se ralentit sans deplacer la hauteur.

pocket-tts n'expose aucun reglage de vitesse : `generate_audio_stream` ne prend
que `max_tokens` et `frames_after_eos`. Le `length_scale` du profil ne sert donc
qu'a Piper. Ralentir la voix sur pocket passe forcement par un etirement
temporel en post-traitement, et cet etirement doit conserver la hauteur — sinon
on obtient une voix ralentie *et* plus grave, ce qui n'est pas demande.
"""
import numpy as np
import pytest

from src.mouth.voice_design import VoiceProfile, VoiceTreatment

SR = 24000
F0 = 440.0


def _sinus(secondes: float = 1.0, frequence: float = F0) -> np.ndarray:
    t = np.arange(int(secondes * SR), dtype=np.float32) / np.float32(SR)
    x = 0.5 * np.sin(2.0 * np.pi * frequence * t)
    return (x * 32767.0).astype(np.int16)


def _hauteur_dominante(pcm16: np.ndarray) -> float:
    """Frequence du pic spectral, en Hz."""
    x = pcm16.astype(np.float64) / 32768.0
    spectre = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return float(np.fft.rfftfreq(x.size, 1.0 / SR)[int(np.argmax(spectre))])


def test_profil_par_defaut_ne_change_pas_la_duree():
    """Sans reglage explicite, le traitement ne doit rien etirer."""
    profil = VoiceProfile()
    assert profil.time_stretch == 1.0

    entree = _sinus()
    sortie = VoiceTreatment(profil, SR).process(entree)
    assert sortie.size == entree.size


def test_etirement_allonge_la_duree():
    """time_stretch=1.15 doit rendre le signal ~15 % plus long."""
    entree = _sinus()
    sortie = VoiceTreatment(VoiceProfile(time_stretch=1.15), SR).process(entree)

    ratio = sortie.size / entree.size
    assert ratio == pytest.approx(1.15, rel=0.05), (
        f"attendu ~1.15x, obtenu {ratio:.3f}x"
    )


def test_etirement_conserve_la_hauteur():
    """C'est le point de la demande : plus lent, pas plus grave."""
    entree = _sinus()
    sortie = VoiceTreatment(VoiceProfile(time_stretch=1.15), SR).process(entree)

    avant = _hauteur_dominante(entree)
    apres = _hauteur_dominante(sortie)
    assert apres == pytest.approx(avant, rel=0.02), (
        f"hauteur deplacee : {avant:.1f} Hz -> {apres:.1f} Hz"
    )


def test_etirement_reste_du_int16_non_vide():
    """Le format de sortie ne change pas : le transport attend du int16."""
    sortie = VoiceTreatment(VoiceProfile(time_stretch=1.15), SR).process(_sinus())
    assert sortie.dtype == np.int16
    assert sortie.size > 0
    assert np.abs(sortie).max() > 0


def test_signal_vide_reste_vide():
    """Garde-fou : un chunk vide ne doit pas faire tomber l'etirement."""
    vide = np.zeros(0, dtype=np.int16)
    sortie = VoiceTreatment(VoiceProfile(time_stretch=1.15), SR).process(vide)
    assert sortie.size == 0
