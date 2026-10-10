"""La documentation et les défauts disent la carte figée, pas l'ancienne pile.

Source de vérité : dev/scripts/carte_figee.env. Chaque document qui présente
les modèles actuels le fait dans un bloc délimité par
``<!-- carte-figee:debut -->`` / ``<!-- carte-figee:fin -->`` : ce bloc doit
citer chaque valeur de la carte et aucun modèle remplacé. Hors du bloc,
l'historique (LFM2.5, Pocket, StepFun…) reste libre.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
CARTE = RACINE / "dev" / "scripts" / "carte_figee.env"
DEBUT = "<!-- carte-figee:debut -->"
FIN = "<!-- carte-figee:fin -->"

# Modèles remplacés : ils peuvent être cités comme historique ou repli, jamais
# dans le bloc qui décrit la carte actuelle.
REMPLACES = (
    "LFM2.5-2.6B", "Luth", "Ministral", "Luciole", "MiniCPM",
    "Pocket", "estelle", "Piper", "large-v3-turbo", "StepFun", "step-3.7",
    "qwen3", "Qwen3-ASR", "Supertonic",
)

DOCUMENTS = ("STACK.md", "README.md", "README.en.md")


def _lire_env(chemin: Path) -> dict[str, str]:
    paires: dict[str, str] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, val = ligne.partition("=")
        paires[cle.strip()] = val.strip()
    return paires


def _bloc(nom: str) -> str:
    texte = (RACINE / nom).read_text(encoding="utf-8")
    assert texte.count(DEBUT) == 1 and texte.count(FIN) == 1, f"{nom} : bloc carte-figee absent ou double"
    return texte.split(DEBUT, 1)[1].split(FIN, 1)[0]


def _valeur_affichable(cle: str, val: str) -> str:
    # Le chemin du GGUF est propre au conteneur : le document cite le fichier.
    return Path(val).name if cle == "MODEL" else val


CARTE_VALEURS = _lire_env(CARTE)


def test_la_carte_contient_les_quatre_roles():
    for cle in ("BRAIN_SERVICE", "BRAIN_MODEL", "MODEL", "EARS_MODEL", "MOUTH_BACKEND", "MOUTH_VOICE_NAME"):
        assert CARTE_VALEURS.get(cle), cle


@pytest.mark.parametrize("nom", DOCUMENTS)
def test_le_bloc_cite_chaque_valeur_de_la_carte(nom):
    bloc = _bloc(nom)
    assert "dev/scripts/carte_figee.env" in bloc
    manquantes = [
        f"{cle}={val}" for cle, val in CARTE_VALEURS.items()
        if _valeur_affichable(cle, val) not in bloc
    ]
    assert not manquantes, f"{nom} : valeurs de la carte absentes du bloc : {manquantes}"


@pytest.mark.parametrize("nom", DOCUMENTS)
def test_le_bloc_ne_presente_aucun_modele_remplace(nom):
    bloc = _bloc(nom).lower()
    presents = [m for m in REMPLACES if re.search(rf"(?<![\w.-]){re.escape(m.lower())}(?![\w-])", bloc)]
    # « large-v3 » est la carte ; « large-v3-turbo » ne l'est plus.
    assert not presents, f"{nom} : modèles remplacés présentés comme actuels : {presents}"


def test_env_example_suit_la_carte():
    exemple = _lire_env(RACINE / ".env.example")
    ecarts = {
        cle: (exemple.get(cle), val) for cle, val in CARTE_VALEURS.items()
        if exemple.get(cle) != val
    }
    assert not ecarts, f".env.example diverge de la carte (exemple, carte) : {ecarts}"


def test_le_fournisseur_par_defaut_du_cerveau_est_celui_de_la_carte():
    from src.brain import factory

    assert factory.SERVICE_PAR_DEFAUT == CARTE_VALEURS["BRAIN_SERVICE"]


def test_sans_brain_service_le_cerveau_passe_par_le_routeur(monkeypatch):
    import asyncio

    from src.brain import factory

    monkeypatch.delenv("BRAIN_SERVICE", raising=False)
    appele = []

    async def faux_routeur():
        appele.append(True)
        return "routeur"

    monkeypatch.setattr(factory, "build_router", faux_routeur)
    assert asyncio.run(factory.build_brain_with_fallback()) == "routeur"
    assert appele == [True]


def test_build_brain_router_rend_le_distant_compatible(monkeypatch):
    from src.brain import factory
    from src.brain.openai_compat import OpenAICompatBrain
    from src.brain.stepfun import StepFunBrain

    monkeypatch.delenv("BRAIN_SERVICE", raising=False)
    brain = factory.build_brain()
    assert isinstance(brain, OpenAICompatBrain)
    assert not isinstance(brain, StepFunBrain)


def test_le_profil_mac_est_presente_comme_profil_mac():
    """Le profil MLX n'est pas une contradiction : STACK.md le nomme comme tel."""
    mac = _lire_env(RACINE / "packaging" / "macos" / "mac-16g.env.example")
    stack = (RACINE / "STACK.md").read_text(encoding="utf-8")
    assert "packaging/macos/mac-16g.env.example" in stack
    assert mac["BRAIN_MODEL_LOCAL"] in stack
    assert mac["MOTHER_PROFILE"] in stack
