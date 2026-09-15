"""L'amorce ne doit plus revenir dans la reponse finale.

FEEDBACK du 31/08 § 3 : sur les cinq escalades, le rapport lu en seance
affichait « Un instant. Je suis juste la, je ne vois rien » — l'amorce
prononcee hors flux recollee a la reponse du modele. La faute est une ligne
de comptabilite dans `_enchainer`, pas le chemin audio.

Ces tests portent sur `composer_rapport`, fonction pure, donc executables
sur l'hote sans fastapi ni pytest-asyncio. `serve_hostagent` importe
`src.hostagent.transport` (donc fastapi) en tete de module : on pose des
stubs avant de le charger par chemin, plutot que d'installer quoi que ce
soit sur l'hote.
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

RACINE = Path(__file__).resolve().parents[2]


def _charger_serve_hostagent():
    """Charge le script sans exiger fastapi/uvicorn sur l'hote."""
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    # Les doublures ne se posent que si le vrai paquet manque — c'est-a-dire
    # sur l'hote. Les poser inconditionnellement empoisonnait `sys.modules`
    # pour TOUT le reste de la session pytest : dans le conteneur, ou fastapi
    # existe, `test_hostagent_rapport` et `test_hostagent_transport`
    # recevaient ensuite un MagicMock a la place de FastAPI et tombaient en
    # cascade. Mesure : ces cinq tests passent seuls, echouent des que ce
    # fichier est charge avant eux.
    try:  # pragma: no cover - depend de l'environnement, pas du code teste
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        for nom in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
            sys.modules.setdefault(nom, MagicMock(name=nom))
    chemin = RACINE / "dev" / "scripts" / "serve_hostagent.py"
    spec = importlib.util.spec_from_file_location("serve_hostagent_sous_test", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_hostagent = _charger_serve_hostagent()


CAS = [
    (["Un instant."], ["Je suis là", ", rien"], "Je suis là, rien", "Un instant."),
    ([], ["Bleu, blanc, rouge"], "Bleu, blanc, rouge", ""),
    (
        ["Un instant.", "Je traite toujours la demande."],
        [],
        "",
        "Un instant. Je traite toujours la demande.",
    ),
    ([], [], "", ""),
    (["  Un instant.  "], ["  x  "], "x", "Un instant."),
]


@pytest.mark.parametrize("amorces,reponse,attendu_text,attendu_amorces", CAS)
def test_composer_rapport_separe_amorce_et_reponse(
    amorces, reponse, attendu_text, attendu_amorces
):
    text, texte_amorces = serve_hostagent.composer_rapport(amorces, reponse)
    assert text == attendu_text
    assert texte_amorces == attendu_amorces


def test_amorces_jamais_none():
    """Le champ `amorces` du rapport est toujours une chaine, jamais None."""
    _, texte_amorces = serve_hostagent.composer_rapport([], [])
    assert isinstance(texte_amorces, str)


def test_reponse_ne_commence_jamais_par_une_amorce():
    """L'invariant du bug : aucune valeur de FILLERS/HOLDING en prefixe."""
    from src.brain.router import FILLERS, HOLDING

    for amorce in FILLERS + HOLDING:
        text, texte_amorces = serve_hostagent.composer_rapport(
            [amorce], ["Bleu, blanc, rouge"]
        )
        assert not text.startswith(amorce), f"amorce recollee : {text!r}"
        assert text == "Bleu, blanc, rouge"
        assert texte_amorces == amorce


def test_holding_par_defaut_a_six_secondes(monkeypatch):
    """§ 3 : un tour de 4-5 s ne doit plus recevoir une seconde ligne.

    `RouterBrain` ne joint ni reseau ni modele a la construction : les deux
    canaux sont des collaborateurs passes en argument.
    """
    from src.brain.router import RouterBrain

    monkeypatch.delenv("BRAIN_HOLDING_AFTER_MS", raising=False)
    assert RouterBrain(reflex=None, deep=None).holding_after_ms == 6000

    monkeypatch.setenv("BRAIN_HOLDING_AFTER_MS", "3000")
    assert RouterBrain(reflex=None, deep=None).holding_after_ms == 3000
