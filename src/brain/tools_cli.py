"""
BRAIN: `ask_claude` et `ask_hermes`, meme geste que `ask_codex`.

hyper-ambient ne pilote pas les CLI elle-meme : elle pose une question a un **pont**
qui tourne sur l'hote (`native/clibridge/bridge.py`). Claude est lance en
lecture seule (`-p --restricted --permission-mode plan`). Hermes a le chemin
ecrit, mais le pont refuse de l'allumer tant que `CLI_BRIDGE_HERMES=1` n'arme
pas le chemin. D'ou `danger="read"`.

Meme contrat que `ask_codex` : client HTTP injecte, aucun appel sans jeton,
et tout ce qui sort est prononcable — pas de JSON, pas de code HTTP, pas de
trace.
"""
import logging
import os
from typing import Any, Optional

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry, ToolSpec
from src.brain.mandat import RegistreMandats, deposer_depuis_outil

logger = logging.getLogger(__name__)

CLI_BRIDGE_ENDPOINT = os.getenv(
    "CLI_BRIDGE_URL", "http://host.docker.internal:8766/ask"
)

# Cette description est la SEULE chose que le modele lit pour choisir entre
# Claude et Codex. Ecrite a l'identique de celle de Codex, elle ne lui donnait
# aucun critere : il tirait au sort. La distinction posee ici est vraie, pas
# cosmetique — Codex repond vite sur un fichier, Claude raisonne a travers
# plusieurs. `test_deux_outils_ne_partagent_jamais_la_meme_description` la
# defend.
ASK_CLAUDE_DESCRIPTION = (
    "Demande a Claude une analyse d'architecture ou une revue : ce qui relie "
    "plusieurs fichiers entre eux, si un choix technique tient debout, ce qu'une "
    "modification risquerait de casser ailleurs. Plus lent, et reserve aux "
    "questions larges — pour lire un seul fichier, prendre Codex."
)

ASK_HERMES_DESCRIPTION = (
    "Pose une question a Hermes, un agent de code qui lit les fichiers du projet "
    "sur la machine. Hermes peut etre eteint : dans ce cas l'outil le dit "
    "en une phrase, sans erreur technique."
)

ASK_CLAUDE_PARAMETERS = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "La question pour Claude, en langage naturel.",
        }
    },
    "required": ["question"],
}

ASK_HERMES_PARAMETERS = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "La question pour Hermes, en langage naturel.",
        }
    },
    "required": ["question"],
}

_NAMES = {
    "claude": "Claude",
    "hermes": "Hermes",
}

_NO_TOKEN = {
    "claude": "Je n'ai pas encore d'acces a Claude.",
    "hermes": "Je n'ai pas encore d'acces a Hermes.",
}
_NO_CLIENT = {
    "claude": "Mon pont vers Claude n'est pas initialise.",
    "hermes": "Mon pont vers Hermes n'est pas initialise.",
}
_UNREACHABLE = {
    "claude": "Claude ne repond pas pour l'instant, je continue sans lui.",
    "hermes": "Hermes ne repond pas pour l'instant, je continue sans lui.",
}
_FAILED = {
    "claude": "Claude n'a pas pu repondre a cette question.",
    "hermes": "Hermes n'est pas disponible pour l'instant, je continue sans lui.",
}
_EMPTY = {
    "claude": "Claude n'a rien trouve a dire la-dessus.",
    "hermes": "Hermes n'a rien trouve a dire la-dessus.",
}


class CliBridge:
    """Handler d'outil : une question en entree, une phrase en sortie."""

    def __init__(
        self,
        token: Optional[str] = None,
        client: Any = None,
        endpoint: str = CLI_BRIDGE_ENDPOINT,
        timeout_s: float = 45.0,
        agent: str = "claude",
    ):
        self.agent = (agent or "claude").strip().lower()
        if self.agent not in _NAMES:
            self.agent = "claude"
        self.token = token if token is not None else os.getenv("CLI_BRIDGE_TOKEN", "")
        self.client = client
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def __call__(self, question: str) -> str:
        agent = self.agent
        if not self.token:
            logger.info(f"ask_{agent} sans jeton: aucun appel emis")
            return _NO_TOKEN[agent]
        if self.client is None:
            logger.warning(f"ask_{agent} sans client HTTP: aucun appel emis")
            return _NO_CLIENT[agent]

        try:
            response = await self.client.post(
                self.endpoint,
                json={"question": question, "agent": agent},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout_s,
            )
        except Exception as exc:  # le detail va au journal, pas a l'oreille
            logger.warning(f"ask_{agent}: pont injoignable ({exc!r})")
            return _UNREACHABLE[agent]

        if getattr(response, "status_code", 0) != 200:
            logger.warning(f"ask_{agent}: HTTP {getattr(response, 'status_code', '?')}")
            return _FAILED[agent]

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"ask_{agent}: reponse illisible ({exc})")
            return _FAILED[agent]

        if not isinstance(payload, dict) or not payload.get("ok"):
            reason = payload.get("error") if isinstance(payload, dict) else None
            logger.warning(f"ask_{agent}: echec annonce par le pont ({reason})")
            return _FAILED[agent]

        answer = payload.get("answer")
        text = answer.strip() if isinstance(answer, str) else ""
        if not text:
            return _EMPTY[agent]
        if len(text) > MAX_TOOL_CONTENT_CHARS:
            text = text[: MAX_TOOL_CONTENT_CHARS - 4].rstrip() + " […]"
        return text


class ClaudeMandat:
    """Handler vocal : confie à Claude sans attendre son pont."""

    def __init__(self, registre_mandats: RegistreMandats, pont: CliBridge):
        self.registre_mandats = registre_mandats
        self.pont = pont

    async def __call__(self, question: str) -> str:
        return await deposer_depuis_outil(
            self.registre_mandats, "Claude", question, self.pont
        )


def register_ask_claude(
    registry: ToolRegistry,
    token: Optional[str] = None,
    client: Any = None,
    registre_mandats: Optional[RegistreMandats] = None,
    **kwargs,
) -> ToolSpec:
    """Enregistre `ask_claude`. `danger="read"` : le pont epingle Claude en
    lecture seule."""
    kwargs.setdefault("agent", "claude")
    pont = CliBridge(token=token, client=client, **kwargs)
    handler = (
        ClaudeMandat(registre_mandats, pont)
        if registre_mandats is not None
        else pont
    )
    return registry.register(
        ToolSpec(
            name="ask_claude",
            description=ASK_CLAUDE_DESCRIPTION,
            parameters=ASK_CLAUDE_PARAMETERS,
            danger="read",
            handler=handler,
        )
    )


def register_ask_hermes(
    registry: ToolRegistry,
    token: Optional[str] = None,
    client: Any = None,
    **kwargs,
) -> ToolSpec:
    """Enregistre `ask_hermes`. `danger="read"`. Hermes eteint => phrase, pas
    d'exception."""
    kwargs["agent"] = "hermes"
    return registry.register(
        ToolSpec(
            name="ask_hermes",
            description=ASK_HERMES_DESCRIPTION,
            parameters=ASK_HERMES_PARAMETERS,
            danger="read",
            handler=CliBridge(token=token, client=client, **kwargs),
        )
    )
