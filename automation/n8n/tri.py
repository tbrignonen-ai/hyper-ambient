"""Sélection des sujets de la ronde GitHub, sans n8n.

Même règles que le flux ``ronde-github-premier-increment`` : écarter les
demandes de fusion, garder l'ancienneté, exiger un libellé éligible, écarter
un libellé exclu, puis couper au plafond. L'ordre d'entrée est conservé.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

DEPOT = "tbrignonen-ai/hyper-ambient"
MAX_SUJETS = 3
ANCIENNETE_JOURS = 7
LIBELLES_ELIGIBLES = "doc, typo, auto"
LIBELLES_EXCLUS = "security, sécurité, ci, docker, architecture, tts, stt"
ETAT_LISIBLE = "À préparer — validation humaine requise"


def decouper_libelles(brut: str) -> set[str]:
    return {morceau.strip().lower() for morceau in str(brut).split(",") if morceau.strip()}


def _noms(ticket: Mapping[str, Any]) -> list[str]:
    noms: list[str] = []
    for libelle in ticket.get("labels") or []:
        if isinstance(libelle, Mapping):
            nom = str(libelle.get("name") or "")
        else:
            nom = str(libelle)
        nom = nom.strip()
        if nom:
            noms.append(nom)
    return noms


def _instant(valeur: object) -> datetime | None:
    if not isinstance(valeur, str) or not valeur.strip():
        return None
    try:
        moment = datetime.fromisoformat(valeur.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _maintenant(valeur: datetime) -> datetime:
    if valeur.tzinfo is None:
        return valeur.replace(tzinfo=timezone.utc)
    return valeur.astimezone(timezone.utc)


def est_demande_de_fusion(ticket: Mapping[str, Any]) -> bool:
    """Vrai dès que la clé existe, comme ``pull_request === undefined`` est faux."""
    return "pull_request" in ticket


def trier_sujets(
    tickets: list[Mapping[str, Any]],
    *,
    maintenant: datetime,
    max_sujets: int = MAX_SUJETS,
    anciennete_jours: int = ANCIENNETE_JOURS,
    libelles_eligibles: str = LIBELLES_ELIGIBLES,
    libelles_exclus: str = LIBELLES_EXCLUS,
) -> list[dict[str, Any]]:
    eligibles = decouper_libelles(libelles_eligibles)
    exclus = decouper_libelles(libelles_exclus)
    seuil = _maintenant(maintenant) - timedelta(days=max(0, int(anciennete_jours)))
    plafond = max(0, int(max_sujets))
    retenus: list[dict[str, Any]] = []
    for ticket in tickets:
        if est_demande_de_fusion(ticket):
            continue
        instant = _instant(ticket.get("updated_at"))
        if instant is None or instant < seuil:
            continue
        noms = _noms(ticket)
        bas = {nom.lower() for nom in noms}
        if not bas.intersection(eligibles):
            continue
        if bas.intersection(exclus):
            continue
        retenus.append(
            {
                "numero": ticket.get("number"),
                "titre": ticket.get("title") or "",
                "url": ticket.get("html_url") or "",
                "mis_a_jour_le": ticket.get("updated_at") or "",
                "libelles": ", ".join(noms),
                "etat": ETAT_LISIBLE,
                "donnees_ticket_titre": ticket.get("title") or "",
                "donnees_ticket_corps": ticket.get("body") or "",
            }
        )
        if len(retenus) >= plafond:
            break
    return retenus
