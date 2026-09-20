"""Écriture de la configuration dans `.env.local`, sans rien casser.

Le fichier contient déjà la configuration de travail du fondateur. Ce module
modifie une clé sur place, ajoute une clé nouvelle à la fin, et préserve tout
le reste : commentaires, ordre des lignes, blocs désactivés, fins de ligne,
BOM. L'écriture est atomique — temporaire dans le même répertoire, `fsync`,
puis remplacement — et la version d'avant la session est sauvegardée une fois.

Aucune valeur n'est journalisée : le module n'embarque aucun logger, et les
exceptions qu'il lève ne citent que des noms de fichiers ou de variables,
jamais une valeur.

Lot B de `nights/2026-09-20-SPEC-ONBOARDING-V2.md`.
"""
from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

__all__ = [
    "CLES_ONBOARDING",
    "lire_reglages",
    "poser_reglage",
    "poser_reglages",
    "reglage_present",
]

# Les variables que l'onboarding pose, telles qu'elles existent déjà.
CLES_ONBOARDING = (
    "BRAIN_API_ENDPOINT",
    "BRAIN_API_KEY",
    "BRAIN_MODEL",
    "CODEX_BRIDGE_URL",
    "CODEX_BRIDGE_TOKEN",
    "CLI_BRIDGE_URL",
    "CLI_BRIDGE_TOKEN",
    "TYPESAFE_API_KEY",
)

# `.gitignore` couvre `*.tmp` mais pas `.env.local.bak` : la sauvegarde porte
# donc un suffixe `.tmp`, sinon les secrets du fondateur devenaient versionnables.
SUFFIXE_SAUVEGARDE = ".sauvegarde.tmp"
SUFFIXE_TEMPORAIRE = ".tmp"

BOM = "\ufeff"

# Fichiers déjà sauvegardés par ce processus : la sauvegarde précède la
# première écriture d'une session, pas chaque écriture.
_sauvegardes: set[Path] = set()


def lire_reglages(chemin: Path) -> dict[str, str]:
    """Rend les valeurs actives du fichier, un `dict` vide s'il est absent.

    Les lignes commentées et les lignes sans `=` sont ignorées : une valeur
    commentée n'est pas une valeur. Sur une clé dupliquée la dernière gagne,
    comme pour python-dotenv et `docker compose --env-file`.
    """
    chemin = Path(chemin)
    if not chemin.is_file():
        return {}
    reglages: dict[str, str] = {}
    for ligne in _lignes_de(_lire(chemin).lstrip(BOM)):
        paire = _paire(ligne)
        if paire is None:
            continue
        cle, droite = paire
        reglages[cle] = _nettoyer_valeur(droite)
    return reglages


def poser_reglage(chemin: Path, cle: str, valeur: str) -> None:
    """Écrit une seule variable. Voir `poser_reglages`."""
    poser_reglages(chemin, {cle: valeur})


def poser_reglages(chemin: Path, valeurs: dict[str, str]) -> None:
    """Écrit plusieurs variables d'un coup : une sauvegarde, un remplacement.

    Une clé déjà présente est modifiée sur place — sa dernière occurrence,
    celle qui gagne — et conserve sa propre fin de ligne. Une clé nouvelle est
    ajoutée à la fin du fichier, dans la fin de ligne dominante. Un `valeurs`
    vide ne touche à rien, pas même à la sauvegarde.
    """
    chemin = Path(chemin)
    cibles: dict[str, str] = {}
    for cle, valeur in valeurs.items():
        if valeur is None:
            # `str(None)` écrirait « None » comme clé API : on refuse avant.
            raise TypeError(f"valeur absente pour la variable {cle!r}")
        cibles[_valider_cle(cle)] = str(valeur)
    if not cibles:
        return

    brut = _lire(chemin) if chemin.is_file() else ""
    bom = ""
    if brut.startswith(BOM):
        bom, brut = BOM, brut[len(BOM):]
    eol = _eol_dominant(brut)
    lignes = _lignes_de(brut)

    occurrences: dict[str, int] = {}
    for indice, ligne in enumerate(lignes):
        paire = _paire(ligne)
        if paire is not None and paire[0] in cibles:
            occurrences[paire[0]] = indice
    for cle, indice in occurrences.items():
        _, terminaison = _scinder(lignes[indice])
        lignes[indice] = f"{cle}={_formater_valeur(cibles.pop(cle))}{terminaison}"

    for cle, valeur in cibles.items():
        lignes.append(f"{cle}={_formater_valeur(valeur)}{eol}")

    _sauvegarder(chemin)
    _ecrire(chemin, bom + "".join(lignes))


def reglage_present(chemin: Path, cle: str) -> bool:
    """Vrai si la variable porte une valeur non vide.

    Une clé absente, une clé vide (`BRAIN_API_KEY=`, l'état d'un `.env.example`
    recopié) et une clé commentée comptent toutes pour « à poser ». C'est la
    question que l'onboarding se pose avant de demander une valeur.
    """
    return bool(lire_reglages(chemin).get(cle, "").strip())


# ---------------------------------------------------------------------------
# Lecture du texte
# ---------------------------------------------------------------------------

def _lire(chemin: Path) -> str:
    """Lit sans traduire les fins de ligne.

    `Path.read_text` applique le mode universel et rendrait tout en `\\n` :
    un `.env.local` en CRLF ressortirait converti, ce qui réécrit le fichier
    du fondateur ligne à ligne. `newline=""` laisse les `\\r\\n` intacts.
    """
    with open(chemin, "r", encoding="utf-8", newline="") as flux:
        return flux.read()


def _lignes_de(brut: str) -> list[str]:
    """Découpe en lignes complètes, terminateur inclus.

    Recoller les lignes redonne le texte au caractère près : c'est ce qui
    garantit qu'aucun octet du fondateur n'est réécrit. Une dernière ligne
    sans saut de ligne est terminée d'office — sinon elle ne serait ni lue,
    ni reconnue comme une clé existante, et une clé nouvelle s'y collerait.
    """
    if brut and not brut.endswith("\n"):
        brut += "\n"
    return [morceau + "\n" for morceau in brut.split("\n")[:-1]]


def _scinder(ligne: str) -> tuple[str, str]:
    """Sépare le contenu d'une ligne complète de son terminateur."""
    if ligne.endswith("\r\n"):
        return ligne[:-2], "\r\n"
    if ligne.endswith("\n"):
        return ligne[:-1], "\n"
    return ligne, ""


def _eol_dominant(brut: str) -> str:
    """Fin de ligne des lignes ajoutées : la majoritaire, à défaut `\\n`.

    Un fichier mixte — le `.env.local` réel l'est — garde ses lignes telles
    qu'elles sont ; on n'y ajoute pas de `\\r` qui n'y était pas.
    """
    return "\r\n" if brut.count("\r\n") * 2 > brut.count("\n") else "\n"


def _paire(ligne: str) -> tuple[str, str] | None:
    """Rend `(clé, membre droit brut)` pour une ligne active, sinon `None`."""
    corps, _ = _scinder(ligne)
    if corps.lstrip().startswith("#"):
        return None
    cle, separateur, droite = corps.partition("=")
    if not separateur:
        return None
    return cle.strip(), droite


def _nettoyer_valeur(droite: str) -> str:
    """Rend la valeur logique d'un membre droit, guillemets retirés."""
    if len(droite) >= 2 and droite[0] == droite[-1] and droite[0] in "\"'":
        interieur = droite[1:-1]
        return interieur if droite[0] == "'" else _developper(interieur)
    return droite.strip()


def _developper(interieur: str) -> str:
    """Inverse l'échappement d'une valeur entre guillemets doubles."""
    sortie: list[str] = []
    echappements = {"n": "\n", "t": "\t", "r": "\r"}
    fuite = False
    for caractere in interieur:
        if fuite:
            sortie.append(echappements.get(caractere, caractere))
            fuite = False
        elif caractere == "\\":
            fuite = True
        else:
            sortie.append(caractere)
    if fuite:
        sortie.append("\\")
    return "".join(sortie)


def _formater_valeur(valeur: str) -> str:
    """Écrit la valeur sans guillemets, sauf quand le format dotenv l'exige.

    Sans guillemets, une valeur à espaces internes se relit à l'identique et
    passe aussi bien par `docker compose --env-file` que par python-dotenv ;
    un chemin Windows garde ses antislashes. Les guillemets doubles ne servent
    que pour un espace de bordure, un `#` (qui ouvrirait un commentaire en
    ligne), un saut de ligne (qui injecterait une ligne dans le fichier) ou
    une valeur entamée par un guillemet.
    """
    if valeur and (
        valeur != valeur.strip()
        or "#" in valeur
        or "\n" in valeur
        or "\r" in valeur
        or valeur[0] in "\"'"
    ):
        echappee = (
            valeur.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f'"{echappee}"'
    return valeur


def _valider_cle(cle: str) -> str:
    """Refuse un nom qui casserait le fichier ou y injecterait une ligne."""
    nom = cle.strip()
    if not nom or not all(caractere.isalnum() or caractere == "_" for caractere in nom):
        raise ValueError(f"nom de variable invalide : {nom!r}")
    return nom


# ---------------------------------------------------------------------------
# Sauvegarde et écriture atomique
# ---------------------------------------------------------------------------

def _chemin_sauvegarde(chemin: Path) -> Path:
    return chemin.with_name(chemin.name + SUFFIXE_SAUVEGARDE)


def _sauvegarder(chemin: Path) -> None:
    """Copie l'état d'avant la session, une fois par processus et par fichier.

    Un fichier qui n'existe pas encore n'a rien à sauvegarder, mais il est
    quand même marqué : la session ne doit pas écraser plus tard le point de
    retour avec une version qu'elle vient elle-même d'écrire.
    """
    cle = chemin.resolve()
    if cle in _sauvegardes:
        return
    _sauvegardes.add(cle)
    if chemin.is_file():
        shutil.copy2(chemin, _chemin_sauvegarde(chemin))


def _ecrire(chemin: Path, texte: str) -> None:
    """Écrit dans un temporaire du même répertoire puis remplace le fichier.

    `newline=""` évite que Windows traduise les `\\r\\n` déjà présents en
    `\\r\\r\\n`. Le `fsync` précède le remplacement : une coupure laisse
    l'ancien fichier entier, jamais un `.env.local` tronqué.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur, temporaire = tempfile.mkstemp(
        dir=str(chemin.parent),
        prefix=chemin.name + ".",
        suffix=SUFFIXE_TEMPORAIRE,
    )
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8", newline="") as flux:
            flux.write(texte)
            flux.flush()
            os.fsync(flux.fileno())
        _conserver_mode(chemin, temporaire)
        os.replace(temporaire, chemin)
    except BaseException:
        _supprimer(temporaire)
        raise


def _conserver_mode(chemin: Path, temporaire: str) -> None:
    """Garde les permissions d'origine : `mkstemp` crée en 0600.

    Sans ça, un service qui lit `.env.local` sous un autre utilisateur
    perdrait l'accès au fichier après le premier passage de l'onboarding.
    """
    if not chemin.is_file():
        return
    try:
        os.chmod(temporaire, stat.S_IMODE(os.stat(chemin).st_mode))
    except OSError:
        pass


def _supprimer(temporaire: str) -> None:
    try:
        os.unlink(temporaire)
    except OSError:
        pass
