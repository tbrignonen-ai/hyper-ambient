"""État d'alerte Presence : bandeau contrasté, sans jargon, sans GUI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PHRASE_ALERTE_CODEX = "Le pont vers Codex ne répond plus, je continue en local."
PHRASE_REPRISE_CODEX = "Pont Codex rétabli."

BANDEAU_FG = "#fff8e8"
BANDEAU_BG = "#7a1212"


def _composante(canal: float) -> float:
    return canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4


def _luminance(hex_couleur: str) -> float:
    brut = hex_couleur.lstrip("#")
    r = int(brut[0:2], 16) / 255.0
    g = int(brut[2:4], 16) / 255.0
    b = int(brut[4:6], 16) / 255.0
    return 0.2126 * _composante(r) + 0.7152 * _composante(g) + 0.0722 * _composante(b)


def contraste_relatif(premier: str, second: str) -> float:
    clair = max(_luminance(premier), _luminance(second))
    sombre = min(_luminance(premier), _luminance(second))
    return (clair + 0.05) / (sombre + 0.05)


def bandeau_depuis_etat(etat: Mapping[str, Any]) -> dict[str, Any]:
    if etat.get("healthStatus") == "DEGRADED":
        return {
            "visible": True,
            "texte": str(etat.get("alertMessage") or PHRASE_ALERTE_CODEX),
            "texte_reprise": str(etat.get("recoveryMessage") or ""),
            "role": "alert",
            "takefocus": True,
            "fg": BANDEAU_FG,
            "bg": BANDEAU_BG,
        }
    return {
        "visible": False,
        "texte": "",
        "texte_reprise": str(etat.get("recoveryMessage") or ""),
        "role": "status",
        "takefocus": False,
        "fg": BANDEAU_FG,
        "bg": BANDEAU_BG,
    }


def lire_snapshot(chemin: Path) -> dict[str, Any]:
    brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
    if not isinstance(brut, dict):
        return {"healthStatus": "UNKNOWN"}
    return brut
