```python
# === FICHIER: src/brain/contrat_harnais.py ===
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

    texte = re.sub(r"```.*?```", " ", texte, flags=re.DOTALL)
    texte = re.sub(r"`[^`]*`", " ", texte)
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
            valeurs[k] = v if isinstance(v, str) else ("" if v is None else str(v))

        complet = valeurs["resultat_complet"] or texte

        resume = _nettoyer_voix(valeurs["resume_voix"])
        detail = _nettoyer_voix(valeurs["detail_voix"])

        pur = texte.strip() == json_brut.strip()
        conforme = types_ok and pur
        if conforme:
            conforme = (
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

    resume = _nettoyer_voix(_premieres_phrases(texte, LIMITE_RESUME_VOIX))
    resume = _tronquer(resume, LIMITE_RESUME_VOIX)
    return ReponseHarnais(
        verdict="",
        resume_voix=resume,
        detail_voix="",
        resultat_complet=texte,
        conforme=False,
    )
```

```python
# === FICHIER: dev/tests/test_contrat_harnais.py ===
from src.brain.contrat_harnais import (
    LIMITE_DETAIL_VOIX,
    LIMITE_RESUME_VOIX,
    PREFIXE_CONTRAT,
    analyser,
    envelopper,
)


def test_envelopper_ajoute_le_prefixe_et_la_question():
    question = "Quelle est la meteo aujourd hui ?"
    enveloppe = envelopper(question)
    assert PREFIXE_CONTRAT in enveloppe
    assert enveloppe.endswith(question)


def test_json_pur_est_parse_et_conforme():
    charge = (
        '{"verdict": "ok", "resume_voix": "Tout va bien.", '
        '"detail_voix": "Detail complet.", "resultat_complet": "analyse"}'
    )
    rep = analyser(charge)
    assert rep.conforme is True
    assert rep.verdict == "ok"
    assert rep.resume_voix == "Tout va bien."
    assert rep.resultat_complet == "analyse"


def test_json_entoure_de_cloture_markdown_est_extrait():
    charge = (
        '```json\n{"verdict": "ok", "resume_voix": "Ca marche.", '
        '"detail_voix": "D", "resultat_complet": "C"}\n```'
    )
    rep = analyser(charge)
    assert rep.resume_voix == "Ca marche."
    assert rep.conforme is False


def test_json_avec_bavardage_autour_est_extrait():
    charge = (
        'Voici le resultat : {"verdict": "ok", "resume_voix": "Analyse finie.", '
        '"detail_voix": "D", "resultat_complet": "C"} Voila.'
    )
    rep = analyser(charge)
    assert rep.resume_voix == "Analyse finie."
    assert rep.conforme is False


def test_json_avec_cles_manquantes_est_non_conforme():
    charge = '{"verdict": "ok", "resume_voix": "Texte court."}'
    rep = analyser(charge)
    assert rep.conforme is False
    assert rep.resultat_complet == charge
    assert rep.resume_voix == "Texte court."


def test_json_avec_mauvais_types_est_non_conforme():
    charge = (
        '{"verdict": 42, "resume_voix": ["a"], '
        '"detail_voix": null, "resultat_complet": true}'
    )
    rep = analyser(charge)
    assert rep.conforme is False
    assert rep.verdict == "42"


def test_texte_libre_degrade_gracieusement():
    texte = "Bonjour. Voici une analyse simple. Elle est terminee."
    rep = analyser(texte)
    assert rep.conforme is False
    assert rep.resultat_complet == texte
    assert rep.resume_voix.startswith("Bonjour.")
    assert len(rep.resume_voix) <= LIMITE_RESUME_VOIX


def test_texte_libre_trop_long_est_tronque_sans_mot_coupe():
    texte = "Phrase une. " * 50
    rep = analyser(texte)
    assert rep.conforme is False
    assert len(rep.resume_voix) <= LIMITE_RESUME_VOIX
    assert not rep.resume_voix.endswith(" ")


def test_chaine_vide_ou_none_ne_leve_pas():
    for entree in ("", "   ", None):
        rep = analyser(entree)
        assert rep.conforme is False
        assert rep.resume_voix == ""
        assert rep.resultat_complet == (entree or "")


def test_resume_voix_trop_long_est_tronque():
    charge = (
        '{"verdict": "v", "resume_voix": "' + "mot " * 100 +
        '", "detail_voix": "d", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert len(rep.resume_voix) <= LIMITE_RESUME_VOIX
    assert rep.conforme is False


def test_detail_voix_trop_long_est_tronque():
    charge = (
        '{"verdict": "v", "resume_voix": "court", "detail_voix": "' +
        "mot " * 200 + '", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert len(rep.detail_voix) <= LIMITE_DETAIL_VOIX
    assert rep.conforme is False


def test_chemin_windows_est_neutralise_dans_resume():
    charge = r'{"verdict": "v", "resume_voix": "Le fichier C:\\Users\\test\\doc.txt est pret.", "detail_voix": "d", "resultat_complet": "c"}'
    rep = analyser(charge)
    assert "C:" not in rep.resume_voix
    assert "fichier" in rep.resume_voix


def test_cloture_code_est_retiree_dans_resume():
    charge = (
        '{"verdict": "v", "resume_voix": "Voici ```python\\nprint(1)\\n``` '
        'le resultat.", "detail_voix": "d", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert "```" not in rep.resume_voix
    assert "print" not in rep.resume_voix


def test_liste_a_puces_est_neutralisee_dans_resume():
    charge = (
        '{"verdict": "v", "resume_voix": "- premier point\\n'
        '- deuxieme point", "detail_voix": "d", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert not rep.resume_voix.startswith("-")
    assert "premier point" in rep.resume_voix
    assert "deuxieme point" in rep.resume_voix
```