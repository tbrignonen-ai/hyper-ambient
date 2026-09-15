"""
BRAIN: l'outil `ask_codex`, sans reseau et sans Codex.

**Aucun test ici ne lance Codex.** Le client HTTP est injecte et double a la
main, exactement comme pour Tavily : ce qui est prouve, c'est la forme de la
requete, la mise en forme dicible de la reponse, le comportement sans jeton, et
surtout le **chemin degrade** — pont eteint, pont lent, pont en erreur. C'est ce
chemin-la que le jury du 25 verra en direct, donc c'est celui qui est couvert le
plus densement.

Ce qui n'est **pas** prouve ici, c'est l'appel reel : il demande le pont lance
sur l'hote et une verification eveillee.
"""
import asyncio
import functools
import json

import pytest  # noqa: F401


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry
from src.brain.tools_codex import (
    ASK_CODEX_PARAMETERS,
    CODEX_BRIDGE_ENDPOINT,
    CodexBridge,
    register_ask_codex,
)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)

    def json(self):
        if not isinstance(self._payload, (dict, list)):
            raise ValueError("reponse illisible")
        return self._payload


class FakeHTTPClient:
    """Double du client httpx : rend une reponse scriptee, note les appels."""

    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    async def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(
            {"url": url, "json": json, "headers": headers or {}, "timeout": timeout}
        )
        if self.raises:
            raise self.raises
        return self.response


OK = {"ok": True, "answer": "Le depot compte quatre-vingt-douze fichiers Python."}


# --- forme de la requete ------------------------------------------------


@runs_async
async def test_envoie_la_question_au_pont():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CodexBridge(token="jeton", client=client)

    await bridge(question="Combien de fichiers Python dans le depot ?")

    assert len(client.calls) == 1
    envoi = client.calls[0]
    assert envoi["url"] == CODEX_BRIDGE_ENDPOINT
    assert envoi["json"]["question"] == "Combien de fichiers Python dans le depot ?"


@runs_async
async def test_presente_le_jeton_partage():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CodexBridge(token="jeton-secret", client=client)

    await bridge(question="quoi de neuf")

    assert client.calls[0]["headers"]["Authorization"] == "Bearer jeton-secret"


@runs_async
async def test_borne_l_attente_par_un_delai():
    """Une voix ne peut pas attendre Codex indefiniment : le delai part avec
    la requete, il n'est pas laisse au bon vouloir du pont."""
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CodexBridge(token="jeton", client=client, timeout_s=12.0)

    await bridge(question="quoi de neuf")

    assert client.calls[0]["timeout"] == 12.0


@runs_async
async def test_rend_la_reponse_de_codex():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CodexBridge(token="jeton", client=client)

    assert await bridge(question="q") == OK["answer"]


# --- chemins degrades : c'est la demo du 25 -----------------------------


@runs_async
async def test_sans_jeton_aucun_appel_n_est_emis():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CodexBridge(token="", client=client)

    reponse = await bridge(question="q")

    assert client.calls == []
    assert reponse
    assert "{" not in reponse


@runs_async
async def test_sans_client_aucun_appel_n_est_emis():
    bridge = CodexBridge(token="jeton", client=None)

    reponse = await bridge(question="q")

    assert reponse
    assert "Traceback" not in reponse


@runs_async
async def test_pont_eteint_rend_une_phrase_dicible():
    """Le pont coupe en direct, c'est le geste numero 3 de la soutenance :
    l'incident doit s'entendre, pas remonter en trace."""
    client = FakeHTTPClient(raises=ConnectionRefusedError("connexion refusee"))
    bridge = CodexBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert "refus" not in reponse.lower() or "Codex" in reponse
    assert "ConnectionRefusedError" not in reponse
    assert reponse.endswith(".")


@runs_async
async def test_delai_depasse_rend_une_phrase_dicible():
    client = FakeHTTPClient(raises=TimeoutError())
    bridge = CodexBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert "TimeoutError" not in reponse
    assert reponse.endswith(".")


@runs_async
async def test_http_non_200_rend_une_phrase_dicible():
    client = FakeHTTPClient(_FakeResponse({"ok": False}, status_code=503))
    bridge = CodexBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert "503" not in reponse


@runs_async
async def test_corps_illisible_rend_une_phrase_dicible():
    client = FakeHTTPClient(_FakeResponse("pas du json"))
    bridge = CodexBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert reponse.endswith(".")


@runs_async
async def test_echec_annonce_par_le_pont_rend_sa_raison_dicible():
    client = FakeHTTPClient(_FakeResponse({"ok": False, "error": "codex introuvable"}))
    bridge = CodexBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert "{" not in reponse
    assert reponse.endswith(".")


@runs_async
async def test_reponse_vide_ne_rend_pas_le_vide():
    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "   "}))
    bridge = CodexBridge(token="jeton", client=client)

    assert (await bridge(question="q")).strip()


# --- la voix avant l'agent ----------------------------------------------


@runs_async
async def test_une_reponse_fleuve_est_tronquee_avant_la_voix():
    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "mot " * 3000}))
    bridge = CodexBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert len(reponse) <= MAX_TOOL_CONTENT_CHARS


@runs_async
async def test_aucun_chemin_ne_rend_de_json_ni_de_trace():
    """Balayage : quel que soit le malheur, rien de ce qui sort n'est
    imprononcable."""
    cas = [
        FakeHTTPClient(_FakeResponse({"ok": False}, status_code=500)),
        FakeHTTPClient(_FakeResponse(None)),
        FakeHTTPClient(_FakeResponse({"ok": True})),
        FakeHTTPClient(raises=OSError("hote injoignable")),
        FakeHTTPClient(raises=TimeoutError()),
    ]
    for client in cas:
        reponse = await CodexBridge(token="jeton", client=client)(question="q")
        assert reponse.strip()
        assert "{" not in reponse and "Traceback" not in reponse


# --- enregistrement -----------------------------------------------------


def test_enregistrement_declare_un_outil_de_lecture():
    """Le pont epingle Codex en bac a sable lecture seule : l'outil declare
    donc `read`, et cette declaration vit sur la ToolSpec, pas sur l'appelant."""
    registry = ToolRegistry()

    spec = register_ask_codex(registry, token="jeton", client=FakeHTTPClient())

    assert spec.name == "ask_codex"
    assert spec.danger == "read"
    assert "ask_codex" in registry
    assert registry.danger_of("ask_codex") == "read"


def test_le_schema_declare_une_question_obligatoire():
    assert ASK_CODEX_PARAMETERS["required"] == ["question"]
    assert ASK_CODEX_PARAMETERS["properties"]["question"]["type"] == "string"


def test_le_schema_openai_est_bien_forme():
    registry = ToolRegistry()
    register_ask_codex(registry, token="jeton", client=FakeHTTPClient())

    schema = registry.schemas()[0]

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "ask_codex"
    assert schema["function"]["description"].strip()


@runs_async
async def test_le_jeton_vient_de_l_environnement_par_defaut(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "depuis-l-env")
    client = FakeHTTPClient(_FakeResponse(OK))

    await CodexBridge(client=client)(question="q")

    assert client.calls[0]["headers"]["Authorization"] == "Bearer depuis-l-env"
