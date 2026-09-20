"""Les harnais ne repondent qu'a une demande explicite.

Mesure du 2026-09-20, mains libres actif : Whisper a transcrit
« MOTHER Codex Camunda » — la liste `EARS_HOTWORDS` elle-meme, recrachee sur un
segment bruite. Le cerveau y a vu « Codex », a appele le pont, qui a expire :
39 secondes de silence en pleine conversation.

Souffler des mots-cles a un moteur de transcription en fait un aimant a
hallucinations. On ne peut donc pas traiter la simple presence d'un nom d'outil
comme une intention. Il faut un VERBE de requete pointant vers le harnais.

Consigne de l'utilisateur : « elle ne doit pas appeler les harnais sans demande
explicite ».
"""
from __future__ import annotations

import re
import unicodedata

# Les harnais joignables depuis la voix.
OUTILS_HARNAIS = ("ask_codex", "ask_claude", "ask_muse")

_NOMS = r"(?:codex|claude|muse|cursor)"
_VERBES = (
    r"demande(?:r|s|z)?",
    r"interroge(?:r|s|z)?",
    r"consulte(?:r|s|z)?",
    r"pose(?:r|s|z)?\s+la\s+question",
    r"ask",
    r"fais\s+(?:lire|relire|verifier)\s+(?:ca\s+|cela\s+)?(?:par|a)",
)

# Le verbe precede le nom, avec au plus quelques mots entre les deux
# (« demande a Codex », « demande donc a Claude de relire »).
_MOTIF = re.compile(
    r"(?:" + "|".join(_VERBES) + r")\b(?:\W+\w+){0,3}?\W+" + _NOMS + r"\b",
    re.IGNORECASE,
)

# Un refus annule tout : « il ne faut PAS appeler Codex » contient le nom et
# un verbe, mais dit exactement le contraire.
_REFUS = re.compile(
    r"\b(?:pas|jamais|surtout\s+pas|inutile\s+d[e'])\b", re.IGNORECASE
)


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def harnais_demande(transcription: str) -> bool:
    """True si la personne demande EXPLICITEMENT d'interroger un harnais.

    La simple mention d'un nom d'outil ne suffit pas : il faut un verbe de
    requete qui pointe vers lui, et aucune negation dans l'enonce.
    """
    if not transcription or not transcription.strip():
        return False
    texte = _sans_accents(transcription)
    if not _MOTIF.search(texte):
        return False
    return not _REFUS.search(texte)
