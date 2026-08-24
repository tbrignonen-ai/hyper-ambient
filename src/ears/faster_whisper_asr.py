"""
EARS: faster-whisper (CTranslate2) ASR backend.

Chosen over openai-whisper for the same reason llama.cpp beats transformers at
serving: a quantised C++ runtime, int8_float16 on GPU, no Python in the hot loop.

Streaming here is *chunked re-decode*, not true streaming: Whisper is an
offline encoder-decoder. We decode a growing window and emit partial
hypotheses, tracking revisions so downstream consumers know a partial was
retracted. That revision count is a measurable EARS quality signal.
"""
import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


class FasterWhisperASR:
    """Whisper ASR via CTranslate2. EARS-L2 when GPU-backed."""

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        language: str = "fr",
        device: str = "cuda",
        compute_type: Optional[str] = None,
    ):
        self.model_size = model_size
        self.language = language
        self.device = device
        # int8_float16 halves VRAM against float16 at ~no WER cost on turbo.
        self.compute_type = compute_type or ("int8_float16" if device == "cuda" else "int8")
        self.model = None
        self.revisions = 0
        self._last_partial = ""
        logger.info(f"FasterWhisperASR: {model_size} / {language} / {device}:{self.compute_type}")

    async def load_model(self):
        """Load the CTranslate2 model (blocking work pushed off the loop)."""

        def _load():
            from faster_whisper import WhisperModel

            return WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )

        try:
            t0 = time.perf_counter()
            self.model = await asyncio.to_thread(_load)
            logger.info(f"model loaded in {(time.perf_counter() - t0):.1f}s")
        except Exception as e:
            logger.error(f"failed to load {self.model_size}: {e}")
            self.model = None
        return self.model is not None

    # -- inference ---------------------------------------------------------

    def _decode(self, audio: np.ndarray, beam_size: int) -> Dict[str, Any]:
        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=beam_size,
            vad_filter=False,             # TURN owns endpointing, not EARS
            condition_on_previous_text=False,  # prevents drift on long sessions
            without_timestamps=False,
        )
        segs: List[Dict[str, Any]] = [
            {"start": s.start, "end": s.end, "text": s.text} for s in segments
        ]
        return {
            "text": "".join(s["text"] for s in segs).strip(),
            "segments": segs,
            "language": info.language,
            "language_probability": info.language_probability,
        }

    async def transcribe(self, audio: np.ndarray, beam_size: int = 5) -> Dict[str, Any]:
        """
        Transcribe a complete utterance.

        Args:
            audio: mono float32 in [-1, 1] at 16 kHz.

        Returns dict with text, segments, latency_ms and rtf (real-time factor:
        <1.0 means faster than realtime, which is the whole ballgame).
        """
        if self.model is None:
            return {"text": "[stub]", "segments": [], "rtf": 0.0, "latency_ms": 0.0}

        audio = np.asarray(audio, dtype=np.float32)
        duration_s = len(audio) / SAMPLE_RATE
        t0 = time.perf_counter()
        result = await asyncio.to_thread(self._decode, audio, beam_size)
        latency = time.perf_counter() - t0

        result["latency_ms"] = latency * 1000
        result["audio_duration_s"] = duration_s
        result["rtf"] = latency / duration_s if duration_s > 0 else 0.0
        return result

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[np.ndarray],
        partial_every_ms: int = 500,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Emit partial hypotheses over a growing buffer, then a final one.

        Yields {"text", "is_final", "revised", "latency_ms"}. `revised` is True
        when the new partial is not a prefix extension of the previous one —
        i.e. EARS took something back.
        """
        buffer = np.zeros(0, dtype=np.float32)
        last_emit = 0.0
        self.revisions = 0
        self._last_partial = ""

        async for chunk in audio_chunks:
            buffer = np.concatenate([buffer, np.asarray(chunk, dtype=np.float32)])
            elapsed_ms = (len(buffer) / SAMPLE_RATE) * 1000
            if elapsed_ms - last_emit < partial_every_ms:
                continue
            last_emit = elapsed_ms

            # greedy for partials — beam search is wasted on text we'll revise
            partial = await self.transcribe(buffer, beam_size=1)
            text = partial["text"]
            revised = bool(self._last_partial) and not text.startswith(self._last_partial)
            if revised:
                self.revisions += 1
            self._last_partial = text

            yield {
                "text": text,
                "is_final": False,
                "revised": revised,
                "latency_ms": partial["latency_ms"],
            }

        final = await self.transcribe(buffer, beam_size=5)
        yield {
            "text": final["text"],
            "is_final": True,
            "revised": False,
            "latency_ms": final["latency_ms"],
            "rtf": final["rtf"],
            "revisions": self.revisions,
        }
