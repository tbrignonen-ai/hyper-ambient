"""Forme comparée d'un énoncé : minuscules, sans accents, sans ponctuation.

Une seule fonction pour les décisions locales. Les variantes qui ne font pas
la même chose (réveil, sessions de harnais) restent à part.
"""
from __future__ import annotations

import re
import unicodedata


def normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())
