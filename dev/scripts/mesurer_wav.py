"""Passe des WAV deja produits au meme banc que les voix synthetisees ici.

Des echantillons Supertonic dormaient dans data/voix depuis une nuit precedente
sans avoir jamais ete mesures. Plutot que de les regenerer, on leur applique le
filtre qui a servi a eliminer le corpus MLS : fondamentale, et taux d'erreur mot
contre EARS.
"""
from __future__ import annotations

import asyncio
import sys
import wave
from pathlib import Path

import numpy as np

from dev.scripts.banc_piper import PHRASE, fondamentale, taux_erreur_mot, vers_16k


def lire(chemin: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(chemin), "rb") as w:
        brut = w.readframes(w.getnframes())
        canaux, taux = w.getnchannels(), w.getframerate()
    pcm = np.frombuffer(brut, dtype="<i2").astype(np.float32) / 32768.0
    if canaux > 1:
        pcm = pcm.reshape(-1, canaux).mean(axis=1)
    return pcm, taux


async def main(motif: str) -> None:
    from src.ears.faster_whisper_asr import FasterWhisperASR

    ears = FasterWhisperASR(model_size="large-v3-turbo", language="fr", device="cuda")
    await ears.load_model()

    print(f"{'fichier':30} {'f0':>8} {'duree':>8} {'WER':>7}  transcription")
    print("-" * 104)
    for chemin in sorted(Path("/workspace/data/voix").glob(motif)):
        pcm, taux = lire(chemin)
        texte = ((await ears.transcribe(vers_16k(pcm, taux))).get("text") or "").strip()
        print(
            f"{chemin.name:30} {fondamentale(pcm, taux):6.1f}Hz "
            f"{len(pcm) / taux:7.2f}s {taux_erreur_mot(PHRASE, texte):6.1%}  {texte[:44]}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "supertonic_*_fr.wav"))
