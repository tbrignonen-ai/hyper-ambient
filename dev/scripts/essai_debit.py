"""Genere la meme phrase a plusieurs transpositions, pour choisir a l'oreille.

pocket-tts n'a ni vitesse ni hauteur ; descendre par reechantillonnage regle
les deux ensemble. Ce banc ecrit un WAV par valeur de demi-tons afin que le
reglage soit choisi en ecoutant, pas en raisonnant.

    python dev/scripts/essai_debit.py [phrase]
"""
import asyncio
import sys
import wave
from pathlib import Path

from src.mouth.pocket_tts import PocketTTS

PHRASE = "Bonjour Thomas. Je suis prête. Dis-moi ce que tu veux que je fasse."
SORTIE = Path("dev/out/debit")
VALEURS = (0.0, -1.5, -3.0, -4.5, -6.0)


async def main() -> None:
    phrase = " ".join(sys.argv[1:]) or PHRASE
    SORTIE.mkdir(parents=True, exist_ok=True)

    # Un seul chargement du modele : la transposition est un post-traitement,
    # elle n'a aucune raison de repayer 1,5 Go de VRAM par variante.
    tts = PocketTTS(voice="estelle", profile="mother")
    if not await tts.load_model():
        raise SystemExit("pocket-tts indisponible")

    for demi_tons in VALEURS:
        tts.demi_tons = demi_tons
        res = await tts.synthesize(phrase)
        nom = SORTIE / f"demi_tons_{demi_tons:+.1f}.wav".replace("+", "p").replace("-", "m")
        with wave.open(str(nom), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(res["sample_rate"])
            w.writeframes(res["audio"].tobytes())
        print(f"{demi_tons:+5.1f} demi-tons  {res['duration_s']:5.2f}s  {nom}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
