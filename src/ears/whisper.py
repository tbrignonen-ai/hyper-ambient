"""
EARS: Whisper.cpp integration for ASR streaming.

Provides stable partial hypotheses with optional revision tracking.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


class WhisperASR:
    """Whisper ASR engine (MIT license, 99 languages)."""

    def __init__(self, model_size: str = "tiny", language: str = "fr"):
        """
        Initialize Whisper ASR.

        Args:
            model_size: tiny, base, small, medium, large
            language: ISO 639-1 code (fr, en, etc.)
        """
        self.model_size = model_size
        self.language = language
        self.model = None
        self.processor = None
        self.revision_history = []
        logger.info(f"WhisperASR initialized: {model_size}, {language}")

    async def load_model(self, device: str = "cuda"):
        """
        Load Whisper model and processor.

        Args:
            device: cuda or cpu
        """
        try:
            # Lazy import to avoid CUDA errors if not available
            import whisper

            model_names = {
                "tiny": "openai/whisper-tiny",
                "base": "openai/whisper-base",
                "small": "openai/whisper-small",
                "medium": "openai/whisper-medium",
                "large": "openai/whisper-large-v3"
            }

            model_name = model_names.get(self.model_size, "openai/whisper-tiny")
            logger.info(f"Loading model: {model_name}")

            self.model = whisper.load_model(self.model_size, device=device)
            logger.info(f"Model loaded: {self.model_size} on {device}")

        except ImportError:
            logger.warning("whisper not available, using stub")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def transcribe_stream(
        self,
        audio_frames: np.ndarray,
        sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        Transcribe audio stream with stable partials.

        Args:
            audio_frames: numpy array of audio samples
            sample_rate: sample rate in Hz

        Returns:
            {
                "partial": "transcription so far",
                "final": False,
                "confidence": 0.95,
                "language": "fr",
                "revisions_since_last": 0
            }
        """
        if self.model is None:
            # Stub mode
            return {
                "partial": "[stub] audio processed",
                "final": False,
                "confidence": 0.5,
                "language": self.language,
                "revisions_since_last": 0
            }

        try:
            # Whisper expects audio in 16kHz mono PCM
            # This is a simplified version; real implementation would use streaming
            result = self.model.transcribe(
                audio_frames,
                language=self.language,
                verbose=False
            )

            partial_text = result.get("text", "")

            # Track revisions
            if self.revision_history and self.revision_history[-1] != partial_text:
                revisions = 1
            else:
                revisions = 0

            self.revision_history.append(partial_text)

            return {
                "partial": partial_text,
                "final": result.get("is_final", False),
                "confidence": result.get("segments", [{}])[0].get("confidence", 0.0),
                "language": result.get("language", self.language),
                "revisions_since_last": revisions
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {
                "partial": "",
                "final": False,
                "confidence": 0.0,
                "language": self.language,
                "revisions_since_last": 0,
                "error": str(e)
            }

    async def get_revision_rate(self) -> float:
        """
        Compute revision rate: words that changed after being emitted.

        Returns:
            Fraction [0, 1] of words that were revised
        """
        if len(self.revision_history) < 2:
            return 0.0

        # Simple heuristic: count times text changed
        changes = sum(
            1 for i in range(1, len(self.revision_history))
            if self.revision_history[i] != self.revision_history[i-1]
        )
        return changes / max(len(self.revision_history) - 1, 1)

    async def close(self):
        """Cleanup resources."""
        self.model = None
        logger.info("WhisperASR closed")
