"""Balayage des 125 locuteurs francais du corpus MLS servi par Piper.

Le cahier des charges demande une voix feminine, grave et posee. MLS est un
corpus de livres audio francais : chaque locuteur est un lecteur natif, donc
l'accent n'est pas en jeu ; ce qui varie est le timbre. On synthetise une
phrase courte par locuteur et on ne garde que ceux dont la fondamentale tombe
dans la fenetre voulue, entre voix de femme grave et voix de contralto.
"""
from __future__ import annotations

import asyncio
import json
import sys

import numpy as np

MODELE = "/workspace/models/piper/fr_FR-mls-medium.onnx"
PHRASE = "Bonjour, je suis là. Prends ton temps, je t'écoute."
FENETRE = (130.0, 200.0)


def fondamentale(x: np.ndarray, taux: int) -> float:
    x = x.astype(np.float32)
    x -= x.mean()
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    lo, hi = int(taux / 400), int(taux / 70)
    return float(taux / (lo + int(np.argmax(ac[lo:hi]))))


async def main() -> None:
    from src.mouth.piper_tts import PiperTTS

    with open(MODELE + ".json", encoding="utf-8") as f:
        locuteurs = json.load(f)["speaker_id_map"]

    retenus = []
    for nom, ident in locuteurs.items():
        tts = PiperTTS(model_path=MODELE, speaker_id=int(ident), profile="flat")
        if not await tts.load_model():
            continue
        out = await tts.synthesize(PHRASE)
        pcm = np.asarray(out["audio"]).ravel().astype(np.float32) / 32768.0
        if len(pcm) < 1000:
            continue
        f0 = fondamentale(pcm, int(out["sample_rate"]))
        if FENETRE[0] <= f0 <= FENETRE[1]:
            retenus.append((f0, nom, int(ident)))
            print(f"  retenu {nom:>7} (id {ident:>3})  f0 {f0:6.1f} Hz", flush=True)

    retenus.sort()
    print("\n== fenetre feminine grave, du plus grave au plus aigu ==")
    for f0, nom, ident in retenus:
        print(f"{nom:>7}  id={ident:<4} {f0:6.1f} Hz")
    print(json.dumps([{"nom": n, "id": i, "f0": round(f, 1)} for f, n, i in retenus]),
          file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
