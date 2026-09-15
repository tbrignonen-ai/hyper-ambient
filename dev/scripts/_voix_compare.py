"""Wav courts, meme phrase FR, pour trancher a l'oreille.

Tourne sur CPU. Sortie : /workspace/data/out/voix-compare/

    python /workspace/dev/scripts/_voix_compare.py           # Piper
    python /workspace/dev/scripts/_voix_compare.py --pocket  # Pocket estelle+aurora
"""
from __future__ import annotations

import asyncio
import sys
import wave
from pathlib import Path

import numpy as np

SORTIE = Path("/workspace/data/out/voix-compare")
PHRASE = "Bonsoir Thomas. Je suis là. Dis-moi si cette voix te convient."
CASES = [
    ("upmc-mother.wav", "/workspace/models/piper/fr_FR-upmc-medium.onnx", "mother"),
    ("siwis-aurora.wav", "/workspace/models/piper/fr_FR-siwis-medium.onnx", "aurora"),
    ("tom-mother.wav", "/workspace/models/piper/fr_FR-tom-medium.onnx", "mother"),
    ("tom-aurora.wav", "/workspace/models/piper/fr_FR-tom-medium.onnx", "aurora"),
]
POCKET_CASES = [
    ("pocket-estelle.wav", "estelle", "aurora"),
]


def _ecrire(nom: str, out: dict) -> None:
    pcm = np.asarray(out["audio"], dtype=np.int16)
    taux = int(out["sample_rate"])
    chemin = SORTIE / nom
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(pcm.tobytes())
    print(
        f"{nom} duration={out['duration_s']:.2f}s ttfa={out['ttfa_ms']:.0f}ms "
        f"rtf={out['rtf']:.3f} sr={taux} bytes={chemin.stat().st_size}",
        flush=True,
    )


async def piper() -> None:
    from src.mouth.piper_tts import PiperTTS

    SORTIE.mkdir(parents=True, exist_ok=True)
    for nom, modele, profil in CASES:
        tts = PiperTTS(model_path=modele, profile=profil)
        if not await tts.load_model():
            print(f"FAIL load {nom}", flush=True)
            raise SystemExit(1)
        _ecrire(nom, await tts.synthesize(PHRASE))


async def pocket() -> None:
    from src.mouth.pocket_tts import PocketTTS

    SORTIE.mkdir(parents=True, exist_ok=True)
    for nom, voix, profil in POCKET_CASES:
        tts = PocketTTS(
            language="french_24l", voice=voix, device="cpu", profile=profil
        )
        if not await tts.load_model():
            print(f"FAIL load {nom}", flush=True)
            raise SystemExit(1)
        _ecrire(nom, await tts.synthesize(PHRASE))


if __name__ == "__main__":
    if "--pocket" in sys.argv:
        asyncio.run(pocket())
    else:
        asyncio.run(piper())
