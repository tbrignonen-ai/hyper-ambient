"""Volume parlé, sans cerveau.

« Plus fort » est classé réflexe, et le modèle local le ratait comme il
ratait « répète ». Le gain change tout de suite. Le fichier
``data/mouth_gain_db`` (hors dépôt) gagne sur la carte au prochain boot,
jusqu'à « volume normal ».
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

GAIN_MIN = -6.0
GAIN_MAX = 18.0
GAIN_PAS = 3.0
GAIN_CARTE = 9.0
MAX_MOTS = 7

_PAS_UN_REGLAGE = frozenset(
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
    ("normal", r"\b(volume|son) normal\b|\bremets (le |la )?(son|volume)\b"),
    ("baisser", r"\bmoins fort\b|\btrop fort\b|\bplus bas\b|\b(baisse|baisser|diminue)(r|s|z)? (le |la )?(son|volume|voix)\b|\bsofter\b|\bquieter\b|\bturn it down\b|\bmas bajo\b|\bbaja (el )?(volumen|sonido)\b"),
    ("monter", r"\bplus fort\b|\b(monte|monter|augmente|augmenter)(r|s|z)? (le |la )?(son|volume|voix)\b|\blouder\b|\bvolume up\b|\bturn it up\b|\bmas fuerte\b|\bsube (el )?(volumen|sonido)\b"),
    ("annoncer", r"\b(quel|c est quoi le|le) volume\b|\bvolume actuel\b|\bhow loud\b|\bque volumen\b"),
)

_PHRASES: dict[str, dict[str, str]] = {
    "fr": {
        "monter": "Je parle plus fort. Le gain est à {gain} décibels.",
        "baisser": "Je parle moins fort. Le gain est à {gain} décibels.",
        "normal": "Je reviens au gain de la carte, {gain} décibels.",
        "annoncer": "Le gain est à {gain} décibels.",
        "plafond": "C'est déjà le maximum.",
        "plancher": "C'est déjà le minimum.",
    },
    "en": {
        "monter": "Speaking louder. Gain is {gain} decibels.",
        "baisser": "Speaking softer. Gain is {gain} decibels.",
        "normal": "Back to the card gain, {gain} decibels.",
        "annoncer": "Gain is {gain} decibels.",
        "plafond": "That's already as loud as I go.",
        "plancher": "That's already as quiet as I go.",
    },
    "es": {
        "monter": "Hablo más fuerte. La ganancia está en {gain} decibelios.",
        "baisser": "Hablo más bajo. La ganancia está en {gain} decibelios.",
        "normal": "Vuelvo a la ganancia de la carta, {gain} decibelios.",
        "annoncer": "La ganancia está en {gain} decibelios.",
        "plafond": "Ya está al máximo.",
        "plancher": "Ya está al mínimo.",
    },
}


def _normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())


def _formater(gain: float) -> str:
    if abs(gain - round(gain)) < 1e-6:
        return str(int(round(gain)))
    return f"{gain:.1f}"


def borner(valeur: float) -> float:
    return float(min(GAIN_MAX, max(GAIN_MIN, round(valeur, 1))))


def interpreter_volume(transcript: str) -> str | None:
    """``monter``, ``baisser``, ``normal``, ``annoncer``, ou ``None``."""
    normalise = _normaliser(transcript)
    if not normalise or len(normalise.split()) > MAX_MOTS:
        return None
    if _PAS_UN_REGLAGE.intersection(normalise.split()):
        return None
    for sens, motif in _MOTIFS:
        if re.search(motif, normalise):
            return sens
    return None


def regler_volume(
    gain: float,
    sens: str,
    *,
    langue: str = "fr",
    carte: float = GAIN_CARTE,
) -> tuple[float, str]:
    """Nouveau gain et phrase à dire. ``annoncer`` ne change rien."""
    voix = _PHRASES.get(langue, _PHRASES["fr"])
    actuel = float(gain)
    if sens == "annoncer":
        return actuel, voix["annoncer"].format(gain=_formater(actuel))
    if sens == "normal":
        return float(carte), voix["normal"].format(gain=_formater(float(carte)))
    if sens == "monter":
        if actuel >= GAIN_MAX - 1e-6:
            return actuel, voix["plafond"]
        nouveau = borner(actuel + GAIN_PAS)
        return nouveau, voix["monter"].format(gain=_formater(nouveau))
    if sens == "baisser":
        if actuel <= GAIN_MIN + 1e-6:
            return actuel, voix["plancher"]
        nouveau = borner(actuel - GAIN_PAS)
        return nouveau, voix["baisser"].format(gain=_formater(nouveau))
    raise ValueError(f"sens de volume inconnu : {sens!r}")


def lire_gain(chemin: Path) -> float | None:
    """Le gain parlé, ou ``None`` si le fichier est absent ou illisible."""
    try:
        brut = Path(chemin).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        valeur = float(brut.strip())
    except ValueError:
        return None
    if valeur != valeur:  # NaN
        return None
    return borner(valeur)


def ecrire_gain(chemin: Path, gain: float) -> None:
    cible = Path(chemin)
    cible.parent.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_name(cible.name + ".tmp")
    temporaire.write_text(f"{borner(gain):.1f}\n", encoding="utf-8")
    os.replace(temporaire, cible)


def effacer_gain(chemin: Path) -> None:
    try:
        Path(chemin).unlink()
    except FileNotFoundError:
        return


def memoriser_gain(chemin: Path, gain: float, carte: float) -> None:
    """Le fichier ne reste que s'il dit autre chose que la carte."""
    if abs(float(gain) - float(carte)) < 1e-6:
        effacer_gain(chemin)
    else:
        ecrire_gain(chemin, gain)


def resoudre_gain(depuis_env: float, persiste: float | None) -> float:
    """Le fichier parlé gagne. Sinon la valeur déjà posée par la carte ou ``*_FORCE``."""
    if persiste is None:
        return float(depuis_env)
    return borner(persiste)
