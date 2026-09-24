"""Manifeste HF épinglé et téléchargement explicite du pack Mac.

La découverte passe uniquement par /api/models. Aucune commande de lancement
ne télécharge de poids. Les octets sont vérifiés avant publication atomique.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "packaging/macos/models.lock.json"
SPECS = {
    "jev": ("com-kotobalabs/open-jev-deberta-v3-large", "19bf9a64815add579fbf6c907bef584d9277a8e4", None),
    "jev_ru": ("killkli/open-jev-laya-multilingual-onnx", "643219b2b3a112ff1c40fb1143f050aa871f76f7", {"README.md", "config.json", "laya_config.json", "onnx/laya.onnx", "tokenizer.json", "tokenizer_config.json"}),
    "stt": ("moona3k/mlx-qwen3-asr-1.7b-8bit", "22c8abe6a6772122dda5905967d7496d1d3e8dd2", None),
    "stt_ru": ("cstr/kyutai-stt-1b-GGUF", "ab83b1b3c788a8842e5ce5deebc6f6491545ead8", {"README.md", "kyutai-stt-1b-q8_0.gguf"}),
    "text": ("mlx-community/LFM2.5-8B-A1B-OptiQ-4bit", "5a5c595823cf26ab1068508eb5cf85816bb2db6b", None),
    "text_ru": ("Oscilla/Ministral-8B-Instruct-2410-mlx-4Bit", "0a90a00572ac08cfff586c1035bd2f0614023977", None),
    "tts": ("mlx-community/chatterbox-multilingual-v3", "03565773edd72e949572557597af8063bb49a18a", None),
    "tts_s3": ("mlx-community/S3TokenizerV2", "e0c9886f0e1c35ae85b1f27277416fb19fc72bec", None),
}


def api_model(repo: str, revision: str) -> dict:
    url = f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true"
    with urllib.request.urlopen(url, timeout=20) as response:
        data = json.load(response)
    if data["sha"] != revision:
        raise ValueError(f"Révision mouvante pour {repo}")
    return data


def refresh() -> None:
    models = {}
    for family, (repo, revision, allowed) in SPECS.items():
        data = api_model(repo, revision)
        files = {}
        for entry in data["siblings"]:
            name = entry["rfilename"]
            if name == ".gitattributes" or (allowed is not None and name not in allowed):
                continue
            files[name] = {
                "size": entry["size"],
                "sha256": (entry.get("lfs") or {}).get("sha256"),
                "git_blob_sha1": entry.get("blobId"),
            }
        if allowed is not None and set(files) != allowed:
            raise ValueError(f"Fichiers incomplets pour {family}: {allowed - set(files)}")
        models[family] = {
            "repo": repo, "revision": revision,
            "api": f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true",
            "license": (data.get("cardData") or {}).get("license"),
            "files": files,
        }
    payload = {"checked_utc": datetime.now(timezone.utc).isoformat(), "models": models,
               "notes": {"tts_s3": "Auxiliaire obligatoire Chatterbox, sans téléchargement implicite.",
                         "tts_voice": "Référence WAV consentie obligatoire, non incluse.",
                         "text_licenses": "Liquid et Ministral: other; lire les termes avant distribution."}}
    LOCK.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest_ok(path: Path, meta: dict) -> bool:
    if not path.is_file() or path.stat().st_size != meta["size"]:
        return False
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1(f"blob {meta['size']}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha256.update(block)
            sha1.update(block)
    return sha256.hexdigest() == meta["sha256"] if meta["sha256"] else sha1.hexdigest() == meta["git_blob_sha1"]


def status(family: str, root: Path) -> dict:
    item = json.loads(LOCK.read_text(encoding="utf-8"))["models"][family]
    target = root / item["repo"] / item["revision"]
    missing = [name for name, meta in item["files"].items() if not digest_ok(target / name, meta)]
    return {"family": family, "repo": item["repo"], "revision": item["revision"],
            "target": str(target), "status": "PASS" if not missing else "NOT_RUN",
            "missing_or_invalid": missing}


def download(family: str, root: Path) -> None:
    item = json.loads(LOCK.read_text(encoding="utf-8"))["models"][family]
    target = root / item["repo"] / item["revision"]
    if target.exists():
        if status(family, root)["status"] == "PASS":
            if family == "tts_s3":
                install_s3_cache(root)
            return
        raise RuntimeError(f"Snapshot incomplet: {target} ; corriger manuellement avant nouvelle publication")
    stage = target.with_name(target.name + ".partial")
    stage.mkdir(parents=True, exist_ok=True)
    for name, meta in item["files"].items():
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if digest_ok(dest, meta):
            continue
        url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{name}"
        partial = dest.with_name(dest.name + ".part")
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > meta["size"]:
            partial.unlink()
            offset = 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        with urllib.request.urlopen(request, timeout=60) as response:
            if offset and response.status != 206:
                raise RuntimeError(f"Reprise HTTP non confirmée pour {name}")
            with partial.open("ab" if offset else "wb") as stream:
                shutil.copyfileobj(response, stream)
        if not digest_ok(partial, meta):
            raise RuntimeError(f"Digest invalide pour {name}")
        partial.replace(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage.replace(target)
    if family == "tts_s3":
        install_s3_cache(root)


def install_s3_cache(root: Path) -> None:
    """Publie l'auxiliaire vérifié dans le cache HF que mlx-audio lit hors ligne."""
    item = json.loads(LOCK.read_text(encoding="utf-8"))["models"]["tts_s3"]
    source = root / item["repo"] / item["revision"]
    if status("tts_s3", root)["status"] != "PASS":
        raise RuntimeError("S3TokenizerV2 n'est pas vérifié")
    cache = root / ".cache/hub/models--mlx-community--S3TokenizerV2"
    blobs = cache / "blobs"
    snapshot = cache / "snapshots" / item["revision"]
    blobs.mkdir(parents=True, exist_ok=True)
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in ("model.safetensors", "config.json"):
        meta = item["files"][name]
        key = meta["sha256"] or meta["git_blob_sha1"]
        blob = blobs / key
        if not blob.exists():
            os.link(source / name, blob)
        link = snapshot / name
        if not link.exists():
            link.symlink_to(Path("../../blobs") / key)
    refs = cache / "refs"
    refs.mkdir(exist_ok=True)
    (refs / "main").write_text(item["revision"], encoding="ascii")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["refresh", "status", "download"])
    parser.add_argument("--family", choices=list(SPECS))
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    if args.action == "refresh":
        refresh()
        return 0
    from native.macos.profile import paths
    root = args.root or paths()["models"]
    families = [args.family] if args.family else list(SPECS)
    if args.action == "download":
        if not args.family:
            parser.error("--family est obligatoire pour download")
        download(args.family, root)
    for family in families:
        print(json.dumps(status(family, root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
