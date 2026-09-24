"""Lancer un programme console sans lui ouvrir de fenêtre (Windows).

Les ponts tournent sous pythonw, sans console. Sous Windows, un programme
console (`claude`, `codex`) lancé sans CREATE_NO_WINDOW s'en ouvre une,
vide, au premier plan : la « fenêtre vide » vue le 24/09.
"""
from __future__ import annotations

import os
import subprocess


def options() -> dict:
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
