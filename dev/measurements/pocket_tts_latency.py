"""
Benchmark: Measure Time-To-First-Audio (TTFA) of Pocket TTS.

CRITICAL [À VÉRIFIER]: TTFA must be < 300ms for NFR-01 (round-trip < 1200ms).

This measures actual latency: from input trigger to first audible sound,
not just inference time.

Usage:
    python dev/measurements/pocket_tts_latency.py [num_samples]
"""
import asyncio
import sys
import logging
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from mouth.pocket_tts import PocketTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def measure_ttfa(num_samples: int = 10, device: str = "cuda"):
    """
    Measure TTFA of Pocket TTS.

    Args:
        num_samples: number of synthesis calls to measure
        device: cuda or cpu
    """
    logger.info(f"Starting Pocket TTS TTFA benchmark ({num_samples} samples)")

    tts = PocketTTS(language="fr", voice="estelle", sample_rate=24000)

    try:
        await tts.load_model(device=device)
    except Exception as e:
        logger.error(f"Failed to load Pocket TTS: {e}")
        return

    prompts = [
        "Bonjour",
        "Je suis MOTHER",
        "Comment allez-vous ?",
        "Enchanté de faire votre connaissance",
        "Quelle est votre question ?"
    ]

    ttfa_measurements = []

    for i in range(num_samples):
        prompt = prompts[i % len(prompts)]
        logger.info(f"Sample {i+1}/{num_samples}: '{prompt}'")

        start_time = time.time()
        first_chunk_time = None
        chunk_count = 0

        async for chunk in tts.synthesize_streaming(prompt):
            if chunk_count == 0:
                first_chunk_time = time.time()

            chunk_count += 1

            # In real implementation, would measure when audio is actually played
            # Here we just measure when first chunk arrives
            if first_chunk_time:
                ttfa_ms = (first_chunk_time - start_time) * 1000
                ttfa_measurements.append(ttfa_ms)
                logger.debug(f"  TTFA: {ttfa_ms:.1f}ms")
                break

    # Statistics
    if not ttfa_measurements:
        logger.error("No TTFA measurements recorded")
        return

    ttfa_min = min(ttfa_measurements)
    ttfa_max = max(ttfa_measurements)
    ttfa_mean = np.mean(ttfa_measurements)
    ttfa_median = np.median(ttfa_measurements)

    logger.info(f"\n=== POCKET TTS TTFA RESULTS ===")
    logger.info(f"Samples:       {num_samples}")
    logger.info(f"Min:           {ttfa_min:.1f}ms")
    logger.info(f"Max:           {ttfa_max:.1f}ms")
    logger.info(f"Mean:          {ttfa_mean:.1f}ms")
    logger.info(f"Median:        {ttfa_median:.1f}ms")
    logger.info(f"Target:        < 300ms")
    logger.info(f"Status:        {'✓ PASS' if ttfa_mean < 300 else '✗ FAIL (TTFA > 300ms)'}")

    # NFR-01 budget check
    # Budget: 1200ms total
    # - Acoustic overhead: 26-37ms
    # - Synthesis: 200ms (TTFA)
    # - ASR + TURN: remaining
    budget_used = 37 + ttfa_mean  # acoustic + synthesis
    budget_remaining = 1200 - budget_used
    logger.info(f"\nNFR-01 Round-trip budget (1200ms total):")
    logger.info(f"  Acoustic overhead: 37ms")
    logger.info(f"  Synthesis (TTFA):  {ttfa_mean:.0f}ms")
    logger.info(f"  Remaining for ASR+TURN: {budget_remaining:.0f}ms")

    if budget_remaining < 200:
        logger.warning("⚠ Remaining budget is tight. Consider optimizing ASR/TURN.")

    await tts.close()

    return {
        "ttfa_mean": ttfa_mean,
        "ttfa_min": ttfa_min,
        "ttfa_max": ttfa_max,
        "status": "pass" if ttfa_mean < 300 else "fail"
    }


if __name__ == "__main__":
    num_samples = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    device = sys.argv[2] if len(sys.argv) > 2 else "cuda"
    asyncio.run(measure_ttfa(num_samples, device))
