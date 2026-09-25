"""Mains libres : la première phrase après activation n'est plus ignorée (25/09).

Séance du 25/09 : mains libres activé, « Ok, donc s'il te plaît, dis à Codex
bonjour » → JeV « pas adressée » → rien. Puis « Hyper ambiante » seul partait
au distant (4 s) pour une réponse générique.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def _serve():
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    spec = importlib.util.spec_from_file_location(
        "serve_hostagent_ml_entree", RACINE / "dev" / "scripts" / "serve_hostagent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_activer_mains_libres_ouvre_la_conversation():
    pipeline = _serve().HostPipeline()
    pipeline._demarrer_maintien_jev = lambda: None
    pipeline._demarrer_indicateur_conversation = lambda: None
    pipeline.on_options({"mains_libres": True})
    assert pipeline._fenetre.engagee()


def test_le_rappel_periodique_de_l_option_ne_rouvre_pas_la_fenetre():
    """Presence renvoie mains_libres=on à chaque tour : seule la bascule compte."""
    pipeline = _serve().HostPipeline()
    pipeline._demarrer_maintien_jev = lambda: None
    pipeline._demarrer_indicateur_conversation = lambda: None
    pipeline.on_options({"mains_libres": True})
    pipeline._fenetre.fermer()
    pipeline.on_options({"mains_libres": True})
    assert not pipeline._fenetre.engagee()


def test_seulement_le_nom():
    from src.ears.jev_reflexe import seulement_le_nom

    assert seulement_le_nom("Hyper ambiante Hyper ambiante")
    assert seulement_le_nom("Hé, hyper ambient ?")
    assert seulement_le_nom("Oui, hyper-ambiant.")
    assert not seulement_le_nom("Hyper ambient, quelle heure est-il ?")
    assert not seulement_le_nom("dis à Codex bonjour")


def test_nommer_un_harnais_vaut_adresse():
    source = (RACINE / "dev" / "scripts" / "serve_hostagent.py").read_text(encoding="utf-8")
    assert "nom_du_produit_prononce(prompt) or nomme_un_harnais(prompt)" in source
