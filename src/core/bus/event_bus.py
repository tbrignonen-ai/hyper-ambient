"""Bus d'événements : seule voie de communication entre capacités.

Aucune capacité n'en appelle une autre. Le bus est l'invariant n°1 du
projet : EARS, TURN, MOUTH, BRAIN, GATE, WATCH ne se parlent que par
événements. Cette contrainte rend le graphe d'appels observable,
ordonnable, et remplaçable sans recâbler les modules.

L'horloge est monotone (time.monotonic) : un événement horodaté reste
comparable même si l'heure système change. L'heure murale POSIX n'est
jamais utilisée.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Événement immuable transitant sur le bus."""

    payload: Any
    stamp: float


class EventBus:
    """Bus synchrone : publication, abonnement, livraison dans l'ordre d'émission."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[Event], None]] = []
        self._last_stamp: float = float("-inf")

    def subscribe(self, handler: Callable[[Event], None]) -> None:
        """Enregistre un abonné, invoqué ensuite dans l'ordre d'abonnement."""
        self._subscribers.append(handler)

    def publish(self, payload: Any) -> Event:
        """Émet un événement et le livre synchronement à tous les abonnés.

        Sans abonné, la publication réussit quand même et retourne l'événement.
        Une exception levée par un abonné est journalisée et n'interrompt pas
        la livraison aux suivants.
        """
        event = Event(payload=payload, stamp=self._next_stamp())
        for handler in self._subscribers:
            try:
                handler(event)
            except Exception:
                logger.exception("Exception levée par un abonné du bus")
        return event

    def _next_stamp(self) -> float:
        """Prochain stamp monotone, strictement supérieur au précédent."""
        now = time.monotonic()
        if now <= self._last_stamp:
            now = math.nextafter(self._last_stamp, math.inf)
        self._last_stamp = now
        return now
