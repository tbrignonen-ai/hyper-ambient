#!/usr/bin/env python3
"""
Compare local BRAIN candidates head-to-head on the realtime voice criteria.

    python3 dev/scripts/bench_brain.py ministral=http://localhost:8080 luth=http://localhost:8082

Latency alone does not decide this. A 22 ms model that answers wrong, or that
emits markdown a TTS will read aloud as "astérisque astérisque", is not a
cheaper option — it is a worse product. So the bench scores four axes:

  speed      TTFT and char/s
  accuracy   a two-step arithmetic probe, N samples (small models fail it)
  behaviour  does it ask on an ambiguous request, or invent?
  speakable  markdown/emoji pollution rate — measured, not assumed
"""
import argparse
import asyncio
import re
import statistics
import sys
import time

sys.path.insert(0, "/workspace")

from src.mouth.normalize import VOICE_SYSTEM_PROMPT, strip_markup  # noqa: E402

# Two chained steps: start = 14:40 + 20 min = 15:00, end = +40 min = 15:40.
ARITH_Q = (
    "Il est 14 h 40. Ma réunion dure quarante minutes et commence dans vingt "
    "minutes. À quelle heure je finis ?"
)
ARITH_OK = re.compile(r"15\s*[h:.]\s*40")

PROMPTS = [
    ("factuel", "Pourquoi le facteur temps réel doit-il rester inférieur à un ?"),
    ("registre", "Rappelle-moi d'appeler le dentiste demain matin, tu peux ?"),
    ("ambigu", "Mets-le à jour s'il te plaît."),
    ("nombres", "Il est quelle heure s'il est 15 h 47 et 30 secondes ?"),
]

_MARKUP = re.compile(r"\*{1,3}|_{2,}|^#{1,6}\s|`|\[[^\]]*\]\(", re.MULTILINE)


async def collect(brain, prompt, system):
    """Run one prompt, return (ttft_ms, chars_per_s, text) or (None, None, err)."""
    t0 = time.perf_counter()
    ttft = None
    parts = []
    async for chunk in brain.query_streaming(prompt, system=system, temperature=0.2):
        if chunk.get("ttft_ms") is not None:
            ttft = chunk["ttft_ms"]
        if chunk["stop_reason"] == "error":
            return None, None, f"ERROR: {str(chunk.get('error'))[:120]}"
        if chunk["delta"]:
            parts.append(chunk["delta"])
    text = "".join(parts).strip()
    gen_ms = max((time.perf_counter() - t0) * 1000 - (ttft or 0), 1)
    return ttft, len(text) / (gen_ms / 1000), text


async def bench(label, host, samples, system):
    from src.brain.openai_compat import LlamaCppBrain

    brain = LlamaCppBrain(host=host, model="local")
    await brain.initialize()
    await collect(brain, "Bonjour.", system)  # warm the slot

    print("=" * 78)
    print(f"{label}   ({host})")
    print("=" * 78)

    ttfts, rates, polluted = [], [], 0
    for tag, p in PROMPTS:
        ttft, rate, text = await collect(brain, p, system)
        if ttft is None:
            print(f"  [{tag}] {text}\n")
            continue
        ttfts.append(ttft)
        rates.append(rate)
        dirty = bool(_MARKUP.search(text)) or strip_markup(text) != text
        polluted += dirty
        print(f"  [{tag}] Q: {p}")
        print(f"          A: {text[:220]}{'…' if len(text) > 220 else ''}")
        print(f"             TTFT {ttft:.0f} ms | {rate:.0f} char/s"
              f"{'  | MARKUP' if dirty else ''}")
        print()

    ok = 0
    answers = []
    for _ in range(samples):
        _, _, text = await collect(brain, ARITH_Q, system)
        good = bool(text and ARITH_OK.search(text))
        ok += good
        answers.append(("OK " if good else "KO ") + (text or "")[:60].replace("\n", " "))
    print(f"  [arithmétique 2 étapes] attendu 15 h 40 — {ok}/{samples}")
    for a in answers:
        print(f"      {a}")
    print()

    await brain.close()
    if ttfts:
        print(f"  >> TTFT médian {statistics.median(ttfts):.0f} ms"
              f" | débit médian {statistics.median(rates):.0f} char/s"
              f" | markup {polluted}/{len(PROMPTS)}"
              f" | arithmétique {ok}/{samples}")
    print()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+", help="label=http://host:port")
    ap.add_argument("--samples", type=int, default=5, help="arithmetic repetitions")
    ap.add_argument("--raw-system", action="store_true",
                    help="use a bare prompt instead of the voice prompt "
                         "(shows how much markup the voice prompt suppresses)")
    args = ap.parse_args()

    system = (
        "Tu es un assistant en français. Réponds brièvement."
        if args.raw_system
        else VOICE_SYSTEM_PROMPT
    )

    for t in args.targets:
        label, _, host = t.partition("=")
        await bench(label, host, args.samples, system)


if __name__ == "__main__":
    asyncio.run(main())
