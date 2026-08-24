"""
MOUTH: MOSS-TTS-Nano-100M for streaming synthesis (CPU-capable).

Apache-2.0 license, 224 MB, French (20 languages total).
Can run on 4-core CPU with dedicated ONNX build.
"""
import asyncio
import logging
from typing import Dict, Any, AsyncIterator, Optional
import numpy as np

logger = logging.getLogger(__name__)


class MOSSTTS:
    """MOSS-TTS streaming synthesis engine (CPU-friendly)."""

    def __init__(self, language: str = "fr", sample_rate: int = 22050):
        """
        Initialize MOSS-TTS.

        Args:
            language: language code (fr for French)
            sample_rate: output sample rate in Hz (22050 is default)
        """
        self.language = language
        self.sample_rate = sample_rate
        self.model = None
        self.latency_history = []
        logger.info(f"MOSSTTS initialized: {language}, {sample_rate}Hz")

    async def load_model(self, device: str = "cpu", use_onnx: bool = True):
        """
        Load MOSS-TTS model.

        Args:
            device: cpu or cuda
            use_onnx: use ONNX Runtime for better CPU performance
        """
        try:
            logger.info(f"Loading MOSS-TTS on {device} (ONNX={use_onnx})")
            self.model = {
                "device": device,
                "use_onnx": use_onnx,
                "params": 100_000_000,  # 100M nominal
                "size_bytes": 224_000_000  # 224 MB
            }
            logger.info(f"MOSS-TTS loaded: {self.language}")

        except Exception as e:
            logger.error(f"Failed to load MOSS-TTS: {e}")
            raise

    async def synthesize_streaming(
        self,
        text: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Synthesize text with streaming audio chunks (CPU-capable).

        Args:
            text: text to synthesize

        Yields:
            {
                "audio_chunk": np.ndarray,
                "sample_rate": 22050,
                "duration_ms": 100,
                "is_final": False,
                "latency_ms": 45.0
            }
        """
        if self.model is None:
            logger.error("Model not loaded")
            return

        import time
        start_time = time.time()

        try:
            # Stub: simulate streaming synthesis
            chunks = max(2, len(text) // 8)

            for i in range(chunks):
                # Mock audio
                chunk_samples = int(self.sample_rate * 0.1)
                audio_chunk = np.random.randn(chunk_samples).astype(np.float32) * 0.01

                latency_ms = (time.time() - start_time) * 1000
                self.latency_history.append(latency_ms)

                yield {
                    "audio_chunk": audio_chunk,
                    "sample_rate": self.sample_rate,
                    "duration_ms": 100,
                    "is_final": (i == chunks - 1),
                    "latency_ms": latency_ms
                }

                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            yield {"error": str(e), "is_final": True}

    async def get_average_latency(self) -> Optional[float]:
        """
        Get average synthesis latency from recent calls.

        Returns:
            Average latency in ms, or None if not measured
        """
        if not self.latency_history:
            return None
        return np.mean(self.latency_history[-10:])

    async def close(self):
        """Cleanup resources."""
        self.model = None
        logger.info("MOSSTTS closed")
