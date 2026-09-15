"""
BRAIN: les outils `ask_claude` et `ask_hermes`, sans reseau et sans CLI.

**Aucun test ici ne lance Claude ni Hermes.** Le client HTTP est injecte et
double a la main : ce qui est prouve, c'est la forme de la requete (jeton,
agent, question), la mise en forme dicible, le comportement sans jeton, et le
chemin degrade. Hermes reste declare : l'outil existe, il parle, il n'allume
rien.
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
from src.brain.tools_cli import (
    ASK_CLAUDE_PARAMETERS,
    ASK_HERMES_PARAMETERS,
    CLI_BRIDGE_ENDPOINT,
    CliBridge,
    register_ask_claude,
    register_ask_hermes,
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
_CLAUDE_DOWN = "Claude ne repond pas pour l'instant, je continue sans lui."


# --- forme de la requete ------------------------------------------------


@runs_async
async def test_envoie_la_question_au_pont_avec_l_agent():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CliBridge(token="jeton", client=client, agent="claude")

    await bridge(question="Combien de fichiers Python dans le depot ?")

    assert len(client.calls) == 1
    envoi = client.calls[0]
    assert envoi["url"] == CLI_BRIDGE_ENDPOINT
    assert envoi["json"]["question"] == "Combien de fichiers Python dans le depot ?"
    assert envoi["json"]["agent"] == "claude"


@runs_async
async def test_presente_le_jeton_partage():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CliBridge(token="jeton-secret", client=client)

    await bridge(question="quoi de neuf")

    assert client.calls[0]["headers"]["Authorization"] == "Bearer jeton-secret"


@runs_async
async def test_borne_l_attente_par_un_delai():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CliBridge(token="jeton", client=client, timeout_s=12.0)

    await bridge(question="quoi de neuf")

    assert client.calls[0]["timeout"] == 12.0


@runs_async
async def test_rend_la_reponse_de_claude():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CliBridge(token="jeton", client=client, agent="claude")

    assert await bridge(question="q") == OK["answer"]


# --- chemins degrades ---------------------------------------------------


@runs_async
async def test_sans_jeton_aucun_appel_n_est_emis():
    client = FakeHTTPClient(_FakeResponse(OK))
    bridge = CliBridge(token="", client=client)

    reponse = await bridge(question="q")

    assert client.calls == []
    assert reponse
    assert "{" not in reponse


@runs_async
async def test_sans_client_aucun_appel_n_est_emis():
    bridge = CliBridge(token="jeton", client=None)

    reponse = await bridge(question="q")

    assert reponse
    assert "Traceback" not in reponse


@runs_async
async def test_pont_eteint_rend_la_phrase_prevue():
    client = FakeHTTPClient(raises=ConnectionRefusedError("connexion refusee"))
    bridge = CliBridge(token="jeton", client=client, agent="claude")

    reponse = await bridge(question="q")

    assert reponse == _CLAUDE_DOWN
    assert "ConnectionRefusedError" not in reponse


@runs_async
async def test_delai_depasse_rend_une_phrase_dicible():
    client = FakeHTTPClient(raises=TimeoutError())
    bridge = CliBridge(token="jeton", client=client, agent="claude")

    reponse = await bridge(question="q")

    assert reponse == _CLAUDE_DOWN
    assert "TimeoutError" not in reponse


@runs_async
async def test_http_non_200_rend_une_phrase_dicible():
    client = FakeHTTPClient(_FakeResponse({"ok": False}, status_code=503))
    bridge = CliBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert "503" not in reponse
    assert reponse.endswith(".")


@runs_async
async def test_corps_illisible_rend_une_phrase_dicible():
    client = FakeHTTPClient(_FakeResponse("pas du json"))
    bridge = CliBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert reponse.endswith(".")


@runs_async
async def test_echec_annonce_par_le_pont_rend_sa_raison_dicible():
    client = FakeHTTPClient(_FakeResponse({"ok": False, "error": "claude introuvable"}))
    bridge = CliBridge(token="jeton", client=client, agent="claude")

    reponse = await bridge(question="q")

    assert "{" not in reponse
    assert reponse.endswith(".")
    assert "introuvable" not in reponse.lower() or "Claude" in reponse


@runs_async
async def test_hermes_indisponible_rend_une_phrase_dicible_sans_trace():
    """Hermes eteint : le pont le dit, la voix le dit, personne n'allume rien."""
    client = FakeHTTPClient(_FakeResponse({"ok": False, "error": "hermes indisponible"}))
    bridge = CliBridge(token="jeton", client=client, agent="hermes")

    reponse = await bridge(question="q")

    assert client.calls[0]["json"]["agent"] == "hermes"
    assert reponse.endswith(".")
    assert "{" not in reponse
    assert "Traceback" not in reponse
    assert "Hermes" in reponse


@runs_async
async def test_reponse_vide_ne_rend_pas_le_vide():
    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "   "}))
    bridge = CliBridge(token="jeton", client=client)

    assert (await bridge(question="q")).strip()


# --- la voix avant l'agent ----------------------------------------------


@runs_async
async def test_une_reponse_fleuve_est_tronquee_avant_la_voix():
    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "mot " * 3000}))
    bridge = CliBridge(token="jeton", client=client)

    reponse = await bridge(question="q")

    assert len(reponse) <= MAX_TOOL_CONTENT_CHARS


@runs_async
async def test_aucun_chemin_ne_rend_de_json_ni_de_trace():
    cas = [
        FakeHTTPClient(_FakeResponse({"ok": False}, status_code=500)),
        FakeHTTPClient(_FakeResponse(None)),
        FakeHTTPClient(_FakeResponse({"ok": True})),
        FakeHTTPClient(raises=OSError("hote injoignable")),
        FakeHTTPClient(raises=TimeoutError()),
    ]
    for client in cas:
        reponse = await CliBridge(token="jeton", client=client)(question="q")
        assert reponse.strip()
        assert "{" not in reponse and "Traceback" not in reponse


# --- enregistrement -----------------------------------------------------


def test_enregistrement_declare_claude_en_lecture():
    registry = ToolRegistry()

    spec = register_ask_claude(registry, token="jeton", client=FakeHTTPClient())

    assert spec.name == "ask_claude"
    assert spec.danger == "read"
    assert "ask_claude" in registry
    assert registry.danger_of("ask_claude") == "read"


def test_enregistrement_declare_hermes_en_lecture():
    registry = ToolRegistry()

    spec = register_ask_hermes(registry, token="jeton", client=FakeHTTPClient())

    assert spec.name == "ask_hermes"
    assert spec.danger == "read"
    assert "ask_hermes" in registry
    assert registry.danger_of("ask_hermes") == "read"


def test_le_schema_declare_une_question_obligatoire():
    assert ASK_CLAUDE_PARAMETERS["required"] == ["question"]
    assert ASK_CLAUDE_PARAMETERS["properties"]["question"]["type"] == "string"
    assert ASK_HERMES_PARAMETERS["required"] == ["question"]


def test_le_schema_openai_est_bien_forme():
    registry = ToolRegistry()
    register_ask_claude(registry, token="jeton", client=FakeHTTPClient())
    register_ask_hermes(registry, token="jeton", client=FakeHTTPClient())

    names = {s["function"]["name"] for s in registry.schemas()}
    assert names == {"ask_claude", "ask_hermes"}
    for schema in registry.schemas():
        assert schema["type"] == "function"
        assert schema["function"]["description"].strip()


@runs_async
async def test_le_jeton_vient_de_l_environnement_par_defaut(monkeypatch):
    monkeypatch.setenv("CLI_BRIDGE_TOKEN", "depuis-l-env")
    client = FakeHTTPClient(_FakeResponse(OK))

    await CliBridge(client=client)(question="q")

    assert client.calls[0]["headers"]["Authorization"] == "Bearer depuis-l-env"
