"""
Socle tools.py + tools_web.py : bornes de troncature, sanitizer, Tavily
sans reseau — y compris les formes de payload que le lot initial n'envoie pas.
"""
import asyncio
import functools
import json
from dataclasses import FrozenInstanceError

import pytest

from src.brain.tool_loop import _SECRET_KEYS, _sanitize
from src.brain.tools import (
    MAX_TOOL_CONTENT_CHARS,
    ToolCall,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from src.brain.tools_web import (
    TAVILY_ENDPOINT,
    TavilySearch,
    WEB_SEARCH_DESCRIPTION,
    WEB_SEARCH_PARAMETERS,
    _EMPTY,
    _FAILED,
    _NO_CLIENT,
    _NO_KEY,
    _speakable,
    register_web_search,
)


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


async def _echo(text: str) -> str:
    return text


def _spec(name="echo", danger="read"):
    return ToolSpec(
        name=name,
        description="echo",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        danger=danger,
        handler=_echo,
    )


class _FakeResponse:
    def __init__(self, payload, status_code=200, json_raises=None):
        self._payload = payload
        self.status_code = status_code
        self.text = "not-json" if json_raises else json.dumps(payload) if not isinstance(payload, str) else payload
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise self._json_raises
        return self._payload


class FakeHTTPClient:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        if self.raises:
            raise self.raises
        return self.response


# -- ToolResult / ToolSpec / registre ----------------------------------------


def test_troncature_a_la_borne_1200_non_1201():
    pile = "x" * MAX_TOOL_CONTENT_CHARS
    assert len(ToolResult("1", "echo", True, pile).content) == MAX_TOOL_CONTENT_CHARS
    trop = ToolResult("1", "echo", True, "x" * (MAX_TOOL_CONTENT_CHARS + 1))
    assert len(trop.content) == MAX_TOOL_CONTENT_CHARS
    assert trop.content.endswith("[…]")


def test_troncature_rstrip_avant_la_marque():
    r = ToolResult("1", "echo", True, ("y" * 1190) + (" " * 20) + "z")
    assert "z" not in r.content
    assert r.content.endswith("[…]")
    assert len(r.content) <= MAX_TOOL_CONTENT_CHARS


def test_contenu_vide_et_falsey():
    assert ToolResult("1", "echo", True, "").content == ""
    assert ToolResult("1", "echo", True, content="").error is None


def test_champ_error_conserve_sans_entrer_dans_le_message():
    r = ToolResult("c", "web_search", False, content="L'outil n'a pas repondu.", error="boom-secret")
    assert r.error == "boom-secret"
    assert r.to_message()["content"] == "L'outil n'a pas repondu."
    assert "boom-secret" not in r.to_message()["content"]


def test_tool_call_defauts():
    c = ToolCall(id="i", name="n")
    assert c.arguments == {}
    assert c.raw_arguments == ""


def test_types_sont_figes():
    with pytest.raises(FrozenInstanceError):
        _spec().name = "autre"
    with pytest.raises(FrozenInstanceError):
        ToolCall("i", "n").name = "x"
    with pytest.raises(FrozenInstanceError):
        ToolResult("1", "e", True, "x").ok = False


def test_register_rend_la_spec():
    registry = ToolRegistry()
    spec = registry.register(_spec("a"))
    assert spec is registry.get("a")
    assert "a" in registry
    assert "b" not in registry
    assert len(registry) == 1


def test_schemas_suivent_l_ordre_d_enregistrement():
    registry = ToolRegistry()
    registry.register(_spec("un"))
    registry.register(_spec("deux"))
    registry.register(_spec("trois"))
    assert [s["function"]["name"] for s in registry.schemas()] == ["un", "deux", "trois"]


def test_schema_openai_ne_porte_pas_le_danger():
    schema = _spec(danger="exec").to_openai_schema()
    blob = json.dumps(schema)
    assert "exec" not in blob
    assert "danger" not in blob


# -- sanitizer ---------------------------------------------------------------


def test_secret_keys_couvrent_les_marqueurs_usuels():
    for marker in ("api_key", "apikey", "key", "token", "secret", "password", "authorization"):
        assert marker in _SECRET_KEYS


def test_sanitize_est_insensible_a_la_casse_et_aux_separateurs():
    cleaned = _sanitize({
        "Query": "ok",
        "X-Api-Key": "s",
        "refresh_token": "s",
        "clientSecret": "s",
        "PASSWORD": "s",
        "authorization": "s",
        "keyboard": "s",
        "max_results": 3,
    })
    assert cleaned["Query"] == "ok"
    assert cleaned["max_results"] == 3
    assert set(cleaned) == {"Query", "max_results"}


def test_sanitize_ne_descend_pas_dans_les_valeurs():
    nested = {"query": {"api_key": "still-here"}, "token": "gone"}
    cleaned = _sanitize(nested)
    assert cleaned == {"query": {"api_key": "still-here"}}


# -- Tavily / _speakable -----------------------------------------------------


def test_phrases_de_repli_sont_dicibles():
    for phrase in (_NO_KEY, _NO_CLIENT, _FAILED, _EMPTY):
        assert phrase.strip()
        assert "{" not in phrase
        assert "http" not in phrase.lower()
        assert "tavily" not in phrase.lower()
        assert "traceback" not in phrase.lower()


def test_speakable_privilegie_answer():
    text = _speakable(
        {"answer": "Il fait beau.", "results": [{"title": "x", "content": "y"}]},
        max_results=3,
    )
    assert text.startswith("Il fait beau.")
    assert "x" not in text


def test_speakable_answer_blanc_tombe_sur_les_resultats():
    text = _speakable(
        {"answer": "   ", "results": [{"title": "Meteo", "content": "18 degres"}]},
        3,
    )
    assert "Meteo" in text and "18 degres" in text


def test_speakable_tronque_les_resultats_a_max():
    results = [{"title": f"T{i}", "content": f"C{i}"} for i in range(10)]
    text = _speakable({"results": results}, max_results=2)
    assert "T0" in text and "T1" in text
    assert "T2" not in text


def test_speakable_resultats_vides_et_sans_texte():
    assert _speakable({"results": []}, 3) == _EMPTY
    assert _speakable({"answer": "", "results": [{"title": "", "content": ""}]}, 3) == _EMPTY


def test_speakable_tronque_a_1200():
    text = _speakable({"answer": "z" * 5000}, 3)
    assert len(text) <= MAX_TOOL_CONTENT_CHARS
    assert text.endswith("[…]")


@runs_async
async def test_max_results_est_borne_entre_1_et_20():
    client = FakeHTTPClient(_FakeResponse({"answer": "a", "results": []}))
    low = TavilySearch(api_key="k", client=client, max_results=0)
    await low("q")
    assert client.calls[0]["json"]["max_results"] == 1
    high = TavilySearch(api_key="k", client=FakeHTTPClient(_FakeResponse({"answer": "a"})), max_results=99)
    await high("q")
    # le second client
    assert high.max_results == 20


@runs_async
async def test_search_depth_est_transmis():
    client = FakeHTTPClient(_FakeResponse({"answer": "a"}))
    await TavilySearch(api_key="k", client=client, search_depth="advanced")("q")
    assert client.calls[0]["json"]["search_depth"] == "advanced"


@runs_async
async def test_headers_authorization_et_content_type():
    client = FakeHTTPClient(_FakeResponse({"answer": "a"}))
    await TavilySearch(api_key="cle", client=client)("q")
    headers = client.calls[0]["headers"]
    assert headers["Authorization"] == "Bearer cle"
    assert headers["Content-Type"] == "application/json"
    assert client.calls[0]["url"] == TAVILY_ENDPOINT


@runs_async
async def test_json_illisible_reste_dicible():
    client = FakeHTTPClient(_FakeResponse({}, json_raises=ValueError("nope")))
    out = await TavilySearch(api_key="k", client=client)("q")
    assert out == _FAILED
    assert "nope" not in out


@runs_async
async def test_payload_liste_reste_dicible():
    client = FakeHTTPClient(_FakeResponse([{"title": "x"}]))
    out = await TavilySearch(api_key="k", client=client)("q")
    assert out == _FAILED
    assert "{" not in out


@runs_async
async def test_http_403_sans_code_dans_la_voix():
    client = FakeHTTPClient(_FakeResponse({"detail": "forbidden"}, status_code=403))
    out = await TavilySearch(api_key="k", client=client)("q")
    assert out == _FAILED
    assert "403" not in out
    assert "forbidden" not in out


@runs_async
async def test_sans_cle_ignore_meme_une_cle_d_env(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "env-secret")
    client = FakeHTTPClient(_FakeResponse({"answer": "a"}))
    out = await TavilySearch(api_key="", client=client)("q")
    assert client.calls == []
    assert out == _NO_KEY
    assert "env-secret" not in out


@runs_async
async def test_cle_lue_dans_l_env_si_non_passee(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "depuis-env")
    client = FakeHTTPClient(_FakeResponse({"answer": "lu"}))
    out = await TavilySearch(client=client)("q")
    assert client.calls[0]["headers"]["Authorization"] == "Bearer depuis-env"
    assert out.startswith("lu")


@runs_async
async def test_register_web_search_lit_et_n_ecrit_pas():
    registry = ToolRegistry()
    spec = register_web_search(registry, api_key="", client=FakeHTTPClient())
    assert spec.danger == "read"
    assert spec.name == "web_search"
    assert spec.description == WEB_SEARCH_DESCRIPTION
    assert spec.parameters == WEB_SEARCH_PARAMETERS
    out = await spec.handler(query="meteo")
    assert out == _NO_KEY


@runs_async
async def test_register_remplace_un_web_search_existant():
    registry = ToolRegistry()
    register_web_search(registry, api_key="a", client=FakeHTTPClient())
    register_web_search(registry, api_key="b", client=FakeHTTPClient())
    assert len(registry) == 1


def test_speakable_n_est_pas_du_json():
    text = _speakable(
        {"answer": None, "results": [
            {"title": "A", "content": "un", "url": "https://x.example/secret?token=1"},
            {"title": "B", "content": "deux"},
        ]},
        3,
    )
    assert "{" not in text
    # l'url n'est pas lue a voix haute
    assert "https://" not in text
    assert "token=" not in text
