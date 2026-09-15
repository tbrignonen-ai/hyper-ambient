"""
BRAIN: `ask_muse`, le second avis.

`ask_codex` interroge le depot : Codex lit les fichiers de cette machine.
`ask_muse` ne fait pas ca. Le pont Muse tourne dans WSL avec son **propre**
espace de travail (`~/.local/share/muse-bridge/hermes/workspace`) et ne voit
pas le projet en cours. Poser les deux outils cote a cote n'a donc de sens que
si leurs descriptions tranchent : c'est le seul texte que le modele lit pour
choisir, et deux descriptions jumelles font un tirage au sort.

D'ou le partage : **Codex pour les fichiers, Muse pour le raisonnement.**

Le pont etait deja debout — il servait a Hermes, qui reste eteint. On ne
rallume rien, on s'adresse a ce qui ecoute deja (mesure du 13 septembre depuis
le conteneur : HTTP 200 en 23,8 s sur `host.docker.internal:19124`).

Meme contrat que `ask_codex`, pour les memes raisons vocales : client HTTP
injecte, aucun appel sans configuration explicite, et **tout ce qui sort est
prononcable** — ni JSON, ni code HTTP, ni trace. Le chemin degrade doit
s'entendre comme une phrase, pas comme une panne.
"""
import logging
import os
from typing import Any, Optional

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)

# Vide par defaut : brancher un second agent est une decision, pas un effet de
# bord. Sans cette variable, l'outil n'est simplement pas declare au modele.
MUSE_BRIDGE_URL = os.getenv("MUSE_BRIDGE_URL", "")

ASK_MUSE_DESCRIPTION = (
    "Demande un second avis a Muse, une autre intelligence artificielle qui "
    "tourne sur cette machine. A utiliser pour une question de raisonnement, "
    "une explication generale, une definition, ou pour confronter deux avis. "
    "Muse ne voit pas le projet en cours et ne lit rien sur le disque."
)

ASK_MUSE_PARAMETERS = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "La question pour Muse, en langage naturel.",
        }
    },
    "required": ["question"],
}

_NON_CONFIGURE = "Je n'ai pas encore d'acces a Muse."
_SANS_CLIENT = "Mon pont vers Muse n'est pas initialise."
_INJOIGNABLE = "Muse ne repond pas pour l'instant, je continue sans elle."
_ECHEC = "Muse n'a pas pu repondre a cette question."
_VIDE = "Muse n'a rien trouve a dire la-dessus."

# La question part telle quelle, mais la forme de la reponse est imposee : elle
# sera lue a voix haute, et un pont qui rend du markdown fait epeler des etoiles.
_CONSIGNE_VOCALE = (
    "Reponds en francais, en deux ou trois phrases parlables, sans code, "
    "sans liste ni markdown. Question : "
)


class MuseBridge:
    """Handler d'outil : une question en entree, une phrase en sortie."""

    def __init__(
        self,
        url: Optional[str] = None,
        client: Any = None,
        timeout_s: float = 240.0,
    ):
        # 240 s : le pont lance un `muse exec` neuf a chaque appel et plafonne
        # lui-meme a 300 s. Mesure : 23,8 s. Le delai large existe pour que ce
        # soit le pont qui rende sa phrase, jamais le client qui coupe.
        self.url = (url if url is not None else MUSE_BRIDGE_URL).rstrip("/")
        self.client = client
        self.timeout_s = timeout_s

    async def __call__(self, question: str) -> str:
        if not self.url:
            logger.info("ask_muse sans URL de pont: aucun appel emis")
            return _NON_CONFIGURE
        if self.client is None:
            logger.warning("ask_muse sans client HTTP: aucun appel emis")
            return _SANS_CLIENT

        try:
            response = await self.client.post(
                f"{self.url}/ask",
                json={"instruction": _CONSIGNE_VOCALE + (question or "").strip()},
                timeout=self.timeout_s,
            )
        except Exception as exc:  # le detail va au journal, pas a l'oreille
            logger.warning(f"ask_muse: pont injoignable ({exc!r})")
            return _INJOIGNABLE

        if getattr(response, "status_code", 0) != 200:
            logger.warning(f"ask_muse: HTTP {getattr(response, 'status_code', '?')}")
            return _ECHEC

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning(f"ask_muse: reponse illisible ({exc})")
            return _ECHEC

        if not isinstance(payload, dict):
            return _ECHEC

        texte = payload.get("text")
        texte = texte.strip() if isinstance(texte, str) else ""
        if not texte:
            return _VIDE
        if len(texte) > MAX_TOOL_CONTENT_CHARS:
            texte = texte[: MAX_TOOL_CONTENT_CHARS - 4].rstrip() + " […]"
        return texte


def register_ask_muse(
    registry: ToolRegistry,
    url: Optional[str] = None,
    client: Any = None,
    **kwargs,
) -> ToolSpec:
    """Enregistre `ask_muse`. `danger="read"` : Muse repond, elle n'ecrit rien
    sur cette machine."""
    return registry.register(
        ToolSpec(
            name="ask_muse",
            description=ASK_MUSE_DESCRIPTION,
            parameters=ASK_MUSE_PARAMETERS,
            danger="read",
            handler=MuseBridge(url=url, client=client, **kwargs),
        )
    )
