"""
BRAIN: recherche web multi-fournisseurs, testable sans reseau.

La chaine est SearXNG, DuckDuckGo (ddgs), Tavily, Brave, Exa, Jina puis
Serper. Un HTTP 200 sans contenu utilisable est un echec de recherche : il ne
doit jamais couper la chaine (cas observe avec CAPTCHA SearXNG). Les fournisseurs
avec cle ne sont actifs que si leur variable d'environnement est renseignee.

**Le client HTTP est injecte.** C'est ce qui rend l'outil testable sans reseau.

Tout ce qui sort d'ici est destine a etre lu a voix haute : pas de JSON, pas de
code HTTP, pas de trace d'exception.
"""
import logging
import os
from typing import Any, Dict, Iterable, Optional

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
EXA_ENDPOINT = "https://api.exa.ai/search"
JINA_ENDPOINT = "https://s.jina.ai/"
SERPER_ENDPOINT = "https://google.serper.dev/search"
SEARXNG_SEARCH_PATH = "/search"

WEB_SEARCH_DESCRIPTION = (
    "Cherche une information a jour sur internet et rend une reponse courte. "
    "A utiliser pour l'actualite, la meteo, les prix, ou tout fait posterieur a "
    "l'entrainement du modele."
)

WEB_SEARCH_PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "La question, formulee en langage naturel.",
        }
    },
    "required": ["query"],
}

# Phrases de repli. Elles sont prononcables telles quelles : c'est le modele qui
# les reformulera, mais meme brutes elles ne cassent pas la voix.
_NO_KEY = "Je n'ai pas encore d'acces a la recherche internet."
_NO_CLIENT = "Ma recherche internet n'est pas initialisee."
_FAILED = "La recherche internet n'a pas repondu."
_EMPTY = "Je n'ai rien trouve sur ce sujet."


def _result_is_usable(text: str) -> bool:
    """`_EMPTY` n'est pas une reponse : le fournisseur suivant doit essayer."""
    return bool(text.strip()) and text not in {_EMPTY, _FAILED, _NO_KEY, _NO_CLIENT}


class TavilySearch:
    """Handler d'outil : une question en entree, un texte court en sortie."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Any = None,
        endpoint: str = TAVILY_ENDPOINT,
        max_results: int = 3,
        search_depth: str = "basic",  # 1 credit ; "advanced" en coute 2
    ):
        self.api_key = api_key if api_key is not None else os.getenv("TAVILY_API_KEY", "")
        self.client = client
        self.endpoint = endpoint
        self.max_results = max(1, min(int(max_results), 20))
        self.search_depth = search_depth

    async def __call__(self, query: str) -> str:
        _available, text = await self.search(query)
        return text

    async def search(self, query: str) -> tuple[bool, str]:
        if not self.api_key:
            logger.info("web_search sans cle: aucun appel emis")
            return False, _NO_KEY
        if self.client is None:
            logger.warning("web_search sans client HTTP: aucun appel emis")
            return False, _NO_CLIENT

        try:
            response = await self.client.post(
                self.endpoint,
                json={
                    "query": query,
                    "include_answer": True,
                    "max_results": self.max_results,
                    "search_depth": self.search_depth,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        except Exception as exc:  # le detail va au journal, pas a l'oreille
            logger.warning(f"web_search: appel en echec ({exc})")
            return False, _FAILED

        if getattr(response, "status_code", 0) != 200:
            logger.warning(f"web_search: HTTP {getattr(response, 'status_code', '?')}")
            return False, _FAILED

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"web_search: reponse illisible ({exc})")
            return False, _FAILED

        if not isinstance(payload, dict):
            logger.warning("web_search: reponse inattendue (pas un objet)")
            return False, _FAILED

        text = _speakable(payload, self.max_results)
        return _result_is_usable(text), text


class DuckDuckGoSearch:
    """Repli sans cle, charge paresseusement pour ne pas imposer ddgs au boot."""

    def __init__(self, max_results: int = 3, searcher: Any = None):
        self.max_results = max(1, min(int(max_results), 20))
        self.searcher = searcher

    async def __call__(self, query: str) -> str:
        _available, text = await self.search(query)
        return text

    async def search(self, query: str) -> tuple[bool, str]:
        searcher = self.searcher
        if searcher is None:
            try:
                from ddgs import DDGS
            except ImportError:
                logger.info("web_search: ddgs non installe, repli suivant")
                return False, _NO_CLIENT
            searcher = DDGS()
        try:
            text_method = getattr(searcher, "text", searcher)
            results = await _in_thread(text_method, query, max_results=self.max_results)
        except Exception as exc:
            logger.warning(f"web_search: DuckDuckGo en echec ({exc})")
            return False, _FAILED
        raw_results = list(results or [])
        text = _speakable(
            {"results": [
                {
                    "title": item.get("title", ""),
                    "content": item.get("body") or item.get("content", ""),
                }
                for item in raw_results if isinstance(item, dict)
            ]},
            self.max_results,
        )
        return _result_is_usable(text), text

    async def __call__(self, query: str) -> str:
        _available, text = await self.search(query)
        return text


async def _in_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Compatibilite Python 3.8+ sans bloquer le tour vocal sur ddgs synchrone."""
    import asyncio
    import functools

    return await asyncio.get_running_loop().run_in_executor(
        None, functools.partial(func, *args, **kwargs)
    )


class KeyedSearch:
    """Socle des fournisseurs HTTP : aucune requete sans cle ni client."""

    env_key = ""
    name = "web"

    def __init__(self, api_key: Optional[str] = None, client: Any = None, max_results: int = 3):
        self.api_key = api_key if api_key is not None else os.getenv(self.env_key, "")
        self.client = client
        self.max_results = max(1, min(int(max_results), 20))

    async def __call__(self, query: str) -> str:
        _available, text = await self.search(query)
        return text

    async def _request(self, query: str) -> Any:
        raise NotImplementedError

    def _payload(self, response: Any) -> Optional[Dict[str, Any]]:
        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"web_search: reponse {self.name} illisible ({exc})")
            return None
        return payload if isinstance(payload, dict) else None

    async def search(self, query: str) -> tuple[bool, str]:
        if not self.api_key:
            return False, _NO_KEY
        if self.client is None:
            return False, _NO_CLIENT
        try:
            response = await self._request(query)
        except Exception as exc:
            logger.warning(f"web_search: {self.name} en echec ({exc})")
            return False, _FAILED
        if getattr(response, "status_code", 0) != 200:
            logger.warning(f"web_search: {self.name} HTTP {getattr(response, 'status_code', '?')}")
            return False, _FAILED
        payload = self._payload(response)
        if payload is None:
            return False, _FAILED
        text = _speakable(payload, self.max_results)
        return _result_is_usable(text), text


class BraveSearch(KeyedSearch):
    env_key, name = "BRAVE_API_KEY", "Brave"

    async def _request(self, query: str) -> Any:
        response = await self.client.get(
            BRAVE_ENDPOINT,
            params={"q": query, "count": self.max_results},
            headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
        )
        return response

    def _payload(self, response: Any) -> Optional[Dict[str, Any]]:
        payload = super()._payload(response)
        if payload is None:
            return None
        web = payload.get("web")
        results = web.get("results", []) if isinstance(web, dict) else []
        return {"results": [
            {"title": item.get("title", ""), "content": item.get("description", "")}
            for item in results if isinstance(item, dict)
        ]}


class ExaSearch(KeyedSearch):
    env_key, name = "EXA_API_KEY", "Exa"

    async def _request(self, query: str) -> Any:
        return await self.client.post(
            EXA_ENDPOINT,
            json={"query": query, "numResults": self.max_results, "contents": {"text": True}},
            headers={"Content-Type": "application/json", "x-api-key": self.api_key},
        )

    def _payload(self, response: Any) -> Optional[Dict[str, Any]]:
        payload = super()._payload(response)
        if payload is None:
            return None
        results = payload.get("results", [])
        if not isinstance(results, list):
            return {"results": []}
        return {"results": [
            {
                "title": item.get("title", ""),
                "content": item.get("text") or " ".join(
                    part for part in item.get("highlights", []) if isinstance(part, str)
                ),
            }
            for item in results if isinstance(item, dict)
        ]}


class JinaSearch(KeyedSearch):
    env_key, name = "JINA_API_KEY", "Jina"

    async def _request(self, query: str) -> Any:
        return await self.client.get(
            JINA_ENDPOINT,
            params={"q": query},
            headers={"Accept": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )

    def _payload(self, response: Any) -> Optional[Dict[str, Any]]:
        payload = super()._payload(response)
        if payload is None:
            return None
        results = payload.get("data", payload.get("results", []))
        return {"results": [
            {"title": item.get("title", ""), "content": item.get("description") or item.get("content", "")}
            for item in results if isinstance(item, dict)
        ] if isinstance(results, list) else []}


class SerperSearch(KeyedSearch):
    env_key, name = "SERPER_API_KEY", "Serper"

    async def _request(self, query: str) -> Any:
        return await self.client.post(
            SERPER_ENDPOINT,
            json={"q": query, "num": self.max_results},
            headers={"Content-Type": "application/json", "X-API-KEY": self.api_key},
        )

    def _payload(self, response: Any) -> Optional[Dict[str, Any]]:
        payload = super()._payload(response)
        if payload is None:
            return None
        results = payload.get("organic", [])
        return {"results": [
            {"title": item.get("title", ""), "content": item.get("snippet", "")}
            for item in results if isinstance(item, dict)
        ] if isinstance(results, list) else []}


class SearXNGSearch:
    """Recherche sans cle sur une instance SearXNG configuree."""

    def __init__(self, url: str, client: Any = None, max_results: int = 3):
        base = url.strip().rstrip("/")
        self.endpoint = (
            base if base.endswith(SEARXNG_SEARCH_PATH) else base + SEARXNG_SEARCH_PATH
        )
        self.client = client
        self.max_results = max(1, min(int(max_results), 20))

    async def search(self, query: str) -> tuple[bool, str]:
        """Rend ``(joignable, texte)`` pour permettre un repli explicite."""
        if self.client is None:
            logger.warning("web_search SearXNG sans client HTTP")
            return False, _NO_CLIENT

        try:
            response = await self.client.get(
                self.endpoint,
                params={"q": query, "format": "json"},
                headers={"Accept": "application/json"},
            )
        except Exception as exc:
            logger.warning(f"web_search: SearXNG injoignable ({exc})")
            return False, _FAILED

        if getattr(response, "status_code", 0) != 200:
            logger.warning(
                f"web_search: SearXNG HTTP {getattr(response, 'status_code', '?')}"
            )
            return False, _FAILED

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"web_search: reponse SearXNG illisible ({exc})")
            return False, _FAILED

        if not isinstance(payload, dict):
            logger.warning("web_search: reponse SearXNG inattendue")
            return False, _FAILED
        text = _speakable(payload, self.max_results)
        if not _result_is_usable(text):
            logger.info("web_search: SearXNG joignable mais sans resultat utilisable")
        return _result_is_usable(text), text

    async def __call__(self, query: str) -> str:
        _available, text = await self.search(query)
        return text


class WebSearch:
    """Essaie les fournisseurs dans l'ordre, y compris apres un resultat vide."""

    def __init__(
        self,
        searxng_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Any = None,
        endpoint: str = TAVILY_ENDPOINT,
        max_results: int = 3,
        search_depth: str = "basic",
        ddgs_searcher: Any = None,
        brave_api_key: Optional[str] = None,
        exa_api_key: Optional[str] = None,
        jina_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
        providers: Optional[Iterable[Any]] = None,
    ):
        self.searxng = (
            SearXNGSearch(url=searxng_url, client=client, max_results=max_results)
            if searxng_url
            else None
        )
        self.ddgs = DuckDuckGoSearch(max_results=max_results, searcher=ddgs_searcher)
        self.tavily = TavilySearch(
            api_key=api_key,
            client=client,
            endpoint=endpoint,
            max_results=max_results,
            search_depth=search_depth,
        )
        self.brave = BraveSearch(api_key=brave_api_key, client=client, max_results=max_results)
        self.exa = ExaSearch(api_key=exa_api_key, client=client, max_results=max_results)
        self.jina = JinaSearch(api_key=jina_api_key, client=client, max_results=max_results)
        self.serper = SerperSearch(api_key=serper_api_key, client=client, max_results=max_results)
        self.providers = list(providers) if providers is not None else [
            provider for provider in (
                self.searxng, self.ddgs, self.tavily, self.brave,
                self.exa, self.jina, self.serper,
            ) if provider is not None
        ]

    async def __call__(self, query: str) -> str:
        last_text = _NO_KEY
        for provider in self.providers:
            available, text = await provider.search(query)
            if available:
                return text
            last_text = text
            logger.info("web_search: repli apres %s", provider.__class__.__name__)
        # Une erreur reseau est plus utile qu'un "pas de cle" si tout a echoue.
        return _FAILED if last_text == _FAILED else _EMPTY if last_text == _EMPTY else last_text


def _speakable(payload: Dict[str, Any], max_results: int) -> str:
    """Met la reponse Tavily en une forme lisible a voix haute."""
    raw_answer = payload.get("answer")
    answer = raw_answer.strip() if isinstance(raw_answer, str) else ""
    raw_results = payload.get("results")
    results = raw_results if isinstance(raw_results, list) else []

    if answer:
        text = answer
    elif results:
        parts = []
        for r in results[:max_results]:
            if not isinstance(r, dict):
                continue
            title_raw = r.get("title")
            body_raw = r.get("content")
            title = title_raw.strip() if isinstance(title_raw, str) else ""
            body = body_raw.strip() if isinstance(body_raw, str) else ""
            if title and body:
                parts.append(f"{title} : {body}")
            elif title or body:
                parts.append(title or body)
        text = " ".join(parts).strip()
    else:
        return _EMPTY

    if not text:
        return _EMPTY

    # Meme garde que ToolResult, appliquee ici aussi : l'outil peut etre appele
    # hors boucle, et une reponse de 5 000 caracteres lue a voix haute est la
    # regression que tout ce lot cherche a eviter.
    if len(text) > MAX_TOOL_CONTENT_CHARS:
        text = text[: MAX_TOOL_CONTENT_CHARS - 4].rstrip() + " […]"
    return text


def register_web_search(
    registry: ToolRegistry,
    api_key: Optional[str] = None,
    client: Any = None,
    searxng_url: Optional[str] = None,
    **kwargs,
) -> ToolSpec:
    """Enregistre `web_search` dans un registre. `danger="read"` : la recherche
    lit le monde, elle ne le modifie pas."""
    handler = WebSearch(
        searxng_url=searxng_url,
        api_key=api_key,
        client=client,
        **kwargs,
    )
    return registry.register(
        ToolSpec(
            name="web_search",
            description=WEB_SEARCH_DESCRIPTION,
            parameters=WEB_SEARCH_PARAMETERS,
            danger="read",
            handler=handler,
        )
    )
