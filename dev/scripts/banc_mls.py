"""Second tour du corpus MLS : la fondamentale a suffi a designer 56 voix
feminines graves, mais MLS est un corpus de livres audio et la qualite y varie
d'un lecteur a l'autre — la voix 1840 s'est fait transcrire avec 83 % d'erreur.
On ne garde donc que celles qui restent intelligibles, mesure a l'appui.
"""
from __future__ import annotations

import asyncio

import numpy as np

from dev.scripts.banc_piper import PHRASE, SORTIE, ecrire, fondamentale, taux_erreur_mot, vers_16k

MODELE = "/workspace/models/piper/fr_FR-mls-medium.onnx"
CANDIDATES = [
    ("7239", 38), ("10957", 97), ("5295", 100), ("1989", 58), ("4396", 90),
    ("8778", 7), ("9804", 104), ("2033", 66), ("1844", 89), ("2596", 117),
    ("5968", 101), ("2607", 110), ("3204", 70), ("123", 2), ("3595", 118),
    ("13658", 56),
]


async def main() -> None:
    from src.ears.faster_whisper_asr import FasterWhisperASR
    from src.mouth.piper_tts import PiperTTS

    ears = FasterWhisperASR(model_size="large-v3-turbo", language="fr", device="cuda")
    await ears.load_model()

    print(f"{'voix':12} {'f0':>8} {'TTFA':>8} {'WER':>7}  transcription")
    print("-" * 100)
    for nom, ident in CANDIDATES:
        tts = PiperTTS(model_path=MODELE, speaker_id=ident, profile="flat")
        if not await tts.load_model():
            continue
        out = await tts.synthesize(PHRASE)
        pcm = np.asarray(out["audio"]).ravel()
        taux = int(out["sample_rate"])
        flottant = pcm.astype(np.float32) / 32768.0
        texte = ((await ears.transcribe(vers_16k(flottant, taux))).get("text") or "").strip()
        wer = taux_erreur_mot(PHRASE, texte)
        if wer <= 0.10:
            ecrire(SORTIE / f"piper_mls-{nom}_fr.wav", pcm, taux)
        print(
            f"{nom:12} {fondamentale(flottant, taux):6.1f}Hz {out.get('ttfa_ms', 0):7.0f}ms "
            f"{wer:6.1%}  {texte[:52]}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
