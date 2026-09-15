"""
MOUTH: Supertonic-3 — voix feminine lente, ONNX sur CPU.

Choisie le 15 sept apres que Thomas a demande une voix « suave, feminine,
agreable, qui parle plutot lentement ». Banc sur la meme phrase a speed=0.9 :
F5 a la fondamentale la plus basse des styles feminins (168 Hz contre 188-204),
RTF 0.22 sur CPU, 0 VRAM.

Pas de flux dans la phrase : le moteur rend un bloc par appel. On synthetise
donc phrase par phrase, comme Piper, avec la meme coupe et la meme priorite
aux amorces (`flush`).
"""
import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional

import numpy as np

from src.mouth.normalize import strip_markup
from src.mouth.voice_design import FLAT, PROFILES, VoiceTreatment

logger = logging.getLogger(__name__)

MODEL_DIR = "/workspace/models/supertonic"


class SupertonicTTS:
    """Drop-in for PocketTTS / PiperTTS."""

    def __init__(self, style: str = "F5", speed: float = 0.88,
                 profile: str = "aurora", model_dir: str = MODEL_DIR):
        self.style_name = style
        self.speed = speed
        self.model_dir = model_dir
        self.profile = PROFILES.get(profile, FLAT)
        self.engine = None
        self._style = None
        self.sample_rate = 44100
        self._treatment: Optional[VoiceTreatment] = None
        logger.info(f"SupertonicTTS: {style} speed={speed} profile={profile}")

    async def load_model(self) -> bool:
        def _load():
            from supertonic import TTS

            engine = TTS(model="supertonic-3", model_dir=self.model_dir, auto_download=False)
            return engine, engine.get_voice_style(self.style_name)

        try:
            t0 = time.perf_counter()
            self.engine, self._style = await asyncio.to_thread(_load)
            self.sample_rate = int(self.engine.sample_rate)
            logger.info(f"supertonic loaded in {time.perf_counter() - t0:.1f}s @ {self.sample_rate} Hz")
            await self.synthesize("Prête.")
            return True
        except Exception as e:
            logger.error(f"supertonic load failed: {e}")
            self.engine = None
            return False

    def _render(self, text: str) -> np.ndarray:
        wav, _ = self.engine.synthesize(text, voice_style=self._style, speed=self.speed, lang="fr")
        x = np.asarray(wav, dtype=np.float32).ravel()
        pic = float(np.max(np.abs(x))) if x.size else 0.0
        if pic > 1.0:
            x = x / pic * 0.99
        return np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)

    def _treat(self, pcm: np.ndarray) -> np.ndarray:
        if self.profile is FLAT or pcm.size == 0:
            return pcm
        if self._treatment is None:
            self._treatment = VoiceTreatment(self.profile, self.sample_rate)
        return self._treatment.process(pcm)

    async def synthesize(self, text: str) -> Dict[str, Any]:
        if self.engine is None:
            return {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate, "stub": True}
        t0 = time.perf_counter()
        pcm = self._treat(await asyncio.to_thread(self._render, text))
        synth_ms = (time.perf_counter() - t0) * 1000
        return {"audio": pcm, "sample_rate": self.sample_rate, "ttfa_ms": synth_ms, "synth_ms": synth_ms}

    async def synthesize_stream(self, token_stream: AsyncIterator, min_chars: int = 24, **_
                                ) -> AsyncIterator[Dict[str, Any]]:
        from src.mouth.piper_tts import _SENTENCE_END, _first_cut

        pending, index = "", 0

        async def emit(text: str, flushed: bool = False):
            nonlocal index
            out = await self.synthesize(text)
            out.update({"text": text, "index": index, "is_final": False, "flushed": flushed})
            index += 1
            return out

        async for item in token_stream:
            if isinstance(item, dict):
                delta, flush = item.get("text", ""), bool(item.get("flush"))
            else:
                delta, flush = item, False
            pending += delta

            if flush and pending.strip():
                spoken, pending = strip_markup(pending), ""
                if spoken:
                    yield await emit(spoken, flushed=True)
                continue

            while True:
                cut = _first_cut(pending, _SENTENCE_END, min_chars)
                if cut is None:
                    break
                sentence, pending = cut
                sentence = strip_markup(sentence)
                if sentence:
                    yield await emit(sentence)

        tail = strip_markup(pending)
        if tail:
            yield await emit(tail)
        yield {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate,
               "text": "", "index": index, "is_final": True}
