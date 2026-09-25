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


def test_fermer_une_session_nommee():
    assert demande_de_session("Ferme la session que tu viens d'ouvrir de Claude.") == DemandeSession("Claude", "fermer", "")
    d = demande_de_session("Tu fermes la session de l'Afrique du Sud.")
    assert d.action == "fermer" and d.harnais is None and "Afrique du Sud" in d.requete


def test_fermer_oublie_la_session_et_rend_la_cible():
    class _Pont:
        session = "c-1"

        def oublier_session(self):
            self.session = None

        async def chercher_session(self, q):
            return {"id": "c-9", "titre": "Afrique du Sud", "score": 3, "date": 1} if q else None

    pont = _Pont()
    r = asyncio.run(executer(DemandeSession("Claude", "fermer", ""), {"Claude": pont}))
    assert r.fermer and r.harnais == "Claude" and r.session == "c-1" and pont.session is None
    r = asyncio.run(executer(DemandeSession(None, "fermer", "l'Afrique du Sud"), {"Claude": _Pont()}))
    assert r.fermer and r.harnais == "Claude" and r.session == "c-9"


def test_presence_ferme_seulement_la_console_du_harnais_nomme():
    from native.presence.harnais_ouvert import OuvreurHarnais

    fermees = []
    o = OuvreurHarnais("/x", lancer=lambda cmd, **k: cmd[-1] if cmd[-1] != "manual" else cmd[2],
                       fermer=fermees.append, exe=lambda n: n, dossier_de=lambda h, s: None,
                       mode_claude="")
    o.ouvrir("Codex", "x-1", premier_plan=False)
    o.ouvrir("Claude", "c-1", premier_plan=False)
    assert o.fermer_harnais("Claude") is True
    assert fermees == ["c-1"]
    assert o.fermer_harnais("Claude") is False
