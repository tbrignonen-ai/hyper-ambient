#!/usr/bin/env python3
"""
Exercise the two-channel router end to end, with the timeline that matters:
when does MOTHER first make a sound, and which channel eventually answers.

    python3 dev/scripts/router_demo.py
    python3 dev/scripts/router_demo.py --no-filler   # show the naked escalation cost
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, "/workspace")

import numpy as np  # noqa: E402

PROMPTS = [
    "Bonjour MOTHER.",
    "Merci, c'est noté.",
    "Il est 14 h 40, ma réunion dure quarante minutes et commence dans vingt minutes, à quelle heure je finis ?",
    "Quel est le rôle du facteur temps réel dans un système de dialogue ?",
]


async def run_one(router, tts, prompt, out_path):
    print(f'\n> "{prompt}"')
    t0 = time.perf_counter()
    first_audio_ms = None
    channels = []
    pcm_parts = []
    said = []

    async def deltas():
        async for chunk in router.query_streaming(prompt):
            if chunk["stop_reason"] == "error":
                print(f"    ! {str(chunk.get('error'))[:100]}")
                continue
            if chunk["delta"]:
                channels.append(chunk.get("channel", "?"))
                said.append((chunk.get("channel"), chunk["delta"]))
                yield {"text": chunk["delta"], "flush": chunk.get("flush", False)}

    async for out in tts.synthesize_stream(deltas()):
        if not len(out["audio"]):
            continue
        pcm_parts.append(out["audio"])
        if first_audio_ms is None:
            first_audio_ms = (time.perf_counter() - t0) * 1000
            tag = "filler" if out.get("flushed") else "answer"
            print(f'    premier son {first_audio_ms:6.0f} ms  [{tag}] "{out["text"][:48]}"')

    total_ms = (time.perf_counter() - t0) * 1000
    used = []
    for c in channels:
        if not used or used[-1] != c:
            used.append(c)
    text = "".join(d for _, d in said)
    print(f"    canaux : {' -> '.join(used)}")
    print(f'    réponse: "{text[:150]}{"…" if len(text) > 150 else ""}"')
    print(f"    complet {total_ms:6.0f} ms")

    if pcm_parts:
        pcm = np.concatenate(pcm_parts)
        with open(out_path, "wb") as f:
            f.write(tts.to_wav_bytes(pcm, tts.sample_rate))
    return first_audio_ms


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-filler", action="store_true")
    ap.add_argument("--profile", default="mother")
    args = ap.parse_args()

    from src.brain.factory import build_router
    from src.mouth.piper_tts import PiperTTS

    router = await build_router()
    router.enable_filler = not args.no_filler
    print(f"router  : {router.api_endpoint}")
    print(f"santé   : {(await router.health())['detail']}")

    tts = PiperTTS(profile=args.profile)
    if not await tts.load_model():
        print("voix indisponible")
        return 1

    os.makedirs("/workspace/data/out/router", exist_ok=True)
    firsts = []
    for i, p in enumerate(PROMPTS):
        ms = await run_one(router, tts, p, f"/workspace/data/out/router/turn{i}.wav")
        if ms:
            firsts.append(ms)

    print("\n" + "=" * 70)
    print(f"routage : {router.stats}")
    if firsts:
        print(f"premier son : min {min(firsts):.0f} / max {max(firsts):.0f} ms "
              f"(budget 1200 ms)")
    print("=" * 70)
    await router.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
