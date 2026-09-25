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
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

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


def _processus_macos():
    sortie = subprocess.run(["ps", "-axo", "pid=,ppid=,command="],
                            capture_output=True, text=True, timeout=5, check=True).stdout
    processus = {}
    for ligne in sortie.splitlines():
        champs = ligne.strip().split(None, 2)
        if len(champs) == 3 and champs[0].isdigit() and champs[1].isdigit():
            processus[int(champs[0])] = (int(champs[1]), champs[2])
    return processus


def _descendants(processus, parent):
    enfants = [pid for pid, (ppid, _) in processus.items() if ppid == parent]
    return [pid for enfant in enfants for pid in [*_descendants(processus, enfant), enfant]]


def _cli_de_session(commande, harnais, session):
    try:
        mots = shlex.split(commande)
    except ValueError:
        return False
    reprise = "resume" if harnais == "codex" else "--resume"
    return (any(harnais in Path(mot).name.lower() for mot in mots)
            and any(mots[i:i + 2] == [reprise, session] for i in range(len(mots) - 1)))


def _fermer_fenetre_macos(tty):
    """Ferme uniquement une fenêtre Terminal à onglet unique au TTY prouvé."""
    if not tty.startswith("/dev/tty"):
        return
    script = '''on run argv
set targetTTY to item 1 of argv
tell application "Terminal"
  repeat with w in windows
    if (count of tabs of w) is 1 then
      repeat with t in tabs of w
        if (tty of t as text) is targetTTY then
          close w
          return
        end if
      end repeat
    end if
  end repeat
end tell
end run'''
    try:
        subprocess.run(["osascript", "-e", script, tty], capture_output=True,
                       text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("fenetre Terminal Presence non fermee : %s", exc)


def liberer_console_macos(dossier, *, processus=None):
    """Libère un .command Presence vérifié, sans signaler un Terminal étranger."""
    dossier = Path(dossier)
    if not dossier.name.startswith("mother-harnais-") or dossier.parent != Path(tempfile.gettempdir()):
        return False
    try:
        meta = json.loads((dossier / "session.json").read_text(encoding="utf-8"))
        pid = int((dossier / "pid").read_text(encoding="ascii").strip())
        tty = (dossier / "tty").read_text(encoding="ascii").strip()
        sonde_reelle = processus is None
        processus = _processus_macos() if sonde_reelle else processus
        commande = processus[pid][1]
        if str(dossier / "reprendre.command") not in shlex.split(commande):
            return False
        descendants = _descendants(processus, pid)
        cli_pids = [p for p in descendants if _cli_de_session(
            processus[p][1], meta["harnais"], meta["session"])]
        if not cli_pids:
            return False
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        logger.warning("console Presence Mac non verifiee : %s", exc)
        return False
    signales = False
    for cible in descendants:
        try:
            os.kill(cible, signal.SIGTERM)
            signales = True
        except ProcessLookupError:
            pass
        except OSError as exc:
            logger.warning("console Presence Mac %s non arretee : %s", cible, exc)
    if sonde_reelle and signales:
        # Certains wrappers Node ignorent TERM. Revalider PID, parent et ligne
        # avant KILL : jamais un processus réutilisé entre deux sondes.
        time.sleep(0.3)
        try:
            encore = _processus_macos()
            for cible in descendants:
                if encore.get(cible) == processus[cible]:
                    try:
                        os.kill(cible, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("verification arret console Mac : %s", exc)
    try:
        os.kill(pid, signal.SIGTERM)
        signales = True
    except ProcessLookupError:
        pass
    except OSError as exc:
        logger.warning("shell Presence Mac %s non arrete : %s", pid, exc)
    if not signales:
        return False
    _fermer_fenetre_macos(tty)
    logger.info("session %s %s liberee (console Presence %s)", meta["harnais"], meta["session"], pid)
    return True


def _liberer_session_macos(session, harnais):
    racine = Path(tempfile.gettempdir())
    liberee = False
    for dossier in racine.glob("mother-harnais-*"):
        try:
            meta = json.loads((dossier / "session.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("session") == session and meta.get("harnais") == harnais:
            liberee = liberer_console_macos(dossier) or liberee
    return liberee


def liberer_session(session, harnais="codex"):
    """Ferme les consoles Presence de cette session ; vrai si l'une l'était."""
    if not session:
        return False
    if sys.platform == "darwin":
        return _liberer_session_macos(session, harnais)
    if os.name != "nt":
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
