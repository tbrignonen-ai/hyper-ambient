#!/usr/bin/env python3
"""
Render A/B samples so the hyper-ambient voice can be chosen by ear, not by argument.

    python3 dev/scripts/voice_lab.py                # all voices x all profiles
    python3 dev/scripts/voice_lab.py --voice siwis  # one voice, all profiles

Writes data/out/voice_lab/<voice>__<profile>.wav and prints the synthesis cost
of each, because a voice that misses the latency budget is not a candidate.
"""
import argparse
import asyncio
import glob
import os
import sys

sys.path.insert(0, "/workspace")

VOICE_DIR = "/workspace/models/piper"
OUT_DIR = "/workspace/data/out/voice_lab"

LINE = (
    "Attention. Le facteur temps réel a dépassé le seuil critique. "
    "Je recommande une intervention immédiate."
)


async def render(voice_path, profile, speaker_id, text):
    from src.mouth.piper_tts import PiperTTS

    tts = PiperTTS(model_path=voice_path, profile=profile, speaker_id=speaker_id)
    if not await tts.load_model():
        return None
    out = await tts.synthesize(text)
    name = os.path.basename(voice_path).replace(".onnx", "")
    if speaker_id is not None:
        name += f"-spk{speaker_id}"
    dest = os.path.join(OUT_DIR, f"{name}__{profile}.wav")
    with open(dest, "wb") as f:
        f.write(tts.to_wav_bytes(out["audio"], out["sample_rate"]))
    return dest, out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", help="substring filter, e.g. siwis")
    ap.add_argument("--profiles", default="flat,mother,alert")
    ap.add_argument("--speaker", type=int, action="append",
                    help="speaker id for multi-speaker voices (repeatable)")
    ap.add_argument("--text", default=LINE)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    voices = sorted(glob.glob(os.path.join(VOICE_DIR, "*.onnx")))
    if args.voice:
        voices = [v for v in voices if args.voice in v]
    if not voices:
        print("no voice matched")
        return 1

    speakers = args.speaker or [None]
    print(f'texte : "{args.text}"')
    print("-" * 78)
    for v in voices:
        for spk in speakers:
            for profile in args.profiles.split(","):
                res = await render(v, profile, spk, args.text)
                if res is None:
                    print(f"  {os.path.basename(v)} — échec de chargement")
                    continue
                dest, out = res
                print(f"  {os.path.basename(dest):<48} "
                      f"{out['duration_s']:5.2f}s audio | synth {out['synth_ms']:5.0f} ms "
                      f"| RTF {out['rtf']:.3f}")
    print("-" * 78)
    print(f"écrits dans {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
