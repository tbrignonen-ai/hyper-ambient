"""Banc jetable de calibrage du signal JeV ``addressed_to_mother``.

S'execute dans ``mother-core-dev``. La cle est lue de l'environnement ou de
``/workspace/.env.local`` et n'est jamais ecrite dans la sortie.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from src.ears.jev_reflexe import JevReflexe


ADDRESSEES = (
    "Hyper Ambient",
    "oui ?",
    "stop",
    "attends",
    "quelle heure est-il ?",
    "dis-moi l'heure",
    "tu m'entends ?",
    "est-ce que tu m'entends ?",
    "Hyper Ambient, tu m'entends ?",
    "peux-tu regarder la meteo a Marseille ?",
    "donne-moi la capitale du Japon",
    "rappelle-moi d'appeler Lea demain matin",
    "mets une minuterie de cinq minutes",
    "Hyper Ambient, explique-moi la photosynthese",
    "cherche un restaurant vegetarien pres d'ici",
    "MOTHER, annule la derniere demande",
)

NON_ADRESSEES = (
    "bon alors on disait le module deux",
    "attends deux secondes je parle a quelqu'un d'autre",
    "tu prends le train de 18 heures ou celui de 19 heures ?",
    "non, je pense qu'on devrait reporter la reunion a lundi",
    "je t'envoie le document apres le dejeuner",
    "la recette dit de laisser mijoter pendant vingt minutes",
    "dans le chapitre trois, le personnage quitte enfin Paris",
    "il etait une fois une petite fille qui vivait dans la foret",
    "voyons, si je divise par douze ca fait combien deja",
    "il faut que je pense a acheter du cafe en rentrant",
    "ah non, j'ai oublie mes cles sur la table",
    "ce soir dans le journal, la circulation reste difficile sur le peripherique",
    "la meteo annonce des averses sur la moitie nord du pays",
    "et maintenant, place au film de la soiree sur votre chaine",
    "oui je suis d'accord avec toi, on fait comme ca",
    "passe-moi le sel, s'il te plait",
)


def _read_env_value(path: Path, name: str) -> str:
    """Lire une seule valeur dotenv sans l'interpreter ni l'afficher."""
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().lstrip("\ufeff") == name:
            return value.strip().strip('"').strip("'")
    return ""


def _ensure_key() -> None:
    if os.getenv("TYPESAFE_API_KEY", "").strip():
        return
    key = _read_env_value(Path("/workspace/.env.local"), "TYPESAFE_API_KEY")
    if key:
        os.environ["TYPESAFE_API_KEY"] = key


async def _measure() -> list[tuple[str, str, float]]:
    _ensure_key()
    if not os.getenv("TYPESAFE_API_KEY", "").strip():
        raise RuntimeError("TYPESAFE_API_KEY absente (non affichee par securite).")

    results: list[tuple[str, str, float]] = []
    async with JevReflexe() as jev:
        # Etablit la connexion hors de chaque mesure, sans exposer la cle.
        await jev.prechauffer()
        for expected, phrases in (("adressee", ADDRESSEES), ("non adressee", NON_ADRESSEES)):
            for phrase in phrases:
                evaluation = await jev.evaluate(phrase)
                if evaluation is None:
                    raise RuntimeError(f"JeV indisponible pour une mesure: {phrase!r}")
                score = float(evaluation.answers["addressed_to_mother"]["noul"])
                results.append((expected, phrase, score))
    return results


def _print_report(results: list[tuple[str, str, float]]) -> None:
    print("# Calibrage JeV — mesure API reelle")
    print()
    print("## Scores `addressed_to_mother.noul`")
    print()
    print("| Jeu attendu | Phrase | Score |")
    print("|---|---|---:|")
    for expected, phrase, score in results:
        print(f"| {expected} | {phrase} | {score:.2f} |")

    print()
    print("## Erreurs par seuil")
    print()
    print("| Seuil | Faux negatifs | Faux positifs |")
    print("|---:|---:|---:|")
    for threshold_hundredths in range(20, 81, 5):
        threshold = threshold_hundredths / 100
        false_negatives = sum(
            expected == "adressee" and score < threshold for expected, _, score in results
        )
        false_positives = sum(
            expected == "non adressee" and score >= threshold for expected, _, score in results
        )
        print(f"| {threshold:.2f} | {false_negatives} | {false_positives} |")


async def main() -> None:
    _print_report(await _measure())


if __name__ == "__main__":
    asyncio.run(main())
