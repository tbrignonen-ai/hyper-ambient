"""Inventaire modeles TTS et tentative de clonage Pocket sur CPU."""
from __future__ import annotations

import os
import traceback
from pathlib import Path

print("HF_TOKEN", "set" if os.environ.get("HF_TOKEN") else "absent")
print("HUGGING_FACE_HUB_TOKEN", "set" if os.environ.get("HUGGING_FACE_HUB_TOKEN") else "absent")

for p in [
    Path("/workspace/models/tts"),
    Path("/workspace/models/pocket-tts"),
    Path("/workspace/models/supertonic"),
    Path("/root/.cache/huggingface/hub"),
]:
    print("\n==", p, "exists" if p.exists() else "MISSING")
    if p.exists():
        for child in sorted(p.iterdir())[:30]:
            extra = ""
            if child.is_dir():
                extra = f"  ({sum(1 for _ in child.rglob('*'))} files)"
            print(f"  {child.name}{extra}")

print("\n== imports")
import importlib

for m in ["pocket_tts", "huggingface_hub", "torch"]:
    try:
        mod = importlib.import_module(m)
        print(m, "OK", getattr(mod, "__version__", ""), getattr(mod, "__file__", "")[:80])
    except Exception as e:
        print(m, type(e).__name__, e)
