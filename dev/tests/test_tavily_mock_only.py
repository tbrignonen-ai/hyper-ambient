"""
Tavily mock-only (vague H). Aucun test ici n'ouvre de socket.

Les nappes D/F collent answer, HTTP 403, JSON illisible, cle d'env.
Ici les formes de payload que `_speakable` / `__call__` avalaient mal :

  - `answer` non-str, `results` non-liste, items non-dict,
  - titre seul / corps seul, titre non-str,
  - `status_code` absent,
  - endpoint injecte, max_results float,
  - sans cle : zero POST meme si le client leverait.

Le client HTTP est un double. `TAVILY_API_KEY` n'est jamais consommee
pour un vrai appel.
"""
import asyncio
import functools
import os

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry
from src.brain.tools_web import (
    TAVILY_ENDPOINT,
    TavilySearch,
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


class _FakeResponse:
    def __init__(self, payload, status_code=200, missing_status=False):
        self._payload = payload
        if not missing_status:
            self.status_code = status_code

    def json(self):
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


def test_speakable_ignore_les_items_non_dict():
    text = _speakable(
        {"results": ["nope", None, 3, {"title": "Meteo", "content": "18 degres"}]},
        5,
    )
    assert text == "Meteo : 18 degres"
    assert "nope" not in text


def test_speakable_titre_seul_et_corps_seul():
    titre = _speakable({"results": [{"title": "Seul", "content": ""}]}, 3)
    corps = _speakable({"results": [{"title": "", "content": "corps"}]}, 3)
    assert titre == "Seul"
    assert corps == "corps"
    assert ":" not in titre
    assert ":" not in corps


def test_speakable_results_chaine_ne_plante_pas():
    assert _speakable({"results": "pas-une-liste"}, 3) == _EMPTY


def test_speakable_results_objet_ne_plante_pas():
    assert _speakable({"results": {"title": "x", "content": "y"}}, 3) == _EMPTY


def test_speakable_answer_non_str_tombe_sur_les_resultats():
    text = _speakable(
        {"answer": 18, "results": [{"title": "Meteo", "content": "nuageux"}]},
        3,
    )
    assert text == "Meteo : nuageux"
    assert "{" not in text


def test_speakable_answer_non_str_sans_resultats_est_vide():
    assert _speakable({"answer": 18, "results": []}, 3) == _EMPTY
    assert _speakable({"answer": {"n": 1}}, 3) == _EMPTY


def test_speakable_titre_non_str_est_ignore():
    text = _speakable({"results": [{"title": 12, "content": "ok"}]}, 3)
    assert text == "ok"
    assert "12" not in text


def test_speakable_url_jamais_lue():
    text = _speakable(
        {"results": [{
            "title": "A",
            "content": "b",
            "url": "https://api.tavily.com/secret?token=1",
        }]},
        3,
    )
    assert "https://" not in text
    assert "tavily" not in text.lower()
    assert "token=" not in text


def test_speakable_tronque_un_titre_long():
    text = _speakable({"answer": "z" * 5000}, 3)
    assert len(text) <= MAX_TOOL_CONTENT_CHARS
    assert text.endswith("[…]")


@runs_async
async def test_status_code_absent_est_un_echec_dicible():
    client = FakeHTTPClient(_FakeResponse({"answer": "x"}, missing_status=True))
    out = await TavilySearch(api_key="k", client=client)("q")
    assert out == _FAILED
    assert client.calls  # l'appel a eu lieu, le statut manque
    assert "x" not in out


@runs_async
async def test_json_none_reste_dicible():
    client = FakeHTTPClient(_FakeResponse(None))
    out = await TavilySearch(api_key="k", client=client)("q")
    assert out == _FAILED


@runs_async
async def test_objet_vide_sans_answer_ni_results_est_vide():
    client = FakeHTTPClient(_FakeResponse({}))
    out = await TavilySearch(api_key="k", client=client)("q")
    assert out == _EMPTY


@runs_async
async def test_endpoint_injecte_est_honore():
    client = FakeHTTPClient(_FakeResponse({"answer": "a"}))
    tool = TavilySearch(api_key="k", client=client, endpoint="http://127.0.0.1:9/search")
    await tool("q")
    assert client.calls[0]["url"] == "http://127.0.0.1:9/search"
    assert client.calls[0]["url"] != TAVILY_ENDPOINT


@runs_async
async def test_max_results_float_est_borne():
    client = FakeHTTPClient(_FakeResponse({"answer": "a"}))
    tool = TavilySearch(api_key="k", client=client, max_results=3.9)
    await tool("q")
    assert client.calls[0]["json"]["max_results"] == 3
    assert tool.max_results == 3


@runs_async
async def test_sans_cle_aucun_post_meme_si_le_client_leverait():
    client = FakeHTTPClient(raises=RuntimeError("reseau"))
    out = await TavilySearch(api_key="", client=client)("q")
    assert client.calls == []
    assert out == _NO_KEY


@runs_async
async def test_sans_client_phrase_exacte():
    out = await TavilySearch(api_key="k", client=None)("q")
    assert out == _NO_CLIENT


@runs_async
async def test_register_transmet_endpoint_et_max(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    client = FakeHTTPClient(_FakeResponse({"answer": "lu"}))
    registry = ToolRegistry()
    spec = register_web_search(
        registry,
        api_key="k",
        client=client,
        endpoint="http://127.0.0.1:9/search",
        max_results=2,
    )
    out = await spec.handler(query="meteo")
    assert out == "lu"
    assert client.calls[0]["url"] == "http://127.0.0.1:9/search"
    assert client.calls[0]["json"]["max_results"] == 2
    assert registry.danger_of("web_search") == "read"


@runs_async
async def test_include_answer_toujours_vrai():
    client = FakeHTTPClient(_FakeResponse({"answer": "a"}))
    await TavilySearch(api_key="k", client=client)("q")
    assert client.calls[0]["json"]["include_answer"] is True
    assert "TAVILY_API_KEY" not in str(client.calls[0])


def test_defaut_endpoint_est_tavily_https():
    assert TavilySearch(api_key="k", client=FakeHTTPClient()).endpoint == TAVILY_ENDPOINT
    assert TAVILY_ENDPOINT.startswith("https://")
    assert "tavily.com" in TAVILY_ENDPOINT


def test_phrases_de_repli_n_ont_pas_de_jargon():
    for phrase in (_NO_KEY, _NO_CLIENT, _FAILED, _EMPTY):
        blob = phrase.lower()
        assert "http" not in blob
        assert "tavily" not in blob
        assert "traceback" not in blob
        assert "status" not in blob
        assert "{" not in phrase


@runs_async
async def test_cle_d_env_n_est_pas_lue_si_api_key_chaine_vide(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "ne-pas-utiliser")
    client = FakeHTTPClient(_FakeResponse({"answer": "fuite"}))
    out = await TavilySearch(api_key="", client=client)("q")
    assert client.calls == []
    assert out == _NO_KEY
    assert os.environ["TAVILY_API_KEY"] == "ne-pas-utiliser"
