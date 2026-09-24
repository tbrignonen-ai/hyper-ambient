"""Préflight sans effet matériel ; JSON PASS/FAIL/NOT_RUN pour le profil Mac."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import plistlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native.macos.profile import NAME, apply, paths  # noqa: E402
from dev.scripts.models_macos import LOCK, digest_ok, status  # noqa: E402


def read_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def inspect(config: Path, *, dry_run: bool = True) -> dict:
    env = dict(os.environ)
    env.update(read_env(config))
    checks = {}

    def record(name, state, detail):
        checks[name] = {"status": state, "detail": detail}

    if env.get("MOTHER_PROFILE") != NAME:
        record("profile", "FAIL", f"MOTHER_PROFILE={NAME} requis")
    else:
        try:
            apply(env)
            record("profile", "PASS", NAME)
        except ValueError as exc:
            record("profile", "FAIL", str(exc))
    record("platform", "PASS" if sys.platform == "darwin" and platform.machine().lower() == "arm64" else "NOT_RUN" if dry_run else "FAIL",
           f"{sys.platform}/{platform.machine()} ; cible darwin/arm64")
    record("python", "PASS" if sys.version_info[:2] == (3, 12) else "NOT_RUN" if dry_run else "FAIL",
           f"{platform.python_version()} ; cible 3.12 arm64")
    record("carte_figee", "PASS" if env.get("CARTE_FIGEE") == "0" else "FAIL",
           "désactivée dans le profil" if env.get("CARTE_FIGEE") == "0" else "CARTE_FIGEE doit valoir 0")
    try:
        with (ROOT / "packaging/macos/Info.plist").open("rb") as stream:
            plistlib.load(stream)
        record("plist", "PASS", "XML valide ; aucun bundle .app vérifié")
    except Exception as exc:
        record("plist", "FAIL", type(exc).__name__)
    for key in ("mlx", "mlx_audio", "mlx_qwen3_asr", "mlx_lm", "torch", "transformers", "sounddevice", "tkinter"):
        present = importlib.util.find_spec(key) is not None
        record("dependency_" + key, "PASS" if present else "NOT_RUN" if dry_run else "FAIL",
               "module présent" if present else "module absent dans cet interpréteur")
    model_root = paths(env)["models"]
    for family in ("jev", "stt", "text", "tts", "tts_s3"):
        result = status(family, model_root)
        state = result["status"] if result["status"] == "PASS" else "NOT_RUN" if dry_run else "FAIL"
        record("model_" + family, state,
               "snapshot vérifié" if result["status"] == "PASS" else f"{len(result['missing_or_invalid'])} fichier(s) absent(s)/invalides")
    jev_files = json.loads(LOCK.read_text(encoding="utf-8"))["models"]["jev"]["files"]
    vendor = ROOT / "native/macos/typed_decisions"
    audited = all(digest_ok(vendor / name, jev_files["typed_decisions/" + name])
                  for name in ("encoder.py", "schema.py", "open_jev.py"))
    record("vendor_jev", "PASS" if audited else "FAIL", "copies exactes du snapshot épinglé" if audited else "code JeV local divergent")
    ref = env.get("MOTHER_TTS_REFERENCE_WAV", "")
    record("voice_reference", "PASS" if ref and Path(ref).expanduser().is_file() else "NOT_RUN" if dry_run else "FAIL",
           "WAV présent" if ref and Path(ref).expanduser().is_file() else "MOTHER_TTS_REFERENCE_WAV requis")
    free = shutil.disk_usage(model_root if model_root.exists() else ROOT).free
    record("disk", "PASS" if free >= 30_000_000_000 else "NOT_RUN" if dry_run else "FAIL",
           f"{free} octets libres ; 30 Go recommandés pour primaire et staging")
    record("metal_inference", "NOT_RUN", "Mac réel et poids requis")
    record("tcc_audio", "NOT_RUN", "permission et callback à observer sur Mac")
    record("fr_quality", "NOT_RUN", "corpus et écoute Thomas requis")
    safe_env = {key: env.get(key, "") for key in (
        "MOTHER_PROFILE", "CARTE_FIGEE", "BRAIN_SERVICE", "BRAIN_LOCAL_BACKEND",
        "EARS_BACKEND", "MOUTH_BACKEND", "JEV_BACKEND", "CLI_BRIDGE_URL", "CODEX_BRIDGE_URL")}
    return {"mode": "dry-run" if dry_run else "preflight", "config": str(config),
            "environment": safe_env, "model_root": str(model_root),
            "actions": ["vérifier snapshots", "démarrer service texte", "attendre identité texte",
                        "démarrer ponts configurés", "démarrer host-agent", "attendre transport", "ouvrir Presence"],
            "checks": checks,
            "status": "FAIL" if any(c["status"] == "FAIL" for c in checks.values()) else "PASS"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "packaging/macos/mac-16g.env.example")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = inspect(args.config, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["status"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
