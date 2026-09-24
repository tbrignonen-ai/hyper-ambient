"""Indicateur et bascule du cerveau distant (24/09).

« Je ne sais pas sur quel modèle je suis. » Le host-agent annonce le distant
actif à Presence, et en change à chaud sur demande — sans les ~40 s d'une
relance complète.
"""
import asyncio
from types import SimpleNamespace

from dev.scripts import serve_hostagent
from src.brain.factory import construire_distant, libelle_distant


class _Socket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class _Distant:
    def __init__(self, nom):
        self.name = nom
        self.initialise = False
        self.ferme = False

    async def initialize(self):
        self.initialise = True

    async def close(self):
        self.ferme = True


def test_construire_distant_accepte_un_choix_explicite(monkeypatch):
    monkeypatch.setenv("BRAIN_DEEP", "api")
    distant = construire_distant(mode="abonnement-chatgpt", modele="gpt-6-luna", effort="low")
    assert distant.name == "abonnement-chatgpt/gpt-6-luna"
    assert distant.effort == "low"


def test_libelles_lisibles():
    assert libelle_distant(SimpleNamespace(name="abonnement-claude/claude-sonnet-5")) == "Claude Sonnet 5"
    assert libelle_distant(SimpleNamespace(name="abonnement-chatgpt/gpt-6-luna")) == "GPT-6-Luna"
    assert libelle_distant(SimpleNamespace(name="MiniMaxAI/MiniMax-M3")) == "MiniMax-M3"


def test_bascule_a_chaud_et_annonce(monkeypatch):
    ancien, nouveau = _Distant("abonnement-claude/claude-sonnet-5"), _Distant("abonnement-chatgpt/gpt-6-luna")
    monkeypatch.setattr(serve_hostagent, "construire_distant", lambda **kw: nouveau)
    pipeline = serve_hostagent.HostPipeline()
    pipeline.brain = SimpleNamespace(deep=ancien)
    socket = _Socket()
    pipeline._websocket = socket

    async def scenario():
        statut = pipeline.on_options(
            {"type": "options", "cerveau": {"mode": "abonnement-chatgpt", "model": "gpt-6-luna", "effort": "low"}}
        )
        await pipeline._tache_cerveau
        return statut

    statut = asyncio.run(scenario())
    assert statut == {"type": "cerveau", "state": "switching", "nom": "GPT-6-Luna"}
    assert pipeline.brain.deep is nouveau and nouveau.initialise and ancien.ferme
    assert socket.messages[-1] == {"type": "cerveau", "state": "ready", "nom": "GPT-6-Luna",
                                   "mode": "abonnement-chatgpt"}


def test_le_hello_annonce_le_cerveau_actif():
    pipeline = serve_hostagent.HostPipeline()
    pipeline.brain = SimpleNamespace(deep=_Distant("abonnement-claude/claude-sonnet-5"))
    socket = _Socket()
    pipeline._websocket = socket

    async def scenario():
        pipeline.on_options({"type": "hello", "secret": "x"})
        await pipeline._tache_cerveau

    asyncio.run(scenario())
    assert socket.messages[-1]["type"] == "cerveau"
    assert socket.messages[-1]["nom"] == "Claude Sonnet 5"
    assert socket.messages[-1]["state"] == "ready"
