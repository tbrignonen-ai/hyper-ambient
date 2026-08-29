"""Cloner le timbre de la reference fournie par l'utilisateur.

Les catalogues de voix preenregistrees ont ete epuises : aucune ne rejoint le
timbre demande, parce qu'un catalogue n'offre que ce qu'il contient. Viser un
timbre precis demande de partir d'un enregistrement, ce que Pocket sait faire —
`get_state_for_audio_prompt` accepte un chemin audio la ou il recoit d'habitude
un embedding de voix.

On produit le francais et l'anglais, les deux langues demandees pour cette voix.
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import torch

VOIX = Path("/workspace/data/voix")
REFERENCE = VOIX / "aurora voice.m4a"
PREPAREE = VOIX / "ref_aurora_24k.wav"

PHRASES = {
    "french_24l": "Bonjour, je suis là. Prends ton temps, je t'écoute.",
    "english": "Hello, I am here. Take your time, I am listening.",
}


def preparer_reference() -> Path:
    """Pocket attend du 24 kHz mono. ffmpeg s'en charge, et normalise au passage."""
    if not PREPAREE.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(REFERENCE), "-ac", "1", "-ar", "24000",
             "-af", "loudnorm", str(PREPAREE)],
            check=True, capture_output=True,
        )
    with wave.open(str(PREPAREE), "rb") as w:
        secondes = w.getnframes() / w.getframerate()
    print(f"reference preparee : {secondes:.1f}s de 24 kHz mono", flush=True)
    return PREPAREE


def fondamentale(x: np.ndarray, taux: int) -> float:
    x = x.astype(np.float32) - float(np.mean(x))
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    lo, hi = int(taux / 400), int(taux / 70)
    return float(taux / (lo + int(np.argmax(ac[lo:hi]))))


def ecrire(chemin: Path, x: np.ndarray, taux: int) -> None:
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(np.clip(x * 32768.0, -32768, 32767).astype("<i2").tobytes())


def main(langues: list[str]) -> None:
    from pocket_tts import TTSModel

    reference = preparer_reference()
    with wave.open(str(reference), "rb") as w:
        brut = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    print(f"f0 de la reference : {fondamentale(brut / 32768.0, 24000):.1f} Hz", flush=True)

    for langue in langues:
        try:
            modele = TTSModel.load_model(language=langue, temp=0.6)
            modele = modele.to("cuda")
            etat = modele.get_state_for_audio_prompt(str(reference), truncate=True)
            audio = modele.generate_audio(etat, PHRASES[langue])
        except Exception as erreur:
            print(f"{langue:12} echec : {type(erreur).__name__}: {erreur}", flush=True)
            continue

        x = audio.detach().cpu().float().numpy().ravel()
        sortie = VOIX / f"clone_aurora_{langue.split('_')[0]}.wav"
        ecrire(sortie, x, modele.sample_rate)
        print(
            f"{langue:12} f0 {fondamentale(x, modele.sample_rate):6.1f} Hz  "
            f"{len(x) / modele.sample_rate:4.1f}s  -> {sortie.name}",
            flush=True,
        )


if __name__ == "__main__":
    main(sys.argv[1:] or list(PHRASES))
