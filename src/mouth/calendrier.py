"""La date, dite sans cerveau.

« On est quel jour ? » et « quelle est la date ? » ne sont pas un calcul.
« Dans trois jours, on sera quel jour ? » en est un : ça reste au modèle.
"""
from __future__ import annotations

import re
from datetime import datetime

from src.mouth.normalize import _cardinal, _cardinal_en
from src.parole import normaliser
from src.temps import maintenant_local

MAX_MOTS = 8

_PAS_LA_DATE = frozenset(
    {
        "demain",
        "hier",
        "dans",
        "sera",
        "serons",
        "semaine",
        "prochaine",
        "prochain",
        "naissance",
        "anniversaire",
        "limite",
        "rendez",
        "reunion",
        "deadline",
        "tomorrow",
        "yesterday",
        "birthday",
        "meeting",
        "manana",
        "cumple",
        "demande",
        "explique",
        "note",
        "ecris",
        "ajoute",
    }
)

_MOTIFS = (
    r"\bquel jour\b",
    r"\bquelle est la date\b",
    r"\bquelle date\b",
    r"\bdonne moi la date\b",
    r"\bon est le combien\b",
    r"\bc est quoi la date\b",
    r"\bwhat day is it\b",
    r"\bwhat s the date\b",
    r"\bwhat is the date\b",
    r"\btoday s date\b",
    r"\bque dia es\b",
    r"\bque fecha es\b",
    r"\ba que fecha estamos\b",
)

_JOURS_FR = (
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
)
_MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
_JOURS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_MOIS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_ORDINAL_EN = (
    "",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
    "twenty-first",
    "twenty-second",
    "twenty-third",
    "twenty-fourth",
    "twenty-fifth",
    "twenty-sixth",
    "twenty-seventh",
    "twenty-eighth",
    "twenty-ninth",
    "thirtieth",
    "thirty-first",
)
_JOURS_ES = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
_MOIS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_UNITE_ES = (
    "cero",
    "uno",
    "dos",
    "tres",
    "cuatro",
    "cinco",
    "seis",
    "siete",
    "ocho",
    "nueve",
    "diez",
    "once",
    "doce",
    "trece",
    "catorce",
    "quince",
    "dieciséis",
    "diecisiete",
    "dieciocho",
    "diecinueve",
)
_VEINTI_ES = (
    "veinte",
    "veintiuno",
    "veintidós",
    "veintitrés",
    "veinticuatro",
    "veinticinco",
    "veintiséis",
    "veintisiete",
    "veintiocho",
    "veintinueve",
)
_DIZAINE_ES = (
    "",
    "",
    "veinte",
    "treinta",
    "cuarenta",
    "cincuenta",
    "sesenta",
    "setenta",
    "ochenta",
    "noventa",
)


def demande_de_date(transcript: str) -> bool:
    texte = normaliser(transcript)
    if not texte or len(texte.split()) > MAX_MOTS:
        return False
    if _PAS_LA_DATE.intersection(texte.split()):
        return False
    return any(re.search(motif, texte) for motif in _MOTIFS)


def _cardinal_es(n: int) -> str:
    n = int(n)
    if n < 20:
        return _UNITE_ES[n]
    if n < 30:
        return _VEINTI_ES[n - 20]
    if n < 100:
        diz, unit = divmod(n, 10)
        if unit == 0:
            return _DIZAINE_ES[diz]
        return f"{_DIZAINE_ES[diz]} y {_UNITE_ES[unit]}"
    if 2000 <= n < 2100:
        reste = n - 2000
        if reste == 0:
            return "dos mil"
        return f"dos mil {_cardinal_es(reste)}"
    return str(n)


def phrase_date(quand: datetime | None = None, langue: str = "fr") -> str:
    local = maintenant_local(quand)
    jour, mois, annee = local.day, local.month, local.year
    index = local.weekday()
    if langue == "en":
        return (
            f"It's {_JOURS_EN[index]}, {_MOIS_EN[mois - 1]} "
            f"{_ORDINAL_EN[jour]}, {_cardinal_en(annee)}."
        )
    if langue == "es":
        quantieme = "primero" if jour == 1 else _cardinal_es(jour)
        return (
            f"Es {_JOURS_ES[index]}, {quantieme} de {_MOIS_ES[mois - 1]} "
            f"de {_cardinal_es(annee)}."
        )
    quantieme = "premier" if jour == 1 else _cardinal(jour)
    return (
        f"Nous sommes {_JOURS_FR[index]} {quantieme} {_MOIS_FR[mois - 1]} "
        f"{_cardinal(annee)}."
    )
