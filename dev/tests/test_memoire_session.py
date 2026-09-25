"""La conversation n'est plus effacée au silence (25/09).

Une séance de plusieurs heures perdait tout après 60 s de silence (mode
bouton), à la fermeture de la fenêtre d'écoute ou en coupant les mains
libres : le pont ne reconnaissait plus la conversation et repartait à zéro.
La mémoire vit désormais aussi longtemps que le host-agent.
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
        "serve_hostagent_memoire", RACINE / "dev" / "scripts" / "serve_hostagent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fermer_la_fenetre_ne_purge_plus_la_memoire():
    pipeline = _serve().HostPipeline()
    echanges = [
        {"role": "user", "content": "je m'appelle Thomas"},
        {"role": "assistant", "content": "Enchantée, Thomas."},
    ]
    pipeline._historique = list(echanges)
    pipeline._memoire.retenir("je m'appelle Thomas", "Enchantée, Thomas.", timestamp=0.0)
    pipeline._fermer_conversation()
    assert pipeline._historique == echanges
    assert pipeline._memoire.messages() == echanges
