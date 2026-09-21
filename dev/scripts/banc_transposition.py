"""Combien descendre siwis sans la casser.

siwis est nativement francaise et mesure 235 Hz. La voix que l'utilisateur avait
aimee, eponine, en mesurait 153. On cherche donc l'intervalle qui rapproche siwis
de cette cible sans degrader l'intelligibilite, mesuree contre EARS.
"""
from __future__ import annotations

import asyncio

import numpy as np

from dev.scripts.banc_piper import PHRASE, SORTIE, ecrire, fondamentale, taux_erreur_mot, vers_16k

MODELE = "/workspace/models/piper/fr_FR-siwis-medium.onnx"
INTERVALLES = [0.0, -2.0, -3.0, -4.0, -5.0, -6.0]


async def main() -> None:
    from src.ears.faster_whisper_asr import FasterWhisperASR
    from src.mouth.piper_tts import PiperTTS

    ears = FasterWhisperASR(model_size="large-v3-turbo", language="fr", device="cuda")
    await ears.load_model()

    print(f"{'intervalle':>10} {'f0':>8} {'TTFA':>8} {'duree':>8} {'WER':>7}  transcription")
    print("-" * 100)
    for demi_tons in INTERVALLES:
        tts = PiperTTS(model_path=MODELE, profile="ambiante", demi_tons=demi_tons)
        if not await tts.load_model():
            continue
        out = await tts.synthesize(PHRASE)
        pcm = np.asarray(out["audio"]).ravel()
        taux = int(out["sample_rate"])
        ecrire(SORTIE / f"piper_siwis{demi_tons:+.0f}dt_fr.wav", pcm, taux)

        flottant = pcm.astype(np.float32) / 32768.0
        texte = ((await ears.transcribe(vers_16k(flottant, taux))).get("text") or "").strip()
        print(
            f"{demi_tons:+9.0f}  {fondamentale(flottant, taux):6.1f}Hz "
            f"{out.get('ttfa_ms', 0):7.0f}ms {out.get('duration_s', 0):7.2f}s "
            f"{taux_erreur_mot(PHRASE, texte):6.1%}  {texte[:48]}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
