"""8 voix FR feminines neuves pour hyper-ambient (CPU, conteneur live).

Interdits : Pocket estelle/cosette, Piper siwis/upmc/mls/tom, Supertonic F1/F5,
clone Qwen3-TTS, MMS-TTS fra, Kokoro ff_siwis. Pas de clonage d'une personne.

Tourne dans mother-core-dev, cwd /workspace :
  CUDA_VISIBLE_DEVICES= python3 /workspace/dev/scripts/_voix_nouvelles.py
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import re
import subprocess
import sys
import time
import wave
from math import gcd
from pathlib import Path

# Avant tout import torch : ne pas voir le GPU du live (8,4 Go deja pris).
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HOME", "/workspace/models/hf-cache")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np

SORTIE = Path("/workspace/data/out/voix-nouvelles")
SCRIPT = Path("/workspace/nights/2026-09-13-SCRIPT-VOIX-LONG.txt")
POCKET_EMB = Path("/workspace/models/pocket-tts/languages/french_24l/embeddings")
SUPERTONIC_DIR = Path("/workspace/models/supertonic")
META = SORTIE / "meta.jsonl"
VITESSE = 0.88

# 5 Pocket (embeddings jamais retenus comme voix live) + 3 Supertonic F2/F3/F4.
# lola = timbre Common Voice ES : on la tente ; repli jane/mary/azelma.
POCKET_VOIX = ["fantine", "eve", "lola", "anna", "vera"]
POCKET_REPLIS = ["jane", "mary", "azelma"]
SUPERTONIC_VOIX = ["F2", "F3", "F4"]

LICENCES = {
    "pocket": (
        "MIT (code kyutai-labs/pocket-tts) + CC-BY-4.0 (poids french_24l / VCTK) ; "
        "lola : Common Voice (CC-0) via kyutai/pocket-tts"
    ),
    "supertonic": "OpenRAIL-M (poids Supertone/supertonic-3) + MIT (SDK)",
}

ORIGINE_POCKET = {
    "fantine": "VCTK p244, CC-BY-4.0",
    "eve": "VCTK p361, CC-BY-4.0",
    "lola": "Common Voice ES, CC-0",
    "anna": "VCTK p228, CC-BY-4.0",
    "vera": "VCTK p229, CC-BY-4.0",
    "jane": "VCTK p339, CC-BY-4.0",
    "mary": "VCTK p333, CC-BY-4.0",
    "azelma": "VCTK p303, CC-BY-4.0",
}


def lire_script() -> str:
    texte = SCRIPT.read_text(encoding="utf-8").strip()
    return re.sub(r"\s+", " ", texte.replace("''", "'"))


def pcm16(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).ravel()
    pic = float(np.max(np.abs(x))) if x.size else 0.0
    if pic > 1.0:
        x = x / pic * 0.99
    elif pic == 0.0:
        return np.zeros(0, dtype=np.int16)
    return np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)


def ralentir(pcm: np.ndarray, vitesse: float) -> np.ndarray:
    """Etire le PCM a taux constant (Pocket n'a pas de vitesse)."""
    from scipy.signal import resample_poly

    if vitesse <= 0 or abs(vitesse - 1.0) < 1e-6 or pcm.size == 0:
        return pcm
    up, down = 100, max(1, int(round(100 * vitesse)))
    g = gcd(up, down)
    up, down = up // g, down // g
    lent = resample_poly(np.asarray(pcm, dtype=np.float32), up, down)
    return pcm16(lent)


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
            "ffmpeg", "-y", "-i", str(wav), "-ac", "1",
            "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3),
        ],
        check=True,
        capture_output=True,
    )


def duree_mp3(chemin: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(chemin),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def mp3_valide(chemin: Path) -> bool:
    if not chemin.is_file() or chemin.stat().st_size <= 80_000:
        return False
    dec = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(chemin), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if dec.returncode != 0:
        return False
    return duree_mp3(chemin) > 20.0


def lire_meta() -> dict[str, dict]:
    seen: dict[str, dict] = {}
    if META.exists():
        for line in META.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                seen[r["fichier"]] = r
    return seen


def ecrire_meta(ligne: dict) -> None:
    seen = lire_meta()
    seen[ligne["fichier"]] = ligne
    tmp = META.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False) + "\n"
            for r in sorted(seen.values(), key=lambda r: r["fichier"])
        ),
        encoding="utf-8",
    )
    tmp.replace(META)


def livrer(nom: str, pcm: np.ndarray, taux: int, meta: dict) -> dict:
    SORTIE.mkdir(parents=True, exist_ok=True)
    wav = SORTIE / f"{nom}.wav"
    mp3 = SORTIE / f"{nom}.mp3"
    ecrire_wav(wav, pcm, taux)
    wav_vers_mp3(wav, mp3)
    wav.unlink(missing_ok=True)
    sec = duree_mp3(mp3)
    synth_s = float(meta.get("synth_s") or 0.0)
    rtf = round(synth_s / sec, 3) if sec > 0 else None
    ligne = {
        "fichier": mp3.name,
        "chemin": str(mp3),
        "duree_s": round(sec, 2),
        "sr": int(taux),
        "octets": mp3.stat().st_size,
        "rtf": rtf,
        "device": "CPU",
        **meta,
    }
    ecrire_meta(ligne)
    print(
        f"OK {mp3.name}  {sec:.2f}s  RTF={rtf}  {mp3.stat().st_size} o  "
        f"{meta.get('moteur')} / {meta.get('voix')}",
        flush=True,
    )
    if sec <= 20:
        print(f"WARN duree <= 20s : {mp3.name}", flush=True)
    return ligne


def gpu_vide() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def job_pocket(texte: str) -> None:
    from pocket_tts import TTSModel

    print("pocket french_24l chargement CPU (quantize)…", flush=True)
    t_load = time.perf_counter()
    try:
        modele = TTSModel.load_model(
            language="french_24l",
            temp=0.7,
            eos_threshold=0.0,
            quantize=True,
        )
    except Exception as exc:
        print(f"quantize echoue ({exc!r}), repli fp32", flush=True)
        modele = TTSModel.load_model(
            language="french_24l", temp=0.7, eos_threshold=0.0
        )
    try:
        modele.cpu()
    except Exception:
        pass
    print(
        f"pocket charge {time.perf_counter()-t_load:.1f}s  "
        f"device={getattr(modele, 'device', '?')} sr={modele.sample_rate}",
        flush=True,
    )

    faits = []
    file_idx = 1
    candidats = list(POCKET_VOIX)
    for repli in POCKET_REPLIS:
        if repli not in candidats:
            candidats.append(repli)

    for voix in candidats:
        if len(faits) >= 5:
            break
        nom = f"{file_idx:02d}-pocket-{voix}"
        mp3 = SORTIE / f"{nom}.mp3"
        if mp3_valide(mp3):
            print(f"SKIP {mp3.name} deja valide", flush=True)
            faits.append(voix)
            file_idx += 1
            continue
        emb = POCKET_EMB / f"{voix}.safetensors"
        if not emb.exists():
            print(f"SKIP {voix} : pas d'embedding {emb}", flush=True)
            continue
        print(f"— pocket {voix}", flush=True)
        t0 = time.perf_counter()
        try:
            etat = modele.get_state_for_audio_prompt(str(emb), truncate=True)
            audio = modele.generate_audio(etat, texte, copy_state=True)
            arr = audio.detach().cpu().float().numpy()
            pcm = ralentir(pcm16(arr), VITESSE)
        except Exception as exc:
            print(f"FAIL pocket {voix}: {type(exc).__name__}: {exc}", flush=True)
            gpu_vide()
            continue
        if pcm.size == 0:
            print(f"FAIL pocket {voix}: silence", flush=True)
            continue
        livrer(
            nom,
            pcm,
            int(modele.sample_rate),
            {
                "moteur": "pocket",
                "voix": voix,
                "vitesse": VITESSE,
                "synth_s": round(time.perf_counter() - t0, 1),
                "licence": (
                    f"MIT + CC-BY-4.0 (french_24l) ; origine {ORIGINE_POCKET.get(voix, '?')}"
                ),
            },
        )
        faits.append(voix)
        file_idx += 1
        gpu_vide()

    del modele
    gpu_vide()
    if len(faits) < 5:
        raise RuntimeError(f"pocket : seulement {len(faits)} voix valides {faits}")


def job_supertonic(texte: str) -> None:
    from supertonic import TTS

    print("supertonic-3 chargement ONNX CPU…", flush=True)
    tts = TTS(model="supertonic-3", model_dir=str(SUPERTONIC_DIR), auto_download=False)
    dispo = list(tts.voice_style_names)
    print(f"supertonic voix={dispo} sr={tts.sample_rate}", flush=True)
    # Chauffe (premiere passe ONNX).
    style0 = tts.get_voice_style(SUPERTONIC_VOIX[0] if SUPERTONIC_VOIX[0] in dispo else dispo[0])
    tts.synthesize("Ok.", voice_style=style0, lang="fr", speed=VITESSE)

    for i, voix in enumerate(SUPERTONIC_VOIX, start=6):
        if voix not in dispo:
            raise RuntimeError(f"supertonic {voix} absent, dispo={dispo}")
        nom = f"{i:02d}-supertonic-{voix.lower()}"
        mp3 = SORTIE / f"{nom}.mp3"
        if mp3_valide(mp3):
            print(f"SKIP {mp3.name} deja valide", flush=True)
            continue
        print(f"— supertonic {voix} speed={VITESSE}", flush=True)
        style = tts.get_voice_style(voix)
        t0 = time.perf_counter()
        wav, _dur = tts.synthesize(
            texte, voice_style=style, lang="fr", speed=VITESSE
        )
        pcm = pcm16(wav)
        if pcm.size == 0:
            raise RuntimeError(f"supertonic {voix} silence")
        livrer(
            nom,
            pcm,
            int(tts.sample_rate),
            {
                "moteur": "supertonic",
                "voix": voix,
                "vitesse": VITESSE,
                "synth_s": round(time.perf_counter() - t0, 1),
                "licence": LICENCES["supertonic"],
            },
        )
        gpu_vide()

    del tts
    gpu_vide()


def ecrire_index() -> None:
    lignes = list(lire_meta().values())
    lignes.sort(key=lambda r: r["fichier"])
    corps = [
        "# INDEX — 8 voix FR feminines neuves (hyper-ambient)",
        "",
        "Script : `nights/2026-09-13-SCRIPT-VOIX-LONG.txt` (`''` → `'`).",
        "Cible : suave, feminine, lente (~0.88). CPU only. Pas de clonage.",
        "Exclus : Pocket estelle/cosette, Piper siwis/upmc/mls/tom, Supertonic F1/F5,",
        "Qwen3-TTS clone, MMS-TTS fra, Kokoro ff_siwis.",
        "",
        "| # | fichier | moteur | voix | vitesse | duree | CPU/GPU | licence | RTF |",
        "|---|---|---|---|---:|---:|---|---|---:|",
    ]
    for r in lignes:
        num = r["fichier"][:2]
        lic = (r.get("licence") or "").replace("|", "/")
        corps.append(
            f"| {num} | `{r['fichier']}` | {r.get('moteur','')} | {r.get('voix','')} | "
            f"{r.get('vitesse','')} | {r.get('duree_s', 0):.1f} s | {r.get('device','CPU')} | "
            f"{lic} | {r.get('rtf', '—')} |"
        )
    mp3s = sorted(p for p in SORTIE.glob("*.mp3") if mp3_valide(p))
    corps += [
        "",
        f"MP3 valides (> 20 s) : **{len(mp3s)} / 8**",
        "",
    ]
    index = SORTIE / "INDEX.md"
    index.write_text("\n".join(corps) + "\n", encoding="utf-8")
    print(f"INDEX {index} n={len(lignes)} mp3_ok={len(mp3s)}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--job", default="", choices=["", "pocket", "supertonic", "index"])
    args = p.parse_args()
    SORTIE.mkdir(parents=True, exist_ok=True)

    if args.job == "index":
        ecrire_index()
        return

    if not args.job:
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "PYTHONUNBUFFERED": "1"}
        fails = []
        for job in ("pocket", "supertonic"):
            print(f"\n======== JOB {job} ========", flush=True)
            rc = subprocess.call(
                [sys.executable, str(Path(__file__).resolve()), "--job", job],
                env=env,
            )
            if rc != 0:
                fails.append(f"{job}:{rc}")
                print(f"JOB FAIL {job} rc={rc}", flush=True)
        ecrire_index()
        if fails:
            raise SystemExit(f"echecs {fails}")
        n_ok = sum(1 for pth in SORTIE.glob("*.mp3") if mp3_valide(pth))
        if n_ok < 8:
            raise SystemExit(f"seulement {n_ok}/8 MP3 valides")
        print(f"DONE {n_ok}/8", flush=True)
        return

    if not SCRIPT.exists():
        raise SystemExit(f"manque {SCRIPT}")
    texte = lire_script()
    print(f"job={args.job} script={len(texte)} car", flush=True)
    if args.job == "pocket":
        job_pocket(texte)
    elif args.job == "supertonic":
        job_supertonic(texte)
    ecrire_index()


if __name__ == "__main__":
    main()
