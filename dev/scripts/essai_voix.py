#!/usr/bin/env python3
"""Generate comparable TTS samples for the hyper-ambient voice shortlist.

Writes only to /workspace/data/voix/. Does not start any server.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

OUT_DIR = Path("/workspace/data/voix")
TARGET_SR = 16000

TEXT = {
    "fr": "Je suis là. Prends ton temps, je t'écoute.",
    "en": "I am here with you. Take your time, there is no hurry.",
    "es": "Estoy aquí contigo. Tómate tu tiempo, no hay prisa.",
}

# Kyutai catalog genders (kyutai.org demo + Les Mis / VCTK names).
# Alba is listed as male ("Alba (m, reading)"); we still try it because
# the brief named it, but we will not pick it as a feminine finalist.
POCKET_FEMALE = [
    "estelle",
    "cosette",
    "lola",
    "anna",
    "azelma",
    "caro_davy",
    "eponine",
    "eve",
    "fantine",
    "jane",
    "mary",
    "vera",
]
POCKET_NAMED_EXTRA = ["alba"]  # requested explicitly; male in the catalog


def log(msg: str) -> None:
    print(msg, flush=True)


def to_mono_float(wav) -> np.ndarray:
    x = np.asarray(wav)
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    x = np.asarray(x, dtype=np.float32).squeeze()
    if x.ndim == 2:
        x = x.mean(axis=0 if x.shape[0] < x.shape[1] else 1)
    return np.ascontiguousarray(x, dtype=np.float32)


def resample_16k(wav: np.ndarray, sr: int) -> np.ndarray:
    wav = to_mono_float(wav)
    if sr == TARGET_SR:
        return wav
    g = gcd(int(sr), TARGET_SR)
    return resample_poly(wav, TARGET_SR // g, int(sr) // g).astype(np.float32)


def save_wav(path: Path, wav, sr: int) -> dict:
    audio = resample_16k(wav, sr)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak * 0.99
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, TARGET_SR, subtype="PCM_16")
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) if audio.size else 0.0
    dur = float(audio.size / TARGET_SR)
    return {"path": str(path), "duration_s": dur, "rms": rms, "peak": peak, "n_samples": int(audio.size)}


def mean_f0_hz(wav, sr: int) -> float:
    """Median autocorrelation F0 on voiced frames. Lower = graver."""
    x = to_mono_float(wav).astype(np.float64)
    if x.size < int(sr * 0.08):
        return float("nan")
    frame = int(sr * 0.04)
    hop = int(sr * 0.01)
    min_lag = max(1, int(sr / 350.0))
    max_lag = max(min_lag + 1, int(sr / 70.0))
    win = np.hanning(frame)
    f0s = []
    for i in range(0, x.size - frame, hop):
        w = x[i : i + frame]
        w = (w - w.mean()) * win
        energy = float(np.dot(w, w))
        if energy < 1e-8:
            continue
        corr = np.correlate(w, w, mode="full")
        corr = corr[corr.size // 2 :]
        if corr[0] <= 0:
            continue
        segment = corr[min_lag:max_lag]
        if segment.size == 0:
            continue
        lag = min_lag + int(np.argmax(segment))
        if corr[lag] > 0.35 * corr[0]:
            f0s.append(sr / lag)
    if not f0s:
        return float("nan")
    return float(np.median(f0s))


def spectral_centroid_hz(wav, sr: int) -> float:
    x = to_mono_float(wav).astype(np.float64)
    if x.size < 64:
        return float("nan")
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, 1.0 / sr)
    denom = spec.sum()
    if denom <= 0:
        return float("nan")
    return float(np.dot(freqs, spec) / denom)


def rank_grave(rows: list[dict]) -> list[dict]:
    """Sort feminine voices: lowest F0, then lowest centroid, then longest duration."""
    def key(r):
        f0 = r.get("f0_hz")
        cen = r.get("centroid_hz")
        f0 = 9999.0 if f0 is None or (isinstance(f0, float) and np.isnan(f0)) else f0
        cen = 99999.0 if cen is None or (isinstance(cen, float) and np.isnan(cen)) else cen
        return (f0, cen, -r.get("duration_s", 0.0))

    return sorted(rows, key=key)


def run_supertonic(metrics: dict) -> list[dict]:
    log("\n========== SUPERTONIC ==========")
    from supertonic import TTS

    t0 = time.perf_counter()
    tts = TTS(auto_download=True)
    load_s = time.perf_counter() - t0
    metrics["supertonic"] = {
        "load_s": load_s,
        "sample_rate_native": int(tts.sample_rate),
        "voices_all": list(tts.voice_style_names),
        "voices_female": [v for v in tts.voice_style_names if str(v).upper().startswith("F")],
        "speed_default": 1.05,
        "speed_lent": 0.70,
        "pitch_control": False,
    }
    log(f"chargement: {load_s:.3f}s")
    log(f"sample_rate natif: {tts.sample_rate}")
    log(f"voix preset: {tts.voice_style_names}")
    female = metrics["supertonic"]["voices_female"]
    log(f"voix feminines: {female}")

    rows = []
    ttfa_done = False
    for name in female:
        style = tts.get_voice_style(voice_name=name)
        t1 = time.perf_counter()
        wav, dur = tts.synthesize(TEXT["fr"], voice_style=style, lang="fr")
        synth_s = time.perf_counter() - t1
        if not ttfa_done:
            # Pas d'API streaming publique: le premier echantillon n'existe
            # qu'au retour de synthesize(). TTFA = latence complete.
            metrics["supertonic"]["ttfa_s"] = synth_s
            metrics["supertonic"]["ttfa_note"] = (
                "pas de streaming dans l'API Python; TTFA = duree de synthesize()"
            )
            metrics["supertonic"]["ttfa_voice"] = name
            ttfa_done = True
            log(f"TTFA (premiere phrase FR, voix {name}): {synth_s:.3f}s")
        out = OUT_DIR / f"supertonic_{name.lower()}_fr.wav"
        info = save_wav(out, wav, tts.sample_rate)
        native = to_mono_float(wav)
        info.update(
            {
                "system": "supertonic",
                "voice": name.lower(),
                "lang": "fr",
                "feminine": True,
                "synth_s": synth_s,
                "f0_hz": mean_f0_hz(native, tts.sample_rate),
                "centroid_hz": spectral_centroid_hz(native, tts.sample_rate),
            }
        )
        log(
            f"  {out.name}  dur={info['duration_s']:.2f}s  "
            f"f0={info['f0_hz']:.1f}Hz  synth={synth_s:.3f}s"
        )
        rows.append(info)

    ranked = rank_grave(rows)
    metrics["supertonic"]["ranking_fr"] = [
        {
            "voice": r["voice"],
            "f0_hz": r["f0_hz"],
            "centroid_hz": r["centroid_hz"],
            "duration_s": r["duration_s"],
        }
        for r in ranked
    ]
    top2 = ranked[:2]
    best = ranked[0]
    log(f"top 2 graves/posees: {[r['voice'] for r in top2]}")

    for r in top2:
        style = tts.get_voice_style(voice_name=r["voice"].upper())
        for lang in ("en", "es"):
            t1 = time.perf_counter()
            wav, _ = tts.synthesize(TEXT[lang], voice_style=style, lang=lang)
            synth_s = time.perf_counter() - t1
            out = OUT_DIR / f"supertonic_{r['voice']}_{lang}.wav"
            info = save_wav(out, wav, tts.sample_rate)
            log(f"  {out.name}  dur={info['duration_s']:.2f}s  synth={synth_s:.3f}s")

    style = tts.get_voice_style(voice_name=best["voice"].upper())
    t1 = time.perf_counter()
    wav, _ = tts.synthesize(TEXT["fr"], voice_style=style, lang="fr", speed=0.70)
    synth_s = time.perf_counter() - t1
    out = OUT_DIR / f"supertonic_{best['voice']}_fr_lent.wav"
    info = save_wav(out, wav, tts.sample_rate)
    log(f"  {out.name}  dur={info['duration_s']:.2f}s  speed=0.70  synth={synth_s:.3f}s")
    metrics["supertonic"]["best_voice"] = best["voice"]
    metrics["supertonic"]["lent_file"] = out.name
    return rows


def pocket_load(language: str, eos_threshold: float = 0.0):
    from pocket_tts import TTSModel

    t0 = time.perf_counter()
    model = TTSModel.load_model(language=language, eos_threshold=eos_threshold)
    load_s = time.perf_counter() - t0
    # Stay on CPU. Do not call .cuda().
    log(f"pocket-tts language={language} device={model.device} load={load_s:.3f}s sr={model.sample_rate}")
    return model, load_s


def pocket_voice_state(model, name: str):
    from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES

    try:
        return model.get_state_for_audio_prompt(name, truncate=True)
    except Exception as exc:
        log(f"  preset {name} indisponible sur ce checkpoint ({exc}); clonage audio")
        origin = _ORIGINS_OF_PREDEFINED_VOICES.get(name)
        if not origin:
            raise
        return model.get_state_for_audio_prompt(origin, truncate=True)


def pocket_generate(model, state, text: str):
    import torch

    chunks = []
    t0 = time.perf_counter()
    ttfa = None
    for chunk in model.generate_audio_stream(state, text):
        if ttfa is None:
            ttfa = time.perf_counter() - t0
        chunks.append(chunk.detach().cpu())
    total_s = time.perf_counter() - t0
    if not chunks:
        audio = torch.zeros(0)
        ttfa = total_s
    else:
        audio = torch.cat(chunks, dim=-1)
    return audio, ttfa, total_s


def run_pocket(metrics: dict) -> list[dict]:
    log("\n========== POCKET-TTS ==========")
    from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES

    available = sorted(_ORIGINS_OF_PREDEFINED_VOICES.keys())
    log(f"voix catalogue: {available}")
    voices_fr = [v for v in POCKET_FEMALE if v in _ORIGINS_OF_PREDEFINED_VOICES]
    extras = [v for v in POCKET_NAMED_EXTRA if v in _ORIGINS_OF_PREDEFINED_VOICES]
    log(f"voix feminines a generer (FR): {voices_fr}")
    log(f"voix extra demandees: {extras}")

    model, load_s = pocket_load("french_24l", eos_threshold=0.0)
    metrics["pockettts"] = {
        "load_s_french_24l": load_s,
        "sample_rate_native": int(model.sample_rate),
        "voices_catalog": available,
        "voices_female": voices_fr,
        "speed_control": False,
        "pitch_control": False,
        "eos_threshold": 0.0,
        "eos_threshold_note": "0.0 pour eviter le collapse silencieux des checkpoints 24l",
        "alba_note": "alba est cataloguee masculine (m, reading) chez Kyutai; generee car demandee, exclue du top 2 feminin",
    }

    rows = []
    ttfa_done = False
    for name in voices_fr + extras:
        feminine = name in voices_fr
        try:
            state = pocket_voice_state(model, name)
            audio, ttfa, total_s = pocket_generate(model, state, TEXT["fr"])
        except Exception:
            log(f"ECHEC voix {name}:\n{traceback.format_exc()}")
            continue
        if not ttfa_done and feminine:
            metrics["pockettts"]["ttfa_s"] = ttfa
            metrics["pockettts"]["ttfa_total_s"] = total_s
            metrics["pockettts"]["ttfa_voice"] = name
            metrics["pockettts"]["ttfa_note"] = (
                "premier chunk de generate_audio_stream() sur la phrase FR"
            )
            ttfa_done = True
            log(f"TTFA (premiere phrase FR, voix {name}): {ttfa:.3f}s  (total {total_s:.3f}s)")
        out = OUT_DIR / f"pockettts_{name}_fr.wav"
        info = save_wav(out, audio, model.sample_rate)
        native = to_mono_float(audio)
        info.update(
            {
                "system": "pockettts",
                "voice": name,
                "lang": "fr",
                "feminine": feminine,
                "synth_s": total_s,
                "ttfa_s": ttfa,
                "f0_hz": mean_f0_hz(native, model.sample_rate),
                "centroid_hz": spectral_centroid_hz(native, model.sample_rate),
            }
        )
        log(
            f"  {out.name}  dur={info['duration_s']:.2f}s  rms={info['rms']:.4f}  "
            f"f0={info['f0_hz']:.1f}Hz  synth={total_s:.3f}s"
        )
        if info["rms"] < 0.001:
            log(f"  WARNING: {out.name} quasi silencieux")
        rows.append(info)

    feminine_rows = [r for r in rows if r.get("feminine")]
    ranked = rank_grave(feminine_rows)
    metrics["pockettts"]["ranking_fr"] = [
        {
            "voice": r["voice"],
            "f0_hz": r["f0_hz"],
            "centroid_hz": r["centroid_hz"],
            "duration_s": r["duration_s"],
        }
        for r in ranked
    ]
    top2 = ranked[:2]
    log(f"top 2 graves/posees: {[r['voice'] for r in top2]}")
    metrics["pockettts"]["best_voice"] = top2[0]["voice"] if top2 else None

    del model

    if top2:
        model_en, load_en = pocket_load("english")
        metrics["pockettts"]["load_s_english"] = load_en
        for r in top2:
            try:
                state = pocket_voice_state(model_en, r["voice"])
                audio, _, total_s = pocket_generate(model_en, state, TEXT["en"])
                out = OUT_DIR / f"pockettts_{r['voice']}_en.wav"
                info = save_wav(out, audio, model_en.sample_rate)
                log(f"  {out.name}  dur={info['duration_s']:.2f}s  synth={total_s:.3f}s")
            except Exception:
                log(f"ECHEC en/{r['voice']}:\n{traceback.format_exc()}")
        del model_en

        try:
            model_es, load_es = pocket_load("spanish")
            metrics["pockettts"]["load_s_spanish"] = load_es
            spanish_ok = True
        except Exception:
            log("language=spanish a echoue, essai spanish_24l")
            log(traceback.format_exc())
            model_es, load_es = pocket_load("spanish_24l")
            metrics["pockettts"]["load_s_spanish"] = load_es
            metrics["pockettts"]["spanish_checkpoint"] = "spanish_24l (fallback)"
            spanish_ok = True
        if spanish_ok:
            metrics["pockettts"].setdefault("spanish_checkpoint", "spanish")
            for r in top2:
                try:
                    state = pocket_voice_state(model_es, r["voice"])
                    audio, _, total_s = pocket_generate(model_es, state, TEXT["es"])
                    out = OUT_DIR / f"pockettts_{r['voice']}_es.wav"
                    info = save_wav(out, audio, model_es.sample_rate)
                    log(f"  {out.name}  dur={info['duration_s']:.2f}s  synth={total_s:.3f}s")
                except Exception:
                    log(f"ECHEC es/{r['voice']}:\n{traceback.format_exc()}")
            del model_es

    return rows


def main() -> int:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    try:
        import torch

        torch.set_num_threads(4)
    except Exception:
        pass

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics: dict = {"out_dir": str(OUT_DIR), "target_sr": TARGET_SR, "text": TEXT}

    try:
        run_supertonic(metrics)
    except Exception:
        log("ECHEC SUPERSONIC/SUPERTONIC:\n" + traceback.format_exc())
        metrics["supertonic_error"] = traceback.format_exc()

    try:
        run_pocket(metrics)
    except Exception:
        log("ECHEC POCKET-TTS:\n" + traceback.format_exc())
        metrics["pockettts_error"] = traceback.format_exc()

    mesures = OUT_DIR / "mesures.json"
    mesures.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"\nmesures ecrites: {mesures}")
    log("\n===== fichiers =====")
    for p in sorted(OUT_DIR.iterdir()):
        log(f"  {p.name:40s} {p.stat().st_size:8d} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
