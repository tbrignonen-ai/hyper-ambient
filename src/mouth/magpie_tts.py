"""
MOUTH: MagpieTTS multilingual 357M — voix Sofia, GGUF.

Thomas a retenu Sofia à la dégustation. Magpie saute les chiffres arabes
(« 24 », « 12 ») : on verbalise avant synthèse. Pas de réglage de débit.

Le modèle reste chargé : un `nemo-speech serve` persistant, pas un
exécutable relancé à chaque phrase. Port dédié, jamais 8080 (llama-server).
Device : MOUTH_DEVICE (défaut cuda), repli cpu si CUDA indisponible.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import numpy as np

from src.mouth.normalize import nombres_en_lettres, strip_markup

logger = logging.getLogger(__name__)

MAGPIE_ROOT = "/workspace/models/tts-bench/magpie"
PORTS_RESERVES = {8001, 8080, 8090}
_BINAIRES_CUDA = (
    Path("/workspace/models/asr-bench/nemotron.new/bin/nemo-speech"),
    Path("/workspace/models/asr-bench/nemotron/bin/nemo-speech"),
)


def _port_libre(brut) -> int:
    try:
        port = int(brut)
    except (TypeError, ValueError):
        port = 8092
    if port in PORTS_RESERVES:
        return 8092
    return port


def _cuda_disponible() -> bool:
    vis = os.environ.get("CUDA_VISIBLE_DEVICES")
    if vis is not None and vis.strip() == "":
        return False
    try:
        r = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def _resoudre_device(demande: Optional[str]) -> str:
    brut = demande if demande is not None else os.getenv("MOUTH_DEVICE", "cuda")
    brut = str(brut or "cuda").strip().lower()
    if brut in {"cuda", "gpu"}:
        return "cuda" if _cuda_disponible() else "cpu"
    return "cpu"


class _MagpieServe:
    """Client HTTP du serveur persistant. Une instance = un modèle chargé."""

    def __init__(self, url: str, proc: Optional[subprocess.Popen] = None):
        self.url = url.rstrip("/")
        self.proc = proc
        self.sample_rate = 22050

    def synthesize(self, text: str, voice: str, language: str, **_) -> np.ndarray:
        # nemo-speech tamponne le WAV entier : pas de flux intra-phrase
        # (serve n'expose que le realtime ASR en WebSocket).
        corps = json.dumps(
            {
                "input": text,
                "voice": voice,
                "language": language,
                "response_format": "wav",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/v1/audio/speech",
            data=corps,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            wav = resp.read()
        return _pcm_depuis_wav(wav, self)


class MagpieTTS:
    """Drop-in for PocketTTS / PiperTTS / SupertonicTTS."""

    def __init__(
        self,
        voice: str = "Sofia",
        language: str = "fr",
        device: Optional[str] = None,
        model_dir: str = MAGPIE_ROOT,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
    ):
        self.voice = voice
        self.language = language
        self.device = _resoudre_device(device)
        self.model_dir = model_dir
        self.host = host
        self.port = _port_libre(
            port if port is not None else os.getenv("MOUTH_MAGPIE_PORT", "8092")
        )
        self.engine = None
        self.sample_rate = 22050
        logger.info(f"MagpieTTS: {voice} lang={language} device={self.device}")

    async def load_model(self) -> bool:
        def _load():
            url = f"http://{self.host}:{self.port}"
            proc = None
            if _pret(url) and _serve_device(self.port) != self.device:
                _arreter_serve(self.port)
            if not _pret(url):
                proc = _demarrer_serveur(
                    root=Path(self.model_dir),
                    host=self.host,
                    port=self.port,
                    device=self.device,
                )
                time.sleep(0.5)
                if proc.poll() is not None and self.device == "cuda":
                    logger.warning("magpie serve cuda mort au boot, repli cpu")
                    self.device = "cpu"
                    proc = _demarrer_serveur(
                        root=Path(self.model_dir),
                        host=self.host,
                        port=self.port,
                        device="cpu",
                    )
                if not _attendre_pret(url):
                    if self.device == "cuda":
                        _arreter_serve(self.port)
                        self.device = "cpu"
                        proc = _demarrer_serveur(
                            root=Path(self.model_dir),
                            host=self.host,
                            port=self.port,
                            device="cpu",
                        )
                        if not _attendre_pret(url):
                            return None
                    else:
                        return None
            return _MagpieServe(url, proc)

        try:
            t0 = time.perf_counter()
            self.engine = await asyncio.to_thread(_load)
            if self.engine is None:
                logger.error("magpie serve injoignable")
                return False
            self.sample_rate = int(self.engine.sample_rate)
            logger.info(
                f"magpie loaded in {time.perf_counter() - t0:.1f}s @ {self.sample_rate} Hz"
            )
            await self.synthesize("Prête.")
            return True
        except Exception as e:
            logger.error(f"magpie load failed: {e}")
            self.engine = None
            return False

    def _render(self, text: str) -> np.ndarray:
        spoken = nombres_en_lettres(strip_markup(text))
        pcm = self.engine.synthesize(
            spoken, voice=self.voice, language=self.language
        )
        x = np.asarray(pcm).ravel()
        if x.dtype != np.int16:
            x = np.asarray(x, dtype=np.float32)
            pic = float(np.max(np.abs(x))) if x.size else 0.0
            if pic > 1.0:
                x = x / pic * 0.99
            x = np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)
        return x

    async def synthesize(self, text: str) -> Dict[str, Any]:
        if self.engine is None:
            return {
                "audio": np.zeros(0, dtype=np.int16),
                "sample_rate": self.sample_rate,
                "stub": True,
            }
        t0 = time.perf_counter()
        pcm = await asyncio.to_thread(self._render, text)
        synth_ms = (time.perf_counter() - t0) * 1000
        return {
            "audio": pcm,
            "sample_rate": self.sample_rate,
            "ttfa_ms": synth_ms,
            "synth_ms": synth_ms,
        }

    async def synthesize_stream(
        self,
        token_stream: AsyncIterator,
        min_chars: int = 24,
        first_chunk_max_chars: int = 34,
        **_,
    ) -> AsyncIterator[Dict[str, Any]]:
        from src.mouth.piper_tts import _CLAUSE_END, _first_cut, _word_cut

        pending, index = "", 0

        async def emit(text: str, flushed: bool = False):
            nonlocal index
            out = await self.synthesize(text)
            out.update(
                {"text": text, "index": index, "is_final": False, "flushed": flushed}
            )
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
                # Pas de flux intra-WAV : on coupe les phrases longues aux
                # virgules pour jouer le premier morceau plus tôt.
                cut = _first_cut(pending, _CLAUSE_END, min_chars)
                if cut is None and index == 0:
                    # Aucune ponctuation n'est arrivee : le fragment
                    # d'ouverture est coupe a un mot, sinon il porte toute la
                    # phrase et c'est lui qui fixe le premier son.
                    cut = _word_cut(pending, first_chunk_max_chars)
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


def _pcm_depuis_wav(blob: bytes, moteur: _MagpieServe) -> np.ndarray:
    import io
    import wave

    with wave.open(io.BytesIO(blob), "rb") as w:
        moteur.sample_rate = int(w.getframerate())
        nchan = w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if nchan > 1:
        pcm = pcm.reshape(-1, nchan)[:, 0].copy()
    return pcm


def _pret(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/ready", timeout=2) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _attendre_pret(url: str, budget_s: float = 120.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < budget_s:
        if _pret(url):
            return True
        time.sleep(0.4)
    return False


def _premier(racine: Path, motif: str) -> Optional[Path]:
    hits = sorted(
        p for p in racine.rglob(motif) if p.is_file() and not p.name.endswith(".lock")
    )
    return hits[0] if hits else None


def _arbre_cuda(binaire: Path) -> bool:
    return binaire.is_file() and (binaire.parent.parent / "lib" / "libggml-cuda.so").exists()


def _binaire_nemo(root: Path, device: str) -> Path:
    local = root / "bin" / "nemo-speech"
    if device == "cuda":
        for b in _BINAIRES_CUDA:
            if _arbre_cuda(b):
                return b
        if _arbre_cuda(local):
            return local
    if not local.is_file():
        raise FileNotFoundError(local)
    return local


def _ligne_serve(port: int) -> Optional[str]:
    try:
        brut = subprocess.check_output(
            ["pgrep", "-af", "nemo-speech serve"],
            text=True,
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    marque = f"--port {port}"
    for line in brut.splitlines():
        if marque in line or f"--port={port}" in line:
            return line
    return None


def _serve_device(port: int) -> Optional[str]:
    line = _ligne_serve(port)
    if not line:
        return None
    parts = line.split()
    try:
        return parts[parts.index("--device") + 1].split(":", 1)[0].lower()
    except (ValueError, IndexError):
        return None


def _arreter_serve(port: int, budget_s: float = 8.0) -> None:
    line = _ligne_serve(port)
    if not line:
        return
    try:
        pid = int(line.split(None, 1)[0])
    except ValueError:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    t0 = time.monotonic()
    while time.monotonic() - t0 < budget_s:
        if _ligne_serve(port) is None:
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _demarrer_serveur(
    root: Path, host: str, port: int, device: str
) -> subprocess.Popen:
    binaire = _binaire_nemo(root, device)
    if not binaire.is_file():
        raise FileNotFoundError(binaire)
    lib = binaire.parent.parent / "lib"
    env = os.environ.copy()
    ancien = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = str(lib) if not ancien else f"{lib}:{ancien}"
    env["NEMO_SPEECH_MODEL_DIR"] = str(root / "models")
    magpie = _premier(root / "models", "*.gguf")
    codec = None
    for p in sorted((root / "models").rglob("*.gguf")):
        if p.name.endswith(".lock"):
            continue
        nom = p.name.lower()
        if "codec" in nom:
            codec = p
        elif "magpie" in nom:
            magpie = p
    tokenizer = next((p for p in (root / "models").rglob("tokenizer") if p.is_dir()), None)
    cmd = [
        str(binaire),
        "serve",
        "--host",
        host,
        "--port",
        str(port),
        "--device",
        device,
        "--no-ui",
    ]
    if magpie is not None:
        cmd.extend(["--tts-model", str(magpie)])
    if codec is not None:
        cmd.extend(["--codec-model", str(codec)])
    if tokenizer is not None:
        cmd.extend(["--tokenizer-dir", str(tokenizer)])
    logger.info("magpie serve: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
