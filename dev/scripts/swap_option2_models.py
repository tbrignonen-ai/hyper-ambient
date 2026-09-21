#!/usr/bin/env python3
"""Vérifie les poids option 2 et imprime l'env suggéré. Ne charge rien.

Ne touche pas serve_hostagent.py. N'appelle pas llama-server.
Ne décharge pas Luciole / faster-whisper. Disque + impression seulement.

    python dev/scripts/swap_option2_models.py
    python dev/scripts/swap_option2_models.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODELS = Path(os.environ.get("HA_MODELS") or os.environ.get("MOTHER_MODELS") or (REPO / "models"))
GGUF_DIR = MODELS / "gguf"
HF_CACHE = MODELS / "hf-cache"

MINICPM_FILE = "MiniCPM5-2B-Q4_K_M.gguf"
MINICPM_BYTES = 1_561_318_368
ASR_WEIGHTS = "model.safetensors"
ASR_BYTES = 1_876_091_704
ASR_REPO_DIRS = (
    HF_CACHE / "hub" / "models--Qwen--Qwen3-ASR-0.6B",
    HF_CACHE / "models--Qwen--Qwen3-ASR-0.6B",
)

# Option 2 CHOIX 13 sept — env câblé par la lane Codex/Claude.
SUGGESTED_ENV = {
    "BRAIN_MODEL_LOCAL": "mother-local",
    "ALIAS": "mother-local",
    "MODEL": "/workspace/models/gguf/MiniCPM5-2B-Q4_K_M.gguf",
    "CTX": "4096",
    "HF_HOME": "/workspace/models/hf-cache",
    "EARS_BACKEND": "qwen3",
    "EARS_MODEL": "0.6B",
    "EARS_DEVICE": "cuda",
    "MOUTH_BACKEND": "pocket",
    "MOUTH_VOICE_NAME": "estelle",
    "MOUTH_LANGUAGE": "french_24l",
    "MOUTH_DEVICE": "cpu",
    "MOUTH_PROFILE": "aurora",
}

LLAMA_CMD = (
    "docker exec -e MODEL=/workspace/models/gguf/MiniCPM5-2B-Q4_K_M.gguf "
    "-e CTX=4096 -e ALIAS=mother-local mother-core-dev "
    "bash /workspace/dev/scripts/serve_llama.sh"
)


def _find_asr_weights() -> Path | None:
    found: list[Path] = []
    for root in ASR_REPO_DIRS:
        if root.exists():
            found.extend(root.glob(f"snapshots/*/{ASR_WEIGHTS}"))
    return sorted(found)[-1] if found else None


def inspect() -> dict:
    minicpm = GGUF_DIR / MINICPM_FILE
    asr = _find_asr_weights()
    minicpm_ok = minicpm.is_file() and minicpm.stat().st_size == MINICPM_BYTES
    asr_ok = bool(asr) and asr.is_file() and asr.stat().st_size == ASR_BYTES
    return {
        "models_root": str(MODELS),
        "minicpm_path": str(minicpm),
        "minicpm_bytes": minicpm.stat().st_size if minicpm.is_file() else 0,
        "minicpm_expected_bytes": MINICPM_BYTES,
        "minicpm_ok": minicpm_ok,
        "asr_path": str(asr) if asr else "",
        "asr_bytes": asr.stat().st_size if asr and asr.is_file() else 0,
        "asr_expected_bytes": ASR_BYTES,
        "asr_ok": asr_ok,
        "ok": minicpm_ok and asr_ok,
        "suggested_env": SUGGESTED_ENV,
        "llama_reload_later": LLAMA_CMD,
        "hostagent": "câblé via EARS_BACKEND=qwen3 et MOUTH_BACKEND=pocket",
        "gpu": "chargement volontaire à exécuter avec accès Docker",
    }


def _print_human(report: dict) -> None:
    flag = "OK" if report["ok"] else "INCOMPLET"
    print(f"option2 poids: {flag}")
    print(f"  MiniCPM  {report['minicpm_bytes']:>12} / {MINICPM_BYTES}  {report['minicpm_path']}")
    print(f"  ASR      {report['asr_bytes']:>12} / {ASR_BYTES}  {report['asr_path'] or '(absent)'}")
    print()
    print("env option 2:")
    for key, value in SUGGESTED_ENV.items():
        print(f"  export {key}={value}")
    print()
    print("rechargement llama-server (décharge le modèle courant, charge MiniCPM GPU):")
    print(f"  {LLAMA_CMD}")
    print()
    print("hostagent câblé: EARS Qwen3ASR + MOUTH Pocket estelle via env.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie les poids option 2, n'en charge aucun.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = inspect()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
