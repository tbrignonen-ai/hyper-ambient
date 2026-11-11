"""Heure de Paris, y compris quand le conteneur n'a pas tzdata.

Le conteneur est en UTC. Les fichiers de conversation et l'heure dite à voix
haute suivent l'heure du fondateur, pas l'horloge du conteneur.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, tzinfo
from zoneinfo import ZoneInfo


def _dernier_dimanche(annee: int, mois: int):
    jour = date(annee, mois, 31)
    return date.fromordinal(jour.toordinal() - ((jour.weekday() + 1) % 7))


class _Paris(tzinfo):
    """Repli Europe/Paris si tzdata n'est pas installé dans le conteneur."""

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=1)
        jour = dt.date() if hasattr(dt, "date") else dt
        mars = _dernier_dimanche(jour.year, 3)
        octo = _dernier_dimanche(jour.year, 10)
        if mars <= jour < octo:
            return timedelta(hours=2)
        return timedelta(hours=1)

    def tzname(self, dt):
        return "CEST" if self.utcoffset(dt) == timedelta(hours=2) else "CET"

    def dst(self, dt):
        return (
            timedelta(hours=1)
            if self.utcoffset(dt) == timedelta(hours=2)
            else timedelta(0)
        )


def fuseau_paris():
    """Europe/Paris, même sans la base tzdata du conteneur."""
    try:
        return ZoneInfo("Europe/Paris")
    except Exception:
        return _Paris()


FUSEAU_CONVERSATION = fuseau_paris()


def maintenant_local(quand=None):
    """Heure de la machine (Europe/Paris), jamais l'UTC du conteneur."""
    if quand is None:
        return datetime.now(FUSEAU_CONVERSATION)
    if getattr(quand, "tzinfo", None) is None:
        return quand
    return quand.astimezone(FUSEAU_CONVERSATION)
