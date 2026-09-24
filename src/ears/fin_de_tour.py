"""Fin de tour sémantique : le silence seul ne suffit pas.

Presence découpe l'écoute continue au silence. Une pause au milieu d'une
pensée (« Alors demain je voudrais… ») coupait donc la phrase en deux, et la
première moitié partait au cerveau. Ce module juge, sur la transcription,
si l'énoncé sonne achevé. Inachevé, le tour attend le segment suivant.

Décision pure et locale : aucun modèle, aucune latence.
"""
from __future__ import annotations

import re
import unicodedata

# Mots après lesquels une phrase française ne s'arrête pas.
_MOTS_DE_SUITE = frozenset(
    """
    et mais ou donc alors puis car parce que qui quoi dont de du des le la les
    l un une au aux a en pour avec sans sur sous dans par vers chez entre
    euh heu hum bah ben genre enfin bref je j tu il elle on nous vous ils
    mon ma mes ton ta tes son sa ses notre votre leur si comme quand ce cet
    cette est
    """.split()
)

# Fins figées qui annoncent une suite.
_FINS_OUVERTES = (
    "je voudrais",
    "je veux",
    "est ce que",
    "attends",
    "attend",
    "tu peux",
    "il faut",
)


def _normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())


def enonce_incomplet(texte: str) -> bool:
    brut = (texte or "").strip()
    if not brut:
        return False
    # Une question posée est un tour complet, quelle que soit sa forme.
    if brut.endswith("?"):
        return False
    # Points de suspension ou virgule finale : Whisper note une pensée ouverte.
    if brut.endswith(("...", "…", ",", ";", ":")):
        return True
    normalise = _normaliser(brut)
    if not normalise:
        return False
    if any(normalise.endswith(fin) for fin in _FINS_OUVERTES):
        return True
    return normalise.split()[-1] in _MOTS_DE_SUITE
