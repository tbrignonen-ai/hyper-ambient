"""Rejoindre une session de harnais à la voix (24/09).

« Reprends la dernière session Claude », « rejoins la session Codex qui parle
de n8n », « ouvre la session contenant soutenance ou démo dans le titre »,
« nouvelle session Claude ». Décision locale, prise avant le cerveau comme
l'annulation : ce n'est pas un jugement, et le 3B l'aurait envoyée au harnais
comme une question.

Le pont cherche dans les sessions de l'utilisateur ; la session trouvée est
adoptée par le client, si bien que les demandes suivantes y vont, et Presence
l'ouvre dans le harnais.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

from src.brain.mandat import redresser_harnais
from src.i18n import t

MAX_MOTS = 20
MOTS_TITRE = 8

_OUTILS = (("Claude", "ask_claude"), ("Codex", "ask_codex"))

# Une demande adressée au harnais (« demande à Claude d'ouvrir la session… »)
# reste une demande : c'est le harnais qu'elle concerne, pas la session.
_ADRESSE = re.compile(
    r"^\s*(?:(?:ok|bon|alors|euh|et|hyper ambiant|hyper ambient)\s+)*"
    r"(?:demande|dis|pose|envoie|ask)\b"
)
_NOUVELLE = re.compile(r"\bnouvel(?:le)? session\b|\bsession (?:vierge|neuve)\b")
_VERBE = re.compile(
    r"\b(?:repren\w*|reprend\w*|rejoin\w*|rejoind\w*|ouvr\w*|retourn\w*|revien\w*|"
    r"bascul\w*|continu\w*|va|vas|aller|allons|passe|charge\w*|remets?|retrouv\w*)\b"
)
_HARNAIS = re.compile(r"\b(claude|codex)\b")
_DE = r"(?:de |d'|du |des |sur )?"
_MARQUEUR = re.compile(
    r"\b(?:qui (?:parl\w*|concern\w*|port\w*) " + _DE + r"|concernant |a propos " + _DE
    + r"|au sujet " + _DE + r"|ou (?:on|tu|j'ai) parl\w* " + _DE
    + r"|sur |contenant |dont le titre contient |intitulee? |appelee? |nommee? )"
)
_FIN_TITRE = re.compile(r"\s+dans (?:le|son) titre\s*$", re.I)


@dataclass(frozen=True)
class DemandeSession:
    harnais: Optional[str]
    action: str  # "derniere" | "chercher" | "nouvelle"
    requete: str


@dataclass(frozen=True)
class ResultatSession:
    phrase: str
    harnais: Optional[str] = None
    session: Optional[str] = None


def _normaliser(texte: str) -> str:
    """Minuscules sans accents, caractère pour caractère : les positions restent
    celles du texte d'origine, d'où l'on extrait la requête telle que dite."""
    sortie = []
    for c in texte:
        n = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x))
        n = n.lower()
        sortie.append(n if len(n) == 1 else c.lower()[:1] or " ")
    return "".join(sortie).replace("’", "'")


def demande_de_session(prompt: str) -> Optional[DemandeSession]:
    texte = redresser_harnais(prompt or "").strip()
    if not texte or len(texte.split()) > MAX_MOTS:
        return None
    norme = _normaliser(texte)
    if "session" not in norme or _ADRESSE.match(norme):
        return None
    trouve = _HARNAIS.search(norme)
    harnais = trouve.group(1).capitalize() if trouve else None
    if _NOUVELLE.search(norme):
        return DemandeSession(harnais, "nouvelle", "")
    if not _VERBE.search(norme):
        return None
    debut = norme.index("session")
    marqueur = _MARQUEUR.search(norme, debut)
    requete = ""
    if marqueur:
        requete = _FIN_TITRE.sub("", texte[marqueur.end():]).strip(" .?!,;")
    if requete:
        return DemandeSession(harnais, "chercher", requete)
    return DemandeSession(harnais, "derniere", "")


def ponts_harnais(registre) -> dict[str, Any]:
    """Les clients de pont branchés, trouvés derrière leurs outils."""
    ponts: dict[str, Any] = {}
    for harnais, outil in _OUTILS:
        spec = registre.get(outil) if registre is not None else None
        if spec is None:
            continue
        pont = getattr(spec.handler, "pont", spec.handler)
        if hasattr(pont, "chercher_session"):
            ponts[harnais] = pont
    return ponts


def _titre_court(session: dict) -> str:
    titre = (session.get("titre") or "").strip() or (session.get("apercu") or "").strip()
    mots = titre.replace("«", "").replace("»", "").split()
    return " ".join(mots[:MOTS_TITRE])


def _et(noms: list[str]) -> str:
    return t("session.et").join(noms)


async def executer(demande: DemandeSession, ponts: dict[str, Any]) -> ResultatSession:
    if demande.harnais and demande.harnais not in ponts:
        return ResultatSession(t("session.absent", harnais=demande.harnais))
    cibles = [demande.harnais] if demande.harnais else [h for h, _ in _OUTILS if h in ponts]
    if not cibles:
        return ResultatSession(t("session.aucun_pont"))

    if demande.action == "nouvelle":
        for harnais in cibles:
            pont = ponts[harnais]
            if hasattr(pont, "oublier_session"):
                pont.oublier_session()
            else:
                pont.session = None
        return ResultatSession(t("session.nouvelle", harnais=_et(cibles)))

    trouvees = []
    for harnais in cibles:
        session = await ponts[harnais].chercher_session(demande.requete)
        if session:
            trouvees.append((harnais, session))
    if not trouvees:
        if demande.requete:
            cle = "session.introuvable" if demande.harnais else "session.introuvable_partout"
            return ResultatSession(t(cle, harnais=demande.harnais or "", sujet=demande.requete))
        return ResultatSession(t("session.aucune", harnais=_et(cibles)))
    harnais, session = max(
        trouvees, key=lambda hs: (hs[1].get("score") or 0, hs[1].get("date") or 0)
    )
    ponts[harnais].adopter_session(session)
    titre = _titre_court(session)
    cle = "session.reprise" if titre else "session.reprise_sans_titre"
    return ResultatSession(
        t(cle, harnais=harnais, titre=titre), harnais=harnais, session=str(session["id"])
    )
