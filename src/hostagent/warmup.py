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


def _vers_float32(pcm) -> np.ndarray:
    """Normalise le PCM int16 de MOUTH. Frontiere materielle, la conversion est ici légitime."""
    tableau = np.asarray(pcm)
    if tableau.dtype == np.int16:
        return (tableau.astype(np.float32) / 32768.0).astype(np.float32)
    return tableau.astype(np.float32)


def _signal_synthetique(taux: int = SAMPLE_RATE) -> np.ndarray:
    """Une seconde de sinus 440 Hz, float32 — repli sans parole, et zéro fichier."""
    t = np.linspace(0.0, 1.0, taux, endpoint=False, dtype=np.float32)
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

    # MOUTH d'abord : sa sortie est la matiere qui chauffera EARS.
    pcm_mouth = None
    sr_mouth = SAMPLE_RATE_MOUTH
    try:
        debut = time.monotonic()
        sortie = await mouth.synthesize(_PHRASE_MOUTH) or {}
        rapport.durees_ms["mouth"] = (time.monotonic() - debut) * 1000.0
        rapport.etages_chauffes.append("mouth")
        audio = np.asarray(sortie.get("audio", []))
        if audio.size:
            pcm_mouth = _vers_float32(audio)
            sr_mouth = int(sortie.get("sample_rate") or SAMPLE_RATE_MOUTH)
    except Exception as exc:
        _consigner(journal, f"MOUTH : préchauffage échoué — {exc}")

    # Rééchantillonnage : construit le filtre, et convertit au passage la
    # parole de MOUTH au taux du canal, celui qu'attend EARS.
    parole = None
    if rechantillonner is not None:
        source = pcm_mouth if pcm_mouth is not None else _signal_synthetique(SAMPLE_RATE_MOUTH)
        try:
            debut = time.monotonic()
            converti = rechantillonner(source, sr_mouth)
            rapport.durees_ms["resample"] = (time.monotonic() - debut) * 1000.0
            rapport.etages_chauffes.append("resample")
            if pcm_mouth is not None:
                parole = np.asarray(converti, dtype=np.float32)
        except Exception as exc:
            _consigner(journal, f"RESAMPLE : préchauffage échoué — {exc}")

    # EARS en dernier, sur de la parole reelle quand on en a. Le sinus de
    # repli chauffe l'encodeur ; seule la parole chauffe le decodeur.
    try:
        debut = time.monotonic()
        await ears.transcribe(parole if parole is not None else _signal_synthetique())
        rapport.durees_ms["ears"] = (time.monotonic() - debut) * 1000.0
        rapport.etages_chauffes.append("ears")
    except Exception as exc:
        _consigner(journal, f"EARS : préchauffage échoué — {exc}")

    return rapport
