"""Presence : indicateur et bascule du cerveau distant (24/09).

« Je ne sais pas sur quel modèle je suis. » Presence affiche le distant actif
annoncé par le host-agent, et propose une bascule rapide sous l'éclair.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "native" / "presence"))
sys.path.insert(0, str(RACINE))

from native.presence import cerveau_distant as cd  # noqa: E402


def test_relayer_cerveau():
    import pytest

    pytest.importorskip("tkinter")
    from native.presence.app import relayer_cerveau

    deposes = []
    assert relayer_cerveau({"type": "cerveau", "state": "ready", "nom": "Claude Sonnet 5",
                            "mode": "abonnement-claude"}, deposes.append)
    assert deposes == [{"type": "cerveau", "state": "ready", "nom": "Claude Sonnet 5",
                        "mode": "abonnement-claude"}]
    assert not relayer_cerveau({"type": "conversation"}, deposes.append)


def test_choix_de_bascule_gardent_le_modele_choisi(tmp_path):
    env_local = tmp_path / ".env.local"
    env_local.write_text("BRAIN_DEEP=abonnement-chatgpt\nBRAIN_ABONNEMENT_MODEL=gpt-6-sol\n",
                         encoding="utf-8")
    choix = cd.choix_bascule(env_local)
    libelles = [libelle for libelle, _ in choix]
    assert libelles == ["Claude Sonnet 5", "GPT-6-Sol", "MiniMax (clé d'API)"]
    assert choix[1][1] == {"mode": "abonnement-chatgpt", "model": "gpt-6-sol", "effort": "low"}
    assert choix[2][1]["mode"] == "api"


def test_la_bascule_n_envoie_pas_le_mode_mains_libres():
    """Renvoyer mains_libres=False refermerait la conversation côté host-agent."""
    import pytest

    pytest.importorskip("tkinter")
    from native.presence.app import SessionVocale

    class _Ws:
        def __init__(self):
            self.envoyes = []

        def send(self, texte):
            self.envoyes.append(json.loads(texte))

    session = SessionVocale.__new__(SessionVocale)
    import threading

    session.mains_libres = False
    session._options_a_envoyer = threading.Event()
    session._ml_a_envoyer = False
    session._cerveau_a_envoyer = None
    session._attendre_jev = False
    ws = _Ws()
    session.demander_bascule_cerveau({"mode": "abonnement-claude", "model": "claude-sonnet-5", "effort": "low"})
    session._pousser_options(ws)
    assert ws.envoyes == [{"type": "options", "cerveau": {"mode": "abonnement-claude",
                                                           "model": "claude-sonnet-5", "effort": "low"}}]
    # À la connexion, sans bascule en attente, le mode mains libres part comme avant.
    session._pousser_options(ws)
    assert ws.envoyes[-1] == {"type": "options", "mains_libres": False}
