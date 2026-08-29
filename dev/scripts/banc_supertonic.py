"""Banc Supertonic-3 : voix preset en francais, mesures a l'appui.

Les presets ne sont pas etiquetes par langue : F1-F5 et M1-M5 parlent
toutes le francais via lang='fr'. On les mesure toutes. EARS filtre
l'intelligibilite comme sur Piper et MLS.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path

import numpy as np

from dev.scripts.banc_piper import (
    PHRASE,
    SORTIE,
    ecrire,
    fondamentale,
    taux_erreur_mot,
    vers_16k,
)

MODELE = Path("/workspace/models/supertonic")
CACHE_LOCAL = Path("/root/.cache/supertonic3")
REPO = "Supertone/supertonic-3"
REVISION = "724fb5abbf5502583fb520898d45929e62f02c0b"


def _onnx_ok(racine: Path) -> bool:
    return all(
        (racine / "onnx" / nom).exists()
        for nom in (
            "duration_predictor.onnx",
            "text_encoder.onnx",
            "vector_estimator.onnx",
            "vocoder.onnx",
        )
    )


def installer_poids() -> str:
    """Place les ONNX dans MODELE. Telecharge si besoin, sinon copie le cache."""
    MODELE.mkdir(parents=True, exist_ok=True)
    if _onnx_ok(MODELE):
        return f"deja present dans {MODELE}"

    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=REPO,
            revision=REVISION,
            local_dir=str(MODELE),
        )
        if _onnx_ok(MODELE):
            return f"telecharge {REPO}@{REVISION[:12]} vers {MODELE}"
    except Exception as exc:
        print(f"telechargement HF echoue ({exc!r}), repli sur le cache local", flush=True)

    if _onnx_ok(CACHE_LOCAL):
        if MODELE.exists():
            shutil.rmtree(MODELE)
        shutil.copytree(CACHE_LOCAL, MODELE)
        return f"copie {CACHE_LOCAL} -> {MODELE} (revision pinee {REVISION[:12]})"

    raise FileNotFoundError(
        f"ONNX introuvables dans {MODELE} et {CACHE_LOCAL}. "
        "Arret : pas de poids, pas d'inference."
    )


def pcm16(wav: np.ndarray) -> np.ndarray:
    x = np.asarray(wav, dtype=np.float32).ravel()
    pic = float(np.max(np.abs(x))) if x.size else 0.0
    if pic > 1.0:
        x = x / pic * 0.99
    return np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)


async def main() -> None:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    origine = installer_poids()
    print(f"poids: {origine}", flush=True)
    for rel in (
        "onnx/duration_predictor.onnx",
        "onnx/text_encoder.onnx",
        "onnx/vector_estimator.onnx",
        "onnx/vocoder.onnx",
    ):
        p = MODELE / rel
        print(f"  {rel:36} {p.stat().st_size / 1e6:7.1f} Mo", flush=True)

    from supertonic import TTS
    from src.ears.faster_whisper_asr import FasterWhisperASR

    t0 = time.perf_counter()
    tts = TTS(
        model="supertonic-3",
        model_dir=str(MODELE),
        auto_download=False,
    )
    print(
        f"chargement ONNX CPU: {time.perf_counter() - t0:.2f}s  "
        f"sr={tts.sample_rate}  voix={tts.voice_style_names}",
        flush=True,
    )

    # Chauffe : la premiere passe ONNX n'est pas un TTFA representatif.
    style0 = tts.get_voice_style(tts.voice_style_names[0])
    tts.synthesize("Ok.", voice_style=style0, lang="fr")

    SORTIE.mkdir(parents=True, exist_ok=True)
    ears = FasterWhisperASR(model_size="large-v3-turbo", language="fr", device="cuda")
    if not await ears.load_model():
        raise RuntimeError("EARS indisponible (Whisper n'a pas charge).")

    print(
        f"{'voix':6} {'f0':>8} {'TTFA':>8} {'RTF':>6} {'WER':>7}  transcription",
        flush=True,
    )
    print("-" * 110, flush=True)

    for nom in tts.voice_style_names:
        style = tts.get_voice_style(nom)
        t1 = time.perf_counter()
        wav, _dur = tts.synthesize(PHRASE, voice_style=style, lang="fr")
        synth_s = time.perf_counter() - t1
        pcm = pcm16(wav)
        taux = int(tts.sample_rate)
        etiquette = nom.lower()
        ecrire(SORTIE / f"supertonic_{etiquette}_fr.wav", pcm, taux)

        flottant = pcm.astype(np.float32) / 32768.0
        duree_s = len(flottant) / taux if taux else 0.0
        rtf = synth_s / duree_s if duree_s > 0 else 0.0
        texte = (
            (await ears.transcribe(vers_16k(flottant, taux))).get("text") or ""
        ).strip()
        print(
            f"{etiquette:6} {fondamentale(flottant, taux):6.1f}Hz "
            f"{synth_s * 1000:7.0f}ms {rtf:6.2f} "
            f"{taux_erreur_mot(PHRASE, texte):6.1%}  {texte[:64]}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
