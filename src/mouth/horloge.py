"""L'heure, dite sans cerveau.

« Il est 14 h 40, je finis à quelle heure ? » reste une escalade : c'est un
calcul, et les modèles locaux le ratent. « Quelle heure est-il ? » n'en est
pas un. La voix lit l'horloge de Paris.
"""
from __future__ import annotations

import re
from datetime import datetime

from src.mouth.normalize import _heure_en_lettres, _horloge_en
from src.parole import normaliser
from src.temps import maintenant_local

MAX_MOTS = 7

_PAS_L_HEURE = frozenset(
    {
        "finis",
        "fini",
        "finir",
        "reunion",
        "rendez",
        "minute",
        "minutes",
        "demain",
        "matin",
        "soir",
        "dure",
        "duree",
        "commence",
        "commencer",
        "dans",
        "reste",
        "restent",
        "demande",
        "explique",
    }
)

_MOTIFS = (
    r"\bquelle heure est il\b",
    r"\bquelle heure il est\b",
    r"\bil est quelle heure\b",
    r"\btu as l heure\b",
    r"\bdonne moi l heure\b",
    r"\bl heure s il te plait\b",
    r"\bwhat time is it\b",
    r"\bwhats the time\b",
    r"\bque hora es\b",
    r"\bdime la hora\b",
)


def demande_d_heure(transcript: str) -> bool:
    texte = normaliser(transcript)
    if not texte or len(texte.split()) > MAX_MOTS:
        return False
    if _PAS_L_HEURE.intersection(texte.split()):
        return False
    return any(re.search(motif, texte) for motif in _MOTIFS)


def phrase_heure(quand: datetime | None = None, langue: str = "fr") -> str:
    local = maintenant_local(quand)
    heures, minutes = local.hour, local.minute
    if langue == "en":
        return f"It's {_horloge_en(str(heures), str(minutes))}."
    if langue == "es":
        if minutes == 0:
            return f"Son las {heures} en punto."
        return f"Son las {heures} y {minutes}."
    if heures == 0 and minutes == 0:
        return "Il est minuit."
    if heures == 12 and minutes == 0:
        return "Il est midi."
    return f"Il est {_heure_en_lettres(str(heures), str(minutes))}."
