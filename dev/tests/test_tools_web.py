"""
BRAIN: l'outil de recherche internet (Tavily), sans reseau.

**Aucun test ici ne parle a Tavily.** Le client HTTP est injecte et double a la
main : il n'existe pas de cle dans l'environnement, et en creer une est une
decision de Thomas. Ce qui est prouve ici, c'est la forme de la requete, la mise
en forme dicible de la reponse, et le comportement sans cle. Ce qui n'est **pas**
prouve, c'est l'appel reel — il attendra une cle et une verification eveillee.
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


from src.brain.tools import ToolRegistry
from src.brain.tools_web import (
    BRAVE_ENDPOINT,
    EXA_ENDPOINT,
    JINA_ENDPOINT,
    SERPER_ENDPOINT,
    BraveSearch,
    ExaSearch,
    JinaSearch,
    SearXNGSearch,
    SerperSearch,
    TavilySearch,
    WebSearch,
    register_web_search,
)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeHTTPClient:
    """Double du client httpx : rend une reponse scriptee, note les appels."""

    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        if self.raises:
            raise self.raises
        return self.response

    async def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers or {}})
        if self.raises:
            raise self.raises
        return self.response


ANSWER = {
    "query": "meteo a Paris",
    "answer": "Il fait 18 degres et nuageux a Paris.",
    "results": [
        {"title": "Meteo Paris", "url": "https://exemple.fr/paris", "content": "18 degres", "score": 0.9},
        {"title": "Previsions", "url": "https://exemple.fr/prev", "content": "nuageux", "score": 0.7},
    ],
}


def test_loutil_est_en_lecture_et_enregistrable():
    registry = ToolRegistry()
    spec = register_web_search(registry, api_key="k", client=FakeHTTPClient())
    assert spec.name == "web_search"
    assert registry.danger_of("web_search") == "read"
    schema = spec.to_openai_schema()
    assert "query" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["query"]


@runs_async
async def test_searxng_utilise_le_format_json_et_ses_extraits():
    payload = {
        "results": [
            {"title": "OpenAI Codex", "content": "Agent de code OpenAI."},
            {"title": "Documentation", "content": "Guide officiel."},
        ]
    }
    client = FakeHTTPClient(_FakeResponse(payload))
    out = await SearXNGSearch("http://searxng:8080", client=client)("openai codex")

    assert out.startswith("OpenAI Codex : Agent de code OpenAI.")
    assert client.calls == [{
        "url": "http://searxng:8080/search",
        "params": {"q": "openai codex", "format": "json"},
        "headers": {"Accept": "application/json"},
    }]


@runs_async
async def test_searxng_est_prefere_a_tavily():
    client = FakeHTTPClient(_FakeResponse({"results": [{"title": "Local", "content": "ok"}]}))
    tool = WebSearch(
        searxng_url="http://searxng:8080",
        api_key="cle-tavily",
        client=client,
    )
    assert await tool("question") == "Local : ok"
    assert len(client.calls) == 1
    assert "params" in client.calls[0], "Tavily ne doit pas etre appele si SearXNG repond"


class _FallbackHTTPClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None, headers=None):
        self.calls.append(("get", url))
        raise RuntimeError("searxng down")

    async def post(self, url, json=None, headers=None):
        self.calls.append(("post", url))
        return _FakeResponse({"answer": "Reponse Tavily."})


@runs_async
async def test_tavily_prend_le_relais_si_searxng_est_injoignable():
    client = _FallbackHTTPClient()
    tool = WebSearch(
        searxng_url="http://searxng:8080",
        api_key="cle-tavily",
        client=client,
    )
    assert await tool("question") == "Reponse Tavily."
    assert [method for method, _url in client.calls] == ["get", "post"]


class _EmptySearXThenTavilyClient:
    """Reproduction du CAPTCHA : SearXNG repond 200 mais sans resultat."""

    def __init__(self):
        self.calls = []

    async def get(self, url, params=None, headers=None):
        self.calls.append(("get", url))
        return _FakeResponse({"results": []})

    async def post(self, url, json=None, headers=None):
        self.calls.append(("post", url))
        return _FakeResponse({"answer": "Reponse Tavily apres CAPTCHA."})


@runs_async
async def test_zero_resultat_searxng_declenche_le_repli_tavily():
    """Un 200 vide est un echec de recherche, pas un resultat final."""
    client = _EmptySearXThenTavilyClient()
    tool = WebSearch(
        searxng_url="http://searxng:8080",
        api_key="cle-tavily",
        client=client,
    )

    assert await tool("question bloquee par CAPTCHA") == "Reponse Tavily apres CAPTCHA."
    assert [method for method, _url in client.calls] == ["get", "post"]


class _Provider:
    def __init__(self, name, available, text):
        self.name, self.available, self.text, self.calls = name, available, text, []

    async def search(self, query):
        self.calls.append(query)
        return self.available, self.text


@runs_async
async def test_la_chaine_passe_au_fournisseur_suivant_apres_un_vide():
    searx = _Provider("searx", False, "Je n'ai rien trouve sur ce sujet.")
    ddgs = _Provider("ddgs", False, "La recherche internet n'a pas repondu.")
    brave = _Provider("brave", True, "Resultat Brave.")
    serper = _Provider("serper", True, "Ne doit pas etre appele.")

    tool = WebSearch(providers=[searx, ddgs, brave, serper])
    assert await tool("une question") == "Resultat Brave."
    assert [provider.calls for provider in (searx, ddgs, brave, serper)] == [
        ["une question"], ["une question"], ["une question"], [],
    ]


@runs_async
async def test_squelettes_http_ont_les_endpoints_et_jetons_attendus():
    providers = [
        (BraveSearch(api_key="brave-secret", client=FakeHTTPClient(_FakeResponse({"web": {"results": [{"title": "B", "description": "ok"}]}}))), BRAVE_ENDPOINT, "get"),
        (ExaSearch(api_key="exa-secret", client=FakeHTTPClient(_FakeResponse({"results": [{"title": "E", "text": "ok"}]}))), EXA_ENDPOINT, "post"),
        (JinaSearch(api_key="jina-secret", client=FakeHTTPClient(_FakeResponse({"data": [{"title": "J", "description": "ok"}]}))), JINA_ENDPOINT, "get"),
        (SerperSearch(api_key="serper-secret", client=FakeHTTPClient(_FakeResponse({"organic": [{"title": "S", "snippet": "ok"}]}))), SERPER_ENDPOINT, "post"),
    ]
    for provider, endpoint, method in providers:
        out = await provider("question")
        assert out.endswith("ok")
        call = provider.client.calls[0]
        assert call["url"] == endpoint
        assert "secret" not in out
        assert provider.api_key in str(call["headers"])
        assert method in {"get", "post"}


@runs_async
async def test_la_requete_a_la_bonne_forme():
    client = FakeHTTPClient(_FakeResponse(ANSWER))
    tool = TavilySearch(api_key="cle-secrete", client=client)
    await tool("meteo a Paris")

    call = client.calls[0]
    assert call["url"] == "https://api.tavily.com/search"
    assert call["headers"]["Authorization"] == "Bearer cle-secrete"
    assert call["json"]["query"] == "meteo a Paris"
    assert call["json"]["include_answer"] is True
    assert call["json"]["search_depth"] == "basic"
    assert 1 <= call["json"]["max_results"] <= 20


@runs_async
async def test_la_reponse_privilegie_le_champ_answer():
    tool = TavilySearch(api_key="k", client=FakeHTTPClient(_FakeResponse(ANSWER)))
    out = await tool("meteo a Paris")
    assert out.startswith("Il fait 18 degres et nuageux a Paris.")
    assert "cle-secrete" not in out
    assert "{" not in out, "un resultat lu a voix haute ne contient pas de JSON"


@runs_async
async def test_sans_answer_on_resume_les_resultats():
    payload = {"query": "x", "results": ANSWER["results"]}
    out = await TavilySearch(api_key="k", client=FakeHTTPClient(_FakeResponse(payload)))("x")
    assert "Meteo Paris" in out
    assert "18 degres" in out


@runs_async
async def test_zero_resultat_se_dit():
    out = await TavilySearch(api_key="k", client=FakeHTTPClient(_FakeResponse({"results": []})))("x")
    assert out.strip()
    assert "{" not in out


@runs_async
async def test_sans_cle_aucun_appel_reseau():
    client = FakeHTTPClient(_FakeResponse(ANSWER))
    out = await TavilySearch(api_key="", client=client)("meteo")
    assert client.calls == [], "sans cle, l'outil ne doit rien appeler"
    assert out.strip()
    assert "TAVILY_API_KEY" not in out, "le message est pour l'oreille, pas pour le journal"


@runs_async
async def test_sans_client_aucun_appel_reseau():
    out = await TavilySearch(api_key="k", client=None)("meteo")
    assert out.strip()


@runs_async
async def test_erreur_http_reste_dicible():
    client = FakeHTTPClient(_FakeResponse({"detail": "unauthorized"}, status_code=401))
    out = await TavilySearch(api_key="k", client=client)("meteo")
    assert out.strip()
    assert "401" not in out
    assert "unauthorized" not in out


@runs_async
async def test_exception_reseau_reste_dicible():
    client = FakeHTTPClient(raises=RuntimeError("connexion refusee"))
    out = await TavilySearch(api_key="k", client=client)("meteo")
    assert out.strip()
    assert "connexion refusee" not in out


@runs_async
async def test_le_resultat_reste_court():
    payload = {"answer": "z" * 5000, "results": []}
    out = await TavilySearch(api_key="k", client=FakeHTTPClient(_FakeResponse(payload)))("x")
    assert len(out) <= 1200
