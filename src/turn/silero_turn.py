"""
TURN: Silero VAD endpoint detector (TURN-L1).

This is the *acoustic* half of turn-taking: it knows when sound stopped, not
when the speaker finished a thought. It cannot tell "j'ai pris... euh..."
(still speaking) from "j'ai pris." (done) — that needs the semantic model
(TURN-L2, Pipecat Smart Turn, see src/turn/pipecat_adapter.py).

It exists because OQ-15 says TURN must not have a single-component dependency:
if the learned model is unavailable, MOTHER degrades to L1 rather than to
nothing. false_endpoint_rate on corpus A01-A04 is what separates the two.

Silero requires exactly 512-sample frames at 16 kHz (32 ms).
"""
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512  # Silero's fixed frame size at 16 kHz


class SileroTurnDetector:
    """Endpoint detector driven by Silero VAD probabilities."""

    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_duration_ms: int = 700,
        speech_pad_ms: int = 100,
        use_onnx: bool = True,
    ):
        """
        Args:
            threshold: speech probability above which a frame counts as voiced.
            min_silence_duration_ms: trailing silence before declaring an
                endpoint. This single number is the L1 latency/accuracy
                trade-off — lower cuts the user off, higher adds dead air.
            speech_pad_ms: padding kept around detected speech.
            use_onnx: ONNX runtime (CPU, ~1 ms/frame) instead of torch.
        """
        self.threshold = threshold
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms
        self.use_onnx = use_onnx
        self.model = None
        self.iterator = None
        self._residual = np.zeros(0, dtype=np.float32)
        self._speaking = False
        self._speech_started_at: Optional[float] = None
        logger.info(
            f"SileroTurnDetector: thr={threshold} silence={min_silence_duration_ms}ms onnx={use_onnx}"
        )

    def load_model(self) -> bool:
        try:
            from silero_vad import VADIterator, load_silero_vad

            self.model = load_silero_vad(onnx=self.use_onnx)
            self.iterator = VADIterator(
                self.model,
                threshold=self.threshold,
                sampling_rate=SAMPLE_RATE,
                min_silence_duration_ms=self.min_silence_duration_ms,
                speech_pad_ms=self.speech_pad_ms,
            )
            logger.info("silero-vad loaded")
            return True
        except Exception as e:
            logger.error(f"silero-vad load failed: {e}")
            self.model = None
            return False

    def reset(self):
        """Clear state between utterances (mandatory — VADIterator is stateful)."""
        if self.iterator is not None:
            self.iterator.reset_states()
        self._residual = np.zeros(0, dtype=np.float32)
        self._speaking = False
        self._speech_started_at = None

    def process_chunk(self, audio: np.ndarray) -> List[Dict[str, Any]]:
        """
        Feed an arbitrary-length chunk; get back turn events.

        Audio of any length is buffered and consumed in 512-sample frames, so
        callers are free to use whatever frame size the host-agent produces.

        Returns a list of {"event": "speech_start"|"endpoint", "t_s": float,
        "detected_at": float}. Empty list means "nothing decided yet".
        """
        if self.iterator is None:
            return []

        self._residual = np.concatenate(
            [self._residual, np.asarray(audio, dtype=np.float32).ravel()]
        )
        events: List[Dict[str, Any]] = []

        while len(self._residual) >= FRAME_SAMPLES:
            frame, self._residual = (
                self._residual[:FRAME_SAMPLES],
                self._residual[FRAME_SAMPLES:],
            )
            verdict = self.iterator(frame, return_seconds=True)
            if not verdict:
                continue

            now = time.perf_counter()
            if "start" in verdict:
                self._speaking = True
                self._speech_started_at = verdict["start"]
                events.append(
                    {"event": "speech_start", "t_s": verdict["start"], "detected_at": now}
                )
            elif "end" in verdict:
                self._speaking = False
                events.append(
                    {
                        "event": "endpoint",
                        "t_s": verdict["end"],
                        "detected_at": now,
                        "speech_duration_s": (
                            verdict["end"] - self._speech_started_at
                            if self._speech_started_at is not None
                            else None
                        ),
                        # L1 has no semantics: it never claims the thought is done.
                        "confidence": "acoustic_only",
                    }
                )

        return events

    @property
    def is_speaking(self) -> bool:
        return self._speaking
