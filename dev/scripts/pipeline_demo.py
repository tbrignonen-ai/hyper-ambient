#!/usr/bin/env python3
"""
hyper-ambient end-to-end pipeline: EARS -> TURN -> BRAIN -> MOUTH.

Measures the NFR-01 round-trip budget with real numbers, broken down per
capability, so it is obvious which one is over budget.

    python3 dev/scripts/pipeline_demo.py --audio data/in/question.wav
    python3 dev/scripts/pipeline_demo.py --text "Quelle heure est-il à Paris ?"
    BRAIN_SERVICE=llamacpp python3 dev/scripts/pipeline_demo.py --text "..."

--text skips EARS/TURN and exercises BRAIN -> MOUTH only, which is the useful
mode while no microphone is wired (Docker Desktop has no audio device; capture
is the native host-agent's job).
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, "/workspace")

import numpy as np  # noqa: E402

BUDGET_MS = 1200  # NFR-01: perceived round-trip


def load_wav(path: str, target_sr: int = 16000) -> np.ndarray:
    import librosa

    audio, _ = librosa.load(path, sr=target_sr, mono=True)
    return audio.astype(np.float32)


async def run(args):
    marks = {}
    t_start = time.perf_counter()

    def mark(name):
        marks[name] = (time.perf_counter() - t_start) * 1000

    # ---- EARS + TURN -----------------------------------------------------
    if args.audio:
        from src.ears.faster_whisper_asr import FasterWhisperASR
        from src.turn.silero_turn import SileroTurnDetector

        audio = load_wav(args.audio)
        print(f"input: {args.audio} ({len(audio)/16000:.2f}s)")

        turn = SileroTurnDetector(min_silence_duration_ms=args.silence_ms)
        turn.load_model()  # ONNX session init — not part of the turn latency

        # A file ends exactly when the speaker stops, so the trailing silence
        # TURN needs never arrives and no endpoint is ever emitted. A live mic
        # keeps streaming; pad to reproduce that.
        pad = np.zeros(int(16000 * (args.silence_ms + 300) / 1000), dtype=np.float32)
        stream = np.concatenate([audio, pad])

        t_turn = time.perf_counter()
        events = []
        for i in range(0, len(stream), 1600):
            events += turn.process_chunk(stream[i : i + 1600])
        turn_ms = (time.perf_counter() - t_turn) * 1000
        endpoints = [e for e in events if e["event"] == "endpoint"]
        mark("turn")
        detail = f"at {endpoints[0]['t_s']:.2f}s" if endpoints else "NONE — check silence_ms"
        print(
            f"TURN  : {len(endpoints)} endpoint(s) {detail} — {turn_ms:.0f} ms compute "
            f"(RTF {turn_ms/1000/(len(stream)/16000):.4f})"
        )

        asr = FasterWhisperASR(model_size=args.asr_model, language="fr", device=args.device)
        await asr.load_model()
        t_asr = time.perf_counter()
        result = await asr.transcribe(audio)
        asr_ms = (time.perf_counter() - t_asr) * 1000
        prompt = result["text"]
        mark("ears")
        print(f"EARS  : \"{prompt}\" — {asr_ms:.0f} ms (RTF {result['rtf']:.3f})")
    else:
        prompt = args.text
        asr_ms = 0.0
        print(f"input : \"{prompt}\" (text mode, EARS/TURN skipped)")

    if not prompt.strip():
        print("nothing transcribed — aborting")
        return 1

    # ---- BRAIN -> MOUTH (streamed, overlapped) ---------------------------
    from src.brain.factory import build_brain, build_brain_with_fallback
    from src.mouth.piper_tts import PiperTTS

    brain = build_brain() if args.no_fallback else await build_brain_with_fallback()
    if args.no_fallback:
        await brain.initialize()
    health = await brain.health()
    print(f"BRAIN : {brain.name} @ {brain.api_endpoint} — {health['detail']}")

    tts = PiperTTS(model_path=args.voice)
    if not await tts.load_model():
        print("MOUTH : voice unavailable — run dev/scripts/fetch_models.sh core")
        await brain.close()
        return 1

    ttft_ms = None
    full_text = []
    brain_error = None

    async def deltas():
        nonlocal ttft_ms, brain_error
        async for chunk in brain.query_streaming(prompt):
            if chunk.get("ttft_ms") is not None:
                ttft_ms = chunk["ttft_ms"]
            if chunk["stop_reason"] == "error":
                brain_error = chunk.get("error", "unknown")
            if chunk["delta"]:
                full_text.append(chunk["delta"])
                yield chunk["delta"]

    t_gen = time.perf_counter()
    pcm_parts = []
    ttfa_perceived = None
    first_audio_ms = None
    n_chunks = 0

    async for out in tts.synthesize_stream(deltas()):
        if out.get("ttfa_perceived_ms") is not None:
            ttfa_perceived = out["ttfa_perceived_ms"]
        if len(out["audio"]):
            pcm_parts.append(out["audio"])
            n_chunks += 1
            if n_chunks == 1:
                first_audio_ms = (time.perf_counter() - t_gen) * 1000
                print(f"        first audio after {first_audio_ms:.0f} ms — \"{out['text'][:60]}\"")

    total_ms = (time.perf_counter() - t_start) * 1000
    await brain.close()

    text = "".join(full_text).strip()
    if not text:
        print(f"BRAIN : produced nothing — {brain_error}")
        return 1
    print(f"BRAIN : \"{text[:120]}{'...' if len(text) > 120 else ''}\"")

    if pcm_parts:
        pcm = np.concatenate(pcm_parts)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(tts.to_wav_bytes(pcm, tts.sample_rate))
        spoken_s = len(pcm) / tts.sample_rate
    else:
        spoken_s = 0.0

    # ---- budget ----------------------------------------------------------
    print()
    print("=" * 66)
    print("LATENCY BREAKDOWN (NFR-01 budget: {} ms)".format(BUDGET_MS))
    print("=" * 66)
    if args.audio:
        print(f"  EARS transcribe            {asr_ms:8.0f} ms")

    # Wall-clock, not the sum of the parts. When BRAIN demotes, the time spent
    # waiting on the abandoned backend belongs in the budget: summing the
    # reported components would credit us with the *local* TTFT and silently
    # drop the deadline we burned first.
    brain_to_audio = first_audio_ms if first_audio_ms is not None else 0.0
    reported_ttft = ttft_ms or 0.0
    reported_ttfa = ttfa_perceived or 0.0
    overhead = brain_to_audio - reported_ttft - reported_ttfa

    print(f"  BRAIN time-to-first-token  {reported_ttft:8.0f} ms  ({brain.name}"
          f"{', demoted' if getattr(brain, 'demoted', False) else ''})")
    print(f"  MOUTH time-to-first-audio  {reported_ttfa:8.0f} ms  (from first token)")
    if overhead > 20:
        print(f"  backend abandoned          {overhead:8.0f} ms  (deadline burned before demotion)")
    print(f"  {'-'*62}")
    perceived = (asr_ms or 0) + brain_to_audio
    verdict = "WITHIN BUDGET" if perceived <= BUDGET_MS else "OVER BUDGET"
    print(f"  perceived round-trip       {perceived:8.0f} ms  <- {verdict}")
    print(f"  full generation            {total_ms:8.0f} ms  ({n_chunks} audio chunks, {spoken_s:.1f}s speech)")
    print("=" * 66)
    print(f"wrote {args.out}")
    return 0


def main():
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--audio", help="input wav (any sample rate, resampled to 16k)")
    src.add_argument("--text", help="skip EARS/TURN, feed BRAIN directly")
    p.add_argument("--asr-model", default=os.getenv("EARS_MODEL", "large-v3-turbo"))
    p.add_argument("--device", default="cuda")
    p.add_argument("--silence-ms", type=int, default=700)
    p.add_argument("--voice", default="/workspace/models/piper/fr_FR-tom-medium.onnx")
    p.add_argument("--out", default="/workspace/data/out/reply.wav")
    p.add_argument("--no-fallback", action="store_true",
                   help="use the configured backend only, never demote to llama.cpp")
    args = p.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
