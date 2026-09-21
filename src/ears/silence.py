"""Garde-fous déterministes pour les artefacts ASR produits sur du silence."""
from __future__ import annotations

import re
import unicodedata


# faster-whisper : mêmes seuils que le décodeur (no_speech_threshold / logprob_threshold).
SEUIL_NON_PAROLE = 0.6
SEUIL_LOGPROB = -1.0

# Filet textuel, pas la défense principale : no_speech_prob / avg_logprob d'abord.
# Couvre le cas où les probabilités passent et que Whisper récite un crédit
# de sous-titrage appris sur les données d'entraînement.
_MOTIFS_HALLUCINATION = (
    "sous titrage",
    "sous titres realises par",
    "amara org",
    "merci d avoir regarde",
    "abonnez vous",
    "subtitles by",
    "thanks for watching",
)


def _normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())


def est_artefact_whisper_silencieux(texte: str) -> bool:
    """Reconnaît l'unique crédit fantôme mesuré sur le micro réel.

    Le filtre d'énergie avant ASR est le garde-fou principal : il épargne même
    l'inférence. Celui-ci est volontairement étroit, en seconde ligne, pour le
    cas où le segment contient assez de bruit parasite pour passer le seuil.
    Il ne classe donc pas des phrases usuelles, seulement le crédit de
    sous-titrage récité par Whisper sur le silence.
    """
    return _normaliser(texte) == "sous titrage st 501"


def est_hallucination_whisper(texte: str) -> bool:
    """Filet sur le texte normalisé. La défense principale est le signal du modèle."""
    normalise = _normaliser(texte)
    if not normalise:
        return False
    return any(motif in normalise for motif in _MOTIFS_HALLUCINATION)


def segment_sans_parole(segment) -> bool:
    """True si le segment faster-whisper n'est pas de la parole.

    Un `no_speech_prob` au-dessus du seuil, ou un `avg_logprob` trop bas,
    doit être jeté avant JeV. C'est la défense générale, sans liste.
    """
    if segment is None:
        return False
    if isinstance(segment, dict):
        no_speech = segment.get("no_speech_prob")
        logprob = segment.get("avg_logprob")
    else:
        no_speech = getattr(segment, "no_speech_prob", None)
        logprob = getattr(segment, "avg_logprob", None)
    if no_speech is not None and float(no_speech) >= SEUIL_NON_PAROLE:
        return True
    if logprob is not None and float(logprob) < SEUIL_LOGPROB:
        return True
    return False


def jeter_tour_bruit(texte, segments=None, *, mains_libres: bool) -> bool:
    """Hors mains libres, l'utilisateur a décidé de parler : on ne jette rien."""
    if not mains_libres:
        return False
    for segment in segments or ():
        if segment_sans_parole(segment):
            return True
    return est_hallucination_whisper(texte)
