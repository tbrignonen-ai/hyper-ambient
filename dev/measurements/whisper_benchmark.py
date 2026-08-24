"""
Benchmark: Measure Real-Time Factor (RTF) of Whisper ASR.

CRITICAL [À VÉRIFIER]: RTF must be < 1.5 for PROFILE_MEDIUM.

Usage:
    python dev/measurements/whisper_benchmark.py [audio_file] [model_size]
"""
import asyncio
import sys
import time
import logging
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ears.whisper import WhisperASR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def benchmark_whisper(
    audio_file: str = None,
    model_size: str = "tiny",
    device: str = "cuda"
):
    """
    Benchmark Whisper RTF on audio file.

    Args:
        audio_file: path to audio file (WAV, MP3, etc.)
        model_size: tiny, base, small
        device: cuda or cpu
    """
    logger.info(f"Starting Whisper benchmark: {model_size} on {device}")

    asr = WhisperASR(model_size=model_size, language="fr")

    try:
        await asr.load_model(device=device)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    # Mock audio if no file provided
    if audio_file is None:
        logger.warning("No audio file provided, using mock audio (30 seconds)")
        sample_rate = 16000
        audio_duration_sec = 30
        audio = np.random.randn(sample_rate * audio_duration_sec).astype(np.float32) * 0.1
    else:
        try:
            import librosa
            audio, sample_rate = librosa.load(audio_file, sr=16000, mono=True)
            audio_duration_sec = len(audio) / sample_rate
        except ImportError:
            logger.error("librosa not installed, cannot load audio file")
            return
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            return

    logger.info(f"Audio: {audio_duration_sec:.1f}s @ {sample_rate}Hz")

    # Benchmark
    start = time.time()
    result = await asr.transcribe_stream(audio, sample_rate=sample_rate)
    processing_time = time.time() - start

    rtf = processing_time / audio_duration_sec if audio_duration_sec > 0 else 0

    logger.info(f"\n=== BENCHMARK RESULTS ===")
    logger.info(f"Model size:        {model_size}")
    logger.info(f"Device:            {device}")
    logger.info(f"Audio duration:    {audio_duration_sec:.1f}s")
    logger.info(f"Processing time:   {processing_time:.1f}s")
    logger.info(f"RTF:               {rtf:.2f}")
    logger.info(f"Status:            {'✓ PASS' if rtf < 1.5 else '✗ FAIL (RTF > 1.5)'}")
    logger.info(f"Result:            {result.get('partial', '')[:100]}")

    revision_rate = await asr.get_revision_rate()
    logger.info(f"Revision rate:     {revision_rate:.2%}")

    await asr.close()

    return {"rtf": rtf, "status": "pass" if rtf < 1.5 else "fail"}


if __name__ == "__main__":
    audio_file = sys.argv[1] if len(sys.argv) > 1 else None
    model_size = sys.argv[2] if len(sys.argv) > 2 else "tiny"
    device = sys.argv[3] if len(sys.argv) > 3 else "cuda"

    asyncio.run(benchmark_whisper(audio_file, model_size, device))
