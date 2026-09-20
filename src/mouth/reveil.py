"""Réveil court : accusé de réception d'une interpellation, sans BRAIN.

Quand JeV a tranché « adressé à HA » mais que le transcript n'est pas
une demande exploitable, on répond en une phrase courte. La décision
est locale et gratuite — aucun appel réseau.
"""
from __future__ import annotations

import random
import unicodedata

# Tutoiement, présence calme. Deux ou trois formulations par langue
# pour ne pas sonner comme un robot qui répète.
PHRASES_REVEIL: dict[str, tuple[str, ...]] = {
    "fr": ("Oui ?", "Je t'écoute.", "Oui, je suis là."),
    "en": ("Yes?", "I'm listening.", "Go ahead."),
    "es": ("¿Sí?", "Te escucho.", "Dime."),
}

_NOMS: tuple[tuple[str, ...], ...] = (
    ("hyper", "ambient"),
    ("hyper", "ambiant"),
    ("mother",),
    ("ha",),
)

_PHRASES_VIDES: tuple[tuple[str, ...], ...] = (
    ("tu", "es", "la"),
    ("t", "es", "la"),
    ("tes", "la"),
    ("you", "there"),
    ("estas", "ahi"),
)

_MOTS_VIDES: frozenset[str] = frozenset(
    {
        "eh",
        "dis",
        "hey",
        "bonjour",
        "salut",
        "hello",
        "hi",
        "hola",
        "oye",
        "oh",
        "euh",
        "he",
        "ho",
        "yo",
        "uh",
        "um",
        "allo",
        "please",
        "coucou",
        "bueno",
    }
)


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(ch for ch in decompose if unicodedata.category(ch) != "Mn")


def _jetons(transcript: str) -> list[str]:
    brut = _sans_accents(transcript).lower()
    pieces: list[str] = []
    actuel: list[str] = []
    for ch in brut:
        if ch.isalnum():
            actuel.append(ch)
        elif actuel:
            pieces.append("".join(actuel))
            actuel = []
    if actuel:
        pieces.append("".join(actuel))
    return pieces


def _retirer_sequence(jetons: list[str], sequence: tuple[str, ...]) -> list[str]:
    n = len(sequence)
    if n == 0 or n > len(jetons):
        return jetons
    resultat: list[str] = []
    i = 0
    while i < len(jetons):
        if tuple(jetons[i : i + n]) == sequence:
            i += n
        else:
            resultat.append(jetons[i])
            i += 1
    return resultat


def _reste_utile(jetons: list[str], *, langue: str) -> list[str]:
    restants = list(jetons)
    for nom in _NOMS:
        restants = _retirer_sequence(restants, nom)
    for phrase in _PHRASES_VIDES:
        restants = _retirer_sequence(restants, phrase)
    vides = _MOTS_VIDES | {
        "fr": frozenset({"coucou"}),
        "en": frozenset({"please"}),
        "es": frozenset({"bueno"}),
    }.get(langue, frozenset())
    return [j for j in restants if j not in vides]


def reveil_court_suffit(transcript: str, *, langue: str = "fr") -> bool:
    """True si le transcript est une interpellation sans demande exploitable."""
    jetons = _jetons(transcript)
    if len(jetons) < 4:
        return True
    return not _reste_utile(jetons, langue=langue)


def phrase_de_reveil(*, langue: str = "fr") -> str:
    """Une des phrases courtes, choisie pour ne pas toujours dire la même."""
    voix = PHRASES_REVEIL.get(langue, PHRASES_REVEIL["fr"])
    return random.choice(voix)
