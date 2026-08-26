#!/usr/bin/env python3
"""Point d'entrée conteneur : transport host-agent + chaîne EARS / BRAIN / MOUTH.

    python3 dev/scripts/serve_hostagent.py
    python native/hostagent/talk.py
"""
from __future__ import annotations

import contextlib

import asyncio
import ipaddress
import os
import sys
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame
from src.hostagent.transport import create_transport_app

HOST = "0.0.0.0"
PORT = 8001
SECRET_DEVELOPPEMENT = "partage-installation"
VOIX_PIPER = "/workspace/models/piper/fr_FR-siwis-medium.onnx"


def lire_secret() -> str:
    """Secret d'installation, ou valeur de développement si la variable manque."""
    secret = os.environ.get("MOTHER_HOSTAGENT_SECRET")
    if secret:
        return secret
    print(
        "ATTENTION : MOTHER_HOSTAGENT_SECRET est absent. "
        "Secret de développement utilisé (« partage-installation »). "
        "Ne pas exposer ce service hors de la machine.",
        file=sys.stderr,
        flush=True,
    )
    return SECRET_DEVELOPPEMENT


def _vers_float32(echantillons) -> np.ndarray:
    """Convertit int16 → float32 ∈ [-1, 1] ; laisse le float32 intact."""
    arr = np.asarray(echantillons).reshape(-1)
    if arr.dtype == np.int16:
        return arr.astype(np.float32) / np.float32(32768.0)
    return np.ascontiguousarray(arr, dtype=np.float32)


def _rechantillonner(pcm: np.ndarray, orig_sr: int) -> np.ndarray:
    """Ramène le PCM MOUTH à 16 kHz, le taux du canal host-agent."""
    if orig_sr == SAMPLE_RATE or pcm.size == 0:
        return pcm
    import librosa

    return librosa.resample(pcm, orig_sr=orig_sr, target_sr=SAMPLE_RATE)


def _trames_depuis_pcm(pcm: np.ndarray, leftover: list) -> list[AudioFrame]:
    """Découpe en trames de FRAME_SAMPLES. Le reliquat reste pour le morceau suivant."""
    convertis = np.concatenate([leftover[0], pcm]) if leftover[0].size else pcm
    n_complet = (convertis.size // FRAME_SAMPLES) * FRAME_SAMPLES
    trames = []
    for debut in range(0, n_complet, FRAME_SAMPLES):
        chunk = np.array(
            convertis[debut : debut + FRAME_SAMPLES],
            dtype=np.float32,
            copy=True,
        )
        trames.append(AudioFrame(samples=chunk))
    leftover[0] = np.array(convertis[n_complet:], dtype=np.float32, copy=True)
    return trames


def _vider_reliquat(leftover: list) -> list[AudioFrame]:
    """Émet la dernière trame, paddée de silence : on ne jette pas la queue."""
    reste = leftover[0]
    leftover[0] = np.zeros(0, dtype=np.float32)
    if reste.size == 0:
        return []
    pad = np.zeros(FRAME_SAMPLES, dtype=np.float32)
    pad[: reste.size] = reste
    return [AudioFrame(samples=pad)]


def _json_trames(trames: list[AudioFrame]) -> dict:
    """Même encodage qu'à l'aller : listes de flottants, une par trame."""
    return {
        "type": "invoke",
        "primitive": "audio.render",
        "frames": [trame.samples.tolist() for trame in trames],
    }


class HostPipeline:
    """Modèles chargés une fois ; chaque tour de parole réutilise la même instance."""

    def __init__(self) -> None:
        self.asr = None
        self.brain = None
        self.tts = None
        self._websocket = None
        self._lock = asyncio.Lock()

    def peer_address_of(self, websocket) -> str:
        """Mémorise le socket pour le retour audio, et tranche la localité.

        Docker Desktop présente l'hôte derrière une passerelle, pas en
        loopback, alors que le client parle bien à localhost:8001. On
        ramène ce cas à 127.0.0.1 ; le secret, lui, reste exigé.
        """
        self._websocket = websocket
        host = websocket.client.host if websocket.client is not None else "127.0.0.1"
        try:
            if ipaddress.ip_address(host).is_loopback:
                return host
        except ValueError:
            pass
        return "127.0.0.1"

    def on_frames(self, frames) -> None:
        """Rappel synchrone du transport : enfile le tour sur la boucle uvicorn."""
        websocket = self._websocket
        asyncio.get_running_loop().create_task(self._tour(frames, websocket))

    async def load(self) -> None:
        """Charge EARS, BRAIN et MOUTH une seule fois, avant d'accepter un client."""
        from src.brain.factory import build_brain_with_fallback
        from src.ears.faster_whisper_asr import FasterWhisperASR
        from src.mouth.piper_tts import PiperTTS

        model_size = os.getenv("EARS_MODEL", "large-v3-turbo")
        device = os.getenv("EARS_DEVICE", "cuda")
        voix = os.getenv("MOUTH_VOICE", VOIX_PIPER)

        print(f"EARS  : chargement {model_size} sur {device}…", flush=True)
        self.asr = FasterWhisperASR(
            model_size=model_size, language="fr", device=device
        )
        if not await self.asr.load_model():
            print("EARS  : modèle indisponible", flush=True)
            raise SystemExit(1)
        await self.asr.transcribe(
            np.zeros(SAMPLE_RATE, dtype=np.float32), beam_size=1
        )

        self.brain = await build_brain_with_fallback()
        health = await self.brain.health()
        print(
            f"BRAIN : {self.brain.name} @ {self.brain.api_endpoint} — {health['detail']}",
            flush=True,
        )

        print(f"MOUTH : chargement {voix}…", flush=True)
        self.tts = PiperTTS(model_path=voix)
        if not await self.tts.load_model():
            print(
                "MOUTH : voix indisponible — lancer dev/scripts/fetch_models.sh core",
                flush=True,
            )
            raise SystemExit(1)

        print(f"écoute sur {HOST}:{PORT} /hostagent", flush=True)

    async def close(self) -> None:
        if self.brain is not None:
            await self.brain.close()

    async def _envoyer(self, websocket, trames: list[AudioFrame]) -> None:
        """Envoie des paquets d'une seconde, ou un marqueur vide de fin de tour."""
        if websocket is None:
            return
        if not trames:
            await websocket.send_json(_json_trames([]))
            return
        paquet = SAMPLE_RATE // FRAME_SAMPLES
        for debut in range(0, len(trames), paquet):
            await websocket.send_json(_json_trames(trames[debut : debut + paquet]))

    async def _tour(self, frames, websocket) -> None:
        async with self._lock:
            await self._enchainer(frames, websocket)

    async def _enchainer(self, frames, websocket) -> None:
        leftover = [np.zeros(0, dtype=np.float32)]
        try:
            if not frames:
                await self._envoyer(websocket, [])
                return

            audio = np.concatenate([trame.samples for trame in frames])
            result = await self.asr.transcribe(audio)
            prompt = (result.get("text") or "").strip()
            print(
                f"EARS  : \"{prompt}\" — {result.get('latency_ms', 0):.0f} ms",
                flush=True,
            )
            if not prompt:
                print("EARS  : rien transcrit — tour abandonné", flush=True)
                await self._envoyer(websocket, [])
                return

            ttft_ms = None
            full_text = []
            brain_error = None

            async def deltas():
                nonlocal ttft_ms, brain_error
                async for chunk in self.brain.query_streaming(prompt):
                    if chunk.get("ttft_ms") is not None:
                        ttft_ms = chunk["ttft_ms"]
                    if chunk["stop_reason"] == "error":
                        brain_error = chunk.get("error", "unknown")
                    if chunk["delta"]:
                        full_text.append(chunk["delta"])
                        yield chunk["delta"]

            t_gen = time.perf_counter()
            n_chunks = 0
            async for out in self.tts.synthesize_stream(deltas()):
                pcm = _rechantillonner(
                    _vers_float32(out.get("audio", [])),
                    int(out.get("sample_rate") or self.tts.sample_rate),
                )
                trames = _trames_depuis_pcm(pcm, leftover)
                if not trames:
                    continue
                n_chunks += 1
                if n_chunks == 1:
                    print(
                        f"MOUTH : premier audio après {(time.perf_counter() - t_gen) * 1000:.0f} ms",
                        flush=True,
                    )
                await self._envoyer(websocket, trames)

            queue = _vider_reliquat(leftover)
            if queue:
                await self._envoyer(websocket, queue)

            text = "".join(full_text).strip()
            if not text:
                print(f"BRAIN : rien produit — {brain_error}", flush=True)
            else:
                suffixe = "..." if len(text) > 120 else ""
                print(f"BRAIN : \"{text[:120]}{suffixe}\"", flush=True)
                if ttft_ms is not None:
                    print(f"BRAIN : TTFT {ttft_ms:.0f} ms", flush=True)

            await self._envoyer(websocket, [])
        except Exception as exc:
            print(f"tour interrompu : {exc}", flush=True)
            try:
                await self._envoyer(websocket, [])
            except Exception:
                return


def main() -> None:
    secret = lire_secret()
    pipeline = HostPipeline()
    app = create_transport_app(
        secret=secret,
        on_frames=pipeline.on_frames,
        peer_address_of=pipeline.peer_address_of,
    )
    # FastAPI 0.141 a retire add_event_handler : les evenements startup/shutdown
    # passent desormais par un gestionnaire de contexte lifespan. On charge les
    # modeles une seule fois, a l'ouverture, et jamais par tour de parole.
    @contextlib.asynccontextmanager
    async def lifespan(_app):
        await pipeline.load()
        try:
            yield
        finally:
            await pipeline.close()

    app.router.lifespan_context = lifespan

    import uvicorn

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        ws_max_size=16 * 1024 * 1024,
    )


if __name__ == "__main__":
    main()
