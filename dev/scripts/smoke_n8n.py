#!/usr/bin/env python3
"""Fumée de la ronde n8n, sans n8n et sans réseau.

Vérifie le fichier de flux : chaîne des nœuds, branches fausses silencieuses,
réglages par défaut, aucun secret. Le tri lui-même est ``automation/n8n/tri.py``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from automation.n8n.tri import (  # noqa: E402
    ANCIENNETE_JOURS,
    DEPOT,
    LIBELLES_ELIGIBLES,
    LIBELLES_EXCLUS,
    MAX_SUJETS,
)

FLUX = _ROOT / "automation" / "n8n" / "ronde-github-premier-increment.json"

CHAINE = (
    "Déclencheur planifié",
    "Paramètres",
    "Accès GitHub activé ?",
    "Vérifier l’accès GitHub",
    "Accès GitHub autorisé ?",
    "Relever les tickets ouverts",
    "Réponse des tickets valide ?",
    "Déplier les tickets relevés",
    "Écarter les demandes de fusion",
    "Garder les sujets récents",
    "Garder les libellés éligibles",
    "Écarter les libellés exclus",
    "Limiter le nombre de sujets",
    "Préparer l’état lisible",
)

SILENCIEUX = (
    "Accès GitHub activé ?",
    "Accès GitHub autorisé ?",
    "Réponse des tickets valide ?",
    "Écarter les demandes de fusion",
    "Garder les sujets récents",
    "Garder les libellés éligibles",
    "Écarter les libellés exclus",
)

_SECRETS = ("ghp_", "github_pat_", "sk-ant-", "AKIA", "BEGIN PRIVATE", "x-access-token")


def _reglages(flux: dict) -> dict:
    for noeud in flux.get("nodes") or []:
        if noeud.get("name") != "Paramètres":
            continue
        valeurs = {}
        for ligne in (noeud.get("parameters") or {}).get("assignments", {}).get("assignments") or []:
            valeurs[ligne.get("name")] = ligne.get("value")
        return valeurs
    return {}


def _suivant(flux: dict, nom: str) -> str | None:
    branches = (flux.get("connections") or {}).get(nom, {}).get("main") or []
    if not branches or not branches[0]:
        return None
    return branches[0][0].get("node")


def verifier(flux: dict, texte: str) -> list[str]:
    erreurs: list[str] = []
    noms = [noeud.get("name") for noeud in flux.get("nodes") or []]
    if len(noms) != len(set(noms)):
        erreurs.append("noms de nœuds en double")
    manquants = [nom for nom in CHAINE if nom not in noms]
    if manquants:
        erreurs.append("nœuds absents : " + ", ".join(manquants))
    for gauche, droite in zip(CHAINE, CHAINE[1:]):
        if _suivant(flux, gauche) != droite:
            erreurs.append(f"{gauche} ne mène pas à {droite}")
    autre = _suivant(flux, "Déclenchement par un autre flux")
    if autre != "Paramètres":
        erreurs.append("le déclenchement technique ne mène pas aux paramètres")
    for nom in SILENCIEUX:
        branches = (flux.get("connections") or {}).get(nom, {}).get("main") or []
        if len(branches) < 2 or branches[1]:
            erreurs.append(f"la branche fausse de {nom} n'est pas silencieuse")
    reglages = _reglages(flux)
    attendus = {
        "depot": DEPOT,
        "max_sujets": MAX_SUJETS,
        "anciennete_jours": ANCIENNETE_JOURS,
        "libelles_eligibles": LIBELLES_ELIGIBLES,
        "libelles_exclus": LIBELLES_EXCLUS,
        "activer_github": False,
    }
    for cle, valeur in attendus.items():
        if reglages.get(cle) != valeur:
            erreurs.append(f"paramètre {cle} = {reglages.get(cle)!r}, attendu {valeur!r}")
    planifie = next((n for n in flux.get("nodes") or [] if n.get("name") == "Déclencheur planifié"), {})
    regle = (((planifie.get("parameters") or {}).get("rule") or {}).get("interval") or [{}])[0]
    if regle.get("field") != "weeks" or regle.get("weeksInterval") != 1:
        erreurs.append("la ronde n'est pas hebdomadaire")
    if regle.get("triggerAtDay") != [1] or regle.get("triggerAtHour") != 2 or regle.get("triggerAtMinute") != 0:
        erreurs.append("l'horaire n'est pas le lundi à 02:00")
    if flux.get("active") is not False:
        erreurs.append("le flux importé ne doit pas être actif")
    for secret in _SECRETS:
        if secret in texte:
            erreurs.append(f"secret potentiel dans le flux : {secret}")
    expressions = json.dumps(
        [n.get("parameters") for n in flux.get("nodes") or []],
        ensure_ascii=False,
    )
    for fragment in (
        "pull_request === undefined",
        "anciennete_jours",
        "libelles_eligibles",
        "libelles_exclus",
        "max_sujets",
    ):
        if fragment not in expressions:
            erreurs.append(f"expression absente : {fragment}")
    return erreurs


def main(argv: list[str] | None = None) -> int:
    chemin = Path(argv[1]) if argv and len(argv) > 1 else FLUX
    texte = chemin.read_text(encoding="utf-8")
    flux = json.loads(texte)
    erreurs = verifier(flux, texte)
    if erreurs:
        print("FAIL n8n")
        for erreur in erreurs:
            print(f"  - {erreur}")
        return 1
    print(f"PASS n8n {chemin.name} ({len(flux.get('nodes') or [])} nœuds, GitHub inactif)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
