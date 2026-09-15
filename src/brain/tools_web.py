"""
BRAIN: la recherche internet comme premier outil branche.

SearXNG local est prioritaire lorsqu'une URL est configuree. Tavily reste le
repli lorsque SearXNG n'est pas joignable et qu'une cle existe. Les deux
backends rendent le meme contrat vocal court : reponse directe quand elle
existe, sinon titres et extraits des premiers resultats.

**Le client HTTP est injecte.** C'est ce qui rend l'outil testable sans reseau.

Tout ce qui sort d'ici est destine a etre lu a voix haute : pas de JSON, pas de
code HTTP, pas de trace d'exception.
"""
import logging
import os
from typing import Any, Dict, Optional

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"
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
        if not self.api_key:
            logger.info("web_search sans cle: aucun appel emis")
            return _NO_KEY
        if self.client is None:
            logger.warning("web_search sans client HTTP: aucun appel emis")
            return _NO_CLIENT

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
            return _FAILED

        if getattr(response, "status_code", 0) != 200:
            logger.warning(f"web_search: HTTP {getattr(response, 'status_code', '?')}")
            return _FAILED

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"web_search: reponse illisible ({exc})")
            return _FAILED

        if not isinstance(payload, dict):
            logger.warning("web_search: reponse inattendue (pas un objet)")
            return _FAILED

        return _speakable(payload, self.max_results)


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
        return True, _speakable(payload, self.max_results)

    async def __call__(self, query: str) -> str:
        _available, text = await self.search(query)
        return text


class WebSearch:
    """SearXNG d'abord, Tavily seulement si l'instance locale tombe."""

    def __init__(
        self,
        searxng_url: str,
        api_key: Optional[str] = None,
        client: Any = None,
        endpoint: str = TAVILY_ENDPOINT,
        max_results: int = 3,
        search_depth: str = "basic",
    ):
        self.searxng = SearXNGSearch(
            url=searxng_url, client=client, max_results=max_results
        )
        self.tavily = TavilySearch(
            api_key=api_key,
            client=client,
            endpoint=endpoint,
            max_results=max_results,
            search_depth=search_depth,
        )

    async def __call__(self, query: str) -> str:
        available, text = await self.searxng.search(query)
        if available:
            return text
        if self.tavily.api_key:
            logger.info("web_search: repli Tavily apres echec SearXNG")
            return await self.tavily(query)
        return text


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
    handler = (
        WebSearch(
            searxng_url=searxng_url,
            api_key=api_key,
            client=client,
            **kwargs,
        )
        if searxng_url
        else TavilySearch(api_key=api_key, client=client, **kwargs)
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
