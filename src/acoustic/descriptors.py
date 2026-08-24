"""
ACOUSTIC: Frontend audio descriptors for non-speech events.

L1 conformance: RMS energy, spectral centroid, zero-crossing rate.
Minimal computation, always available (Apache-2.0).

L2 requires learned model (FunASR) — license TBD.
"""
import logging
from typing import Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


class AcousticDescriptors:
    """Frontend acoustic event detection via signal processing."""

    def __init__(self, sample_rate: int = 16000):
        """
        Initialize acoustic descriptor extraction.

        Args:
            sample_rate: sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.event_history = []
        logger.info(f"AcousticDescriptors initialized: {sample_rate}Hz")

    def extract_frame_descriptors(self, audio_frame: np.ndarray) -> Dict[str, float]:
        """
        Extract signal descriptors from a single frame.

        Args:
            audio_frame: numpy array of audio samples

        Returns:
            {
                "rms_db": -30.5,
                "spectral_centroid": 1200.0,
                "zero_crossing_rate": 0.05,
                "is_silence": False,
                "is_clipping": False
            }
        """
        try:
            # RMS energy in dB
            rms = np.sqrt(np.mean(audio_frame ** 2))
            rms_db = 20 * np.log10(rms) if rms > 1e-10 else -100.0

            # Spectral centroid (frequency-weighted)
            fft = np.abs(np.fft.rfft(audio_frame))
            freqs = np.fft.rfftfreq(len(audio_frame), 1.0 / self.sample_rate)
            spec_centroid = np.sum(freqs * fft) / np.sum(fft) if np.sum(fft) > 0 else 0.0

            # Zero-crossing rate
            zcr = np.mean(np.abs(np.diff(np.sign(audio_frame)))) / 2.0

            # Clipping detection (values at -1.0 or 1.0)
            clipping_fraction = np.sum(np.abs(audio_frame) >= 0.99) / len(audio_frame)

            return {
                "rms_db": float(rms_db),
                "spectral_centroid": float(spec_centroid),
                "zero_crossing_rate": float(zcr),
                "is_silence": rms_db < -40.0,
                "is_clipping": clipping_fraction > 0.01
            }

        except Exception as e:
            logger.error(f"Descriptor extraction error: {e}")
            return {
                "rms_db": -100.0,
                "spectral_centroid": 0.0,
                "zero_crossing_rate": 0.0,
                "is_silence": True,
                "is_clipping": False,
                "error": str(e)
            }

    def classify_event(self, descriptors: Dict[str, float]) -> Dict[str, Any]:
        """
        Classify event based on signal descriptors (heuristic).

        L1 only: No learned model, just pattern matching.

        Args:
            descriptors: output from extract_frame_descriptors

        Returns:
            {
                "event": "silence" | "speech" | "noise" | "music" | None,
                "confidence": 0.0,
                "is_learned": False
            }
        """
        rms_db = descriptors.get("rms_db", -100.0)
        zcr = descriptors.get("zero_crossing_rate", 0.0)

        # Simple heuristic
        if rms_db < -40.0:
            event = "silence"
            confidence = 0.9
        elif zcr > 0.1:  # High ZCR often indicates noise or fricatives
            event = "noise"
            confidence = 0.5
        elif -40.0 <= rms_db < -20.0:
            event = "speech"
            confidence = 0.7
        else:
            event = None
            confidence = 0.0

        return {
            "event": event,
            "confidence": confidence,
            "is_learned": False
        }

    async def detect_acoustic_events(self, audio_frame: np.ndarray) -> Dict[str, Any]:
        """
        Detect non-speech acoustic events from frame.

        This is L1 (frontend only). L2 would use FunASR or similar.

        Args:
            audio_frame: audio samples

        Returns:
            {
                "events": ["laughter", "sigh"],
                "confidence_per_event": [0.3, 0.2],
                "level": "L1"
            }
        """
        # L1 only reports descriptors, not learned events
        descriptors = self.extract_frame_descriptors(audio_frame)
        classification = self.classify_event(descriptors)

        self.event_history.append({
            "descriptors": descriptors,
            "classification": classification
        })

        return {
            "events": [],  # L1 doesn't detect specific events like laughter
            "confidence_per_event": [],
            "level": "L1",
            "descriptors": descriptors
        }

    async def close(self):
        """Cleanup."""
        logger.info("AcousticDescriptors closed")
