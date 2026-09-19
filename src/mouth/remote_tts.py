"""MOUTH distant via une API compatible ``POST /audio/speech``.

Ce module est volontairement sans moteur local : il n'importe ni framework ML,
ni backend MOUTH local, et ne lance aucun processus. Un repli peut etre injecte
par l'appelant, ce qui laisse a l'orchestrateur la propriete de la voix locale
deja chargee sans risquer un second chargement GPU.

Le catalogue de voix n'est jamais code en dur. Apres le probe d'authentification
``GET /models``, ``load_model`` tente ``GET /audio/voices``. Certains forfaits
refusent ce catalogue ; une voix explicitement configuree reste alors utilisable.
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
import wave
from typing import Any, AsyncIterator, Dict, Optional

import numpy as np

from src.mouth.normalize import strip_markup

logger = logging.getLogger(__name__)

_SENTENCE_END = re.compile(r"(?<=[.!?…:;])\s+")


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.strip('/')}"


def _voice_ids(payload: Any) -> tuple[str, ...]:
    """Extrait les identifiants des formes de catalogue les plus courantes."""
    if isinstance(payload, dict):
        entries = payload.get("data", payload.get("voices", []))
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []

    found: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str):
            voice_id = entry
        elif isinstance(entry, dict):
            voice_id = entry.get("id") or entry.get("voice_id") or entry.get("name")
        else:
            voice_id = None
        if voice_id:
            value = str(voice_id).strip()
            if value and value not in found:
                found.append(value)
    return tuple(found)


def _decode_wav(blob: bytes) -> tuple[np.ndarray, int]:
    """Decode un WAV PCM 16 bits mono ou stereo en PCM int16 mono."""
    with wave.open(io.BytesIO(blob), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("MOUTH distant: WAV autre que PCM 16 bits")
        sample_rate = int(source.getframerate())
        channels = int(source.getnchannels())
        pcm = np.frombuffer(
            source.readframes(source.getnframes()), dtype="<i2"
        ).astype(np.int16, copy=False)

    if channels > 1:
        pcm = pcm.reshape(-1, channels).astype(np.int32).mean(axis=1).astype(np.int16)
    return pcm.copy(), sample_rate


def _first_sentence(text: str, min_chars: int) -> Optional[tuple[str, str]]:
    for match in _SENTENCE_END.finditer(text):
        head = text[: match.start()].strip()
        if len(head) >= min_chars:
            return head, text[match.end() :]
    return None


class RemoteTTS:
    """Backend MOUTH sans calcul local pour les API ``/audio/speech``.

    ``client`` et ``fallback`` sont injectables pour les tests et l'integration.
    Le fallback n'est ni charge ni ferme ici : son cycle de vie appartient au
    host-agent, ce qui empeche tout chargement GPU implicite.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        voice: str,
        client=None,
        fallback=None,
        timeout_s: float = 30.0,
        auth_path: str = "models",
        voices_path: str = "audio/voices",
        speech_path: str = "audio/speech",
    ):
        self.base_url = str(base_url or "").rstrip("/")
        self.api_key = str(api_key or "")
        self.model = str(model or "").strip()
        self.voice = str(voice or "").strip()
        self.timeout_s = float(timeout_s)
        self.auth_path = auth_path
        self.voices_path = voices_path
        self.speech_path = speech_path
        self.client = client
        self.fallback = fallback
        self._owns_client = client is None
        self._ready = False
        self.available_voices: tuple[str, ...] = ()
        self.sample_rate = int(getattr(fallback, "sample_rate", 24000))

    @classmethod
    def from_env(cls, *, client=None, fallback=None) -> "RemoteTTS":
        """Construit le backend generique ; les alias StepFun sont acceptes."""
        base_url = os.getenv("MOUTH_REMOTE_BASE_URL") or os.getenv(
            "STEPFUN_BASE_URL", ""
        )
        api_key = os.getenv("MOUTH_REMOTE_API_KEY") or os.getenv(
            "STEPFUN_API_KEY", ""
        )
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=os.getenv("MOUTH_REMOTE_MODEL", ""),
            voice=os.getenv("MOUTH_REMOTE_VOICE", ""),
            client=client,
            fallback=fallback,
            timeout_s=float(os.getenv("MOUTH_REMOTE_TIMEOUT_S", "30")),
            auth_path=os.getenv("MOUTH_REMOTE_AUTH_PATH", "models"),
            voices_path=os.getenv("MOUTH_REMOTE_VOICES_PATH", "audio/voices"),
            speech_path=os.getenv("MOUTH_REMOTE_SPEECH_PATH", "audio/speech"),
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model and self.voice)

    async def _ensure_client(self):
        if self.client is None:
            import httpx

            self.client = httpx.AsyncClient(timeout=self.timeout_s)
        return self.client

    async def list_voices(self) -> tuple[str, ...]:
        """Recupere le catalogue du fournisseur sans valeur locale de secours."""
        client = await self._ensure_client()
        response = await client.get(
            _endpoint(self.base_url, self.voices_path), headers=self._headers
        )
        response.raise_for_status()
        self.available_voices = _voice_ids(response.json())
        return self.available_voices

    async def load_model(self) -> bool:
        """Valide la configuration et la cle ; ne charge aucun modele local."""
        if not self._configured():
            logger.error(
                "MOUTH distant non configure (URL, cle, modele et voix requis)"
            )
            return False

        try:
            client = await self._ensure_client()
            probe = await client.get(
                _endpoint(self.base_url, self.auth_path), headers=self._headers
            )
            probe.raise_for_status()
        except Exception as exc:
            logger.error(
                "MOUTH distant: probe d'authentification echoue (%s)",
                type(exc).__name__,
            )
            return False

        try:
            await self.list_voices()
        except Exception as exc:
            # Le forfait Step Plan observe le 19/09 autorise la synthese mais
            # pas le catalogue. La voix choisie explicitement reste valide.
            self.available_voices = ()
            logger.info(
                "MOUTH distant: catalogue de voix indisponible (%s)",
                type(exc).__name__,
            )

        self._ready = True
        logger.info(
            "MOUTH distant pret: modele=%s voix=%s catalogue=%d",
            self.model,
            self.voice,
            len(self.available_voices),
        )
        return True

    async def _fallback_or_empty(self, text: str, exc: Exception) -> Dict[str, Any]:
        logger.warning("MOUTH distant: synthese echouee (%s)", type(exc).__name__)
        if self.fallback is not None:
            result = await self.fallback.synthesize(text)
            result.update({"remote": False, "fallback": True})
            return result
        return {
            "audio": np.zeros(0, dtype=np.int16),
            "sample_rate": self.sample_rate,
            "remote": False,
            "stub": True,
            "error_type": type(exc).__name__,
        }

    async def synthesize(self, text: str) -> Dict[str, Any]:
        spoken = strip_markup(text)
        if not self._ready:
            return await self._fallback_or_empty(
                spoken, RuntimeError("MOUTH distant non initialise")
            )

        payload = {
            "model": self.model,
            "voice": self.voice,
            "input": spoken,
            "response_format": "wav",
        }
        started = time.perf_counter()
        try:
            client = await self._ensure_client()
            response = await client.post(
                _endpoint(self.base_url, self.speech_path),
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            pcm, sample_rate = _decode_wav(response.content)
        except Exception as exc:
            return await self._fallback_or_empty(spoken, exc)

        elapsed_s = time.perf_counter() - started
        self.sample_rate = sample_rate
        duration_s = len(pcm) / sample_rate if sample_rate else 0.0
        return {
            "audio": pcm,
            "sample_rate": sample_rate,
            # L'API renvoie ici un WAV entier : le premier octet utile et la
            # fin de synthese ont la meme mesure cote client.
            "ttfa_ms": elapsed_s * 1000,
            "synth_ms": elapsed_s * 1000,
            "duration_s": duration_s,
            "rtf": elapsed_s / duration_s if duration_s else 0.0,
            "remote": True,
        }

    async def synthesize_stream(
        self, token_stream: AsyncIterator, min_chars: int = 24, **_
    ) -> AsyncIterator[Dict[str, Any]]:
        """Emet un WAV par phrase ; l'API distante elle-meme reste non streaming."""
        pending = ""
        index = 0

        async def emit(text: str, *, flushed: bool = False):
            nonlocal index
            result = await self.synthesize(text)
            result.update(
                {
                    "text": text,
                    "index": index,
                    "is_final": False,
                    "flushed": flushed,
                }
            )
            index += 1
            return result

        async for item in token_stream:
            if isinstance(item, dict):
                delta = str(item.get("text", ""))
                flush = bool(item.get("flush"))
            else:
                delta, flush = str(item), False
            pending += delta

            if flush and pending.strip():
                spoken, pending = strip_markup(pending), ""
                if spoken:
                    yield await emit(spoken, flushed=True)
                continue

            while True:
                cut = _first_sentence(pending, min_chars)
                if cut is None:
                    break
                sentence, pending = cut
                sentence = strip_markup(sentence)
                if sentence:
                    yield await emit(sentence)

        tail = strip_markup(pending)
        if tail:
            yield await emit(tail)
        yield {
            "audio": np.zeros(0, dtype=np.int16),
            "sample_rate": self.sample_rate,
            "text": "",
            "index": index,
            "is_final": True,
        }

    async def close(self) -> None:
        """Ferme seulement le client HTTP dont cette instance est proprietaire."""
        if self._owns_client and self.client is not None:
            await self.client.aclose()
            self.client = None
        self._ready = False
