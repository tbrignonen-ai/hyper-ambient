"""Réveil court : accusé de réception quand JeV entend une interpellation.

En écoute continue, une bribe adressée à HA (« hyper ambient ») ne doit
pas déclencher une réponse sérieuse de BRAIN. La décision est locale,
gratuite, et testable sans réseau ni périphérique.
"""
from __future__ import annotations

import inspect
from pathlib import Path


def _reveil(transcript: str, langue: str = "fr") -> bool:
    from src.mouth.reveil import reveil_court_suffit

    return reveil_court_suffit(transcript, langue=langue)


def test_hyper_ambient_seul_suffit():
    assert _reveil("hyper ambient") is True


def test_hyper_ambiant_casse_et_ponctuation():
    assert _reveil("Hyper Ambiant !") is True


def test_mother_seul_suffit():
    assert _reveil("MOTHER") is True


def test_une_demande_complete_ne_suffit_pas():
    assert _reveil("hyper ambient, quelle heure est-il ?") is False


def test_une_longue_demande_sans_nom_ne_suffit_pas():
    assert _reveil(
        "dis-moi pourquoi le facteur temps reel doit rester sous 1"
    ) is False


def test_eh_hyper_ambient_suffit():
    assert _reveil("eh hyper ambient") is True


def test_bonjour_hyper_ambient_suffit():
    assert _reveil("bonjour hyper ambient") is True


def test_chaine_vide_suffit():
    assert _reveil("") is True
    assert _reveil("   ") is True


def test_phrases_reveil_existent_courtes_fr_en_es():
    from src.mouth.reveil import PHRASES_REVEIL, phrase_de_reveil

    for langue in ("fr", "en", "es"):
        phrases = PHRASES_REVEIL[langue]
        assert len(phrases) >= 2, f"{langue} doit varier"
        for phrase in phrases:
            assert phrase.strip(), f"{langue} a une phrase blanche"
            assert len(phrase) < 30, f"{langue} trop longue : {phrase!r}"
        assert phrase_de_reveil(langue=langue) in phrases


def test_silence_reste_muet_en_ecoute_continue():
    from src.mouth.secours import phrase_de_secours

    assert (
        phrase_de_secours(
            transcript="",
            reply="",
            brain_injoignable=False,
            duree_audio_s=0.0,
            mains_libres=True,
        )
        is None
    )


def test_decision_est_une_fonction_pure():
    from src.mouth.reveil import reveil_court_suffit

    source = inspect.getsource(reveil_court_suffit)
    assert "print(" not in source
    assert "asyncio" not in source
    assert "websocket" not in source


def test_cablage_apres_jev_en_mains_libres_seulement():
    """Le réveil court ne s'arme qu'en écoute continue, après JeV."""
    texte = Path("dev/scripts/serve_hostagent.py").read_text(encoding="utf-8")
    assert "reveil_court_suffit" in texte
    assert "interpellation sans demande — reveil court" in texte
    assert "phrase_de_reveil" in texte
    idx_jev = texte.find("jev_doit_ignorer")
    idx_reveil = texte.find("reveil_court_suffit(")
    assert 0 <= idx_jev < idx_reveil
