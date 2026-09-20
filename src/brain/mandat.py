"""Un appel harnais n'est plus une reponse : c'est un mandat confie.

L'accuse part tout de suite. L'appel reseau vit dans une tache de fond.
Le texte long n'est jamais lu : seulement un resume court, plus un pointeur.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from src.i18n import t

try:
    from src.brain.contrat_harnais import ReponseHarnais, analyser, envelopper
except ImportError:  # le voisin s'ecrit en parallele ; les tests monkeypatchent
    class ReponseHarnais:  # type: ignore[no-redef]
        def __init__(
            self,
            verdict="fait",
            resume_voix="",
            detail_voix="",
            resultat_complet="",
            conforme=False,
        ):
            self.verdict = verdict
            self.resume_voix = resume_voix
            self.detail_voix = detail_voix
            self.resultat_complet = resultat_complet
            self.conforme = conforme

    def envelopper(question: str) -> str:  # type: ignore[misc]
        return question

    def analyser(texte: str) -> ReponseHarnais:  # type: ignore[misc]
        return ReponseHarnais(resultat_complet=texte or "", conforme=False)

MAX_MANDATS_EN_COURS = 3
DELAI_EXPIRATION_S = 300.0
DELAI_RAPPEL_S = 60.0

OUTIL_PAR_HARNAIS = {
    "Codex": "ask_codex",
    "Claude": "ask_claude",
    "Muse": "ask_muse",
}

_NOMS = r"(codex|claude|muse|cursor)"
_NOMS_VERS_HARNAIS = {
    "claude": "Claude",
    "codex": "Codex",
    "muse": "Muse",
    "cursor": "Codex",
}


class PleinMandats(Exception):
    """Plus de trois mandats en cours : on refuse, on n'empile pas."""

    def __init__(self, phrase: str):
        super().__init__(phrase)
        self.phrase = phrase


@dataclass
class Mandat:
    identifiant: str
    harnais: str
    question: str
    sujet: str
    depose_a: float
    etat: str
    reponse: Optional[ReponseHarnais] = None
    annonce_faite: bool = False
    rappel_fait: bool = False
    tache: Optional[asyncio.Task] = field(default=None, repr=False)


class RegistreMandats:
    """Depot en memoire. Borne dure : au plus 3 mandats en cours."""

    def __init__(self) -> None:
        self._par_id: dict[str, Mandat] = {}

    def deposer(self, mandat: Mandat) -> None:
        if len(self.en_cours()) >= MAX_MANDATS_EN_COURS:
            raise PleinMandats(phrase_plein())
        self._par_id[mandat.identifiant] = mandat

    def en_cours(self) -> list[Mandat]:
        return [m for m in self._par_id.values() if m.etat == "en_cours"]

    def prets(self) -> list[Mandat]:
        return [
            m
            for m in self._par_id.values()
            if m.etat in {"fini", "echoue"} and not m.annonce_faite
        ]

    def marquer_annonce(self, identifiant: str) -> None:
        mandat = self._par_id.get(identifiant)
        if mandat is not None:
            mandat.annonce_faite = True

    def oublier(self, identifiant: str) -> None:
        mandat = self._par_id.pop(identifiant, None)
        if mandat is None:
            return
        tache = mandat.tache
        if tache is not None and not tache.done():
            tache.cancel()


def extraire_harnais(prompt: str) -> str:
    for m in re.finditer(r"\b" + _NOMS + r"\b", prompt or "", re.IGNORECASE):
        return _NOMS_VERS_HARNAIS[m.group(1).lower()]
    return "Codex"


def extraire_sujet(prompt: str) -> str:
    texte = (prompt or "").strip()
    if not texte:
        return "ça"
    m = re.search(
        r"\b" + _NOMS + r"\b(?:\s+(?:de|d['’]|to|about|for))?\s*(.*)$",
        texte,
        re.IGNORECASE,
    )
    if not m:
        return "ça"
    reste = (m.group(2) or "").strip(" .?!,;:")
    reste = re.sub(
        r"^(?:de\s+|d['’]|to\s+|about\s+|for\s+)", "", reste, flags=re.IGNORECASE
    ).strip(" .?!,;:")
    return reste or "ça"


def phrase_accuse(harnais: str, sujet: str) -> str:
    return t("mandat.accuse", harnais=harnais, sujet=sujet)


def phrase_rappel(harnais: str) -> str:
    return t("mandat.rappel", harnais=harnais)


def phrase_plein() -> str:
    return t("mandat.plein")


def _deux_phrases(texte: str) -> str:
    texte = (texte or "").strip()
    if not texte:
        return ""
    morceaux = re.split(r"(?<=[.!?])\s+", texte)
    return " ".join(morceaux[:2]).strip()


def phrase_arrivee(mandat: Mandat) -> str:
    if mandat.etat == "echoue":
        return t("mandat.echoue", harnais=mandat.harnais)
    fini = t("mandat.fini", harnais=mandat.harnais)
    offre = t("mandat.offre")
    resume = ""
    if mandat.reponse is not None:
        resume = (getattr(mandat.reponse, "resume_voix", None) or "").strip()
    if not resume:
        return t("mandat.sans_resume", harnais=mandat.harnais)
    resume = _deux_phrases(resume)
    return f"{fini} {resume} {offre}".strip()


async def _courir(mandat: Mandat, appel: Callable[[str], Awaitable[str]]) -> None:
    try:
        question = envelopper(mandat.question)
        texte = await asyncio.wait_for(appel(question), timeout=DELAI_EXPIRATION_S)
        mandat.reponse = analyser(texte)
        mandat.etat = "fini"
    except asyncio.CancelledError:
        mandat.etat = "echoue"
        mandat.reponse = None
        raise
    except Exception:
        mandat.etat = "echoue"
        mandat.reponse = None


async def confier(
    registre: RegistreMandats,
    harnais: str,
    question: str,
    sujet: str,
    appel: Callable[[str], Awaitable[str]],
) -> Mandat:
    """Cree le mandat, rend la main, lance l'appel dans une tache de fond."""
    mandat = Mandat(
        identifiant=uuid.uuid4().hex[:12],
        harnais=harnais,
        question=question,
        sujet=sujet,
        depose_a=time.monotonic(),
        etat="en_cours",
    )
    registre.deposer(mandat)
    mandat.tache = asyncio.create_task(_courir(mandat, appel))
    return mandat
