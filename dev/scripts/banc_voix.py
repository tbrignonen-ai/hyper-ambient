"""Banc d'essai des voix : intelligibilite mesuree, pas jugee a l'oreille.

On ne peut pas entendre un accent depuis un script. On peut en revanche
mesurer ses consequences : une voix qui ecorche le francais se fait mal
transcrire. Chaque echantillon est donc repasse dans EARS, et on compare le
texte reconnu au texte d'origine.

Trois indicateurs par voix :
  - taux d'erreur mot, contre le texte demande ;
  - probabilite de langue rendue par Whisper, qui chute quand la prononciation
    derive vers une autre langue ;
  - fondamentale et TTFA, pour verifier qu'on ne troque pas le timbre demande
    (grave, pose) contre l'intelligibilite.
"""
from __future__ import annotations

import asyncio
import re
import sys
import unicodedata
import wave
from pathlib import Path

import numpy as np

SORTIE = Path("/workspace/data/voix")
PHRASE = (
    "Bonjour, je suis là. Prends ton temps, je t'écoute. "
    "Le facteur temps réel doit rester inférieur à un."
)


def normaliser(texte: str) -> list[str]:
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", texte.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.findall(r"[a-z0-9']+", sans_accent)


def taux_erreur_mot(attendu: str, obtenu: str) -> float:
    a, b = normaliser(attendu), normaliser(obtenu)
    if not a:
        return 1.0
    # Levenshtein sur les mots.
    d = list(range(len(b) + 1))
    for i, mot_a in enumerate(a, 1):
        prec, d[0] = d[0], i
        for j, mot_b in enumerate(b, 1):
            prec, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prec + (mot_a != mot_b))
    return d[len(b)] / len(a)


def fondamentale(x: np.ndarray, taux: int) -> float:
    x = x.astype(np.float32)
    x = x - x.mean()
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    lo, hi = int(taux / 400), int(taux / 70)
    return float(taux / (lo + int(np.argmax(ac[lo:hi]))))


def ecrire(chemin: Path, pcm: np.ndarray, taux: int) -> None:
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(pcm.astype("<i2").tobytes())


def vers_16k(x: np.ndarray, taux: int) -> np.ndarray:
    if taux == 16000:
        return x.astype(np.float32)
    n = int(len(x) * 16000 / taux)
    return np.interp(
        np.linspace(0, len(x) - 1, n), np.arange(len(x)), x.astype(np.float32)
    ).astype(np.float32)


async def main(voix_pocket: list[str]) -> None:
    from src.ears.faster_whisper_asr import FasterWhisperASR
    from src.mouth.pocket_tts import PocketTTS

    SORTIE.mkdir(parents=True, exist_ok=True)
    ears = FasterWhisperASR(model_size="large-v3-turbo", language="fr", device="cuda")
    await ears.load_model()

    print(f"{'voix':14} {'f0':>7} {'TTFA':>8} {'WER':>7}  transcription")
    print("-" * 100)
    for nom in voix_pocket:
        tts = PocketTTS(language="french_24l", voice=nom, device="cuda")
        if not await tts.load_model():
            print(f"{nom:14} indisponible")
            continue
        out = await tts.synthesize(PHRASE)
        pcm = np.asarray(out["audio"]).ravel()
        taux = int(out["sample_rate"])
        ecrire(SORTIE / f"pocket_{nom}_fr.wav", pcm, taux)

        flottant = pcm.astype(np.float32) / 32768.0
        reconnu = await ears.transcribe(vers_16k(flottant, taux))
        texte = (reconnu.get("text") or "").strip()
        print(
            f"{nom:14} {fondamentale(flottant, taux):6.1f}Hz "
            f"{out.get('ttfa_ms', 0):7.0f}ms {taux_erreur_mot(PHRASE, texte):6.1%}  {texte[:60]}"
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["eponine"]))
