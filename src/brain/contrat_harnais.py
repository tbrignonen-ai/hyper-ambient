"""Contrat de sortie impose aux harnais de code distants.

Pourquoi : un harnais CLI (Codex, Claude Code) peut renvoyer un diff ou une
analyse de plusieurs milliers de caracteres. Lire ce texte tel quel a voix
haute est inacceptable. On impose donc un format JSON strict et on le parse
de facon defensive. Le resume vocal est redige par le modele distant, jamais
par le modele local Granite 3B, pour eviter les contresens prononces.
"""

import json
import re
from dataclasses import dataclass
from typing import Iterator


LIMITE_RESUME_VOIX = 220
LIMITE_DETAIL_VOIX = 600

PREFIXE_CONTRAT = (
    "Reponds uniquement par un objet JSON valide, sans texte avant ni apres, "
    "sans balisage markdown. Cles exigees : verdict (une phrase courte), "
    "resume_voix (max 220 caracteres), detail_voix (max 600 caracteres), "
    "resultat_complet (texte integral). Les champs resume_voix et detail_voix "
    "seront lus a voix haute par une synthese vocale : ecris des phrases "
    "completes et naturelles, sans code, sans chemin de fichier, sans liste "
    "a puces, sans balisage. Ecris les nombres en toutes lettres si possible."
)


@dataclass
class ReponseHarnais:
    """Represente la reponse du harnais apres application du contrat."""

    verdict: str
    resume_voix: str
    detail_voix: str
    resultat_complet: str
    conforme: bool


def envelopper(question: str) -> str:
    """Retourne la question prefixee par le contrat de sortie."""
    return PREFIXE_CONTRAT + "\n\n" + question


def _candidats_json(texte: str) -> Iterator[str]:
    """Genere les sous-chaines JSON equilibrees trouvees dans le texte.

    On compte les accolades en ignorant celles contenues dans les chaines
    et en gerant les echappements. Chaque objet equilibre est propose ;
    l appelant tente de le parser.
    """
    i = 0
    while True:
        start = texte.find("{", i)
        if start == -1:
            return
        profondeur = 0
        dans_chaine = False
        echappe = False
        fin = -1
        for j in range(start, len(texte)):
            c = texte[j]
            if dans_chaine:
                if echappe:
                    echappe = False
                elif c == "\\":
                    echappe = True
                elif c == '"':
                    dans_chaine = False
            else:
                if c == '"':
                    dans_chaine = True
                elif c == "{":
                    profondeur += 1
                elif c == "}":
                    profondeur -= 1
                    if profondeur == 0:
                        fin = j
                        break
        if fin != -1:
            yield texte[start : fin + 1]
        i = start + 1


def _nettoyer_voix(texte: str) -> str:
    """Neutralise les elements non prononcables dans un champ vocal.

    Retire les clotures de code, les chemins Windows, les marqueurs de liste
    a puces et le balisage leger. Le resultat reste une phrase continue.
    """
    if not texte:
        return texte

    # Retire le balisage, jamais le texte. Mesure du 21/09 : les accents
    # graves avalaient le contenu (`python:3.11`) — phrase encore
    # grammaticale, donc fausse à l'oreille sans signal de perte.
    texte = re.sub(r"```\w*", " ", texte)
    texte = texte.replace("`", "")
    texte = re.sub(r"[A-Za-z]:[\\/][^\s]+", " ", texte)

    lignes = texte.splitlines()
    propres = []
    for ligne in lignes:
        s = ligne.strip()
        if not s:
            continue
        if s.startswith(("-", "*", "+", "\u2022")) and len(s) > 1:
            s = s[1:].strip()
        else:
            m = re.match(r"^(\d+[.)])\s+(.*)$", s)
            if m:
                s = m.group(2).strip()
        if s:
            propres.append(s)
    texte = " ".join(propres)

    texte = re.sub(r"[*_#>`]", " ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def _tronquer(texte: str, limite: int) -> str:
    """Tronque a la limite en coupant sur une frontiere de mot.

    Termine par une ponctuation si la coupe tombe en fin de mot. Ne leve
    jamais d exception.
    """
    if not texte:
        return texte
    if len(texte) <= limite:
        return texte
    coupe = texte[:limite]
    idx = coupe.rfind(" ")
    if idx <= 0:
        return texte[:limite]
    resultat = coupe[:idx].strip()
    if resultat and resultat[-1] not in ".!?":
        resultat += "."
    return resultat


def _premieres_phrases(texte: str, limite: int) -> str:
    """Construit un resume vocal depuis du texte libre.

    Prend les premieres phrases tant que la limite n est pas depassee,
    puis coupe a la frontiere de mot si la premiere phrase est trop longue.
    """
    texte = re.sub(r"\s+", " ", texte.strip())
    if not texte:
        return ""
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    resume = ""
    for phrase in phrases:
        if not phrase:
            continue
        candidat = phrase if not resume else resume + " " + phrase
        if len(candidat) <= limite:
            resume = candidat
        else:
            break
    if not resume:
        return _tronquer(phrases[0], limite)
    return resume


def analyser(texte: str) -> ReponseHarnais:
    """Analyse la reponse brute du harnais et retourne une ReponseHarnais.

    Survivre a tous les cas rencontres en pratique : JSON pur, JSON entoure
    de balisage ou de bavardage, cles manquantes, texte libre, chaine vide.
    """
    if not texte:
        return ReponseHarnais("", "", "", "", conforme=False)

    cles = ("verdict", "resume_voix", "detail_voix", "resultat_complet")

    for json_brut in _candidats_json(texte):
        try:
            data = json.loads(json_brut)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        types_ok = all(k in data and isinstance(data[k], str) for k in cles)
        valeurs = {}
        for k in cles:
            v = data.get(k)
            # Une valeur qui n'est pas une chaine est jetee, jamais convertie :
            # `str(["a"])` rendrait « crochet ouvrant a crochet fermant » a
            # l'oreille. Mieux vaut un champ vide qu'un repr Python prononce.
            valeurs[k] = v if isinstance(v, str) else ""

        complet = valeurs["resultat_complet"] or texte

        resume = _nettoyer_voix(valeurs["resume_voix"])
        detail = _nettoyer_voix(valeurs["detail_voix"])
        if not resume:
            # Le verdict est la seule phrase de repli qui vienne du harnais
            # lui-meme ; la preferer au silence quand `resume_voix` manque.
            resume = _nettoyer_voix(valeurs["verdict"])

        # La conformite porte sur le CONTRAT, pas sur la proprete de l'envelope.
        # Un agent CLI entoure presque toujours son JSON d'une cloture ```json
        # ou d'une phrase de politesse ; le contrat est tenu des lors que les
        # quatre cles sont presentes, typees, et dans les limites de longueur.
        conforme = types_ok and (
            len(data["resume_voix"]) <= LIMITE_RESUME_VOIX
            and len(data["detail_voix"]) <= LIMITE_DETAIL_VOIX
        )

        resume = _tronquer(resume, LIMITE_RESUME_VOIX)
        detail = _tronquer(detail, LIMITE_DETAIL_VOIX)

        return ReponseHarnais(
            verdict=valeurs["verdict"],
            resume_voix=resume,
            detail_voix=detail,
            resultat_complet=complet,
            conforme=conforme,
        )

    # Debris de JSON : un objet tronque ou illisible ne se parse pas, et ses
    # premieres phrases seraient des accolades et des guillemets lus a voix
    # haute. On prefere rendre un resume vide — l'appelant a une phrase de
    # secours — plutot que de prononcer de la ponctuation.
    depouille = texte.strip().lstrip("`").lstrip()
    if depouille[:1] in ("{", "["):
        return ReponseHarnais(
            verdict="",
            resume_voix="",
            detail_voix="",
            resultat_complet=texte,
            conforme=False,
        )

    resume = _nettoyer_voix(_premieres_phrases(texte, LIMITE_RESUME_VOIX))
    resume = _tronquer(resume, LIMITE_RESUME_VOIX)
    return ReponseHarnais(
        verdict="",
        resume_voix=resume,
        detail_voix="",
        resultat_complet=texte,
        conforme=False,
    )
