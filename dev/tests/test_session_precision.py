"""« Ouvre une session Codex » : nouvelle ou dernière ? Elle demande (25/09)."""
from __future__ import annotations

import asyncio

from src.brain.sessions_voix import (
    DemandeSession,
    demande_de_session,
    executer,
    resoudre_precision,
)


def test_ouvre_une_session_est_ambigu():
    assert demande_de_session("Ouvre une session Codex, s'il te plaît.") == DemandeSession("Codex", "ambigu", "")


def test_formules_claires_restent_directes():
    assert demande_de_session("Reprends la dernière session Codex").action == "derniere"
    assert demande_de_session("Ouvre la dernière session Claude").action == "derniere"
    assert demande_de_session("Ouvre une nouvelle session Codex").action == "nouvelle"
    assert demande_de_session("Rejoins la session Codex qui parle de n8n").action == "chercher"


def test_elle_demande_une_precision():
    class _Pont:
        async def chercher_session(self, q):
            raise AssertionError("ne doit rien reprendre")

    resultat = asyncio.run(executer(DemandeSession("Codex", "ambigu", ""), {"Codex": _Pont()}))
    assert "nouvelle" in resultat.phrase.lower() and "dernière" in resultat.phrase.lower()
    assert resultat.session is None


def test_la_reponse_tranche():
    attente = DemandeSession("Codex", "ambigu", "")
    assert resoudre_precision("Une nouvelle.", attente) == DemandeSession("Codex", "nouvelle", "")
    assert resoudre_precision("La dernière, oui.", attente) == DemandeSession("Codex", "derniere", "")
    assert resoudre_precision("Reprends l'ancienne", attente) == DemandeSession("Codex", "derniere", "")
    assert resoudre_precision("Quelle heure est-il ?", attente) is None


def test_verbe_mal_entendu_par_whisper_demande_quand_meme():
    """Whisper a rendu « Ouvre une session Codex » par « On vous fait une
    session codex » (25/09) : le harnais et « session » suffisent pour demander."""
    assert demande_de_session("On vous fait une session codex, s'il te plaît.") == DemandeSession("Codex", "ambigu", "")


def test_session_sans_harnais_ni_verbe_reste_hors_sujet():
    assert demande_de_session("On va faire une session de tests demain.") is None


def test_les_deux_harnais_ensemble():
    """25/09 : « Nouvelle session pour les deux » ne remettait que Claude à zéro."""
    assert demande_de_session(
        "Connecte-toi à Claude et à Codex, s'il te plaît. Nouvelle session pour les deux."
    ) == DemandeSession(None, "nouvelle", "")
