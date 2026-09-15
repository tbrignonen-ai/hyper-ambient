"""
MOUTH: Piper TTS (ONNX VITS) streaming synthesis.

Piper is the pragmatic MOUTH: ~60 MB per voice, runs on CPU faster than
realtime, French voices available, deterministic latency. It leaves the GPU
entirely to EARS and BRAIN — which matters on a 12 GB card that also hosts a
Whisper model and a GGUF.

The number that counts is TTFA (time-to-first-audio): how long after BRAIN's
first token the user hears something. Piper synthesises per sentence, so
feeding it BRAIN's stream sentence-by-sentence keeps TTFA ~flat regardless of
how long the full answer is.
"""
import asyncio
import logging
import re
import time
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

import numpy as np

from src.mouth.normalize import strip_markup
from src.mouth.voice_design import (
    FLAT,
    PROFILES,
    VoiceTreatment,
    facteur_transposition,
    transposer,
)

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "/workspace/models/piper/fr_FR-tom-medium.onnx"

# Taux que siwis/upmc annoncent nativement, et que le canal host-agent
# chauffe par défaut. Tom sort à 44 100 Hz : sans alignement, un chemin
# qui oublie `tts.sample_rate` joue le PCM deux fois trop lent — haché.
PIPELINE_RATE = 22050


def ramener_au_taux_pipeline(
    pcm: np.ndarray, taux_source: int, taux_cible: int = PIPELINE_RATE
) -> np.ndarray:
    """Ramène un énoncé complet au taux Piper du pipeline.

    Un énoncé entier, jamais un chunk de 80 ms : `soxr.resample` pose
    ses bords à zéro, ce qui est correct ici et interdit sur le flux
    (voir `RechantillonneurContinu`).
    """
    pcm = np.asarray(pcm)
    if pcm.size == 0 or int(taux_source) == int(taux_cible):
        return np.asarray(pcm, dtype=np.int16)
    import soxr

    x = pcm.astype(np.float32) / np.float32(32768.0)
    y = np.asarray(
        soxr.resample(x, int(taux_source), int(taux_cible)), dtype=np.float32
    )
    y = np.clip(y, -1.0, 1.0)
    return (y * np.float32(32767.0)).astype(np.int16)


# Split on sentence enders, but only when followed by space/end — keeps
# "3.14" and "M. Dupont" from being cut in half.
_SENTENCE_END = re.compile(r"(?<=[.!?…:;])\s+")

# Piper is non-autoregressive: it emits ONE chunk per sentence, so TTFA grows
# linearly with sentence length (measured: 130 ms @ 8 chars, 1387 ms @ 109).
# For the FIRST utterance only, we also break at clause boundaries so the user
# hears something fast; prosody across a comma is a cheap price for ~1 s.
_CLAUSE_END = re.compile(r"(?<=[.!?…:;,])\s+")


def _word_cut(text: str, cap: int):
    """
    Fallback cut at the last word boundary at or before `cap`.

    Punctuation-based cutting stalls when BRAIN opens with a long unpunctuated
    clause — measured: the first comma landed at 49 characters, so every
    clause-boundary setting produced an identical fragment and TTFA was set by
    the model's phrasing rather than by us. Cutting at a word bounds it.

    Returns (head, rest) or None if there is no usable boundary yet.
    """
    if len(text) < cap:
        return None
    window = text[:cap]
    space = window.rfind(" ")
    if space <= 0:
        return None
    return window[:space].strip(), text[space + 1:]


def _first_cut(text: str, splitter: re.Pattern, min_chars: int):
    """
    Cut at the earliest boundary whose head is at least `min_chars` long.

    Taking simply the first boundary would stall forever on openings like
    "Le facteur temps réel, ..." — the head is too short to synthesise, so the
    loop breaks and no audio is ever emitted while the buffer keeps growing.

    Returns (head, rest) or None if no boundary qualifies yet.
    """
    for m in splitter.finditer(text):
        head = text[: m.start()].strip()
        if len(head) >= min_chars:
            return head, text[m.end():]
    return None


class PiperTTS:
    """Streaming TTS. MOUTH-L2 when driven sentence-wise from a token stream."""

    def __init__(
        self,
        model_path: str = DEFAULT_VOICE,
        config_path: Optional[str] = None,
        use_cuda: bool = False,
        length_scale: Optional[float] = None,
        profile: str = "aurora",
        speaker_id: Optional[int] = None,
        demi_tons: float = 0.0,
    ):
        """
        Args:
            profile: voice character from src.mouth.voice_design.PROFILES.
                "flat" is the raw voice; "aurora" is the close-mic profile
                validated in production. "mother" is the hull treatment.
            length_scale: overrides the profile's rate if given.
            speaker_id: for multi-speaker voices (upmc, mls).
            demi_tons: transposition de la voix, en demi-tons. Les voix
                francaises natives de Piper sont claires (235 Hz mesures) et
                hyper-ambient demande grave ; on les descend ici plutot que de
                renoncer au francais natif. Le debit de synthese est accelere
                d'autant, car descendre par reechantillonnage allonge le bloc.
        """
        self.model_path = model_path
        self.config_path = config_path
        self.use_cuda = use_cuda
        self.profile = PROFILES.get(profile, FLAT)
        self.length_scale = (
            length_scale if length_scale is not None else self.profile.length_scale
        )
        self.speaker_id = speaker_id
        self.demi_tons = demi_tons
        if demi_tons:
            self.length_scale *= facteur_transposition(demi_tons)
        self.voice = None
        self.native_sample_rate = PIPELINE_RATE
        self.sample_rate = PIPELINE_RATE
        self._treatment: Optional[VoiceTreatment] = None
        self.ttfa_history: List[float] = []
        logger.info(
            f"PiperTTS: {model_path} profile={profile} cuda={use_cuda} "
            f"demi_tons={demi_tons}"
        )

    async def load_model(self) -> bool:
        def _load():
            from piper import PiperVoice

            return PiperVoice.load(
                self.model_path, config_path=self.config_path, use_cuda=self.use_cuda
            )

        try:
            t0 = time.perf_counter()
            self.voice = await asyncio.to_thread(_load)
            self.native_sample_rate = int(self.voice.config.sample_rate)
            # Le traitement DSP suit le taux natif (Tom : 44 100 Hz, le
            # low-pass aurora à 12 kHz y a de la place). On n'annonce
            # ensuite que PIPELINE_RATE, pour que le host-agent voie
            # Tom comme siwis/upmc.
            self.sample_rate = PIPELINE_RATE
            # Treatment is stateful across chunks — one instance per voice.
            self._treatment = (
                VoiceTreatment(self.profile, self.native_sample_rate)
                if self.profile is not FLAT
                else None
            )
            logger.info(
                f"voice loaded in {(time.perf_counter() - t0):.2f}s @ "
                f"{self.native_sample_rate} Hz -> {self.sample_rate} Hz"
            )
            return True
        except Exception as e:
            logger.error(f"piper load failed: {e}")
            self.voice = None
            return False

    # -- synthesis ---------------------------------------------------------

    def _synth_blocking(self, text: str, t0: float):
        """
        Returns (pcm, first_chunk_s, total_s).

        Piper yields AudioChunks as it decodes, so the timestamp of the *first*
        chunk is the real TTFA — the moment the host-agent could start playing.
        Timing the concatenated result instead would report full synthesis time
        and silently overstate latency by several hundred milliseconds.
        """
        from piper import SynthesisConfig

        cfg = SynthesisConfig(
            length_scale=self.length_scale,
            noise_scale=self.profile.noise_scale,
            noise_w_scale=self.profile.noise_w_scale,
            speaker_id=self.speaker_id,
        )
        parts, first_chunk_s = [], None
        for chunk in self.voice.synthesize(text, syn_config=cfg):
            if first_chunk_s is None:
                first_chunk_s = time.perf_counter() - t0
            parts.append(chunk.audio_int16_array)

        pcm = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int16)
        if self.demi_tons:
            pcm = transposer(pcm, self.demi_tons)
        if self._treatment is not None:
            pcm = self._treatment.process(pcm)
        pcm = ramener_au_taux_pipeline(
            pcm, self.native_sample_rate, self.sample_rate
        )
        return pcm, (first_chunk_s or 0.0), time.perf_counter() - t0

    async def synthesize(self, text: str) -> Dict[str, Any]:
        """Synthesise one block of text. Returns int16 PCM + timing."""
        if self.voice is None:
            return {"audio": np.zeros(0, dtype=np.int16), "sample_rate": self.sample_rate,
                    "ttfa_ms": 0.0, "synth_ms": 0.0, "rtf": 0.0, "stub": True}

        t0 = time.perf_counter()
        audio, first_chunk_s, total_s = await asyncio.to_thread(self._synth_blocking, text, t0)
        duration_s = len(audio) / self.sample_rate if self.sample_rate else 0.0

        self.ttfa_history.append(first_chunk_s * 1000)
        return {
            "audio": audio,
            "sample_rate": self.sample_rate,
            "ttfa_ms": first_chunk_s * 1000,   # audible latency
            "synth_ms": total_s * 1000,        # full synthesis cost
            "duration_s": duration_s,
            "rtf": total_s / duration_s if duration_s > 0 else 0.0,
        }

    async def synthesize_stream(
        self,
        token_stream: AsyncIterator[str],
        min_chars: int = 24,
        first_chunk_max_chars: int = 34,
        first_chunk_min_chars: int = 12,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Consume BRAIN's token deltas and emit audio per sentence.

        This is the piece that makes the round-trip budget work: the first
        sentence is spoken while BRAIN is still generating the rest. TTFA is
        reported on the first emitted chunk relative to the first token.

        Args:
            token_stream: async iterator of text deltas.
            min_chars: don't synthesise fragments shorter than this; wait for
                more text. Avoids choppy one-word utterances.
            first_chunk_max_chars: once the first fragment exceeds this, cut at
                the nearest clause boundary instead of waiting for a full stop.
                Bounds TTFA regardless of how verbose BRAIN's opening sentence
                turns out to be.
            first_chunk_min_chars: minimum length of the opening fragment.
                Piper's cost is linear in fragment length (measured: 130 ms at
                8 chars, 730 ms at 66), and the model itself is already 30x
                realtime — so TTFA is set by *how much text we wait for*, not
                by synthesis speed. This is the knob that moves it.
        """
        pending = ""
        first_token_at: Optional[float] = None
        index = 0

        async for item in token_stream:
            # Items may be plain text, or {"text": ..., "flush": bool}. A flush
            # item is spoken as its own utterance regardless of length — that is
            # how the router's filler ("Un instant.", 11 chars) gets out ahead
            # of the min-length gate instead of sitting in the buffer.
            if isinstance(item, dict):
                delta, flush = item.get("text", ""), bool(item.get("flush"))
            else:
                delta, flush = item, False

            if first_token_at is None:
                first_token_at = time.perf_counter()
            pending += delta

            if flush and pending.strip():
                spoken = strip_markup(pending)
                pending = ""
                if spoken:
                    result = await self.synthesize(spoken)
                    result.update({
                        "text": spoken,
                        "index": index,
                        "is_final": False,
                        "flushed": True,
                        "ttfa_perceived_ms": (
                            (time.perf_counter() - first_token_at) * 1000
                            if index == 0 else None
                        ),
                    })
                    index += 1
                    yield result
                continue

            while True:
                # aggressive clause split for the opening fragment only
                opening = index == 0 and len(pending) > first_chunk_min_chars
                splitter = _CLAUSE_END if opening else _SENTENCE_END
                floor = first_chunk_min_chars if opening else min_chars
                cut = _first_cut(pending, splitter, floor)
                if cut is None and opening:
                    # no punctuation arrived in time — cut at a word instead
                    cut = _word_cut(pending, first_chunk_max_chars)
                if cut is None:
                    break
                sentence, pending = cut
                sentence = strip_markup(sentence)
                if not sentence:
                    continue
                result = await self.synthesize(sentence)
                result.update(
                    {
                        "text": sentence,
                        "index": index,
                        "is_final": False,
                        "ttfa_perceived_ms": (
                            (time.perf_counter() - first_token_at) * 1000 if index == 0 else None
                        ),
                    }
                )
                index += 1
                yield result

        tail = strip_markup(pending)
        if tail:
            result = await self.synthesize(tail)
            result.update(
                {
                    "text": tail,
                    "index": index,
                    "is_final": True,
                    "ttfa_perceived_ms": (
                        (time.perf_counter() - first_token_at) * 1000
                        if index == 0 and first_token_at
                        else None
                    ),
                }
            )
            yield result
        else:
            yield {
                "audio": np.zeros(0, dtype=np.int16),
                "sample_rate": self.sample_rate,
                "text": "",
                "index": index,
                "is_final": True,
            }

    @staticmethod
    def to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
        """Wrap int16 PCM in a WAV container (for host-agent playback / debug)."""
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(audio.astype(np.int16).tobytes())
        return buf.getvalue()
