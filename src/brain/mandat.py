"""Un appel harnais n'est plus une reponse : c'est un mandat confie.

L'accuse part tout de suite. L'appel reseau vit dans une tache de fond.
Le texte long n'est jamais lu : seulement un resume court, plus un pointeur.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field, replace
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
NOMS_HARNAIS = _NOMS
_NOMS_VERS_HARNAIS = {
    "claude": "Claude",
    "codex": "Codex",
    "muse": "Muse",
    "cursor": "Cursor",
}

# Un harnais ne doit jamais recevoir le simple geste de le nommer.  Cette
# vérification vit à la frontière du mandat (et non dans le prompt) : le modèle
# peut encore produire un appel d'outil avec ``question=""`` ou reformuler la
# demande de l'utilisateur en « demande à Codex ».  Elle est volontairement
# structurelle, pas une liste de verbes ou de sujets autorisés.
_MOTS_QUESTION = re.compile(r"[^\W\d_]+", re.UNICODE)
_LONGUEUR_MIN_QUESTION = 8
_NOMBRE_MIN_MOTS_QUESTION = 2


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


def nom_harnais_dit(prompt: str) -> str:
    """Le nom tel que l'utilisateur l'a prononcé, pour le dire en retour."""
    if re.search(r"\bclaude\s+code\b", prompt or "", re.IGNORECASE):
        return "Claude Code"
    return extraire_harnais(prompt)


def proposer_harnais(registre) -> Optional[str]:
    """Premier harnais réellement branché, pour le proposer sans le saisir."""
    if registre is None:
        return None
    for nom, outil in OUTIL_PAR_HARNAIS.items():
        if registre.get(outil) is not None:
            return nom
    return None


def harnais_est_branche(nom: str, registre) -> bool:
    outil = OUTIL_PAR_HARNAIS.get(nom)
    return outil is not None and registre is not None and registre.get(outil) is not None


def phrase_harnais_absent(nom: str, propose: Optional[str] = None) -> str:
    tete = f"{nom} n'est pas connecté sur cette machine"
    if propose:
        return f"{tete}. Je peux demander à {propose}, si tu veux."
    return tete


def phrase_si_harnais_non_branche(prompt, registre) -> Optional[str]:
    """Phrase unique : harnais nommé, pont absent. Cursor, Muse, Claude."""
    if not re.search(r"\b" + _NOMS + r"\b", prompt or "", re.IGNORECASE):
        return None
    if harnais_est_branche(extraire_harnais(prompt), registre):
        return None
    return phrase_harnais_absent(nom_harnais_dit(prompt), proposer_harnais(registre))


def respecter_harnais_nomme(prompt, appels, registre):
    """Le harnais nommé fait autorité au moment du choix d'outil.

    Ne force pas d'appel : « qu'est-ce que Codex ? » reste une question.
    Si le distant saisit un autre harnais, on réécrit. S'il n'est pas
    configuré, on le dit — on ne bascule pas.
    """
    if not re.search(r"\b" + _NOMS + r"\b", prompt or "", re.IGNORECASE):
        return list(appels or []), None
    refus = phrase_si_harnais_non_branche(prompt, registre)
    if refus:
        return [], refus
    exigé = OUTIL_PAR_HARNAIS.get(extraire_harnais(prompt))
    if exigé is None:
        return list(appels or []), None
    noms_harnais = set(OUTIL_PAR_HARNAIS.values())
    retenus = list(appels or [])
    if not any(getattr(appel, "name", None) in noms_harnais for appel in retenus):
        return retenus, None
    recrits = []
    for appel in retenus:
        if appel.name in noms_harnais and appel.name != exigé:
            recrits.append(replace(appel, name=exigé))
        else:
            recrits.append(appel)
    return recrits, None


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


def question_est_substantielle(question: str) -> bool:
    """Vrai si le mandat porte une demande, pas seulement un destinataire.

    Deux mots et huit caractères laissent passer « la météo », « quel temps »
    ou « relis transport.py », tout en arrêtant une chaîne vide, « Codex » et
    « demande à Codex ».  Quand le texte mentionne un harnais, ``extraire_sujet``
    doit en outre en extraire autre chose que le pronom de repli ``ça``.
    """
    texte = " ".join((question or "").split())
    mots = _MOTS_QUESTION.findall(texte)
    if len(texte) < _LONGUEUR_MIN_QUESTION or len(mots) < _NOMBRE_MIN_MOTS_QUESTION:
        return False
    if re.search(r"\b" + _NOMS + r"\b", texte, re.IGNORECASE):
        sujet = extraire_sujet(texte)
        if sujet == "ça":
            return False
        mots_sujet = _MOTS_QUESTION.findall(sujet)
        return len(sujet) >= _LONGUEUR_MIN_QUESTION and len(mots_sujet) >= _NOMBRE_MIN_MOTS_QUESTION
    return True


def phrase_question_manquante(harnais: str) -> str:
    return f"Que veux-tu que je demande à {harnais} ?"


def phrase_accuse(harnais: str, sujet: str) -> str:
    return t("mandat.accuse", harnais=harnais, sujet=sujet)


def phrase_depot(harnais: str) -> str:
    """Accusé bref rendu par un outil harnais dans le tour vocal.

    Ce texte est la réponse du handler, pas une amorce : le tour peut donc se
    clore sans attendre le pont. L'arrivée de la réponse reste annoncée par
    ``phrase_arrivee`` dans la veille des mandats.
    """
    return f"Je demande à {harnais}. Je te préviens dès qu'il répond."


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
        # Le pont Codex préfixe déjà une consigne parlable. Empiler
        # PREFIXE_CONTRAT devant la question produit l'écho mesuré
        # (« Je répondrai uniquement en français avec un objet JSON »).
        # Le résumé vocal vient de la réponse du harnais, parsée ensuite.
        texte = await asyncio.wait_for(appel(mandat.question), timeout=DELAI_EXPIRATION_S)
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


async def deposer_depuis_outil(
    registre: RegistreMandats,
    harnais: str,
    question: str,
    appel: Callable[[str], Awaitable[str]],
) -> str:
    """Dépose un mandat depuis un handler et rend immédiatement l'accusé.

    L'appel réseau n'est volontairement jamais attendu ici : ``confier`` le
    place dans sa tâche de fond avant de rendre la main au tour vocal.
    """
    if not question_est_substantielle(question):
        return phrase_question_manquante(harnais)
    try:
        await confier(registre, harnais, question, extraire_sujet(question), appel)
    except PleinMandats as exc:
        return exc.phrase
    return phrase_depot(harnais)
