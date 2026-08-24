"""
MOUTH: Kyutai Pocket TTS — the streaming French voice.

This is the backend the original MOTHER spec asked for, and it differs from
Piper in the way that matters: Piper is non-autoregressive and emits one chunk
per sentence, so time-to-first-audio grows with sentence length and has to be
bounded by cutting the text early (see `piper_tts._word_cut`, and the seam it
costs). Pocket TTS is an audio language model — it emits chunks *as it
decodes*, so a whole sentence can go in and audio comes out immediately.

Measured on this machine (RTX 4070, `french_24l`, voice estelle):

    device   TTFA cold   TTFA warm   RTF     chunks
    cpu        518 ms      —         0.834    41
    cuda       535 ms      72 ms     0.369    51

Piper stays as the fallback: RTF 0.03 against 0.37 means Piper has far more
headroom, and it costs no VRAM at all. Pocket TTS buys a better voice, 24 kHz,
26 French speakers and true incremental output, and spends GPU for it.

int8 quantisation is CPU-only in this build (`quantized::linear_dynamic` has no
CUDA kernel), so the GPU path runs fp32.
"""
import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import numpy as np

from src.mouth.normalize import strip_markup
from src.mouth.voice_design import FLAT, PROFILES, VoiceTreatment

logger = logging.getLogger(__name__)

MODEL_ROOT = "/workspace/models/pocket-tts/languages"
DEFAULT_LANGUAGE = "french_24l"
DEFAULT_VOICE = "estelle"


class PocketTTS:
    """Streaming French TTS. Drop-in for PiperTTS."""

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        voice: str = DEFAULT_VOICE,
        device: str = "cuda",
        profile: str = "mother",
        temperature: float = 0.7,
        max_tokens: int = 50,
    ):
        self.language = language
        self.voice = voice
        self.device = device
        self.profile = PROFILES.get(profile, FLAT)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = None
        self._state = None
        self.sample_rate = 24000
        self._treatment: Optional[VoiceTreatment] = None
        self.ttfa_history: List[float] = []
        logger.info(f"PocketTTS: {language}/{voice} on {device} profile={profile}")

    @property
    def voice_path(self) -> str:
        return f"{MODEL_ROOT}/{self.language}/embeddings/{self.voice}.safetensors"

    async def load_model(self) -> bool:
        def _load():
            import torch
            from pocket_tts import TTSModel

            model = TTSModel.load_model(language=self.language, temp=self.temperature)
            if self.device.startswith("cuda") and torch.cuda.is_available():
                model = model.to(self.device)
            state = model.get_state_for_audio_prompt(self.voice_path)
            return model, state

        try:
            t0 = time.perf_counter()
            self.model, self._state = await asyncio.to_thread(_load)
            self.sample_rate = self.model.sample_rate
            self._treatment = (
                VoiceTreatment(self.profile, self.sample_rate)
                if self.profile is not FLAT
                else None
            )
            logger.info(
                f"pocket-tts loaded in {time.perf_counter() - t0:.1f}s @ {self.sample_rate} Hz"
            )
            # The first generation pays graph/kernel warmup — measured 535 ms
            # against 72 ms warm. Burn it here so the first real turn is fast.
            await self.synthesize("Prête.")
            return True
        except Exception as e:
            logger.error(f"pocket-tts load failed: {e}")
            self.model = None
            return False

    # -- synthesis ---------------------------------------------------------

    def _stream_blocking(self, text: str, t0: float, out: list):
        """Runs in a worker thread; appends (chunk, timestamp) as they arrive."""
        for chunk in self.model.generate_audio_stream(
            self._state, text, max_tokens=self.max_tokens
        ):
            pcm = chunk.reshape(-1).float().cpu().numpy()
            out.append((pcm, time.perf_counter() - t0))

    async def synthesize_incremental(self, text: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Yield audio chunks **as the model decodes them**.

        `synthesize()` collects everything before returning, which throws away
        the only reason to pay 1.5 GB of VRAM for this model: measured, that
        buffering turned a 75 ms first chunk into 2147 ms of perceived latency.
        The generator runs on a worker thread and hands chunks back through a
        queue so the event loop can forward them immediately.
        """
        if self.model is None:
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        t0 = time.perf_counter()
        SENTINEL = object()

        def worker():
            try:
                for chunk in self.model.generate_audio_stream(
                    self._state, text, max_tokens=self.max_tokens
                ):
                    pcm = chunk.reshape(-1).float().cpu().numpy()
                    loop.call_soon_threadsafe(queue.put_nowait, pcm)
            except Exception as e:  # surface, don't hang the consumer
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

        task = asyncio.create_task(asyncio.to_thread(worker))
        index = 0
        try:
            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                if isinstance(item, Exception):
                    logger.error(f"pocket-tts stream error: {item}")
                    break
                pcm = np.clip(item * 32767.0, -32768, 32767).astype(np.int16)
                if self._treatment is not None:
                    pcm = self._treatment.process(pcm)
                yield {
                    "audio": pcm,
                    "sample_rate": self.sample_rate,
                    "chunk_index": index,
                    "elapsed_ms": (time.perf_counter() - t0) * 1000,
                }
                index += 1
        finally:
            await task

    async def synthesize(self, text: str) -> Dict[str, Any]:
        """Synthesise one block. Returns int16 PCM plus true first-chunk timing."""
        if self.model is None:
            return {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate,
                    "ttfa_ms": 0.0, "synth_ms": 0.0, "rtf": 0.0, "stub": True}

        t0 = time.perf_counter()
        parts: list = []
        await asyncio.to_thread(self._stream_blocking, text, t0, parts)
        total_s = time.perf_counter() - t0

        if not parts:
            return {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate,
                    "ttfa_ms": 0.0, "synth_ms": total_s * 1000, "rtf": 0.0}

        first_s = parts[0][1]
        pcm_f = np.concatenate([p for p, _ in parts])
        pcm = np.clip(pcm_f * 32767.0, -32768, 32767).astype(np.int16)
        if self._treatment is not None:
            pcm = self._treatment.process(pcm)

        duration_s = len(pcm) / self.sample_rate
        self.ttfa_history.append(first_s * 1000)
        return {
            "audio": pcm,
            "sample_rate": self.sample_rate,
            "ttfa_ms": first_s * 1000,
            "synth_ms": total_s * 1000,
            "duration_s": duration_s,
            "rtf": total_s / duration_s if duration_s > 0 else 0.0,
            "chunks": len(parts),
        }

    async def synthesize_stream(
        self, token_stream: AsyncIterator, min_chars: int = 24, **_
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Consume BRAIN's deltas and emit audio per sentence.

        Unlike the Piper path there is no word-boundary cut and no shortened
        opening fragment: this model already emits audio mid-sentence, so
        chopping the text early would only damage prosody without improving
        latency. Sentence boundaries are enough.

        Accepts plain strings or {"text", "flush"} items, same as PiperTTS, so
        the router's filler still jumps the queue.
        """
        from src.mouth.piper_tts import _SENTENCE_END, _first_cut

        pending = ""
        first_token_at: Optional[float] = None
        index = 0

        async def emit(text: str, final: bool, flushed: bool = False):
            """Forward this sentence's audio chunk-by-chunk, not as a block."""
            nonlocal index
            sent_any = False
            async for piece in self.synthesize_incremental(text):
                piece.update({
                    "text": text if not sent_any else "",
                    "index": index,
                    "is_final": False,
                    "flushed": flushed,
                    "ttfa_ms": piece["elapsed_ms"] if not sent_any else None,
                    "ttfa_perceived_ms": (
                        (time.perf_counter() - first_token_at) * 1000
                        if index == 0 and not sent_any else None
                    ),
                })
                sent_any = True
                yield piece
            index += 1
            if final:
                yield {"audio": np.zeros(0, dtype=np.int16),
                       "sample_rate": self.sample_rate, "text": "",
                       "index": index, "is_final": True}

        async for item in token_stream:
            if isinstance(item, dict):
                delta, flush = item.get("text", ""), bool(item.get("flush"))
            else:
                delta, flush = item, False

            if first_token_at is None:
                first_token_at = time.perf_counter()
            pending += delta

            if flush and pending.strip():
                spoken, pending = strip_markup(pending), ""
                if spoken:
                    async for piece in emit(spoken, False, flushed=True):
                        yield piece
                continue

            while True:
                cut = _first_cut(pending, _SENTENCE_END, min_chars)
                if cut is None:
                    break
                sentence, pending = cut
                sentence = strip_markup(sentence)
                if sentence:
                    async for piece in emit(sentence, False):
                        yield piece

        tail = strip_markup(pending)
        if tail:
            async for piece in emit(tail, True):
                yield piece
        else:
            yield {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate,
                   "text": "", "index": index, "is_final": True}

    @staticmethod
    def to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(audio.astype(np.int16).tobytes())
        return buf.getvalue()
