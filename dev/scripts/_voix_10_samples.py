"""10 samples MP3, meme script long, timbres FR differents, profil aurora.

Tourne dans mother-core-dev. Ne pas lancer tant que le host-agent Pocket
est charge : second chargement du modele (~642 Mo) dans le plafond 8 Go.
"""
from __future__ import annotations

import asyncio
import gc
import os
import re
import subprocess
import time
import wave
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HOME", "/workspace/models/hf-cache")
os.environ.pop("HF_HUB_OFFLINE", None)

SORTIE = Path("/workspace/data/out/voix-10-samples")
SCRIPT = Path("/workspace/dev/scripts/_voix_10_script.txt")
PIPER = Path("/workspace/models/piper")
POCKET_EMB = Path("/workspace/models/pocket-tts/languages/french_24l/embeddings")
SUPERTONIC_DIR = Path("/workspace/models/supertonic")
QWEN_REF = Path("/workspace/data/voix/aurora_prompt_6s.wav")
QWEN_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

# MLS locutrice grave intelligible (banc_mls.py : id 38, nom 7239).
MLS_SPEAKER_ID = 38
MLS_SPEAKER_NOM = "7239"


def lire_script() -> str:
    texte = SCRIPT.read_text(encoding="utf-8").strip()
    texte = texte.replace("''", "'")
    texte = re.sub(r"\s+", " ", texte)
    return texte


def phrases(texte: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", texte)
    return [p.strip() for p in parts if p.strip()]


def pcm16(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).ravel()
    pic = float(np.max(np.abs(x))) if x.size else 0.0
    if pic > 1.0:
        x = x / pic * 0.99
    elif pic == 0.0:
        return np.zeros(0, dtype=np.int16)
    return np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)


def aurora(pcm: np.ndarray, taux: int) -> np.ndarray:
    from src.mouth.voice_design import PROFILES, VoiceTreatment

    if pcm.size == 0:
        return pcm
    return VoiceTreatment(PROFILES["aurora"], int(taux)).process(np.asarray(pcm, dtype=np.int16))


def ecrire_wav(chemin: Path, pcm: np.ndarray, taux: int) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(taux))
        w.writeframes(np.asarray(pcm, dtype=np.int16).tobytes())


def wav_vers_mp3(wav: Path, mp3: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav),
            "-ac",
            "1",
            "-codec:a",
            "libmp3lame",
            "-qscale:a",
            "2",
            str(mp3),
        ],
        check=True,
        capture_output=True,
    )


def duree_wav(chemin: Path) -> float:
    with wave.open(str(chemin), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def livrer(nom: str, pcm: np.ndarray, taux: int, meta: dict) -> dict:
    wav = SORTIE / f"{nom}.wav"
    mp3 = SORTIE / f"{nom}.mp3"
    ecrire_wav(wav, pcm, taux)
    wav_vers_mp3(wav, mp3)
    sec = duree_wav(wav)
    wav.unlink(missing_ok=True)
    ligne = {
        "fichier": mp3.name,
        "chemin": str(mp3),
        "duree_s": round(sec, 2),
        "sr": int(taux),
        "octets": mp3.stat().st_size,
        **meta,
    }
    print(
        f"OK {mp3.name}  {sec:.2f}s  {taux} Hz  {mp3.stat().st_size} o  "
        f"{meta.get('modele')} / {meta.get('voix')}",
        flush=True,
    )
    if sec < 20:
        print(f"WARN duree < 20s : {mp3.name}", flush=True)
    return ligne


async def synth_piper(texte: str, onnx: Path, speaker_id, profil: str) -> tuple[np.ndarray, int]:
    from src.mouth.piper_tts import PiperTTS

    tts = PiperTTS(model_path=str(onnx), profile=profil, speaker_id=speaker_id)
    if not await tts.load_model():
        raise RuntimeError(f"piper load failed: {onnx}")
    parts = []
    taux = tts.sample_rate
    for phrase in phrases(texte):
        out = await tts.synthesize(phrase)
        pcm = np.asarray(out["audio"], dtype=np.int16).ravel()
        if pcm.size:
            parts.append(pcm)
            taux = int(out["sample_rate"])
    if not parts:
        raise RuntimeError(f"piper silence: {onnx}")
    return np.concatenate(parts), taux


async def synth_pocket(texte: str, voix: str) -> tuple[np.ndarray, int]:
    from src.mouth.pocket_tts import PocketTTS

    tts = PocketTTS(
        language="french_24l",
        voice=voix,
        device="cpu",
        profile="flat",
        max_tokens=50,
    )
    if not await tts.load_model():
        raise RuntimeError(f"pocket load failed: {voix}")
    parts = []
    for phrase in phrases(texte):
        out = await tts.synthesize(phrase)
        pcm = np.asarray(out["audio"], dtype=np.int16).ravel()
        if pcm.size:
            parts.append(pcm)
    del tts
    gc.collect()
    if not parts:
        raise RuntimeError(f"pocket silence: {voix}")
    brut = np.concatenate(parts)
    return aurora(brut, 24000), 24000


def synth_supertonic(texte: str, style_nom: str) -> tuple[np.ndarray, int]:
    from banc_supertonic import installer_poids
    from supertonic import TTS

    installer_poids()
    tts = TTS(model="supertonic-3", model_dir=str(SUPERTONIC_DIR), auto_download=False)
    dispo = list(tts.voice_style_names)
    if style_nom not in dispo:
        raise RuntimeError(f"style {style_nom} absent, dispo={dispo}")
    style = tts.get_voice_style(style_nom)
    tts.synthesize("Ok.", voice_style=style, lang="fr")
    parts = []
    for phrase in phrases(texte):
        wav, _dur = tts.synthesize(phrase, voice_style=style, lang="fr")
        pcm = pcm16(wav)
        if pcm.size:
            parts.append(pcm)
    taux = int(tts.sample_rate)
    del tts
    gc.collect()
    if not parts:
        raise RuntimeError(f"supertonic silence: {style_nom}")
    return aurora(np.concatenate(parts), taux), taux


def synth_qwen(texte: str) -> tuple[np.ndarray, int]:
    import torch
    from qwen_tts import Qwen3TTSModel

    if not QWEN_REF.exists():
        raise FileNotFoundError(QWEN_REF)
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    print(f"qwen3-tts chargement {device} {dtype}…", flush=True)
    modele = Qwen3TTSModel.from_pretrained(QWEN_ID, device_map=device, dtype=dtype)
    parts = []
    sr = 24000
    for phrase in phrases(texte):
        t0 = time.perf_counter()
        wavs, sr = modele.generate_voice_clone(
            text=phrase,
            language="French",
            ref_audio=str(QWEN_REF),
            x_vector_only_mode=True,
        )
        print(f"  qwen phrase {time.perf_counter()-t0:.1f}s  {phrase[:48]}", flush=True)
        pcm = pcm16(np.asarray(wavs[0]))
        if pcm.size:
            parts.append(pcm)
    del modele
    gc.collect()
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    if not parts:
        raise RuntimeError("qwen silence")
    return aurora(np.concatenate(parts), int(sr)), int(sr)


def synth_mms(texte: str) -> tuple[np.ndarray, int]:
    import torch
    from transformers import AutoTokenizer, VitsModel

    print("mms-tts-fra chargement CPU…", flush=True)
    modele = VitsModel.from_pretrained("facebook/mms-tts-fra")
    tok = AutoTokenizer.from_pretrained("facebook/mms-tts-fra")
    modele.eval()
    parts = []
    taux = int(getattr(modele.config, "sampling_rate", 16000))
    for phrase in phrases(texte):
        entrees = tok(phrase, return_tensors="pt")
        with torch.no_grad():
            onde = modele(**entrees).waveform
        pcm = pcm16(onde.squeeze().cpu().numpy())
        if pcm.size:
            parts.append(pcm)
    del modele
    gc.collect()
    if not parts:
        raise RuntimeError("mms silence")
    return aurora(np.concatenate(parts), taux), taux


def synth_kokoro(texte: str) -> tuple[np.ndarray, int]:
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="f")
    parts = []
    taux = 24000
    for phrase in phrases(texte):
        for _gs, _ps, audio in pipe(phrase, voice="ff_siwis"):
            pcm = pcm16(np.asarray(audio))
            if pcm.size:
                parts.append(pcm)
    del pipe
    gc.collect()
    if not parts:
        raise RuntimeError("kokoro silence")
    return aurora(np.concatenate(parts), taux), taux


async def main() -> None:
    import sys

    sys.path.insert(0, "/workspace/dev/scripts")
    SORTIE.mkdir(parents=True, exist_ok=True)
    texte = lire_script()
    print(f"script {len(texte)} car, {len(phrases(texte))} phrases", flush=True)
    print(texte[:120], "…", flush=True)

    jobs = [
        (
            "01-pocket-estelle-aurora",
            "pocket",
            {"modele": "pocket-tts french_24l", "voix": "estelle", "profil": "aurora",
             "note": "voix live ; seule FR native du catalogue Pocket"},
            lambda: synth_pocket(texte, "estelle"),
        ),
        (
            "02-pocket-cosette-aurora",
            "pocket",
            {"modele": "pocket-tts french_24l", "voix": "cosette", "profil": "aurora",
             "note": "autre embedding ; origine Expresso/EN, accent possible"},
            lambda: synth_pocket(texte, "cosette"),
        ),
        (
            "03-piper-siwis-aurora",
            "piper",
            {"modele": "piper fr_FR-siwis-medium.onnx", "voix": "siwis", "profil": "aurora",
             "note": "fallback Piper a conserver"},
            lambda: synth_piper(texte, PIPER / "fr_FR-siwis-medium.onnx", None, "aurora"),
        ),
        (
            "04-piper-upmc-jessica-aurora",
            "piper",
            {"modele": "piper fr_FR-upmc-medium.onnx", "voix": "jessica (id 0)", "profil": "aurora",
             "note": "UPMC, locutrice jessica"},
            lambda: synth_piper(texte, PIPER / "fr_FR-upmc-medium.onnx", 0, "aurora"),
        ),
        (
            "05-piper-mls-7239-aurora",
            "piper",
            {"modele": "piper fr_FR-mls-medium.onnx",
             "voix": f"mls {MLS_SPEAKER_NOM} (id {MLS_SPEAKER_ID})", "profil": "aurora",
             "note": "locutrice MLS grave retenue au banc"},
            lambda: synth_piper(
                texte, PIPER / "fr_FR-mls-medium.onnx", MLS_SPEAKER_ID, "aurora"
            ),
        ),
        (
            "06-piper-tom-aurora",
            "piper",
            {"modele": "piper fr_FR-tom-medium.onnx", "voix": "tom", "profil": "aurora",
             "note": "natif 44100 Hz, ramene a 22050 avant MP3"},
            lambda: synth_piper(texte, PIPER / "fr_FR-tom-medium.onnx", None, "aurora"),
        ),
        (
            "07-supertonic-f5-aurora",
            "supertonic",
            {"modele": "supertonic-3 ONNX", "voix": "F5", "profil": "aurora",
             "note": "preset feminin le plus proche Aurora en brillance (aout)"},
            lambda: synth_supertonic(texte, "F5"),
        ),
        (
            "08-supertonic-f1-aurora",
            "supertonic",
            {"modele": "supertonic-3 ONNX", "voix": "F1", "profil": "aurora",
             "note": "autre style feminin, timbre distinct de F5"},
            lambda: synth_supertonic(texte, "F1"),
        ),
        (
            "09-qwen3tts-clone-aurora",
            "qwen3-tts",
            {"modele": "Qwen3-TTS-12Hz-0.6B-Base", "voix": "clone aurora_prompt_6s",
             "profil": "aurora",
             "note": "clone de la ref YouTube Aura Ray ; cible esthetique"},
            lambda: synth_qwen(texte),
        ),
        (
            "10-mms-tts-fra-aurora",
            "mms",
            {"modele": "facebook/mms-tts-fra", "voix": "mms-fra (1 locuteur)",
             "profil": "aurora",
             "note": "VITS MMS, moteur distinct, CPU"},
            lambda: synth_mms(texte),
        ),
    ]

    replis = [
        (
            "supertonic-f3-aurora",
            "supertonic",
            {"modele": "supertonic-3 ONNX", "voix": "F3", "profil": "aurora",
             "note": "repli style feminin"},
            lambda: synth_supertonic(texte, "F3"),
        ),
        (
            "pocket-fantine-aurora",
            "pocket",
            {"modele": "pocket-tts french_24l", "voix": "fantine", "profil": "aurora",
             "note": "repli embedding feminin"},
            lambda: synth_pocket(texte, "fantine"),
        ),
        (
            "kokoro-ff-siwis-aurora",
            "kokoro",
            {"modele": "kokoro-82m", "voix": "ff_siwis", "profil": "aurora",
             "note": "repli Kokoro FR"},
            lambda: synth_kokoro(texte),
        ),
        (
            "pocket-eve-aurora",
            "pocket",
            {"modele": "pocket-tts french_24l", "voix": "eve", "profil": "aurora",
             "note": "repli embedding feminin"},
            lambda: synth_pocket(texte, "eve"),
        ),
    ]

    lignes: list[dict] = []
    echecs: list[str] = []
    repli_idx = 0

    async def run_job(nom, moteur, meta, fn):
        t0 = time.perf_counter()
        print(f"— {nom} ({moteur})", flush=True)
        resultat = fn()
        if asyncio.iscoroutine(resultat):
            pcm, taux = await resultat
        else:
            pcm, taux = resultat
        meta = dict(meta)
        meta["synth_s"] = round(time.perf_counter() - t0, 1)
        return livrer(nom, pcm, taux, meta)

    for nom, moteur, meta, fn in jobs:
        try:
            lignes.append(await run_job(nom, moteur, meta, fn))
        except Exception as exc:
            msg = f"{nom}: {type(exc).__name__}: {exc}"
            print(f"FAIL {msg}", flush=True)
            echecs.append(msg)
            pris = False
            while repli_idx < len(replis):
                rnom, rmoteur, rmeta, rfn = replis[repli_idx]
                repli_idx += 1
                numero = nom.split("-", 1)[0]
                alias = f"{numero}-{rnom}"
                try:
                    lignes.append(await run_job(alias, rmoteur, rmeta, rfn))
                    pris = True
                    break
                except Exception as exc2:
                    msg2 = f"{alias}: {type(exc2).__name__}: {exc2}"
                    print(f"FAIL {msg2}", flush=True)
                    echecs.append(msg2)
            if not pris:
                print(f"AUCUN REPLI pour {nom}", flush=True)

    index = SORTIE / "INDEX.md"
    lignes.sort(key=lambda r: r["fichier"])
    corps = [
        "# INDEX — 10 samples voix FR (script long)",
        "",
        f"Script : `{SCRIPT}`",
        "Cible esthetique : Aura Ray (YouTube) — douce, presentielle, proche. Profil DSP `aurora`.",
        "",
        "| # | Fichier | Modele | Voix | Profil | Duree | SR | Chemin | Note |",
        "|---|---|---|---|---|---:|---:|---|---|",
    ]
    for i, r in enumerate(lignes, 1):
        corps.append(
            f"| {i} | `{r['fichier']}` | {r.get('modele','')} | {r.get('voix','')} | "
            f"{r.get('profil','')} | {r['duree_s']:.2f}s | {r['sr']} | `{r['chemin']}` | "
            f"{r.get('note','')} |"
        )
    corps += ["", "## Echecs", ""]
    if echecs:
        corps.extend(f"- {e}" for e in echecs)
    else:
        corps.append("Aucun.")
    index.write_text("\n".join(corps) + "\n", encoding="utf-8")
    print(f"INDEX {index}  n={len(lignes)}", flush=True)
    if len(lignes) < 10:
        raise SystemExit(f"seulement {len(lignes)} samples")


if __name__ == "__main__":
    asyncio.run(main())
