"""
EARS: Qwen3-ASR (transformers) — même contrat que FasterWhisperASR.

Option 2 (CHOIX 13 sept) : Qwen3-ASR-0.6B Q4, peak annoncé 1,2 Go.
Le vrai streaming officiel de Qwen passe par vLLM et réserve une fraction
du GPU (`gpu_memory_utilization`) : hors budget coloc ≤ 10 Go. On charge
donc via `Qwen3ASRModel.from_pretrained` (transformers, `load_in_4bit`)
et on re-décode une fenêtre croissante, comme faster-whisper.

TURN possède l'endpointing. Ici : utterance complète + partiels révisables.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
PEAK_VRAM_GB = 1.2

_MODEL_IDS = {
    "0.6B": "Qwen/Qwen3-ASR-0.6B",
    "0.6b": "Qwen/Qwen3-ASR-0.6B",
    "1.7B": "Qwen/Qwen3-ASR-1.7B",
    "1.7b": "Qwen/Qwen3-ASR-1.7B",
}

_ISO_TO_QWEN = {
    "fr": "French",
    "en": "English",
    "zh": "Chinese",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
}

_QWEN_TO_ISO = {name.lower(): iso for iso, name in _ISO_TO_QWEN.items()}


def _audio_tower_of(wrapper: Any) -> Any:
    model = getattr(wrapper, "model", None)
    if model is None:
        return None
    thinker = getattr(model, "thinker", None)
    if thinker is None:
        return None
    return getattr(thinker, "audio_tower", None)


def _cast_audio_tower_input_features(module, args):
    """Caste ``input_features`` vers ``conv2d1.weight.dtype`` ; laisse les lens."""
    if not args:
        return None
    features = args[0]
    conv = getattr(module, "conv2d1", None)
    weight = getattr(conv, "weight", None) if conv is not None else None
    if weight is None:
        return None
    import torch

    if not torch.is_tensor(features) or not torch.is_floating_point(features):
        return None
    if features.dtype == weight.dtype:
        return None
    return (features.to(dtype=weight.dtype),) + tuple(args[1:])


def install_audio_tower_dtype_hook(wrapper: Any) -> Any:
    """Pose un ``forward_pre_hook`` sur ``wrapper.model.thinker.audio_tower``.

    qwen-asr 0.0.6 recaste le processor vers ``model.dtype`` (souvent float32
    sous 4-bit) avant ``generate``. Le frontend ``conv2d1`` reste en float16 :
    sans ce hook, le premier tour lève ``Input type (float) and bias type (Half)``.
    No-op si le wrapper n'expose pas encore la tour. Le handle vit sur
    ``wrapper._audio_tower_pre_hook``.
    """
    audio_tower = _audio_tower_of(wrapper)
    if audio_tower is None or not hasattr(audio_tower, "register_forward_pre_hook"):
        return None
    conv = getattr(audio_tower, "conv2d1", None)
    weight = getattr(conv, "weight", None) if conv is not None else None
    cible = getattr(weight, "dtype", None)
    poids = getattr(weight, "dtype", None)
    msg = f"audio_tower dtype entrant visé={cible} conv2d1.weight.dtype={poids}"
    logger.info(msg)
    # serve_hostagent redirige stdout vers /tmp/hostagent.log sans basicConfig :
    # logger.info resterait invisible, print est la journalisation effective.
    print(msg, flush=True)
    ancien = getattr(wrapper, "_audio_tower_pre_hook", None)
    if ancien is not None:
        try:
            ancien.remove()
        except Exception:
            pass
    handle = audio_tower.register_forward_pre_hook(_cast_audio_tower_input_features)
    wrapper._audio_tower_pre_hook = handle
    return handle


class Qwen3ASR:
    """Qwen3-ASR via transformers 4-bit. EARS-L2 candidate, drop-in Whisper."""

    def __init__(
        self,
        model_size: str = "0.6B",
        language: str = "fr",
        device: str = "cuda",
        compute_type: Optional[str] = None,
    ):
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type or "q4"
        self.model = None
        self.revisions = 0
        self._last_partial = ""
        logger.info(
            f"Qwen3ASR: {self.model_id} / {language} / {device}:{self.compute_type}"
        )

    @property
    def model_id(self) -> str:
        return _MODEL_IDS.get(self.model_size, self.model_size)

    def _wants_q4(self) -> bool:
        return self.compute_type.lower() in {"q4", "4bit", "int4", "nf4", "q4_k_m"}

    def _from_pretrained_kwargs(self) -> Dict[str, Any]:
        """Kwargs transformers — jamais vLLM / gpu_memory_utilization."""
        on_cuda = str(self.device).startswith("cuda")
        kwargs: Dict[str, Any] = {
            "device_map": "cuda:0" if on_cuda else "cpu",
            "max_inference_batch_size": 1,
            "max_new_tokens": 256,
        }
        if self._wants_q4() and on_cuda:
            # bitsandbytes ne quantifie que les Linear. ``dtype=float16``
            # aligne le chargement, mais sous 4-bit ``model.dtype`` reste
            # souvent float32 : qwen-asr recaste alors les features en fp32
            # avant audio_tower. Le hook pose le cast réel après chargement.
            import torch

            kwargs["load_in_4bit"] = True
            kwargs["dtype"] = torch.float16
        return kwargs

    def _language_for_backend(self) -> str:
        key = (self.language or "").strip()
        return _ISO_TO_QWEN.get(key.lower(), key or "French")

    def _iso_from_backend(self, backend_lang: str) -> str:
        token = (backend_lang or "").split(",")[0].strip().lower()
        return _QWEN_TO_ISO.get(token, self.language)

    def _load(self):
        """Charge qwen-asr. Point de greffe des tests (pas de réseau)."""
        from qwen_asr import Qwen3ASRModel

        wrapper = Qwen3ASRModel.from_pretrained(
            self.model_id, **self._from_pretrained_kwargs()
        )
        install_audio_tower_dtype_hook(wrapper)
        return wrapper

    async def load_model(self) -> bool:
        """Charge les poids (travail bloquant hors boucle). Pas de vLLM."""
        try:
            t0 = time.perf_counter()
            self.model = await asyncio.to_thread(self._load)
            logger.info(f"model loaded in {(time.perf_counter() - t0):.1f}s")
        except Exception as e:
            logger.error(f"failed to load {self.model_id}: {e}")
            self.model = None
        return self.model is not None

    # -- inference ---------------------------------------------------------

    def _unpack(self, raw: Any) -> Any:
        if isinstance(raw, (list, tuple)):
            return raw[0] if raw else _EmptyResult()
        return raw

    def _decode(self, audio: np.ndarray, beam_size: int) -> Dict[str, Any]:
        del beam_size  # contrat FasterWhisper ; Qwen n'a pas de beam
        raw = self.model.transcribe(
            (audio, SAMPLE_RATE),
            language=self._language_for_backend(),
        )
        item = self._unpack(raw)
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            backend_lang = str(item.get("language") or "")
        else:
            text = str(getattr(item, "text", "") or "").strip()
            backend_lang = str(getattr(item, "language", "") or "")
        duration_s = len(audio) / SAMPLE_RATE
        segs: List[Dict[str, Any]] = (
            [{"start": 0.0, "end": duration_s, "text": text}] if text else []
        )
        return {
            "text": text,
            "segments": segs,
            "language": self._iso_from_backend(backend_lang),
            "language_probability": 1.0,
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


class _EmptyResult:
    text = ""
    language = ""
