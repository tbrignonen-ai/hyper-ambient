"""État de santé dit à voix haute, sans cerveau.

« Ça va ? » reste une conversation : le modèle local la tient. Ici, seulement
la question sur les services (« tu fonctionnes ? »). Le relevé est celui du
worker de santé ; absent, on le dit, on n'invente pas que tout va bien.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.parole import normaliser

MAX_MOTS = 7

_PAS_UN_ETAT = frozenset(
    {
        "demande",
        "demander",
        "cherche",
        "chercher",
        "explique",
        "expliquer",
        "pourquoi",
        "ecris",
        "envoie",
        "note",
    }
)

_MOTIFS = (
    r"\btu fonctionnes\b",
    r"\btout fonctionne\b",
    r"\btes services\b",
    r"\betat du systeme\b",
    r"\btu es en ligne\b",
    r"\bare you up\b",
    r"\bsystem status\b",
    r"\bestas en linea\b",
)

_PHRASES: dict[str, dict[str, str]] = {
    "fr": {
        "absent": "Je n'ai pas de relevé récent. Je continue.",
        "ok": "Je vais bien. Tout répond.",
        "degrade": "Un service ne répond plus. Je continue en local.",
        "pont_codex": "Le pont vers Codex ne répond plus, je continue en local.",
        "pont_claude": "Le pont vers Claude ne répond plus, je continue en local.",
        "host_agent": "L'accueil vocal ne répond plus.",
        "modele_local": "Le modèle local ne répond plus.",
        "camunda": "Le suivi automatique n'est pas disponible, je surveille en direct.",
    },
    "en": {
        "absent": "I have no recent reading. I am carrying on.",
        "ok": "I am fine. Everything is answering.",
        "degrade": "A service is not answering. I am staying local.",
        "pont_codex": "The bridge to Codex is not answering. I am staying local.",
        "pont_claude": "The bridge to Claude is not answering. I am staying local.",
        "host_agent": "The voice loop is not answering.",
        "modele_local": "The local model is not answering.",
        "camunda": "Automatic follow-up is unavailable. I am watching directly.",
    },
    "es": {
        "absent": "No tengo una lectura reciente. Sigo.",
        "ok": "Estoy bien. Todo responde.",
        "degrade": "Un servicio no responde. Sigo en local.",
        "pont_codex": "El puente hacia Codex no responde. Sigo en local.",
        "pont_claude": "El puente hacia Claude no responde. Sigo en local.",
        "host_agent": "La acogida vocal no responde.",
        "modele_local": "El modelo local no responde.",
        "camunda": "El seguimiento automático no está disponible. Vigilo directamente.",
    },
}


def demande_d_etat(transcript: str) -> bool:
    normalise = normaliser(transcript)
    if not normalise or len(normalise.split()) > MAX_MOTS:
        return False
    if _PAS_UN_ETAT.intersection(normalise.split()):
        return False
    return any(re.search(motif, normalise) for motif in _MOTIFS)


def lire_etat(chemin: Path) -> dict | None:
    try:
        brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return brut if isinstance(brut, dict) else None


def phrase_d_etat(snapshot: dict | None, langue: str = "fr") -> str:
    voix = _PHRASES.get(langue, _PHRASES["fr"])
    if not isinstance(snapshot, dict) or not snapshot:
        return voix["absent"]
    if snapshot.get("healthStatus") != "DEGRADED":
        if snapshot.get("healthStatus") == "UP":
            return voix["ok"]
        return voix["absent"]
    identifiants = [
        morceau.strip()
        for morceau in str(snapshot.get("degradedComponents") or "").split(",")
        if morceau.strip()
    ]
    if langue != "fr" and identifiants:
        return voix.get(identifiants[0], voix["degrade"])
    message = str(snapshot.get("alertMessage") or "").strip()
    if langue == "fr" and message:
        return message
    if identifiants:
        return voix.get(identifiants[0], voix["degrade"])
    return voix["degrade"]
