"""Ouvre la conversation d'un harnais dans sa propre console (24/09).

Quand Claude ou Codex rend sa réponse, le host-agent envoie l'identifiant
de session ; Presence la rouvre (`claude --resume <id>`, `codex resume <id>`)
dans le dossier où tournent les ponts, pour que la conversation soit visible
dans le harnais. L'écran principal choisit seulement si la console passe au
premier plan ou s'ouvre réduite, sans voler le focus.

Une console par harnais : la réponse suivante remplace la précédente, qui
ne verrait pas les nouveaux messages.
"""
from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Optional

SW_SHOWNORMAL = 1
SW_SHOWMINNOACTIVE = 7

_REPRISE = {
    "Claude": ("claude", ["--resume"]),
    "Codex": ("codex", ["resume"]),
}


class _InfoDemarrage:
    """Repli hors Windows (tests en conteneur) de ``subprocess.STARTUPINFO``."""

    def __init__(self) -> None:
        self.dwFlags = 0
        self.wShowWindow = 0


def _exe(nom: str) -> str:
    found = shutil.which(nom)
    if found or sys.platform != "darwin":
        return found or nom
    home = Path.home()
    extra = [Path("/opt/homebrew/bin"), Path("/usr/local/bin"),
             home / ".local/bin", home / ".npm-global/bin"]
    extra += sorted((home / ".nvm/versions/node").glob("*/bin"), reverse=True)
    return shutil.which(nom, path=os.pathsep.join(map(str, extra))) or nom


def mode_claude_par_defaut(reglages: Optional[Path] = None) -> str:
    """Le mode de permission habituel de l'utilisateur dans Claude Code."""
    chemin = reglages or Path.home() / ".claude" / "settings.json"
    try:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
        mode = (donnees.get("permissions") or {}).get("defaultMode")
    except (OSError, ValueError, AttributeError):
        mode = None
    return mode if isinstance(mode, str) and mode else "manual"


_DEFAUT = object()


def commande(
    harnais: str,
    session: str,
    exe: Callable[[str], str] = _exe,
    mode_claude: Any = _DEFAUT,
) -> Optional[list[str]]:
    if harnais not in _REPRISE or not session:
        return None
    nom, reprise = _REPRISE[harnais]
    cmd = [exe(nom), *reprise, session]
    if harnais == "Claude":
        # La session vient du pont, en lecture seule ; la console est celle de
        # l'utilisateur : son mode habituel, pas le /plan hérité (24/09).
        mode = mode_claude_par_defaut() if mode_claude is _DEFAUT else mode_claude
        if mode:
            cmd += ["--permission-mode", mode]
    return cmd


def options_console(racine: str, premier_plan: bool) -> dict[str, Any]:
    if sys.platform == "darwin":
        env = {k: v for k, v in os.environ.items() if k.upper() != "TERM"}
        prefixes = ["/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local/bin")]
        env["PATH"] = os.pathsep.join(prefixes + [env.get("PATH", "/usr/bin:/bin")])
        return {"cwd": racine, "env": env, "premier_plan_mac": premier_plan}
    info = getattr(subprocess, "STARTUPINFO", _InfoDemarrage)()
    info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
    info.wShowWindow = SW_SHOWNORMAL if premier_plan else SW_SHOWMINNOACTIVE
    # TERM hérité d'un shell (« dumb ») met Codex en mode dégradé.
    env = {k: v for k, v in os.environ.items() if k.upper() != "TERM"}
    return {
        "cwd": racine,
        "env": env,
        "startupinfo": info,
        "creationflags": getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    }


def affichage(options: dict[str, Any]) -> int:
    return options["startupinfo"].wShowWindow


def _consoles_visibles() -> set[int]:
    import ctypes
    import ctypes.wintypes as w

    user32 = ctypes.windll.user32
    trouvees: set[int] = set()

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def _une(hwnd, _):
        classe = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, classe, 64)
        if classe.value == "ConsoleWindowClass" and user32.IsWindowVisible(hwnd):
            trouvees.add(int(hwnd))
        return True

    user32.EnumWindows(_une, 0)
    return trouvees


_VERROU_OUVERTURE = threading.Lock()


def _montrer(avant: set[int], premier_plan: bool) -> None:
    """Trouve la nouvelle console et la passe devant, ou la réduit.

    Windows refuse le premier plan à une application qui n'a pas le focus :
    une frappe Alt simulée lève ce verrou, procédé documenté et sans effet
    visible."""
    import ctypes
    import time

    user32 = ctypes.windll.user32
    for _ in range(40):
        nouvelles = _consoles_visibles() - avant
        if nouvelles:
            hwnd = nouvelles.pop()
            if premier_plan:
                user32.keybd_event(0x12, 0, 0, 0)
                user32.keybd_event(0x12, 0, 2, 0)
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
            else:
                user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
            return
        time.sleep(0.2)


def _lancer(cmd: list[str], **options: Any):
    if sys.platform == "darwin":
        premier_plan = options.pop("premier_plan_mac", True)
        dossier = options["cwd"]
        # LaunchServices ouvre une vraie session Terminal sans permission
        # Automation. Tous les arguments, y compris apostrophes/accents, sont
        # échappés pour sh ; aucun script AppleScript construit par concaténation.
        script_dir = Path(tempfile.mkdtemp(prefix="mother-harnais-"))
        script = script_dir / "reprendre.command"
        (script_dir / "session.json").write_text(json.dumps({
            "harnais": "codex" if cmd[1] == "resume" else "claude",
            "session": cmd[2],
        }), encoding="utf-8")
        # Le shell garde le chemin du .command dans sa ligne de processus.
        # Le pont peut ainsi prouver que le CLI descend de cette console
        # Presence, même si un Terminal utilisateur reprend la même session.
        content = ("#!/bin/sh\ncd " + shlex.quote(dossier) + " || exit 1\n"
                   "printf '%s\\n' \"$$\" > " + shlex.quote(str(script_dir / "pid")) + "\n"
                   "tty > " + shlex.quote(str(script_dir / "tty")) + "\n"
                   + " ".join(map(shlex.quote, cmd)) + "\n")
        script.write_text(content, encoding="utf-8", newline="\n")
        script.chmod(0o700)
        args = ["open", "-a", "Terminal"]
        if not premier_plan:
            args.append("-g")
        args.append(str(script))
        proc = subprocess.Popen(args, cwd=dossier, env=options["env"])
        proc._mother_script_dir = script_dir
        return proc
    if os.name != "nt":
        return subprocess.Popen(cmd, **options)
    # conhost : une vraie fenêtre à soi, pas un onglet de Windows Terminal
    # qu'on ne pourrait ni montrer ni réduire (mesure du 24/09). Les
    # ouvertures sont en série : sinon deux harnais ouverts ensemble
    # peuvent prendre la fenêtre l'un de l'autre. Appelé hors du fil de l'UI.
    with _VERROU_OUVERTURE:
        avant = _consoles_visibles()
        proc = subprocess.Popen(["conhost.exe", *cmd], **options)
        _montrer(avant, affichage(options) == SW_SHOWNORMAL)
    return proc


def _fermer(proc) -> None:
    """Ferme la console et ses enfants (claude.cmd, codex.cmd lancent node)."""
    if sys.platform == "darwin" and getattr(proc, "_mother_script_dir", None):
        from native.consoles_presence import liberer_console_macos
        liberer_console_macos(proc._mother_script_dir)
        return
    if proc.poll() is not None:
        return
    if sys.platform != "win32":
        # open(1) sort dès que Terminal a reçu le .command. La fenêtre appartient
        # ensuite à l'utilisateur : nous ne tuons jamais un terminal existant.
        proc.terminate()
        return
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        proc.kill()


def _dossier_de(harnais: str, session: str) -> Optional[str]:
    from native.sessions_harnais import cwd_de_session

    dossier = cwd_de_session(harnais, session)
    return dossier if dossier and os.path.isdir(dossier) else None


class OuvreurHarnais:
    def __init__(
        self,
        racine: str,
        *,
        lancer: Callable[..., Any] = _lancer,
        fermer: Callable[[Any], None] = _fermer,
        exe: Callable[[str], str] = _exe,
        dossier_de: Callable[[str, str], Optional[str]] = _dossier_de,
        mode_claude: Any = _DEFAUT,
    ) -> None:
        self.racine = racine
        self._mode_claude = mode_claude
        self._dossier_de = dossier_de
        self._lancer = lancer
        self._fermer = fermer
        self._exe = exe
        self._consoles: dict[str, Any] = {}

    def ouvrir(self, harnais: str, session: str, *, premier_plan: bool) -> bool:
        cmd = commande(harnais, session, exe=self._exe, mode_claude=self._mode_claude)
        if cmd is None:
            return False
        precedente = self._consoles.pop(harnais, None)
        if precedente is not None:
            self._fermer(precedente)
        # Une session rejointe peut venir d'un autre projet : sa console
        # s'ouvre dans son dossier, sans quoi Claude ne la retrouve pas.
        try:
            dossier = self._dossier_de(harnais, session) or self.racine
        except Exception:
            dossier = self.racine
        self._consoles[harnais] = self._lancer(cmd, **options_console(dossier, premier_plan))
        return True
