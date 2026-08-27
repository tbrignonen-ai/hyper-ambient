"""
Deux tours de parole ne doivent jamais se chevaucher.

Le haut-parleur ne peut dire qu'une phrase à la fois. Si deux `_tour`
s'exécutaient ensemble, les synthèses s'entrelaceraient : on entendrait
la fin de l'un dans le début de l'autre, et la démo passerait pour une
panne de MOUTH. `HostPipeline` prend déjà un `asyncio.Lock` autour de
chaque tour. Personne ne l'avait vérifié : ce fichier le prouve, sans
charger EARS, BRAIN ni MOUTH — le traitement est un double qui dort.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

_CHEMIN = Path(__file__).resolve().parents[1] / "scripts" / "serve_hostagent.py"


def _charger_host_pipeline():
    """Le harnais n'est pas un paquet : on le charge depuis son fichier."""
    spec = importlib.util.spec_from_file_location("serve_hostagent", _CHEMIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HostPipeline


HostPipeline = _charger_host_pipeline()


class _PipelineSonde(HostPipeline):
    """Même verrou que le produit ; le traitement est un sommeil daté."""

    def __init__(self) -> None:
        super().__init__()
        self.journal: list[str] = []

    async def _enchainer(self, frames, websocket) -> None:
        self.journal.append(f"debut:{frames}")
        await asyncio.sleep(0.05)
        self.journal.append(f"fin:{frames}")


@pytest.mark.asyncio
async def test_le_second_tour_ne_commence_pas_avant_la_fin_du_premier():
    """Le second ne COMMENCE pas avant que le premier ait FINI.

    Sans le verrou, le sommeil laisserait les deux débuts s'écrire
    avant les deux fins. Avec le verrou, A se termine entièrement
    avant que B n'existe dans le journal.
    """
    pipeline = _PipelineSonde()
    await asyncio.gather(
        pipeline._tour("A", None),
        pipeline._tour("B", None),
    )
    assert pipeline.journal == [
        "debut:A",
        "fin:A",
        "debut:B",
        "fin:B",
    ]
