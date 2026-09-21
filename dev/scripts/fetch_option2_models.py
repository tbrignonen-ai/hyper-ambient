#!/usr/bin/env python3
"""Télécharge les poids option 2 sur disque. Jamais de CUDA / GPU.

MiniCPM5-2B Q4_K_M -> models/gguf/ (comme LFM).
Qwen3-ASR-0.6B     -> models/hf-cache/ (HF_HOME, comme faster-whisper).

    python dev/scripts/fetch_option2_models.py

Reprend un téléchargement interrompu. N'importe pas torch.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Disque only : même un import accidentel de CUDA plus tard ne verrait rien.
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

REPO = Path(__file__).resolve().parents[2]
MODELS = Path(os.environ.get("HA_MODELS") or os.environ.get("MOTHER_MODELS") or (REPO / "models"))
GGUF_DIR = MODELS / "gguf"
HF_CACHE = MODELS / "hf-cache"
# HF_HOME=/workspace/models/hf-cache → blobs dans $HF_HOME/hub (comme faster-whisper).
HF_HUB = HF_CACHE / "hub"

MINICPM_REPO = "openbmb/MiniCPM5-2B-GGUF"
MINICPM_FILE = "MiniCPM5-2B-Q4_K_M.gguf"
MINICPM_SHA256 = "ec2d5801640099e97d8d7e8003ad4d81f336e757811f03a26173dddf386602fd"
MINICPM_BYTES = 1_561_318_368

ASR_REPO = "Qwen/Qwen3-ASR-0.6B"
ASR_WEIGHTS = "model.safetensors"
ASR_SHA256 = "79d6cbd4c98c7bbffe9db2edac07f56cd6637d0d5944b27f6c2b8353840323ea"
ASR_BYTES = 1_876_091_704


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _ok(path: Path, expected_bytes: int, expected_sha: str) -> bool:
    if not path.is_file() or path.stat().st_size != expected_bytes:
        return False
    got = _sha256(path)
    if got != expected_sha:
        print(f"  SHA256 mismatch {path.name}: {got}", flush=True)
        return False
    return True


def fetch_minicpm() -> str:
    dest = GGUF_DIR / MINICPM_FILE
    GGUF_DIR.mkdir(parents=True, exist_ok=True)
    if _ok(dest, MINICPM_BYTES, MINICPM_SHA256):
        return f"deja present {dest} ({MINICPM_BYTES} octets)"

    from huggingface_hub import hf_hub_download

    print(f"DL MiniCPM {MINICPM_REPO}/{MINICPM_FILE}", flush=True)
    downloaded = hf_hub_download(
        repo_id=MINICPM_REPO,
        filename=MINICPM_FILE,
        local_dir=str(GGUF_DIR),
        cache_dir=str(HF_HUB),
    )
    path = Path(downloaded)
    if not _ok(path, MINICPM_BYTES, MINICPM_SHA256):
        raise SystemExit(f"MiniCPM incomplet ou hash faux: {path}")
    return f"telecharge {path} ({path.stat().st_size} octets)"


def fetch_asr() -> str:
    HF_HUB.mkdir(parents=True, exist_ok=True)
    snapshot = HF_HUB / "models--Qwen--Qwen3-ASR-0.6B"
    misplaced = HF_CACHE / "models--Qwen--Qwen3-ASR-0.6B"
    if misplaced.exists() and not snapshot.exists():
        import shutil

        shutil.move(str(misplaced), str(snapshot))
        print(f"ASR deplace vers {snapshot}", flush=True)
    # Chemin snapshots/<rev>/model.safetensors si déjà là.
    if snapshot.exists():
        matches = list(snapshot.glob(f"snapshots/*/{ASR_WEIGHTS}"))
        if matches and _ok(matches[0], ASR_BYTES, ASR_SHA256):
            return f"deja present {matches[0]} ({ASR_BYTES} octets)"

    from huggingface_hub import snapshot_download

    print(f"DL ASR {ASR_REPO} -> {HF_HUB}", flush=True)
    root = snapshot_download(
        repo_id=ASR_REPO,
        cache_dir=str(HF_HUB),
        ignore_patterns=["*.md", ".gitattributes"],
    )
    weights = Path(root) / ASR_WEIGHTS
    if not _ok(weights, ASR_BYTES, ASR_SHA256):
        raise SystemExit(f"ASR incomplet ou hash faux: {weights}")
    return f"telecharge {weights} ({weights.stat().st_size} octets)"


def main() -> int:
    print(f"REPO={REPO}", flush=True)
    print(f"MODELS={MODELS}", flush=True)
    print("CUDA_VISIBLE_DEVICES='' (disque only)", flush=True)
    jobs = {
        "minicpm": fetch_minicpm,
        "asr": fetch_asr,
    }
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_map = {pool.submit(fn): name for name, fn in jobs.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                print(f"[{name}] {future.result()}", flush=True)
            except Exception as exc:
                errors.append(f"{name}: {exc!r}")
                print(f"[{name}] FAIL {exc!r}", flush=True)
    if errors:
        print("FETCH_OPTION2_FAIL", flush=True)
        for line in errors:
            print(line, flush=True)
        return 1
    print("FETCH_OPTION2_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
