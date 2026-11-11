"""État public du port 8000 : la carte, pas une boucle vivante.

Le tour réel est le host-agent sur le port 8001. Ce module ne charge aucun
modèle et ne prétend pas qu'une capacité est mesurée.
"""
from __future__ import annotations

from pathlib import Path

CARTE = Path(__file__).resolve().parents[2] / "dev" / "scripts" / "carte_figee.env"


def parser_env(texte: str) -> dict[str, str]:
    paires: dict[str, str] = {}
    for ligne in texte.splitlines():
        corps = ligne.strip()
        if not corps or corps.startswith("#") or "=" not in corps:
            continue
        cle, _, valeur = corps.partition("=")
        paires[cle.strip()] = valeur.strip()
    return paires


def lire_carte(chemin: Path | None = None) -> dict[str, str]:
    cible = chemin or CARTE
    try:
        return parser_env(cible.read_text(encoding="utf-8"))
    except OSError:
        return {}


def statut_public(carte: dict[str, str] | None = None) -> dict:
    valeurs = carte if carte is not None else lire_carte()
    modele = valeurs.get("MODEL", "")
    return {
        "status": "ok",
        "live": False,
        "role": "placeholder",
        "live_loop": "host-agent ws://127.0.0.1:8001/hostagent",
        "card": {
            "brain_service": valeurs.get("BRAIN_SERVICE", ""),
            "brain_model": valeurs.get("BRAIN_MODEL", ""),
            "brain_local": Path(modele).name if modele else "",
            "ears": valeurs.get("EARS_MODEL", ""),
            "mouth_backend": valeurs.get("MOUTH_BACKEND", ""),
            "mouth_voice": valeurs.get("MOUTH_VOICE_NAME", ""),
        },
    }
