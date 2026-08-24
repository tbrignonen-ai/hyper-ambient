#!/usr/bin/env python3
"""
MOTHER container smoke test — verifies every capability actually runs.

Run inside the container:
    python3 dev/scripts/smoke_test.py

Prints one line per capability with a real measurement, not a "should work".
"""
import asyncio
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/workspace")

import numpy as np  # noqa: E402

OK, KO, SKIP = "  OK  ", " FAIL ", " SKIP "
results = []


def report(cap, status, detail):
    results.append((cap, status, detail))
    print(f"[{status}] {cap:<22} {detail}")


def synth_speechlike(duration_s=3.0, sr=16000):
    """Deterministic voiced/unvoiced signal — enough to exercise VAD paths."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    f0 = 120 + 20 * np.sin(2 * np.pi * 3 * t)
    sig = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in (1, 2, 3, 4))
    envelope = (np.sin(2 * np.pi * 0.7 * t) > -0.2).astype(np.float32)  # speech/pause
    return (0.3 * sig * envelope).astype(np.float32)


# --------------------------------------------------------------------------


def check_gpu():
    try:
        import torch

        if not torch.cuda.is_available():
            return report("GPU / CUDA", KO, "torch.cuda.is_available() == False")
        name = torch.cuda.get_device_name(0)
        free, total = torch.cuda.mem_get_info()
        report("GPU / CUDA", OK, f"{name} — {free/2**30:.1f}/{total/2**30:.1f} GiB free")
    except Exception as e:
        report("GPU / CUDA", KO, str(e))


def check_binaries():
    for binary, cap in (("llama-server", "BRAIN llama.cpp"), ("whisper-cli", "EARS whisper.cpp")):
        path = shutil.which(binary)
        if not path:
            report(cap, KO, f"{binary} not on PATH")
            continue
        try:
            out = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=30
            )
            blob = (out.stdout + out.stderr).strip().splitlines()
            ver = next((l for l in blob if l.strip()), "no version output")
            report(cap, OK, f"{path} — {ver[:70]}")
        except Exception as e:
            report(cap, KO, f"{binary}: {e}")


def check_cuda_devices_seen_by_ggml():
    """ggml prints its detected devices on stderr at startup."""
    if not shutil.which("llama-server"):
        return report("ggml CUDA backend", SKIP, "llama-server missing")
    try:
        out = subprocess.run(
            ["llama-server", "--list-devices"], capture_output=True, text=True, timeout=60
        )
        blob = out.stdout + out.stderr
        gpu_lines = [l.strip() for l in blob.splitlines() if "CUDA" in l and "MiB" in l]
        if gpu_lines:
            report("ggml CUDA backend", OK, gpu_lines[0][:80])
        else:
            report("ggml CUDA backend", KO, "no CUDA device listed by ggml")
    except Exception as e:
        report("ggml CUDA backend", KO, str(e))


async def check_ears():
    from src.ears.faster_whisper_asr import FasterWhisperASR

    model_size = os.getenv("SMOKE_ASR_MODEL", "base")
    asr = FasterWhisperASR(model_size=model_size, language="fr", device="cuda")
    if not await asr.load_model():
        return report("EARS faster-whisper", KO, f"could not load {model_size}")

    audio = synth_speechlike(5.0)
    out = await asr.transcribe(audio, beam_size=1)
    report(
        "EARS faster-whisper",
        OK,
        f"{model_size} — RTF {out['rtf']:.3f} on {out['audio_duration_s']:.1f}s "
        f"({out['latency_ms']:.0f} ms)",
    )


def check_turn():
    from src.turn.silero_turn import SileroTurnDetector

    det = SileroTurnDetector(min_silence_duration_ms=400)
    if not det.load_model():
        return report("TURN silero-vad", KO, "model load failed")

    audio = synth_speechlike(6.0)
    t0 = time.perf_counter()
    events = []
    for i in range(0, len(audio), 1600):  # 100 ms host-agent frames
        events += det.process_chunk(audio[i : i + 1600])
    elapsed = time.perf_counter() - t0
    kinds = [e["event"] for e in events]
    report(
        "TURN silero-vad",
        OK if events else KO,
        f"{len(events)} events {kinds[:4]} — {elapsed*1000:.0f} ms for 6 s "
        f"(RTF {elapsed/6:.4f})",
    )


async def check_mouth():
    from src.mouth.piper_tts import PiperTTS

    voice = "/workspace/models/piper/fr_FR-siwis-medium.onnx"
    if not os.path.exists(voice):
        return report("MOUTH piper", SKIP, "voice missing — run fetch_models.sh core")

    tts = PiperTTS(model_path=voice)
    if not await tts.load_model():
        return report("MOUTH piper", KO, "voice load failed")

    out = await tts.synthesize("Bonjour, je suis MOTHER. Comment puis-je vous aider ?")
    wav = tts.to_wav_bytes(out["audio"], out["sample_rate"])
    os.makedirs("/workspace/data/out", exist_ok=True)
    with open("/workspace/data/out/smoke_tts.wav", "wb") as f:
        f.write(wav)
    report(
        "MOUTH piper",
        OK,
        f"TTFA {out['ttfa_ms']:.0f} ms, {out['duration_s']:.2f}s audio, "
        f"RTF {out['rtf']:.3f} -> data/out/smoke_tts.wav",
    )


def check_acoustic():
    import pyloudnorm as pyln

    audio = synth_speechlike(3.0).astype(np.float64)
    meter = pyln.Meter(16000)
    lufs = meter.integrated_loudness(audio)
    report("ACOUSTIC loudness", OK, f"EBU R128 integrated: {lufs:.1f} LUFS")


async def check_brain():
    from src.brain.factory import build_brain

    service = os.getenv("BRAIN_SERVICE", "stepfun")
    brain = build_brain(service)
    await brain.initialize()
    health = await brain.health()
    await brain.close()
    detail = f"{brain.name} @ {brain.api_endpoint} — {health['detail']} ({health['latency_ms']:.0f} ms)"
    report("BRAIN reachability", OK if health["ok"] else KO, detail)


async def main():
    print("=" * 78)
    print("MOTHER smoke test")
    print("=" * 78)
    check_gpu()
    check_binaries()
    check_cuda_devices_seen_by_ggml()
    check_turn()
    check_acoustic()
    await check_ears()
    await check_mouth()
    await check_brain()

    print("=" * 78)
    failed = [r for r in results if r[1] == KO]
    skipped = [r for r in results if r[1] == SKIP]
    print(f"{len(results) - len(failed) - len(skipped)} ok, {len(failed)} failed, {len(skipped)} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
