"""Contrat du MOUTH distant, sans modele ni GPU local.

Le transport est double : ces tests ne parlent jamais au reseau et ne lisent
aucune cle reelle. Le fournisseur vise l'API ``/audio/speech`` de type OpenAI.
"""
from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path

import numpy as np

from src.mouth.remote_tts import RemoteTTS


def _wav(sample_rate: int = 24000) -> bytes:
    audio = np.array([0, 1200, -1200, 32767], dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(audio.tobytes())
    return buf.getvalue()


class _Response:
    def __init__(self, *, status=200, content=b"", payload=None):
        self.status_code = status
        self.content = content
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Client:
    def __init__(self, *, voices_status=200, speech_status=200):
        self.voices_status = voices_status
        self.speech_status = speech_status
        self.gets = []
        self.posts = []
        self.closed = False

    async def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if url.endswith("/models"):
            return _Response(payload={"data": [{"id": "stepaudio-2.5-tts"}]})
        return _Response(
            status=self.voices_status,
            payload={
                "data": [
                    {"id": "voice-from-api", "name": "Voix API"},
                    "second-api-voice",
                ]
            },
        )

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return _Response(status=self.speech_status, content=_wav())

    async def aclose(self):
        self.closed = True


def _remote(client, **kwargs):
    return RemoteTTS(
        base_url="https://tts.invalid/v1",
        api_key="secret-never-log",
        model="stepaudio-2.5-tts",
        voice="voice-from-api",
        client=client,
        **kwargs,
    )


def test_load_model_teste_la_cle_puis_recupere_le_catalogue():
    client = _Client()
    tts = _remote(client)

    assert asyncio.run(tts.load_model()) is True
    assert [url for url, _ in client.gets] == [
        "https://tts.invalid/v1/models",
        "https://tts.invalid/v1/audio/voices",
    ]
    assert tts.available_voices == ("voice-from-api", "second-api-voice")
    assert client.gets[0][1]["headers"]["Authorization"] == "Bearer secret-never-log"


def test_catalogue_interdit_ne_bloque_pas_une_voix_configuree():
    client = _Client(voices_status=403)
    tts = _remote(client)

    assert asyncio.run(tts.load_model()) is True
    assert tts.available_voices == ()


def test_synthesize_envoie_le_contrat_openai_et_decode_le_wav():
    client = _Client()
    tts = _remote(client)
    assert asyncio.run(tts.load_model()) is True

    out = asyncio.run(tts.synthesize("Bonsoir Thomas."))

    url, call = client.posts[0]
    assert url == "https://tts.invalid/v1/audio/speech"
    assert call["json"] == {
        "model": "stepaudio-2.5-tts",
        "voice": "voice-from-api",
        "input": "Bonsoir Thomas.",
        "response_format": "wav",
    }
    assert out["audio"].dtype == np.int16
    assert out["audio"].tolist() == [0, 1200, -1200, 32767]
    assert out["sample_rate"] == 24000
    assert out["remote"] is True


def test_stream_respecte_phrase_et_flush():
    client = _Client()
    tts = _remote(client)
    assert asyncio.run(tts.load_model()) is True

    async def tokens():
        yield {"text": "Un instant.", "flush": True}
        yield "Voici la reponse complete. "
        yield "Et sa suite."

    async def run():
        return [piece async for piece in tts.synthesize_stream(tokens())]

    outs = asyncio.run(run())
    texts = [call[1]["json"]["input"] for call in client.posts]
    assert texts == ["Un instant.", "Voici la reponse complete.", "Et sa suite."]
    assert outs[0]["flushed"] is True
    assert outs[-1]["is_final"] is True


def test_echec_distant_delegue_au_repli_injecte_sans_le_charger():
    class _Fallback:
        sample_rate = 22050

        def __init__(self):
            self.calls = []

        async def synthesize(self, text):
            self.calls.append(text)
            return {"audio": np.ones(2, dtype=np.int16), "sample_rate": 22050}

    client = _Client(speech_status=503)
    fallback = _Fallback()
    tts = _remote(client, fallback=fallback)
    assert asyncio.run(tts.load_model()) is True

    out = asyncio.run(tts.synthesize("Repli."))

    assert fallback.calls == ["Repli."]
    assert out["fallback"] is True
    assert out["remote"] is False


def test_configuration_incomplete_echoue_fermee_sans_reseau():
    client = _Client()
    tts = RemoteTTS(base_url="", api_key="", model="", voice="", client=client)

    assert asyncio.run(tts.load_model()) is False
    assert client.gets == [] and client.posts == []


def test_from_env_accepte_les_alias_stepfun(monkeypatch):
    monkeypatch.setenv("STEPFUN_BASE_URL", "https://api.stepfun.invalid/step_plan/v1/")
    monkeypatch.setenv("STEPFUN_API_KEY", "step-secret")
    monkeypatch.setenv("MOUTH_REMOTE_MODEL", "stepaudio-2.5-tts")
    monkeypatch.setenv("MOUTH_REMOTE_VOICE", "chosen-after-catalog")

    tts = RemoteTTS.from_env(client=_Client())

    assert tts.base_url == "https://api.stepfun.invalid/step_plan/v1"
    assert tts.model == "stepaudio-2.5-tts"
    assert tts.voice == "chosen-after-catalog"


def test_module_ne_peut_pas_charger_un_gpu_local():
    source = Path("src/mouth/remote_tts.py").read_text(encoding="utf-8")
    for interdit in (
        "import torch",
        "import subprocess",
        "magpie_tts",
        "pocket_tts",
        "supertonic_tts",
        "piper_tts",
        "nvidia-smi",
    ):
        assert interdit not in source
