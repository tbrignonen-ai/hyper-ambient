"""Banc d'écoute ASR : 5 oreilles locales + 1 repère distant, un modèle GPU à la fois.

N'installe rien dans le Python système ni dans les venvs existants.
Les venvs et les poids vivent sous /workspace/models/asr-bench/.
La clé STEPFUN_API_KEY est lue à l'exécution, jamais affichée ni écrite.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any, Iterable

CANDIDATS: list[dict[str, str]] = [
    {
        "id": "whisper-turbo",
        "modele": "openai/whisper-large-v3-turbo",
        "voie": "faster-whisper",
        "venv": "whisper-turbo",
    },
    {
        "id": "qwen3-asr",
        "modele": "Qwen/Qwen3-ASR-0.6B",
        "voie": "qwen3",
        "venv": "qwen3-asr",
    },
    {
        "id": "parakeet",
        "modele": "nvidia/parakeet-tdt-0.6b-v3",
        "voie": "sherpa-onnx",
        "venv": "parakeet",
    },
    {
        "id": "nemotron",
        "modele": "nvidia/nemotron-3.5-asr-streaming-0.6b",
        "voie": "nemo-speech-gguf",
        "venv": "nemotron",
    },
    {
        "id": "kyutai",
        "modele": "kyutai/stt-1b-en_fr",
        "voie": "moshi",
        "venv": "kyutai",
    },
    {
        "id": "stepaudio",
        "modele": "stepaudio-2.5-asr",
        "voie": "http-distant",
        "venv": "stepaudio",
    },
    {
        "id": "whisper-large-v3",
        "modele": "openai/whisper-large-v3",
        "voie": "faster-whisper",
        "venv": "whisper-large-v3",
        "fw": "large-v3",
    },
    {
        "id": "canary",
        "modele": "nvidia/canary-1b-v2",
        "voie": "onnx-asr",
        "venv": "canary",
    },
]

_WINDOWS = {
    "faster-whisper": "oui",
    "qwen3": "à vérifier",
    "sherpa-onnx": "oui",
    "onnx-asr": "oui",
    "nemo-speech-gguf": "oui",
    "nemo": "à vérifier",
    "moshi": "à vérifier",
    "http-distant": "oui",
}

PARAKEET_ONNX_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
)
NEMOTRON_GGUF = "nemotron-3.5-asr-streaming-0.6b.q8_0.gguf"
NEMOTRON_REPO = "nvidia/nemotron-3.5-asr-streaming-0.6b"
STEPFUN_ASR_PATH = "/audio/asr/sse"
DEFAUT_STEPFUN_BASE = "https://api.stepfun.ai/step_plan/v1"
WORKSPACE = Path("/workspace")
SEUIL_VRAM_LIBRE_MIB = 4096


def asr_root() -> Path:
    return Path(os.environ.get("ASR_BENCH_ROOT", "/workspace/models/asr-bench"))


def python_venv(nom: str) -> Path:
    return asr_root() / nom / "bin" / "python"


def parser_env_local(chemin: Path) -> dict[str, str]:
    """Lit un dotenv Windows-safe : splitlines enlève LF/CRLF, on jette le ``\\r`` restant."""
    if not Path(chemin).is_file():
        return {}
    paires: dict[str, str] = {}
    for ligne in Path(chemin).read_bytes().splitlines():
        ligne = ligne.replace(b"\r", b"")
        if not ligne or ligne.lstrip().startswith(b"#"):
            continue
        if b"=" not in ligne:
            continue
        cle_b, val_b = ligne.split(b"=", 1)
        cle = cle_b.decode("utf-8", "replace").strip().lstrip("\ufeff")
        val = val_b.decode("utf-8", "replace").strip().strip('"').strip("'")
        if cle:
            paires[cle] = val
    return paires


def lire_cle_stepfun(
    environ: dict[str, str] | None = None,
    chemin: Path | None = None,
) -> str:
    env = environ if environ is not None else os.environ
    brute = str(env.get("STEPFUN_API_KEY") or "").replace("\r", "").strip()
    if brute:
        return brute
    if chemin is None:
        candidats = [
            WORKSPACE / ".env.local",
            Path(__file__).resolve().parents[2] / ".env.local",
        ]
    else:
        candidats = [Path(chemin)]
    for c in candidats:
        val = parser_env_local(c).get("STEPFUN_API_KEY", "").replace("\r", "").strip()
        if val:
            return val
    return ""


def lister_wav(dossier: Path) -> list[Path]:
    return sorted(p for p in Path(dossier).iterdir() if p.is_file() and p.suffix.lower() == ".wav")


def duree_wav_s(chemin: Path) -> float:
    with wave.open(str(chemin), "rb") as w:
        n, taux = w.getnframes(), w.getframerate()
    if taux <= 0:
        return 0.0
    return n / float(taux)


def rtf(temps_s: float | None, duree_s: float | None) -> float | None:
    if temps_s is None or duree_s is None or duree_s <= 0:
        return None
    return float(temps_s) / float(duree_s)


def windows_natif(voie: str) -> str:
    return _WINDOWS.get((voie or "").strip().lower(), "à vérifier")


def filtrer_candidats(
    candidats: Iterable[dict[str, str]],
    ids: Iterable[str] | None,
) -> list[dict[str, str]]:
    voulus = [str(i).strip() for i in (ids or []) if str(i).strip()]
    if not voulus:
        return list(candidats)
    garde = set(voulus)
    return [c for c in candidats if c["id"] in garde]


def fusionner_bruts(
    existants: Iterable[dict[str, Any]],
    nouveaux: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    fusion = list(existants)
    index: dict[tuple[str, str], int] = {}
    for i, brut in enumerate(fusion):
        index[(str(brut.get("id") or ""), str(brut.get("fichier") or ""))] = i
    for brut in nouveaux:
        cle = (str(brut.get("id") or ""), str(brut.get("fichier") or ""))
        if cle in index:
            fusion[index[cle]] = brut
        else:
            index[cle] = len(fusion)
            fusion.append(brut)
    return fusion


def choisir_device_whisper(
    vram_libre: int | None,
    seuil_mib: int = SEUIL_VRAM_LIBRE_MIB,
) -> tuple[str, str]:
    if vram_libre is not None and vram_libre >= seuil_mib:
        return "cuda", "int8_float16"
    return "cpu", "int8"


def vram_propre_mib(avant: int | None, apres: int | None) -> int | None:
    if avant is None or apres is None:
        return None
    return max(0, int(apres) - int(avant))


def kwargs_transcribe_whisper(hotwords: str | None) -> dict[str, Any]:
    kw: dict[str, Any] = {"language": "fr", "beam_size": 5, "vad_filter": False}
    hw = (hotwords or "").strip()
    if hw:
        kw["hotwords"] = hw
    return kw


def anonymiser(bruts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    anonymes: list[dict[str, Any]] = []
    carte: dict[str, Any] = {}
    for i, brut in enumerate(bruts, start=1):
        code = f"O{i}"
        anonymes.append(
            {
                "code": code,
                "fichier": brut.get("fichier", ""),
                "texte": brut.get("texte") or "",
                "temps_s": brut.get("temps_s"),
                "rtf": brut.get("rtf"),
                "vram_max_mib": brut.get("vram_max_mib"),
                "windows_natif": brut.get("windows_natif") or windows_natif(str(brut.get("voie") or "")),
                "erreur": brut.get("erreur"),
            }
        )
        carte[code] = {
            "id": brut.get("id"),
            "modele": brut.get("modele"),
            "voie": brut.get("voie"),
        }
    return anonymes, carte


def _fmt_num(val: Any, digits: int = 3) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.{digits}f}"
    return str(val)


def rendre_resultats_md(anonymes: list[dict[str, Any]]) -> str:
    lignes = [
        "# Banc oreille — résultats anonymisés",
        "",
        "Correspondance des codes : `oreille/.carte-secrete.json` (hors lecture publique).",
        "",
        "| oreille | fichier | temps_s | RTF | VRAM max (MiB) | Windows natif | erreur | transcription |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for a in anonymes:
        err = a.get("erreur") or ""
        texte = (a.get("texte") or "").replace("\n", " ").replace("|", "/")
        lignes.append(
            "| {code} | {fic} | {t} | {rtf} | {vram} | {win} | {err} | {txt} |".format(
                code=a.get("code", ""),
                fic=a.get("fichier", ""),
                t=_fmt_num(a.get("temps_s")),
                rtf=_fmt_num(a.get("rtf")),
                vram=_fmt_num(a.get("vram_max_mib"), 0),
                win=a.get("windows_natif") or "à vérifier",
                err=err.replace("|", "/"),
                txt=texte,
            )
        )
    lignes.append("")
    return "\n".join(lignes)


def extraire_texte_sse(flux: str) -> str:
    dernier = ""
    for ligne in (flux or "").splitlines():
        s = ligne.strip()
        if s.startswith("data:"):
            s = s[5:].strip()
        if not s or s == "[DONE]":
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = str(obj.get("type") or obj.get("event") or "")
        texte = ""
        if isinstance(obj.get("text"), str):
            texte = obj["text"]
        trans = obj.get("transcript")
        if isinstance(trans, dict) and isinstance(trans.get("text"), str):
            texte = trans["text"] or texte
        if isinstance(obj.get("delta"), str) and not texte:
            texte = obj["delta"]
        if typ.endswith("transcript.text.done") or typ == "transcript.text.done":
            if texte:
                return texte
        if texte:
            dernier = texte
    return dernier


def _journal(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _nvidia_smi_mib(requete: str) -> int | None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={requete}", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return int(float(out.strip().splitlines()[0].strip()))
    except (ValueError, IndexError):
        return None


def vram_utilisee_mib() -> int | None:
    return _nvidia_smi_mib("memory.used")


def vram_libre_mib() -> int | None:
    return _nvidia_smi_mib("memory.free")


class _SondeVram:
    def __init__(self) -> None:
        self.max_mib: int | None = vram_utilisee_mib()
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._boucle, daemon=True)

    def _boucle(self) -> None:
        while not self._stop.wait(0.2):
            val = vram_utilisee_mib()
            if val is None:
                continue
            if self.max_mib is None or val > self.max_mib:
                self.max_mib = val

    def __enter__(self) -> "_SondeVram":
        self._th.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._th.join(timeout=2)


def _creer_venv(nom: str) -> Path:
    racine = asr_root() / nom
    py = racine / "bin" / "python"
    if py.is_file():
        return racine
    racine.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [sys.executable, "-m", "venv", "--system-site-packages", str(racine)]
    )
    return racine


def _pip(nom: str, *pkgs: str) -> None:
    py = python_venv(nom)
    cmd = [str(py), "-m", "pip", "install", "--disable-pip-version-check", *pkgs]
    subprocess.check_call(cmd)


def _telecharger(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def _hf_download(repo: str, fichier: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    cible = dest_dir / fichier
    if cible.is_file() and cible.stat().st_size > 0:
        return cible
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub absent") from exc
    local = hf_hub_download(
        repo_id=repo,
        filename=fichier,
        local_dir=str(dest_dir),
        local_dir_use_symlinks=False,
    )
    return Path(local)


def _lier_cache(src: Path, dest: Path) -> None:
    if dest.exists() or not src.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(src, dest, target_is_directory=src.is_dir())
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def installer_candidat(cand: dict[str, str]) -> dict[str, Any]:
    """Crée le venv + dépendances. Ne touche pas au Python système."""
    ident = cand["id"]
    try:
        _creer_venv(cand["venv"])
        poids = asr_root() / "poids"
        hf_cache = asr_root() / "hf-cache"
        hf_cache.mkdir(parents=True, exist_ok=True)
        hub_src = Path("/workspace/models/hf-cache/hub")
        hub_dst = hf_cache / "hub"
        hub_dst.mkdir(parents=True, exist_ok=True)
        if ident == "whisper-turbo":
            _lier_cache(
                hub_src / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
                hub_dst / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
            )
            _lier_cache(
                hub_src / "models--Systran--faster-whisper-large-v3-turbo",
                hub_dst / "models--Systran--faster-whisper-large-v3-turbo",
            )
        elif ident == "whisper-large-v3":
            _lier_cache(
                hub_src / "models--Systran--faster-whisper-large-v3",
                hub_dst / "models--Systran--faster-whisper-large-v3",
            )
            _lier_cache(
                hub_src / "models--openai--whisper-large-v3",
                hub_dst / "models--openai--whisper-large-v3",
            )
        elif ident == "qwen3-asr":
            _lier_cache(
                hub_src / "models--Qwen--Qwen3-ASR-0.6B",
                hub_dst / "models--Qwen--Qwen3-ASR-0.6B",
            )
        elif ident == "parakeet":
            _pip(cand["venv"], "sherpa-onnx")
            archive = poids / "parakeet" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
            _telecharger(PARAKEET_ONNX_URL, archive)
            dest = poids / "parakeet" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
            if not (dest / "encoder.int8.onnx").is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                subprocess.check_call(["tar", "xf", str(archive), "-C", str(dest.parent)])
        elif ident == "nemotron":
            gguf_dir = poids / "nemotron"
            try:
                _hf_download(NEMOTRON_REPO, NEMOTRON_GGUF, gguf_dir)
            except Exception as exc:
                return {"ok": False, "id": ident, "cause": f"gguf: {type(exc).__name__}: {exc}"}
            prefix = asr_root() / "nemotron-cli"
            if _nemo_speech_bin() is None:
                inst = prefix / "install.sh"
                try:
                    prefix.mkdir(parents=True, exist_ok=True)
                    _telecharger(
                        "https://raw.githubusercontent.com/NVIDIA/NeMo-Speech.cpp/main/scripts/install.sh",
                        inst,
                    )
                    subprocess.check_call(
                        ["bash", str(inst), "--prefix", str(prefix)],
                        cwd=str(prefix),
                    )
                except Exception as exc:
                    if _nemo_speech_bin() is None:
                        return {
                            "ok": False,
                            "id": ident,
                            "cause": f"nemo-speech install: {type(exc).__name__}: {exc}",
                        }
            if _nemo_speech_bin() is None:
                return {
                    "ok": False,
                    "id": ident,
                    "cause": "nemo-speech: binaire absent après install.sh",
                }
        elif ident == "kyutai":
            _pip(cand["venv"], "moshi>=0.2.6")
        elif ident == "canary":
            # CUDA 12.x du conteneur : onnxruntime-gpu ≥ 1.27 exige CUDA 13.
            _pip(
                cand["venv"],
                "onnx-asr[hub]",
                "onnxruntime-gpu[cuda,cudnn]<1.27",
            )
            dest = poids / "canary"
            if dest.is_dir() and not (dest / "encoder-model.onnx").is_file():
                try:
                    dest.rmdir()
                except OSError:
                    pass
            _lier_cache(
                hub_src / "models--istupakov--canary-1b-v2-onnx",
                hub_dst / "models--istupakov--canary-1b-v2-onnx",
            )
        elif ident == "stepaudio":
            pass
        return {"ok": True, "id": ident}
    except Exception as exc:
        return {"ok": False, "id": ident, "cause": f"{type(exc).__name__}: {exc}"}


def _lire_pcm(chemin: Path) -> tuple[Any, int]:
    import numpy as np

    with wave.open(str(chemin), "rb") as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        pcm = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    elif sw == 4:
        pcm = np.frombuffer(raw, dtype="<i4").astype("float32")
        pcm = pcm / (abs(pcm).max() or 1.0)
    else:
        raise RuntimeError(f"wav sampwidth={sw} non géré")
    if nch > 1:
        pcm = pcm.reshape(-1, nch).mean(axis=1)
    return pcm, sr


def _resample_16k(pcm: Any, sr: int) -> Any:
    import numpy as np

    if sr == 16000:
        return pcm.astype("float32")
    n = int(len(pcm) * 16000 / sr)
    if n <= 0:
        return pcm.astype("float32")
    x = np.linspace(0, len(pcm) - 1, n)
    return np.interp(x, np.arange(len(pcm)), pcm.astype("float32")).astype("float32")


def worker_whisper(wav: Path) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    t0 = time.perf_counter()
    os.environ.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    model = WhisperModel("large-v3-turbo", device="cuda", compute_type="int8_float16")
    try:
        segs, _info = model.transcribe(str(wav), language="fr", beam_size=5, vad_filter=False)
        texte = "".join(s.text for s in segs).strip()
    finally:
        del model
    return {"texte": texte, "temps_s": time.perf_counter() - t0, "voie": "faster-whisper"}


def worker_whisper_large_v3(wav: Path, hotwords: str = "") -> dict[str, Any]:
    from faster_whisper import WhisperModel

    device, compute = choisir_device_whisper(vram_libre_mib())
    t0 = time.perf_counter()
    os.environ.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    model = WhisperModel("large-v3", device=device, compute_type=compute)
    try:
        segs, _info = model.transcribe(str(wav), **kwargs_transcribe_whisper(hotwords))
        texte = "".join(s.text for s in segs).strip()
    finally:
        del model
    return {
        "texte": texte,
        "temps_s": time.perf_counter() - t0,
        "voie": "faster-whisper",
        "device": device,
        "compute_type": compute,
    }


def worker_canary(wav: Path) -> dict[str, Any]:
    t0 = time.perf_counter()
    ctx = _charger_canary()
    try:
        texte = _transcrire_canary(ctx, wav)
    finally:
        _decharger(ctx)
    return {
        "texte": texte,
        "temps_s": time.perf_counter() - t0,
        "voie": "onnx-asr",
        "device": ctx.get("device"),
    }


def worker_qwen3(wav: Path) -> dict[str, Any]:
    import asyncio

    import numpy as np

    racine = str(WORKSPACE)
    if racine not in sys.path:
        sys.path.insert(0, racine)
    os.environ.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    from src.ears.qwen3_asr import Qwen3ASR

    pcm, sr = _lire_pcm(wav)
    audio = _resample_16k(np.asarray(pcm), sr)
    asr = Qwen3ASR()
    t0 = time.perf_counter()
    ok = asyncio.run(asr.load_model())
    if not ok:
        raise RuntimeError("Qwen3ASR.load_model a échoué")
    try:
        out = asyncio.run(asr.transcribe(audio))
        texte = str(out.get("text") or "").strip()
    finally:
        asr.model = None
    return {"texte": texte, "temps_s": time.perf_counter() - t0, "voie": "qwen3"}


def worker_parakeet(wav: Path) -> dict[str, Any]:
    import numpy as np
    import sherpa_onnx

    d = asr_root() / "poids" / "parakeet" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    kwargs = {
        "encoder": str(d / "encoder.int8.onnx"),
        "decoder": str(d / "decoder.int8.onnx"),
        "joiner": str(d / "joiner.int8.onnx"),
        "tokens": str(d / "tokens.txt"),
        "num_threads": 2,
        "provider": "cuda",
        "model_type": "nemo_transducer",
    }
    t0 = time.perf_counter()
    if hasattr(sherpa_onnx.OfflineRecognizer, "from_transducer"):
        rec = sherpa_onnx.OfflineRecognizer.from_transducer(**kwargs)
    else:
        rec = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(**kwargs)
    pcm, sr = _lire_pcm(wav)
    stream = rec.create_stream()
    stream.accept_waveform(sr, np.asarray(pcm, dtype="float32"))
    rec.decode_stream(stream)
    texte = str(getattr(stream.result, "text", "") or "").strip()
    return {"texte": texte, "temps_s": time.perf_counter() - t0, "voie": "sherpa-onnx"}


def _nemo_speech_bin() -> Path | None:
    for c in (
        asr_root() / "nemotron-cli" / "bin" / "nemo-speech",
        asr_root() / "nemotron.new" / "bin" / "nemo-speech",
        asr_root() / "nemotron" / "bin" / "nemo-speech",
    ):
        if c.is_file() and os.access(c, os.X_OK) and c.stat().st_size > 10_000:
            return c
    return None


def worker_nemotron(wav: Path) -> dict[str, Any]:
    cli = _nemo_speech_bin()
    gguf = asr_root() / "poids" / "nemotron" / NEMOTRON_GGUF
    if cli is None:
        raise RuntimeError("binaire nemo-speech introuvable")
    if not gguf.is_file():
        raise RuntimeError(f"{NEMOTRON_GGUF} introuvable")
    env = os.environ.copy()
    env["LD_PRELOAD"] = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
    libdir = str(cli.resolve().parent.parent / "lib")
    env["LD_LIBRARY_PATH"] = libdir + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            str(cli),
            "transcribe",
            str(wav),
            "--model",
            str(gguf),
            "--language",
            "fr-FR",
            "--device",
            "cuda",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise RuntimeError(combined.strip()[:400] or f"code {proc.returncode}")
    lignes = [
        ln.strip()
        for ln in combined.splitlines()
        if ln.strip() and not ln.strip().startswith("[")
        and "Info:" not in ln
        and "starting inference" not in ln
    ]
    texte = lignes[-1] if lignes else ""
    if not texte:
        raise RuntimeError((combined.strip() or f"code {proc.returncode}")[:400])
    return {"texte": texte, "temps_s": time.perf_counter() - t0, "voie": "nemo-speech-gguf"}


def worker_kyutai(wav: Path) -> dict[str, Any]:
    os.environ.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "moshi.run_inference",
            "--hf-repo",
            "kyutai/stt-1b-en_fr",
            str(wav),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        err = f"moshi exit {proc.returncode}: {(proc.stderr or proc.stdout or '').strip()}"
        raise RuntimeError(err[:400])
    lignes = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    texte = lignes[-1] if lignes else ""
    return {"texte": texte, "temps_s": time.perf_counter() - t0, "voie": "moshi"}


def worker_stepaudio(wav: Path) -> dict[str, Any]:
    cle = lire_cle_stepfun()
    if not cle:
        raise RuntimeError("STEPFUN_API_KEY absente")
    base = (
        os.environ.get("STEPFUN_BASE_URL")
        or parser_env_local(WORKSPACE / ".env.local").get("STEPFUN_BASE_URL")
        or DEFAUT_STEPFUN_BASE
    ).rstrip("/")
    url = base + STEPFUN_ASR_PATH
    audio_b64 = base64.b64encode(Path(wav).read_bytes()).decode("ascii")
    corps = json.dumps(
        {
            "audio": {
                "data": audio_b64,
                "input": {
                    "transcription": {
                        "language": "fr",
                        "model": "stepaudio-2.5-asr",
                        "enable_itn": True,
                    },
                    "format": {"type": "wav"},
                },
            }
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=corps,
        method="POST",
        headers={
            "Authorization": f"Bearer {cle}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            brut = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        corps_err = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HTTP {exc.code}: {corps_err}") from None
    texte = extraire_texte_sse(brut)
    return {"texte": texte, "temps_s": time.perf_counter() - t0, "voie": "http-distant"}


def _charger_parakeet() -> dict[str, Any]:
    import sherpa_onnx

    d = asr_root() / "poids" / "parakeet" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    kwargs = {
        "encoder": str(d / "encoder.int8.onnx"),
        "decoder": str(d / "decoder.int8.onnx"),
        "joiner": str(d / "joiner.int8.onnx"),
        "tokens": str(d / "tokens.txt"),
        "num_threads": 2,
        "provider": "cuda",
        "model_type": "nemo_transducer",
    }
    if hasattr(sherpa_onnx.OfflineRecognizer, "from_transducer"):
        rec = sherpa_onnx.OfflineRecognizer.from_transducer(**kwargs)
    else:
        rec = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(**kwargs)
    return {"model": rec, "voie": "sherpa-onnx", "device": "cuda"}


def _transcrire_parakeet(ctx: dict[str, Any], wav: Path) -> str:
    import numpy as np

    rec = ctx["model"]
    pcm, sr = _lire_pcm(wav)
    stream = rec.create_stream()
    stream.accept_waveform(sr, np.asarray(pcm, dtype="float32"))
    rec.decode_stream(stream)
    return str(getattr(stream.result, "text", "") or "").strip()


def _charger_whisper_large_v3() -> dict[str, Any]:
    from faster_whisper import WhisperModel

    os.environ.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
    return {
        "model": model,
        "voie": "faster-whisper",
        "device": "cuda",
        "compute_type": "int8_float16",
    }


def _transcrire_whisper_large_v3(ctx: dict[str, Any], wav: Path, hotwords: str = "") -> str:
    segs, _info = ctx["model"].transcribe(str(wav), **kwargs_transcribe_whisper(hotwords))
    return "".join(s.text for s in segs).strip()


def _cudnn9_disponible() -> bool:
    return any((dossier / "libcudnn.so.9").is_file() for dossier in _dossiers_libs_nvidia())


def _charger_canary() -> dict[str, Any]:
    import onnx_asr

    os.environ.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    _ajouter_libs_nvidia_venv(os.environ, "canary")
    dest = asr_root() / "poids" / "canary"
    if dest.is_dir() and not (dest / "encoder-model.onnx").is_file():
        try:
            dest.rmdir()
        except OSError:
            for enfant in dest.iterdir():
                if enfant.is_file():
                    enfant.unlink()
            dest.rmdir()
    cuda_ok = _cudnn9_disponible()
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if cuda_ok
        else ["CPUExecutionProvider"]
    )
    model = onnx_asr.load_model("nemo-canary-1b-v2", str(dest), providers=providers)
    return {
        "model": model,
        "voie": "onnx-asr",
        "device": "cuda" if cuda_ok else "cpu",
    }


def _transcrire_canary(ctx: dict[str, Any], wav: Path) -> str:
    texte = ctx["model"].recognize(str(wav), language="fr")
    if isinstance(texte, list):
        texte = " ".join(str(t) for t in texte)
    return str(texte or "").strip()


def _decharger(ctx: dict[str, Any] | None) -> None:
    if not ctx:
        return
    ctx.pop("model", None)


def _run_worker_inline(ident: str, wav: Path, hotwords: str = "") -> dict[str, Any]:
    fn = _WORKERS[ident]
    try:
        if ident == "whisper-large-v3":
            out = fn(wav, hotwords=hotwords)
        else:
            out = fn(wav)
        out.setdefault("erreur", None)
        return out
    except Exception as exc:
        return {
            "texte": "",
            "temps_s": None,
            "voie": next((c["voie"] for c in CANDIDATS if c["id"] == ident), ""),
            "erreur": f"{type(exc).__name__}: {exc}"[:400],
        }


def _run_worker_chaud(
    ident: str,
    wavs: list[Path],
    hotwords: str = "",
) -> dict[str, Any]:
    chargeurs = {
        "parakeet": _charger_parakeet,
        "whisper-large-v3": _charger_whisper_large_v3,
        "canary": _charger_canary,
    }
    transcripteurs = {
        "parakeet": lambda ctx, wav: _transcrire_parakeet(ctx, wav),
        "whisper-large-v3": lambda ctx, wav: _transcrire_whisper_large_v3(ctx, wav, hotwords),
        "canary": _transcrire_canary,
    }
    if ident not in chargeurs:
        raise RuntimeError(f"latence à chaud non gérée pour {ident}")
    vram_avant = vram_utilisee_mib()
    t_load = time.perf_counter()
    ctx = chargeurs[ident]()
    temps_chargement = time.perf_counter() - t_load
    vram_apres = vram_utilisee_mib()
    phrases: list[dict[str, Any]] = []
    try:
        transcrire = transcripteurs[ident]
        for wav in wavs:
            t0 = time.perf_counter()
            try:
                texte = transcrire(ctx, wav)
                err = None
            except Exception as exc:
                texte, err = "", f"{type(exc).__name__}: {exc}"[:400]
            temps = time.perf_counter() - t0
            duree = duree_wav_s(wav)
            phrases.append(
                {
                    "fichier": wav.name,
                    "texte": texte,
                    "temps_s": temps,
                    "rtf": rtf(temps, duree),
                    "duree_wav_s": duree,
                    "erreur": err,
                }
            )
    finally:
        _decharger(ctx)
    return {
        "id": ident,
        "voie": ctx.get("voie"),
        "device": ctx.get("device"),
        "compute_type": ctx.get("compute_type"),
        "hotwords": (hotwords or "").strip() or None,
        "vram_avant_mib": vram_avant,
        "vram_apres_mib": vram_apres,
        "vram_propre_mib": vram_propre_mib(vram_avant, vram_apres),
        "temps_chargement_s": temps_chargement,
        "phrases": phrases,
        "erreur": None,
    }


_WORKERS = {
    "whisper-turbo": worker_whisper,
    "qwen3-asr": worker_qwen3,
    "parakeet": worker_parakeet,
    "nemotron": worker_nemotron,
    "kyutai": worker_kyutai,
    "stepaudio": worker_stepaudio,
    "whisper-large-v3": worker_whisper_large_v3,
    "canary": worker_canary,
}


def _dossiers_libs_nvidia() -> list[Path]:
    racines = [
        asr_root() / "canary" / "lib" / "python3.11" / "site-packages" / "nvidia",
        Path("/usr/local/lib/python3.11/dist-packages/nvidia"),
    ]
    extra: list[Path] = []
    for racine in racines:
        for sous in (
            "cudnn/lib",
            "cuda_runtime/lib",
            "cublas/lib",
            "cufft/lib",
            "curand/lib",
            "cusolver/lib",
            "cusparse/lib",
            "nvjitlink/lib",
            "cuda_nvrtc/lib",
        ):
            p = racine / sous
            if p.is_dir():
                extra.append(p)
    return extra


def _ajouter_libs_nvidia_venv(env: dict[str, str], nom_venv: str = "canary") -> None:
    del nom_venv  # les libs NVIDIA sont dans le venv ou le site système
    extra = [str(p) for p in _dossiers_libs_nvidia()]
    if extra:
        deja = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = ":".join(extra + ([deja] if deja else []))


def _env_worker() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("HF_HOME", str(asr_root() / "hf-cache"))
    env.setdefault("PYTHONPATH", str(WORKSPACE))
    _ajouter_libs_nvidia_venv(env, "canary")
    return env


def _payload_worker(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = proc.stdout or ""
    try:
        payload = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {
            "texte": "",
            "erreur": f"JSON worker invalide (code {proc.returncode})",
        }
    if not isinstance(payload, dict):
        payload = {"texte": "", "erreur": f"JSON worker type={type(payload).__name__}"}
    if proc.returncode != 0 and not payload.get("erreur"):
        err = (proc.stderr or stdout or f"code {proc.returncode}").strip()[:400]
        payload["erreur"] = err
    return payload


def mesurer_un(cand: dict[str, str], wav: Path, hotwords: str = "") -> dict[str, Any]:
    py = python_venv(cand["venv"])
    cmd = [
        str(py),
        str(Path(__file__).resolve()),
        "--worker",
        cand["id"],
        "--wav",
        str(wav),
    ]
    hw = (hotwords or "").strip()
    if hw:
        cmd.extend(["--hotwords", hw])
    with _SondeVram() as sonde:
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            env=_env_worker(),
            timeout=600,
        )
        mur = time.perf_counter() - t0
    payload = _payload_worker(proc)
    temps = payload.get("temps_s")
    if temps is None:
        temps = mur
    duree = duree_wav_s(wav)
    voie = payload.get("voie") or cand["voie"]
    return {
        "id": cand["id"],
        "modele": cand["modele"],
        "voie": voie,
        "fichier": wav.name,
        "texte": payload.get("texte") or "",
        "temps_s": temps,
        "rtf": rtf(temps, duree),
        "vram_max_mib": sonde.max_mib,
        "windows_natif": windows_natif(voie),
        "erreur": payload.get("erreur"),
        "duree_wav_s": duree,
        "device": payload.get("device"),
        "compute_type": payload.get("compute_type"),
        "hotwords": hw or None,
    }


def mesurer_chaud(
    cand: dict[str, str],
    wavs: list[Path],
    hotwords: str = "",
    wav_dir: Path | None = None,
) -> dict[str, Any]:
    py = python_venv(cand["venv"])
    dossier = wav_dir or (wavs[0].parent if wavs else Path("."))
    cmd = [
        str(py),
        str(Path(__file__).resolve()),
        str(dossier),
        "--worker",
        cand["id"],
        "--chaud",
    ]
    hw = (hotwords or "").strip()
    if hw:
        cmd.extend(["--hotwords", hw])
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        env=_env_worker(),
        timeout=900,
    )
    mur = time.perf_counter() - t0
    payload = _payload_worker(proc)
    payload.setdefault("id", cand["id"])
    payload.setdefault("modele", cand["modele"])
    payload.setdefault("voie", cand["voie"])
    payload.setdefault("windows_natif", windows_natif(str(payload.get("voie") or cand["voie"])))
    payload["temps_mur_s"] = mur
    if hw:
        payload["hotwords"] = hw
    return payload


def ecrire_bruts(
    out_dir: Path,
    bruts: list[dict[str, Any]],
    fusionner: bool = False,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    chemin = out_dir / "bruts.json"
    a_ecrire = bruts
    if fusionner and chemin.is_file():
        try:
            existants = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existants = []
        if isinstance(existants, list):
            a_ecrire = fusionner_bruts(existants, bruts)
    chemin.write_text(json.dumps(a_ecrire, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin


def ecrire_sorties(out_dir: Path, bruts: list[dict[str, Any]]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    anonymes, carte = anonymiser(bruts)
    md_path = out_dir / "resultats.md"
    carte_path = out_dir / ".carte-secrete.json"
    md_path.write_text(rendre_resultats_md(anonymes), encoding="utf-8")
    carte_path.write_text(json.dumps(carte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ecrire_bruts(out_dir, bruts, fusionner=False)
    return md_path, carte_path


def _propager_secrets() -> None:
    """Injecte les clés utiles depuis .env.local sans les journaliser."""
    paires = parser_env_local(WORKSPACE / ".env.local")
    if not paires:
        alt = Path(__file__).resolve().parents[2] / ".env.local"
        paires = parser_env_local(alt)
    for cle in ("STEPFUN_API_KEY", "STEPFUN_BASE_URL", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        val = str(paires.get(cle) or "").replace("\r", "").strip()
        if val and not str(os.environ.get(cle) or "").replace("\r", "").strip():
            os.environ[cle] = val


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Banc oreille ASR (venvs isolés).")
    p.add_argument("wav_dir", nargs="?", help="Dossier de fichiers .wav")
    p.add_argument("--out-dir", default="", help="Dossier resultats.md + .carte-secrete.json")
    p.add_argument("--id", action="append", default=[], dest="ids", help="Restreindre à ces id")
    p.add_argument("--merge-bruts", action="store_true", help="Ajouter à bruts.json sans écraser")
    p.add_argument("--worker", default="", help=argparse.SUPPRESS)
    p.add_argument("--wav", default="", help=argparse.SUPPRESS)
    p.add_argument("--install-only", action="store_true")
    p.add_argument(
        "--chaud",
        action="store_true",
        help="Charge le modèle une fois, transcrit tous les wav, VRAM avant/après.",
    )
    p.add_argument("--hotwords", default="", help="Hotwords faster-whisper (whisper-large-v3).")
    args = p.parse_args(list(argv) if argv is not None else None)

    _propager_secrets()

    if args.worker:
        if args.chaud:
            if args.wav_dir:
                wavs = lister_wav(Path(args.wav_dir))
            elif args.wav:
                wavs = [Path(args.wav)]
            else:
                p.error("wav_dir ou --wav requis en mode --worker --chaud")
            try:
                out = _run_worker_chaud(args.worker, wavs, hotwords=args.hotwords)
            except Exception as exc:
                out = {
                    "id": args.worker,
                    "phrases": [],
                    "erreur": f"{type(exc).__name__}: {exc}"[:400],
                }
        else:
            wav = Path(args.wav)
            out = _run_worker_inline(args.worker, wav, hotwords=args.hotwords)
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        return 0 if not out.get("erreur") else 1

    if not args.wav_dir:
        p.error("wav_dir requis")
    wavs = lister_wav(Path(args.wav_dir))
    if not wavs:
        _journal(f"aucun .wav dans {args.wav_dir}")
        return 2

    cibles = filtrer_candidats(CANDIDATS, args.ids)
    if not cibles:
        p.error("aucun candidat pour --id")

    installs: list[dict[str, Any]] = []
    for cand in cibles:
        _journal(f"install {cand['id']}…")
        info = installer_candidat(cand)
        installs.append(info)
        if info.get("ok"):
            _journal(f"install {cand['id']} ok")
        else:
            _journal(f"install {cand['id']} échec")

    if args.install_only:
        sys.stdout.write(json.dumps(installs, ensure_ascii=False, indent=2) + "\n")
        return 0

    if args.chaud:
        chauds: list[dict[str, Any]] = []
        for cand, inst in zip(cibles, installs):
            _journal(f"mesure à chaud {cand['id']} ({len(wavs)} wav)…")
            if not inst.get("ok"):
                chauds.append(
                    {
                        "id": cand["id"],
                        "modele": cand["modele"],
                        "voie": cand["voie"],
                        "phrases": [],
                        "erreur": f"install: {inst.get('cause')}",
                    }
                )
                continue
            chauds.append(
                mesurer_chaud(
                    cand,
                    wavs,
                    hotwords=args.hotwords,
                    wav_dir=Path(args.wav_dir),
                )
            )
        sys.stdout.write(json.dumps(chauds, ensure_ascii=False, indent=2) + "\n")
        return 0 if all(not c.get("erreur") for c in chauds) else 1

    bruts: list[dict[str, Any]] = []
    for wav in wavs:
        for cand, inst in zip(cibles, installs):
            _journal(f"mesure {cand['id']} / {wav.name}…")
            if not inst.get("ok"):
                bruts.append(
                    {
                        "id": cand["id"],
                        "modele": cand["modele"],
                        "voie": cand["voie"],
                        "fichier": wav.name,
                        "texte": "",
                        "temps_s": None,
                        "rtf": None,
                        "vram_max_mib": None,
                        "windows_natif": windows_natif(cand["voie"]),
                        "erreur": f"install: {inst.get('cause')}",
                    }
                )
                continue
            bruts.append(mesurer_un(cand, wav, hotwords=args.hotwords))

    out_dir = Path(args.out_dir) if args.out_dir else Path("oreille-out")
    if args.merge_bruts:
        ecrire_bruts(out_dir, bruts, fusionner=True)
    else:
        ecrire_sorties(out_dir, bruts)
        (out_dir / "installs.json").write_text(
            json.dumps(installs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    _journal(f"écrit {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
