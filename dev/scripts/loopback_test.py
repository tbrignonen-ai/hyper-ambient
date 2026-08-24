#!/usr/bin/env python3
"""
Closed-loop MOUTH -> EARS check.

Piper speaks a known French sentence, Whisper transcribes it back. This gives
a real RTF (synthetic tones make Whisper hallucinate in a loop, which inflates
RTF by 10x and measures nothing) plus a crude WER sanity check on French.
"""
import asyncio
import re
import sys
import time

sys.path.insert(0, "/workspace")

import numpy as np  # noqa: E402

SENTENCES = [
    "Bonjour, je voudrais connaître la météo à Paris pour demain matin.",
    "Le facteur temps réel doit rester inférieur à un pour tenir le budget.",
    "Peux-tu me rappeler à quelle heure commence la réunion de mardi ?",
]


def norm(s: str) -> list:
    return re.sub(r"[^\w\s]", "", s.lower(), flags=re.UNICODE).split()


def wer(ref: str, hyp: str) -> float:
    r, h = norm(ref), norm(hyp)
    d = np.zeros((len(r) + 1, len(h) + 1), dtype=np.int32)
    d[:, 0] = np.arange(len(r) + 1)
    d[0, :] = np.arange(len(h) + 1)
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + cost)
    return d[len(r), len(h)] / max(len(r), 1)


async def main():
    from src.ears.faster_whisper_asr import FasterWhisperASR
    from src.mouth.piper_tts import PiperTTS

    model_size = sys.argv[1] if len(sys.argv) > 1 else "large-v3-turbo"

    tts = PiperTTS()
    assert await tts.load_model(), "piper voice missing — run fetch_models.sh core"

    asr = FasterWhisperASR(model_size=model_size, language="fr", device="cuda")
    assert await asr.load_model(), f"could not load {model_size}"

    # warm up CUDA kernels / cuDNN autotune so run 1 is not the outlier
    await asr.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1)

    print(f"EARS model: {model_size}")
    print("-" * 74)
    rtfs, wers = [], []

    for ref in SENTENCES:
        spoken = await tts.synthesize(ref)
        # Piper outputs 22050 Hz int16; Whisper wants 16 kHz float32 mono
        import librosa

        pcm = spoken["audio"].astype(np.float32) / 32768.0
        pcm16k = librosa.resample(pcm, orig_sr=spoken["sample_rate"], target_sr=16000)

        t0 = time.perf_counter()
        out = await asr.transcribe(pcm16k, beam_size=1)
        elapsed = time.perf_counter() - t0

        dur = len(pcm16k) / 16000
        rtf = elapsed / dur
        e = wer(ref, out["text"])
        rtfs.append(rtf)
        wers.append(e)

        print(f"  ref : {ref}")
        print(f"  hyp : {out['text'].strip()}")
        print(f"  {dur:.2f}s audio | ASR {elapsed*1000:6.0f} ms | RTF {rtf:.3f} | WER {e:.1%}")
        print("-" * 74)

    print(f"mean RTF {np.mean(rtfs):.3f}   mean WER {np.mean(wers):.1%}")
    print(f"MOUTH mean TTFA {np.mean(tts.ttfa_history):.0f} ms")


if __name__ == "__main__":
    asyncio.run(main())
