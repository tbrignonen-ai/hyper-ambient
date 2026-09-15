#!/usr/bin/env python3
"""Génère 2 images sample wan2.7-image (DashScope remote, 0 VRAM locale).

    DASHSCOPE_API_KEY=sk-... python dev/scripts/gen_wan27_images.py
    DASHSCOPE_REGION=beijing python dev/scripts/gen_wan27_images.py   # quota gratuit 50 img

URLs générées valables 24 h : le script les télécharge tout de suite.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("WAN27_OUT", REPO / "data" / "out" / "images-wan27"))

MODEL = os.environ.get("WAN27_MODEL", "wan2.7-image")
SIZE = os.environ.get("WAN27_SIZE", "1280*720")
THINKING = os.environ.get("WAN27_THINKING", "1") not in ("0", "false", "False")

REGIONS = {
    "singapore": "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "beijing": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
}

PROMPTS = [
    (
        "01-presence-lampe.png",
        (
            "Soft ambient companion presence in a quiet apartment at dusk, 16:9 cinematic still. "
            "A wooden desk, one warm lamp, teal-blue evening light through a window. "
            "Near the desk, a gentle diffuse orb of warm amber light like a quiet home companion: "
            "not a person, not a robot, no face, no body, no UI. Cozy, non-threatening, film grain, "
            "shallow depth of field. Palette: amber, teal, charcoal. No text, no watermark, no logo."
        ),
        1302701,
    ),
    (
        "02-presence-orbe.png",
        (
            "Abstract ambient companion visual, 16:9. Dark quiet room filled with slow volumetric fog. "
            "A living lantern of teal and amber light that seems to breathe, soft caustics on the floor. "
            "Distant presence, calm, no human, no face, no mascot, no interface. Painterly cinematic. "
            "No text, no watermark, no logo."
        ),
        1302702,
    ),
]


def _load_dotenv() -> None:
    env_path = REPO / ".env.local"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if (not s) or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _post(url: str, api_key: str, prompt: str, seed: int) -> dict:
    payload = {
        "model": MODEL,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {
            "size": SIZE,
            "n": 1,
            "watermark": False,
            "thinking_mode": THINKING,
            "seed": seed,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"message": raw}
        parsed["_http"] = err.code
        return parsed


def _image_urls(data: dict) -> list[str]:
    urls: list[str] = []
    output = data.get("output") or {}
    for choice in output.get("choices") or []:
        message = (choice.get("message") or {})
        for item in message.get("content") or []:
            if isinstance(item, dict) and item.get("image"):
                urls.append(item["image"])
            elif isinstance(item, dict) and item.get("type") == "image" and item.get("image"):
                urls.append(item["image"])
    results = output.get("results") or []
    for item in results:
        if isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
    return urls


def main() -> int:
    _load_dotenv()
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        print(
            "STOP: DASHSCOPE_API_KEY absent. wan2.7-image est une API DashScope, "
            "pas un checkpoint local. Voir nights/2026-09-13-CURSOR-WAN27-IMAGES.md",
            file=sys.stderr,
        )
        return 2

    region = os.environ.get("DASHSCOPE_REGION", "singapore").strip().lower()
    if region not in REGIONS:
        print(f"region inconnue: {region} (singapore|beijing)", file=sys.stderr)
        return 2
    url = REGIONS[region]
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"model={MODEL} region={region} size={SIZE} thinking={THINKING} out={OUT}", flush=True)
    t0 = time.time()
    written: list[Path] = []
    for name, prompt, seed in PROMPTS:
        dest = OUT / name
        print(f"gen {name} seed={seed} …", flush=True)
        data = _post(url, api_key, prompt, seed)
        if data.get("code") or data.get("_http", 200) >= 400:
            print(json.dumps({k: data.get(k) for k in ("code", "message", "_http", "request_id")}, ensure_ascii=False))
            return 1
        urls = _image_urls(data)
        if not urls:
            print("pas d'URL image dans la réponse:", json.dumps(data)[:800], file=sys.stderr)
            return 1
        urllib.request.urlretrieve(urls[0], dest)
        size = dest.stat().st_size
        if size < 1024:
            print(f"{dest} trop petit ({size} o)", file=sys.stderr)
            return 1
        print(f"  wrote {dest} {size} octets request_id={data.get('request_id')}", flush=True)
        sidecar = dest.with_suffix(".json")
        sidecar.write_text(
            json.dumps(
                {
                    "file": name,
                    "model": MODEL,
                    "region": region,
                    "size": SIZE,
                    "seed": seed,
                    "thinking_mode": THINKING,
                    "request_id": data.get("request_id"),
                    "usage": data.get("usage"),
                    "prompt": prompt,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(dest)

    print(f"ok {len(written)} images en {time.time() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
