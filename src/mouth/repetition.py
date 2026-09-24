"""Répéter la dernière réponse sans passer par le modèle.

Séance du 24 sept : après « Codex a fini. 22 », « Je n'ai pas entendu ta
réponse. » a donné « Je suis là. » ; avec une consigne explicite dans le
prompt, le cerveau local 3B répondait encore « je n'ai pas entendu votre
demande précédente ». Redire ce qui vient d'être dit n'est pas une question
de jugement : c'est une décision locale, instantanée, qui ne peut pas rater.
"""
from __future__ import annotations

import re
import unicodedata

# Au-delà, la phrase porte une vraie demande (« répète après moi que… »).
MAX_MOTS = 8

_MOTIFS = (
    r"\b(pas|rien) (bien )?(entendu|compris|capte|saisi)\b",
    r"\brepete[sz]?\b",
    r"\brepeter\b",
    r"\bredis\b",
    r"\bqu est ce que tu (as|a) dit\b",
    r"\btu (as|a) dit quoi\b",
    r"\bdidn t (hear|catch|get)\b",
    r"\brepeat\b",
    r"\bsay (that|it) again\b",
    r"\bwhat did you say\b",
)


def _normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())


def demande_de_repetition(transcript: str) -> bool:
    normalise = _normaliser(transcript)
    if not normalise or len(normalise.split()) > MAX_MOTS:
        return False
    return any(re.search(motif, normalise) for motif in _MOTIFS)


def derniere_reponse(historique: list[dict]) -> str | None:
    """La dernière phrase prononcée : première ligne du dernier message assistant.

    Les lignes suivantes portent le détail d'un harnais, gardé pour le
    cerveau mais jamais dit à voix haute.
    """
    for message in reversed(historique or []):
        if message.get("role") == "assistant":
            texte = (message.get("content") or "").strip().splitlines()
            if texte and texte[0].strip():
                return texte[0].strip()
    return None


# « Il a dit quoi ? » après une annonce de harnais (séance du 24/09) : au banc,
# le cerveau distant répondait « je ne sais pas » une fois sur trois alors que
# le résultat était dans son contexte.
_MOTIFS_HARNAIS = (
    r"\b(il|elle|codex|claude) (a|as) (dit|repondu) quoi\b",
    r"\bqu est ce qu (il|elle) (a|t a) (dit|repondu)\b",
    r"\bqu a (dit|repondu) (codex|claude)\b",
    r"\bc etait quoi (la|sa) reponse\b",
    r"\bquelle (est|etait) (la|sa) reponse\b",
    r"\bwhat did (it|he|codex|claude) say\b",
)


def demande_resultat_harnais(transcript: str) -> bool:
    normalise = _normaliser(transcript)
    if not normalise or len(normalise.split()) > MAX_MOTS:
        return False
    return any(re.search(motif, normalise) for motif in _MOTIFS_HARNAIS)


def dernier_resultat_harnais(historique: list[dict]) -> str | None:
    """Première ligne de la réponse qui suit la dernière tâche confiée."""
    messages = list(historique or [])
    for i in range(len(messages) - 1, -1, -1):
        contenu = messages[i].get("content") or ""
        if messages[i].get("role") == "user" and contenu.startswith("(Tâche confiée à"):
            return derniere_reponse(messages[i : i + 2])
    return None
