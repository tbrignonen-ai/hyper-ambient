"""Configuration isolée du profil Mac. La simulation ne touche aucun périphérique."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

NAME = "mac-16g-voix-max"
ROOT = Path(__file__).resolve().parents[2]


def active(environ=None) -> bool:
    return (environ if environ is not None else os.environ).get("MOTHER_PROFILE") == NAME


def require_platform(*, simulate: bool = False) -> None:
    if simulate:
        return
    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        raise RuntimeError("Le profil mac-16g-voix-max exige macOS arm64 ; utiliser --dry-run pour simuler.")


def paths(environ=None) -> dict[str, Path]:
    env = environ if environ is not None else os.environ
    home = Path.home()
    models = Path(env.get("MOTHER_MODELS_DIR") or home / "Library/Application Support/MOTHER/models/hf").expanduser()
    logs = Path(env.get("MOTHER_LOG_DIR") or home / "Library/Logs/MOTHER").expanduser()
    return {"models": models, "logs": logs, "hf_home": models / ".cache"}


def model_path(family: str, environ=None) -> Path:
    from json import loads

    manifest = loads((ROOT / "packaging/macos/models.lock.json").read_text(encoding="utf-8"))
    item = manifest["models"][family]
    return paths(environ)["models"] / item["repo"] / item["revision"]


def apply(environ=None) -> dict[str, str]:
    env = environ if environ is not None else os.environ
    if not active(env):
        return env
    env["CARTE_FIGEE"] = "0"
    defaults = {
        "BRAIN_SERVICE": "router", "BRAIN_LOCAL_BACKEND": "mlx",
        "BRAIN_MODEL_LOCAL": "mlx-community/LFM2.5-8B-A1B-OptiQ-4bit",
        "BRAIN_API_ENDPOINT": "http://127.0.0.1:8080/v1/chat/completions",
        "LLAMA_SERVER_HOST": "http://127.0.0.1:8080",
        "COMPACTAGE_RESUMEUR_MODELE": "default_model",
        "EARS_BACKEND": "mlx-qwen3-asr", "EARS_LANGUAGE": "fr",
        "MOUTH_BACKEND": "mlx-chatterbox", "MOUTH_LANGUAGE": "fr",
        "MOUTH_OUTPUT_GAIN_DB": "0", "JEV_BACKEND": "local-deberta",
        "CLI_BRIDGE_URL": "http://127.0.0.1:8766/ask",
        "CODEX_BRIDGE_URL": "http://127.0.0.1:8765/ask",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    }
    for key, value in defaults.items():
        env.setdefault(key, value)
    locked = {
        "BRAIN_SERVICE": "router", "BRAIN_LOCAL_BACKEND": "mlx",
        "BRAIN_MODEL_LOCAL": "mlx-community/LFM2.5-8B-A1B-OptiQ-4bit",
        "BRAIN_API_ENDPOINT": "http://127.0.0.1:8080/v1/chat/completions",
        "EARS_BACKEND": "mlx-qwen3-asr", "MOUTH_BACKEND": "mlx-chatterbox",
        "JEV_BACKEND": "local-deberta",
    }
    for key, expected in locked.items():
        if env[key] != expected:
            raise ValueError(f"{key} doit valoir {expected} dans le profil Mac verrouillé")
    env["BRAIN_MODEL"] = str(model_path("text", env))
    env["MOUTH_OUTPUT_GAIN_DB"] = env.get("MOTHER_MAC_OUTPUT_GAIN_DB", "0")
    env["CLI_BRIDGE_URL"] = "http://127.0.0.1:8766/ask"
    env["CODEX_BRIDGE_URL"] = "http://127.0.0.1:8765/ask"
    env["HF_HOME"] = str(paths(env)["hf_home"])
    return env
