"""Quelle voix du catalogue Pocket ressemble le plus a la reference fournie.

Le clonage est bloque par une porte d'acces chez Kyutai, mais la question de fond
reste : trouver le timbre le plus proche d'un enregistrement donne. On peut y
repondre sans clonage, en comparant chaque voix du catalogue a la reference.

Le timbre tient surtout a l'enveloppe spectrale a long terme — la maniere dont
l'energie se repartit sur les frequences, une fois la melodie moyennee. On compare
donc les spectres moyens en echelle mel, par distance cosinus, apres avoir aligne
les niveaux. La hauteur est rapportee a cote mais ne rentre pas dans le score :
deux voix peuvent partager une fondamentale sans se ressembler du tout.
"""
from __future__ import annotations

import asyncio
import wave
from pathlib import Path

import numpy as np

VOIX = Path("/workspace/data/voix")
REFERENCE = VOIX / "ref_aurora_24k.wav"
PHRASE = "Bonjour, je suis là. Prends ton temps, je t'écoute."
CATALOGUE = [
    "cosette", "alba", "anna", "vera", "fantine", "eponine", "azelma",
    "mary", "jane", "eve", "caro_davy", "lola", "estelle",
]


def spectre_moyen(x: np.ndarray, taux: int, bandes: int = 40) -> np.ndarray:
    """Enveloppe spectrale a long terme, en bandes mel, normalisee."""
    n = 1024
    saut = 256
    fenetre = np.hanning(n)
    trames = [
        np.abs(np.fft.rfft(x[i : i + n] * fenetre))
        for i in range(0, len(x) - n, saut)
        if np.sqrt(np.mean(x[i : i + n] ** 2)) > 1e-3  # ignorer les silences
    ]
    if not trames:
        return np.zeros(bandes)
    moyen = np.mean(trames, axis=0)

    mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)
    frequences = np.fft.rfftfreq(n, 1.0 / taux)
    bornes = np.linspace(mel(50), mel(min(8000, taux / 2)), bandes + 1)
    hertz = 700.0 * (10.0 ** (bornes / 2595.0) - 1.0)

    sortie = np.array([
        moyen[(frequences >= hertz[i]) & (frequences < hertz[i + 1])].mean()
        if np.any((frequences >= hertz[i]) & (frequences < hertz[i + 1])) else 0.0
        for i in range(bandes)
    ])
    sortie = np.log(sortie + 1e-10)
    return (sortie - sortie.mean()) / (sortie.std() + 1e-10)


def lire(chemin: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(chemin), "rb") as w:
        taux, canaux = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return (x.reshape(-1, canaux).mean(axis=1) if canaux > 1 else x), taux


def fondamentale(x: np.ndarray, taux: int) -> float:
    n = int(taux * 0.05)
    lo, hi = int(taux / 400), int(taux / 60)
    seuil = np.sqrt(np.mean(x ** 2)) * 0.5
    valeurs = []
    for d in range(0, len(x) - n, n):
        bloc = x[d : d + n]
        if np.sqrt(np.mean(bloc ** 2)) < seuil:
            continue
        bloc = bloc - bloc.mean()
        ac = np.correlate(bloc, bloc, "full")[n - 1:]
        if ac[0] <= 0:
            continue
        pic = lo + int(np.argmax(ac[lo:hi] / ac[0]))
        valeurs.append(taux / pic)
    return float(np.median(valeurs)) if valeurs else 0.0


async def main() -> None:
    from src.mouth.pocket_tts import PocketTTS

    ref, taux_ref = lire(REFERENCE)
    cible = spectre_moyen(ref, taux_ref)
    print(f"reference : f0 {fondamentale(ref, taux_ref):.1f} Hz\n")

    resultats = []
    for nom in CATALOGUE:
        tts = PocketTTS(language="french_24l", voice=nom, device="cuda")
        if not await tts.load_model():
            continue
        out = await tts.synthesize(PHRASE)
        x = np.asarray(out["audio"]).ravel().astype(np.float32) / 32768.0
        taux = int(out["sample_rate"])
        distance = float(np.linalg.norm(spectre_moyen(x, taux) - cible))
        resultats.append((distance, nom, fondamentale(x, taux)))
        print(f"  {nom:12} distance {distance:5.2f}  f0 {resultats[-1][2]:6.1f} Hz", flush=True)

    print("\n== les plus proches de la reference ==")
    for distance, nom, f0 in sorted(resultats)[:5]:
        print(f"{nom:12} distance {distance:5.2f}  f0 {f0:6.1f} Hz")


if __name__ == "__main__":
    asyncio.run(main())
