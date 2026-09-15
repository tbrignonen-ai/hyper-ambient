"""Verrou anti-OOM pour les campagnes TTS experimentales.

Le live et les essais lourds ne doivent jamais partager le conteneur 8 Gio.
Ce module ne tue rien : il refuse le burn tant que serve_hostagent.py y tourne.
"""
from __future__ import annotations

import os
from pathlib import Path

OVERRIDE_ENV = "TTS_BURN_ALLOW_COLOCATED"


def _hostagent_pids(proc: Path = Path("/proc")) -> list[int]:
    pids: list[int] = []
    if not proc.is_dir():
        return pids
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
        except (OSError, PermissionError):
            continue
        if b"dev/scripts/serve_hostagent.py" in cmdline:
            pids.append(int(entry.name))
    return sorted(pids)


def refuser_colocation_live(proc: Path = Path("/proc")) -> None:
    """Leve avant tout chargement de modele si le live occupe ce conteneur."""
    pids = _hostagent_pids(proc)
    override = os.getenv(OVERRIDE_ENV, "").strip().lower() in {"1", "true", "yes"}
    if pids and not override:
        raise SystemExit(
            "REFUS TTS BURN: host-agent live detecte dans ce conteneur "
            f"(pid={','.join(map(str, pids))}). Utiliser un conteneur dedie ou "
            "arreter explicitement le live. Derogation dangereuse: "
            f"{OVERRIDE_ENV}=1."
        )
