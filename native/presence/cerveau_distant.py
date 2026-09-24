"""Choix du cerveau distant par l'utilisateur : mode et modèle (24/09).

Trois modes : une clé d'API (MiniMax ou tout service compatible), ou
l'abonnement de l'utilisateur à Claude Code ou à ChatGPT (Codex), consulté
par le pont hôte déjà branché pour les harnais. La liste des modèles vient
du pont, en direct ; sans pont joignable, le modèle par défaut reste proposé.

Logique pure, sans Tk : l'écran Réglages ne fait que l'afficher.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Callable, Optional

MODES = (
    ("api", "Clé d'API (MiniMax ou compatible)"),
    ("abonnement-claude", "Abonnement Claude (Claude Code)"),
    ("abonnement-chatgpt", "Abonnement ChatGPT (Codex)"),
)

MODELE_PAR_DEFAUT = {
    "abonnement-claude": "claude-sonnet-5",
    "abonnement-chatgpt": "gpt-6-luna",
}
LIBELLE_PAR_DEFAUT = {
    "claude-sonnet-5": "Claude Sonnet 5",
    "gpt-6-luna": "GPT-6-Luna",
}
# Réflexion au plus bas : la voix ne paie pas le raisonnement (notes voix/UX).
EFFORT_PAR_DEFAUT = "low"

_PONT = {
    "abonnement-claude": ("CLI_BRIDGE_URL", "CLI_BRIDGE_TOKEN", 8766),
    "abonnement-chatgpt": ("CODEX_BRIDGE_URL", "CODEX_BRIDGE_TOKEN", 8765),
}


def url_models(mode: str, valeurs: dict[str, str]) -> Optional[str]:
    """L'adresse du pont vue depuis l'hôte, où tourne Presence."""
    if mode not in _PONT:
        return None
    cle_url, _, port = _PONT[mode]
    url = (valeurs.get(cle_url) or f"http://127.0.0.1:{port}/ask").strip()
    url = url.replace("host.docker.internal", "127.0.0.1").rstrip("/")
    for suffixe in ("/ask", "/chat"):
        if url.endswith(suffixe):
            url = url[: -len(suffixe)]
    return f"{url}/models"


def _lire_http(url: str, jeton: str) -> dict:
    requete = urllib.request.Request(url, headers={"Authorization": f"Bearer {jeton}"})
    with urllib.request.urlopen(requete, timeout=5) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def lister_modeles(
    mode: str,
    valeurs: dict[str, str],
    *,
    lire: Callable[[str, str], dict] = _lire_http,
) -> list[dict]:
    """Les modèles proposés par le pont ; le défaut seul si le pont ne répond pas."""
    url = url_models(mode, valeurs)
    if url is None:
        return []
    defaut = MODELE_PAR_DEFAUT[mode]
    repli = [{"id": defaut, "label": LIBELLE_PAR_DEFAUT.get(defaut, defaut)}]
    try:
        modeles = list(lire(url, valeurs.get(_PONT[mode][1], "")).get("models") or [])
    except Exception:
        return repli
    return [m for m in modeles if m.get("id")] or repli


def choix_courant(chemin: Path) -> tuple[str, str, str]:
    from src.onboarding.reglages import lire_reglages

    valeurs = lire_reglages(Path(chemin))
    mode = (valeurs.get("BRAIN_DEEP") or "api").strip() or "api"
    modele = (valeurs.get("BRAIN_ABONNEMENT_MODEL") or MODELE_PAR_DEFAUT.get(mode, "")).strip()
    effort = (valeurs.get("BRAIN_ABONNEMENT_EFFORT") or EFFORT_PAR_DEFAUT).strip()
    return mode, modele, effort


def enregistrer_choix(chemin: Path, mode: str, modele: str, effort: str = EFFORT_PAR_DEFAUT) -> None:
    from src.onboarding.reglages import poser_reglages

    poser_reglages(
        Path(chemin),
        {
            "BRAIN_DEEP": mode,
            "BRAIN_ABONNEMENT_MODEL": modele or MODELE_PAR_DEFAUT.get(mode, ""),
            "BRAIN_ABONNEMENT_EFFORT": effort or EFFORT_PAR_DEFAUT,
        },
    )


def relancer_host_agent() -> bool:
    """Le host-agent lit le choix au démarrage : on le relance, sans recréer
    le conteneur (relance officielle, jamais de `docker compose up`)."""
    import subprocess

    # Le redémarrage Docker appartient au parcours Windows. Le profil Mac
    # pilote un processus natif sous le superviseur, sans toucher à la démo.
    if os.getenv("MOTHER_PROFILE") == "mac-16g-voix-max":
        return False

    try:
        resultat = subprocess.run(
            ["docker", "exec", "mother-core-dev", "bash",
             "/workspace/dev/scripts/relance_hostagent.sh"],
            capture_output=True, text=True, timeout=240,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return False
    return resultat.returncode == 0


def libelle_modele(modele: str) -> str:
    if modele in LIBELLE_PAR_DEFAUT:
        return LIBELLE_PAR_DEFAUT[modele]
    if modele.lower().startswith("gpt-"):
        return "GPT-" + "-".join(p.capitalize() for p in modele[4:].split("-"))
    return modele


def choix_bascule(chemin: Path) -> list[tuple[str, dict]]:
    """Les trois choix de la bascule rapide ; le mode actif garde son modèle."""
    mode_actif, modele_actif, effort = choix_courant(chemin)
    choix = []
    for mode in ("abonnement-claude", "abonnement-chatgpt"):
        modele = modele_actif if mode == mode_actif and modele_actif else MODELE_PAR_DEFAUT[mode]
        choix.append((libelle_modele(modele), {"mode": mode, "model": modele, "effort": effort}))
    libelle_api = (
        "Texte local MLX" if os.getenv("MOTHER_PROFILE") == "mac-16g-voix-max"
        else "MiniMax (clé d'API)"
    )
    choix.append((libelle_api, {"mode": "api"}))
    return choix
