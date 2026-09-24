"""Chatterbox multilingual v3 sur MLX, FR/EN, référence vocale obligatoire."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import numpy as np

from src.mouth.normalize import nombres_en_lettres, strip_markup


class MLXChatterboxTTS:
    def __init__(self, model_dir: str | Path | None = None, language: str = "fr",
                 reference_wav: str | Path | None = None, loader=None):
        from native.macos.profile import model_path

        self.model_dir = Path(model_dir) if model_dir else model_path("tts")
        self.language = language
        ref = reference_wav or os.getenv("MOTHER_TTS_REFERENCE_WAV", "")
        self.reference_wav = Path(ref).expanduser() if ref else None
        self.loader = loader
        self.engine = None
        self.sample_rate = 24000

    def _load(self):
        if self.loader is not None:
            return self.loader(str(self.model_dir))
        from mlx_audio.tts.utils import load_model

        return load_model(str(self.model_dir))

    async def load_model(self) -> bool:
        from dev.scripts.models_macos import install_s3_cache, status
        from native.macos.model_runtime import runtime
        from native.macos.profile import paths

        if not self.reference_wav or not self.reference_wav.is_file():
            print("MOUTH Chatterbox : MOTHER_TTS_REFERENCE_WAV requis (WAV de référence consentie).", flush=True)
            return False
        if self.loader is None:
            root = paths()["models"]
            if any(status(family, root)["status"] != "PASS" for family in ("tts", "tts_s3")):
                print("MOUTH Chatterbox : snapshots TTS/S3 incomplets ; lancer models_macos.py status.", flush=True)
                return False
            install_s3_cache(root)
        try:
            self.engine = await runtime.run("tts", self._load, on_evict=lambda: setattr(self, "engine", None))
            self.sample_rate = int(self.engine.sample_rate)
            return True
        except Exception as exc:
            print(f"MOUTH Chatterbox indisponible : {exc}", flush=True)
            return False

    def _render(self, model, text: str):
        spoken = nombres_en_lettres(strip_markup(text))
        if not spoken.strip():
            return np.zeros(0, dtype=np.int16)
        results = model.generate(text=spoken, ref_audio=str(self.reference_wav),
                                       lang_code=self.language, exaggeration=0.1,
                                       cfg_weight=0.5, temperature=0.8,
                                       repetition_penalty=1.2, verbose=False)
        chunks = [np.asarray(result.audio, dtype=np.float32).reshape(-1) for result in results]
        if not chunks:
            raise RuntimeError("Chatterbox n'a rendu aucun échantillon")
        audio = np.concatenate(chunks)
        if not np.all(np.isfinite(audio)):
            raise RuntimeError("Chatterbox a rendu un PCM non fini")
        return np.clip(np.round(audio * 32767.0), -32768, 32767).astype(np.int16)

    async def synthesize(self, text: str) -> dict:
        from native.macos.model_runtime import runtime

        if not self.reference_wav or not self.reference_wav.is_file():
            raise RuntimeError("Référence vocale Chatterbox absente")
        started = time.perf_counter()
        pcm = await asyncio.wait_for(
            runtime.run("tts", self._load, lambda model: self._render(model, text),
                        on_evict=lambda: setattr(self, "engine", None)),
            timeout=max(1.0, min(180.0, float(os.getenv("MOTHER_MAC_TTS_TIMEOUT_S", "90")))),
        )
        self.engine = runtime._model
        self.sample_rate = int(self.engine.sample_rate)
        elapsed = (time.perf_counter() - started) * 1000
        return {"audio": pcm, "sample_rate": self.sample_rate,
                "ttfa_ms": elapsed, "synth_ms": elapsed}

    async def synthesize_stream(self, token_stream, min_chars=24, first_chunk_max_chars=34, **_):
        # Le moteur ne diffuse pas l'audio intra-phrase. Segmentation au même
        # contrat que Magpie ; les morceaux anciens sont rejetés sur annulation.
        from src.mouth.piper_tts import _CLAUSE_END, _first_cut, _word_cut

        pending = ""
        index = 0

        async def emit(text, flushed=False):
            nonlocal index
            out = await self.synthesize(text)
            out.update({"text": text, "index": index, "is_final": False, "flushed": flushed})
            index += 1
            return out

        async for item in token_stream:
            delta = item.get("text", "") if isinstance(item, dict) else item
            flush = bool(item.get("flush")) if isinstance(item, dict) else False
            pending += delta
            if flush and pending.strip():
                text, pending = strip_markup(pending), ""
                if text:
                    yield await emit(text, True)
                continue
            while True:
                cut = _first_cut(pending, _CLAUSE_END, min_chars)
                if cut is None and index == 0:
                    cut = _word_cut(pending, first_chunk_max_chars)
                if cut is None:
                    break
                text, pending = cut
                text = strip_markup(text)
                if text:
                    yield await emit(text)
        tail = strip_markup(pending)
        if tail:
            yield await emit(tail)
        yield {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate,
               "text": "", "index": index, "is_final": True}

    async def aclose(self):
        self.engine = None
