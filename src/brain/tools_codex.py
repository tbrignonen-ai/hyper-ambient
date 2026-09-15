"""
BRAIN: `ask_codex`, premier outil du harnais local.

MOTHER ne pilote pas Codex elle-meme : elle pose une question a un **pont**
qui tourne sur l'hote (`native/codexbridge/bridge.py`), lequel lance
`codex exec` en bac a sable **lecture seule**. D'ou `danger="read"` : Codex
lit le depot et repond, il n'ecrit rien.

Meme contrat que `web_search` : client HTTP injecte, aucun appel sans jeton,
et tout ce qui sort est prononcable — pas de JSON, pas de code HTTP, pas de
trace. Le chemin degrade (pont eteint, lent, en erreur) est le geste 3 de la
soutenance : il doit s'entendre comme une phrase, pas comme une panne.
"""
import logging
import os
from typing import Any, Optional

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)

# Le conteneur joint l'hote par host.docker.internal ; surcharge possible.
CODEX_BRIDGE_ENDPOINT = os.getenv(
    "CODEX_BRIDGE_URL", "http://host.docker.internal:8765/ask"
)

ASK_CODEX_DESCRIPTION = (
    "Pose une question a Codex, un agent de code qui lit les fichiers du projet "
    "sur la machine. A utiliser pour une question sur le code, le depot ou les "
    "fichiers locaux. Codex lit seulement, il ne modifie rien."
)

ASK_CODEX_PARAMETERS = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "La question pour Codex, en langage naturel.",
        }
    },
    "required": ["question"],
}

_NO_TOKEN = "Je n'ai pas encore d'acces a Codex."
_NO_CLIENT = "Mon pont vers Codex n'est pas initialise."
_UNREACHABLE = "Codex ne repond pas pour l'instant, je continue sans lui."
_FAILED = "Codex n'a pas pu repondre a cette question."
_EMPTY = "Codex n'a rien trouve a dire la-dessus."


class CodexBridge:
    """Handler d'outil : une question en entree, une phrase en sortie."""

    def __init__(
        self,
        token: Optional[str] = None,
        client: Any = None,
        endpoint: str = CODEX_BRIDGE_ENDPOINT,
        timeout_s: float = 45.0,
    ):
        self.token = token if token is not None else os.getenv("CODEX_BRIDGE_TOKEN", "")
        self.client = client
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def __call__(self, question: str) -> str:
        if not self.token:
            logger.info("ask_codex sans jeton: aucun appel emis")
            return _NO_TOKEN
        if self.client is None:
            logger.warning("ask_codex sans client HTTP: aucun appel emis")
            return _NO_CLIENT

        try:
            response = await self.client.post(
                self.endpoint,
                json={"question": question},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout_s,
            )
        except Exception as exc:  # le detail va au journal, pas a l'oreille
            logger.warning(f"ask_codex: pont injoignable ({exc!r})")
            return _UNREACHABLE

        if getattr(response, "status_code", 0) != 200:
            logger.warning(f"ask_codex: HTTP {getattr(response, 'status_code', '?')}")
            return _FAILED

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"ask_codex: reponse illisible ({exc})")
            return _FAILED

        if not isinstance(payload, dict) or not payload.get("ok"):
            reason = payload.get("error") if isinstance(payload, dict) else None
            logger.warning(f"ask_codex: echec annonce par le pont ({reason})")
            return _FAILED

        answer = payload.get("answer")
        text = answer.strip() if isinstance(answer, str) else ""
        if not text:
            return _EMPTY
        if len(text) > MAX_TOOL_CONTENT_CHARS:
            text = text[: MAX_TOOL_CONTENT_CHARS - 4].rstrip() + " […]"
        return text


def register_ask_codex(
    registry: ToolRegistry,
    token: Optional[str] = None,
    client: Any = None,
    **kwargs,
) -> ToolSpec:
    """Enregistre `ask_codex`. `danger="read"` : le pont epingle Codex en
    bac a sable lecture seule."""
    return registry.register(
        ToolSpec(
            name="ask_codex",
            description=ASK_CODEX_DESCRIPTION,
            parameters=ASK_CODEX_PARAMETERS,
            danger="read",
            handler=CodexBridge(token=token, client=client, **kwargs),
        )
    )
