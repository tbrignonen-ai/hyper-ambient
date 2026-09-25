"""L'etat courant d'hyper-ambient, emis vers sa presence visuelle.

Le conteneur n'a pas plus acces a l'ecran qu'au micro : l'affichage est un client
natif sur l'hote, et il apprend ce que fait hyper-ambient par le meme canal que
l'audio plutot qu'en le devinant.

Une contrainte commande tout le fichier : **l'etat ne doit jamais retarder la
premiere trame audio**. C'est la meme discipline que le rapport de fin de tour,
mais plus stricte, parce que l'etat s'emet au milieu du tour et non a la fin. Un
envoi qui bloquerait sur un client lent decalerait la voix — exactement le defaut
qu'on cherche a corriger dans une conversation parlee.

D'ou le choix d'ecriture : `emettre` n'est pas une coroutine. Elle depose dans une
file et rend la main. Le chemin de parole ne peut donc pas l'attendre, meme si le
client est fige ou parti. Une tache de fond vide la file quand l'ordonnanceur a
un moment libre, et avale les erreurs de socket : une presence visuelle qui tombe
ne doit pas emporter la voix avec elle.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Les cinq etats du cahier des charges, dans l'ordre naturel d'un tour de parole.
ETATS = ("repos", "ecoute", "reflexion", "escalade", "harnais", "parole")


class EtatInconnu(ValueError):
    """Un etat hors des cinq. Leve a l'emission, ou l'erreur est encore lisible.

    Le refus est volontairement bruyant cote serveur, la ou une faute de frappe se
    corrige, plutot que silencieux cote client, ou elle se traduirait par une
    presence qui ne reagit plus sans qu'on sache pourquoi.
    """


class Presence:
    """Emet l'etat sur la session deja ouverte, sans jamais la faire attendre."""

    def __init__(self, websocket: Any) -> None:
        self._websocket = websocket
        self._file: asyncio.Queue[dict] = asyncio.Queue()
        self._dernier: Optional[str] = None

    def emettre(self, etat: str, *, niveau: Optional[float] = None) -> None:
        """Depose un etat. Rend la main immediatement, quoi que fasse le client."""
        if etat not in ETATS:
            raise EtatInconnu(f"etat inconnu : {etat!r}")

        # Un tour de parole repasse par le meme etat plusieurs fois — la boucle
        # d'ecoute notamment. Le repeter noierait le client sous des messages
        # identiques sans rien lui apprendre.
        if etat == self._dernier and niveau is None:
            return
        self._dernier = etat

        message: dict = {"type": "state", "etat": etat}
        if niveau is not None:
            message["niveau"] = min(1.0, max(0.0, float(niveau)))
        self._file.put_nowait(message)

    async def vider(self) -> None:
        """Ecoule la file. Appelee hors du chemin critique, ou l'attente est gratuite."""
        while not self._file.empty():
            message = self._file.get_nowait()
            if self._websocket is None:
                continue
            try:
                await self._websocket.send_json(message)
            except Exception as erreur:  # une presence qui tombe n'emporte pas la voix
                logger.debug("presence injoignable : %s", erreur)
                self._websocket = None
