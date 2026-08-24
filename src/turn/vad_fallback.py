"""
TURN: VAD (Voice Activity Detection) fallback for endpoint detection.

When learned model (Pipecat) is unavailable, use simple silence detection.
This is TURN-L1 conformance level.
"""
import asyncio
import logging
from typing import Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


class VADEndpointDetector:
    """
    Voice Activity Detection based endpoint detector (L1 fallback).

    Simple algorithm: count consecutive silent frames.
    """

    def __init__(
        self,
        silence_threshold_db: float = -40.0,
        silence_duration_ms: int = 800,
        sample_rate: int = 16000
    ):
        """
        Initialize VAD endpoint detector.

        Args:
            silence_threshold_db: RMS energy threshold for silence
            silence_duration_ms: how long until we declare endpoint
            sample_rate: sample rate in Hz
        """
        self.silence_threshold_db = silence_threshold_db
        self.silence_duration_ms = silence_duration_ms
        self.sample_rate = sample_rate
        self.silent_frame_count = 0
        self.total_frames = 0
        logger.info(f"VADEndpointDetector: threshold={silence_threshold_db}dB, duration={silence_duration_ms}ms")

    def _compute_rms(self, audio: np.ndarray) -> float:
        """Compute RMS energy of audio in dB."""
        if len(audio) == 0:
            return -100.0
        rms = np.sqrt(np.mean(audio ** 2))
        # Avoid log(0)
        if rms < 1e-10:
            return -100.0
        return 20 * np.log10(rms)

    async def detect_endpoint(
        self,
        audio_chunk: np.ndarray,
        sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        Detect endpoint based on silence duration.

        Args:
            audio_chunk: audio samples for this frame (typically 20ms)
            sample_rate: sample rate in Hz

        Returns:
            {
                "endpoint_detected": False,
                "confidence": 0.0,
                "silence_duration_ms": 0,
                "is_silent": False
            }
        """
        self.total_frames += 1

        # Compute RMS energy
        rms_db = self._compute_rms(audio_chunk)
        is_silent = rms_db < self.silence_threshold_db

        if is_silent:
            self.silent_frame_count += 1
        else:
            self.silent_frame_count = 0

        # Convert frame count to milliseconds
        # Assume 20ms per frame (standard)
        silence_duration_ms = self.silent_frame_count * 20

        endpoint_detected = silence_duration_ms >= self.silence_duration_ms

        return {
            "endpoint_detected": endpoint_detected,
            "confidence": 0.0 if endpoint_detected else 0.0,  # VAD has no learned confidence
            "silence_duration_ms": silence_duration_ms,
            "is_silent": is_silent,
            "rms_db": rms_db
        }

    async def reset(self):
        """Reset silence counter (e.g., when user speaks again)."""
        self.silent_frame_count = 0
        self.total_frames = 0

    async def close(self):
        """Cleanup."""
        logger.info("VADEndpointDetector closed")
