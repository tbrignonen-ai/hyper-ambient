"""
Benchmark: Evaluate False Endpoint Rate of Pipecat Smart Turn.

CRITICAL [À VÉRIFIER]: FPR must be < 0.15 (15%).

Test cases from benchmark-protocol.md:
  A01: Mid-sentence pause (1-3s), then resume
  A02: Filled pauses (uh, euh, hm), then speech
  A03: Overlapping speech (two speakers)
  A04: Long silence after question (5-10s)

Usage:
    python dev/measurements/pipecat_turn_eval.py
"""
import asyncio
import sys
import logging
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from turn.pipecat_adapter import PipecatSmartTurn
from turn.vad_fallback import VADEndpointDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def evaluate_turn(device: str = "cuda"):
    """
    Evaluate Pipecat Smart Turn on adversarial corpus.

    Args:
        device: cuda or cpu
    """
    logger.info("Starting Pipecat Smart Turn evaluation")

    turn = PipecatSmartTurn(language="fr", confidence_threshold=0.6)

    try:
        await turn.load_model(device=device)
    except Exception as e:
        logger.error(f"Failed to load Pipecat: {e}")
        return

    # Mock test cases
    test_cases = {
        "A01_pause": {
            "description": "Mid-sentence pause (1-3s), then resume",
            "audio": np.random.randn(16000 * 3).astype(np.float32),
            "ground_truth_endpoints": [16000, 48000],  # Pause and resume
            "expected_false_breaks": 0
        },
        "A02_filled_pause": {
            "description": "Filled pauses (uh, euh, hm), then speech",
            "audio": np.random.randn(16000 * 2).astype(np.float32),
            "ground_truth_endpoints": [],
            "expected_false_breaks": 0
        },
        "A03_overlap": {
            "description": "Overlapping speech (two speakers)",
            "audio": np.random.randn(16000 * 2).astype(np.float32),
            "ground_truth_endpoints": [],
            "expected_false_breaks": 0
        },
        "A04_long_silence": {
            "description": "Long silence after question (5-10s)",
            "audio": np.random.randn(16000 * 10).astype(np.float32),
            "ground_truth_endpoints": [16000 * 3],  # Silent for 3s, then response
            "expected_false_breaks": 0
        }
    }

    results = {}
    total_false_positives = 0
    total_predictions = 0

    for case_name, case_data in test_cases.items():
        logger.info(f"\n=== Test Case: {case_name} ===")
        logger.info(f"Description: {case_data['description']}")

        # Simulate endpoint detection on chunks
        audio = case_data["audio"]
        chunk_size = 16000 // 50  # 20ms chunks
        false_breaks = 0
        predicted_endpoints = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            result = await turn.detect_endpoint(
                chunk,
                partial_transcript="[mock transcript]"
            )

            if result["endpoint_detected"]:
                predicted_endpoints.append(i)
                false_breaks += 1  # Mock: assume it's false for now

            total_predictions += 1

        logger.info(f"Predicted endpoints: {len(predicted_endpoints)}")
        logger.info(f"False breaks (estimated): {false_breaks}")

        results[case_name] = {
            "false_breaks": false_breaks,
            "total_predictions": total_predictions
        }

        total_false_positives += false_breaks

    # Summary
    fpr = total_false_positives / total_predictions if total_predictions > 0 else 0

    logger.info(f"\n=== EVALUATION RESULTS ===")
    logger.info(f"Total predictions: {total_predictions}")
    logger.info(f"Total false breaks: {total_false_positives}")
    logger.info(f"False Positive Rate (FPR): {fpr:.2%}")
    logger.info(f"Status: {'✓ PASS' if fpr < 0.15 else '✗ FAIL (FPR > 15%)'}")

    if fpr > 0.15:
        logger.warning("FPR exceeds 15% threshold. Consider falling back to VAD (TURN-L1).")

    await turn.close()

    return {"fpr": fpr, "status": "pass" if fpr < 0.15 else "fail"}


if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "cuda"
    asyncio.run(evaluate_turn(device))
