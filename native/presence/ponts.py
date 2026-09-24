"""Ponts de harnais démarrés par Presence elle-même.

Un utilisateur qui a configuré Codex ou Claude Code ouvre hyper-ambient par
n'importe quel chemin — raccourci, lanceur, double-clic. Les ponts suivent :
Presence les démarre au lancement. Mesure du 24/09 : le lanceur montait la
pile mais aucun pont, et « le pont Claude ne répond pas » s'affichait.

Un pont ne part que s'il a son jeton dans `.env.local` ET que le CLI du
harnais est installé ; un pont déjà en écoute n'est pas empilé. Le jeton
n'est donné qu'au processus du pont, jamais à l'environnement de Presence.
La connexion du CLI lui-même (`codex login`, `claude`) reste à faire une
fois par l'utilisateur : le pont ne peut pas s'authentifier à sa place.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Pont:
    nom: str
    port: int
    module: str
    cle_jeton: str
    executable: str


PONTS = (
    Pont("Codex", 8765, "native.codexbridge.bridge", "CODEX_BRIDGE_TOKEN", "codex"),
    Pont("Claude Code", 8766, "native.clibridge.bridge", "CLI_BRIDGE_TOKEN", "claude"),
)


def port_ouvert(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def ponts_a_demarrer(
    valeurs: dict[str, str],
    *,
    port_ouvert: Callable[[int], bool] = port_ouvert,
    trouver: Callable[[str], str | None] = shutil.which,
) -> list[Pont]:
    return [
        pont
        for pont in PONTS
        if (valeurs.get(pont.cle_jeton) or "").strip()
        and trouver(pont.executable)
        and not port_ouvert(pont.port)
    ]


def _lire_env_local(chemin: Path) -> dict[str, str]:
    valeurs: dict[str, str] = {}
    if not chemin.is_file():
        return valeurs
    for ligne in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def _python_sans_console() -> str:
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return str(pythonw if pythonw.is_file() else exe)


def demarrer_ponts(
    racine: Path,
    *,
    journal_dir: Path | None = None,
    port_ouvert: Callable[[int], bool] = port_ouvert,
    trouver: Callable[[str], str | None] = shutil.which,
    popen: Callable[..., object] = subprocess.Popen,
) -> list[str]:
    """Démarre les ponts configurés et absents ; rend leurs noms."""
    racine = Path(racine)
    valeurs = _lire_env_local(racine / ".env.local")
    if journal_dir is None:
        journal_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "hyper-ambient"
    journal_dir.mkdir(parents=True, exist_ok=True)
    options: dict = {}
    if os.name == "nt":
        options["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
    lances: list[str] = []
    for pont in ponts_a_demarrer(valeurs, port_ouvert=port_ouvert, trouver=trouver):
        env = dict(os.environ)
        env[pont.cle_jeton] = valeurs[pont.cle_jeton].strip()
        journal = journal_dir / f"pont-{pont.executable}.log"
        with open(journal, "ab") as sortie:
            popen(
                [_python_sans_console(), "-m", pont.module],
                cwd=str(racine),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=sortie,
                stderr=subprocess.STDOUT,
                close_fds=True,
                **options,
            )
        lances.append(pont.nom)
    return lances
