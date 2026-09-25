"""Les consoles de harnais ouvertes par Presence sur une session (25/09).

Presence montre la conversation d'un harnais dans une console
(`conhost.exe <codex> resume <id>`, `conhost.exe <claude> --resume <id>`).
Tant qu'elle est ouverte, elle tient la session : Codex refuse un second
écrivain, Claude écrirait sur une branche que la console ne voit pas. Le pont
la ferme avant d'écrire dans la même session ; Presence la rouvre à la
réponse. Une console lancée par l'utilisateur n'est jamais visée.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess

from native import sans_console

logger = logging.getLogger("consoles_presence")


def consoles_de_session(processus, session, harnais="codex"):
    trouves = []
    for p in processus or []:
        if str(p.get("Name") or "").lower() != "conhost.exe":
            continue
        ligne = str(p.get("CommandLine") or "")
        mots = ligne.replace('"', " ").split()
        reprise = "resume" in mots or "--resume" in mots
        if harnais in ligne.lower() and reprise and session in mots:
            trouves.append(int(p["ProcessId"]))
    return trouves


def liberer_session(session, harnais="codex"):
    """Ferme les consoles Presence de cette session ; vrai si l'une l'était."""
    if os.name != "nt" or not session:
        return False
    try:
        brut = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='conhost.exe'\" | "
             "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15, **sans_console.options(),
        ).stdout.strip()
        processus = json.loads(brut) if brut else []
        if isinstance(processus, dict):
            processus = [processus]
    except Exception as exc:
        logger.warning("liberer_session : %s", exc)
        return False
    pids = consoles_de_session(processus, session, harnais)
    for pid in pids:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=10, **sans_console.options())
    if pids:
        logger.info("session %s %s liberee (consoles %s)", harnais, session, pids)
    return bool(pids)
