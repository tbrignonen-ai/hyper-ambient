"""Préchauffage vocal : payer le froid avant la première phrase, pas pendant.

Mesuré sur le serveur, première phrase contre les suivantes :

    étage       à froid    à chaud    surcoût
    MOUTH        703 ms     164 ms     +539 ms
    EARS         542 ms     193 ms     +349 ms
    BRAIN         20 ms      20 ms        0 ms

Le surcoût attribué à MOUTH n'est pas de la synthèse. Isolé dans le
conteneur : ``import librosa`` coûte 1 ms, mais le **premier**
``librosa.resample`` coûte 596 ms et le second 0 ms — le filtre de
rééchantillonnage se construit à la première conversion. MOUTH sort à
22 050 Hz, le canal host-agent tourne à 16 000 : chaque tour passe donc par
ce filtre. Chauffer la synthèse sans chauffer la conversion ne déplace rien,
ce qui a été vérifié : 45 ms de synthèse préchauffée, et 703 ms quand même
sur la première phrase.

BRAIN n'est pas sollicité. llama-server est un processus séparé, déjà
chargé, et une génération manuelle lancée avant la première passe n'a rien
changé à la mesure — l'hypothèse a été testée puis écartée.

Le signal est produit par numpy, jamais lu sur disque : un WAV absent ferait
échouer le démarrage sur une machine tierce.

Un étage qui lève est journalisé et ignoré. Le préchauffage est une
optimisation ; en propager l'exception transformerait un confort en panne de
démarrage.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from src.hostagent.audio import SAMPLE_RATE

_PHRASE_MOUTH = "Bonjour."

# Taux de sortie de Piper. Le rééchantillonnage n'est chauffé que si la source
# diffère de la cible : convertir 16 kHz vers 16 kHz est un court-circuit qui ne
# construit aucun filtre.
SAMPLE_RATE_MOUTH = 22050


@dataclass
class RapportPrechauffage:
    """Durées d'étage, horloge monotone, uniquement pour ce qui a réellement chauffé."""

    etages_chauffes: list[str] = field(default_factory=list)
    durees_ms: dict[str, float] = field(default_factory=dict)


def _signal_synthetique() -> np.ndarray:
    """Une seconde de sinus 440 Hz, float32, 16 kHz — assez pour les noyaux, zéro fichier."""
    t = np.linspace(0.0, 1.0, SAMPLE_RATE, endpoint=False, dtype=np.float32)
    return (np.float32(0.1) * np.sin(np.float32(2.0 * np.pi * 440.0) * t)).astype(
        np.float32
    )


def _consigner(journal, message: str) -> None:
    if journal is None:
        print(message, flush=True)
        return
    if hasattr(journal, "append"):
        journal.append(message)
        return
    print(message, flush=True)


async def prechauffer(
    *, ears, mouth, brain=None, rechantillonner=None, journal=None
) -> RapportPrechauffage:
    """Sollicite EARS, MOUTH, puis le rééchantillonnage. `brain` est accepté et ignoré."""
    rapport = RapportPrechauffage()

    try:
        debut = time.monotonic()
        await ears.transcribe(_signal_synthetique())
        rapport.durees_ms["ears"] = (time.monotonic() - debut) * 1000.0
        rapport.etages_chauffes.append("ears")
    except Exception as exc:
        _consigner(journal, f"EARS : préchauffage échoué — {exc}")

    try:
        debut = time.monotonic()
        await mouth.synthesize(_PHRASE_MOUTH)
        rapport.durees_ms["mouth"] = (time.monotonic() - debut) * 1000.0
        rapport.etages_chauffes.append("mouth")
    except Exception as exc:
        _consigner(journal, f"MOUTH : préchauffage échoué — {exc}")

    if rechantillonner is not None:
        try:
            debut = time.monotonic()
            rechantillonner(
                np.zeros(SAMPLE_RATE_MOUTH, dtype=np.float32), SAMPLE_RATE_MOUTH
            )
            rapport.durees_ms["resample"] = (time.monotonic() - debut) * 1000.0
            rapport.etages_chauffes.append("resample")
        except Exception as exc:
            _consigner(journal, f"RESAMPLE : préchauffage échoué — {exc}")

    return rapport
