"""Qwen3-ASR MLX 8-bit via mlx-qwen3-asr >= 0.4.3, local-only."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import numpy as np

from src.hostagent.audio import SAMPLE_RATE


class MLXQwen3ASR:
    def __init__(self, model_size: str | None = None, language: str = "fr",
                 device: str = "metal", session_factory=None):
        from native.macos.profile import model_path

        self.model_size = str(model_path("stt")) if model_size is None else model_size
        self.language = language
        self.device = device
        self._factory = session_factory
        self.model = None
        self.revisions = 0

    def _load(self):
        if self._factory is not None:
            return self._factory(self.model_size)
        from mlx_qwen3_asr import Session

        if not Path(self.model_size).is_dir():
            raise FileNotFoundError(f"Snapshot STT absent : {self.model_size}")
        return Session(model=self.model_size)

    async def load_model(self) -> bool:
        from native.macos.model_runtime import runtime

        try:
            self.model = await runtime.run("stt", self._load, on_evict=lambda: setattr(self, "model", None))
            return True
        except Exception as exc:
            print(f"EARS MLX indisponible : {exc}", flush=True)
            return False

    def _transcribe(self, model, audio: np.ndarray):
        language = "French" if self.language == "fr" else "English"
        return model.transcribe((audio, SAMPLE_RATE), language=language)

    async def transcribe(self, audio: np.ndarray, beam_size: int = 5) -> dict:
        del beam_size
        from native.macos.model_runtime import runtime
        samples = np.asarray(audio).reshape(-1)
        if samples.dtype == np.int16:
            samples = samples.astype(np.float32) / 32768.0
        else:
            samples = np.asarray(samples, dtype=np.float32)
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio ASR non fini")
        samples = np.ascontiguousarray(np.clip(samples, -1.0, 1.0))
        started = time.perf_counter()
        raw = await asyncio.wait_for(
            runtime.run("stt", self._load,
                        lambda model: (model, self._transcribe(model, samples)),
                        on_evict=lambda: setattr(self, "model", None)),
            timeout=max(1.0, min(120.0, float(os.getenv("MOTHER_MAC_ASR_TIMEOUT_S", "30")))),
        )
        self.model, raw = raw
        elapsed = time.perf_counter() - started
        text = str(getattr(raw, "text", "") or "").strip()
        duration = samples.size / SAMPLE_RATE
        return {"text": text,
                "segments": [{"start": 0.0, "end": duration, "text": text}] if text else [],
                "language": self.language, "language_probability": None,
                "latency_ms": elapsed * 1000, "audio_duration_s": duration,
                "rtf": elapsed / duration if duration else 0.0,
                "truncated": bool(getattr(raw, "truncated", False))}

    async def transcribe_stream(self, audio_chunks, partial_every_ms: int = 500):
        pending = np.zeros(0, dtype=np.float32)
        previous = ""
        last_ms = 0.0
        self.revisions = 0
        async for chunk in audio_chunks:
            pending = np.concatenate((pending, np.asarray(chunk, dtype=np.float32).reshape(-1)))
            elapsed_ms = pending.size / SAMPLE_RATE * 1000
            if elapsed_ms - last_ms < partial_every_ms:
                continue
            last_ms = elapsed_ms
            result = await self.transcribe(pending)
            revised = bool(previous) and not result["text"].startswith(previous)
            self.revisions += int(revised)
            previous = result["text"]
            yield {"text": previous, "is_final": False, "revised": revised,
                   "latency_ms": result["latency_ms"]}
        result = await self.transcribe(pending)
        yield {"text": result["text"], "is_final": True, "revised": False,
               "latency_ms": result["latency_ms"], "rtf": result["rtf"],
               "revisions": self.revisions}

    async def aclose(self):
        self.model = None
