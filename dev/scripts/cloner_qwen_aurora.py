"""Cloner Aurora avec Qwen3-TTS 0.6B-Base, CPU, une phrase.

x_vector_only_mode: la reference YouTube n'a pas de transcript fiable
(musique + credits), donc on ne conditionne que sur l'embedding locuteur.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

PHRASE = "Bonjour, je suis là. Prends ton temps, je t'écoute."
REF = "/workspace/data/voix/aurora_prompt_6s.wav"
REF_TEXT = (
    "The Galactic Federation has issued what they're calling their most "
    "critical human infrastructure alert of this decade."
)
OUT = Path("/workspace/data/voix/qwen3tts_aurora_fr.wav")


def main() -> None:
    from qwen_tts import Qwen3TTSModel

    print("chargement Qwen3-TTS-12Hz-0.6B-Base CUDA bf16…")
    t0 = time.perf_counter()
    modele = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )
    print(f"charge en {time.perf_counter()-t0:.1f}s")

    t1 = time.perf_counter()
    wavs, sr = modele.generate_voice_clone(
        text=PHRASE,
        language="French",
        ref_audio=REF,
        x_vector_only_mode=True,
    )
    dt = time.perf_counter() - t1
    y = np.asarray(wavs[0])
    sf.write(OUT, y, sr)
    print(f"synth {dt:.1f}s  dur={len(y)/sr:.2f}s  sr={sr} -> {OUT}")


if __name__ == "__main__":
    main()
