"""Captures Presence HA — 18 sept. Hors runtime live (pas de session vocale)."""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "native" / "presence"))

from native.presence.app import Application, analyser_arguments  # noqa: E402
from native.presence import overlay as visuel  # noqa: E402

DEST_REPO = ROOT / "nights"
DEST_COFFRE = Path(
    r"C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights"
)
PREFIX = "2026-09-18-cursor-ui"


def _grab(racine, dest: Path) -> None:
    racine.deiconify()
    racine.lift()
    racine.attributes("-topmost", True)
    racine.update_idletasks()
    racine.update()
    for _ in range(8):
        racine.update()
        time.sleep(0.05)
    x, y = racine.winfo_rootx(), racine.winfo_rooty()
    w, h = racine.winfo_width(), racine.winfo_height()
    if w < 40 or h < 40:
        raise SystemExit(f"fenêtre trop petite : {w}x{h}")
    image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    print(f"capture : {dest} ({image.size[0]}x{image.size[1]})", flush=True)


def _sauver(source: Path) -> None:
    if DEST_COFFRE.exists():
        shutil.copy2(source, DEST_COFFRE / source.name)


def capturer_app() -> None:
    tmp = Path(tempfile.mkdtemp()) / "presence.json"
    args = analyser_arguments(["--onboarding", "--config", str(tmp)])
    application = Application(args)
    application.session_lancee = True
    try:
        application.racine.geometry("520x800+80+40")
        application.tic()
        _grab(application.racine, DEST_REPO / f"{PREFIX}-1-bienvenue.png")
        _sauver(DEST_REPO / f"{PREFIX}-1-bienvenue.png")

        application._afficher_reglage_ptt()
        application.tic()
        _grab(application.racine, DEST_REPO / f"{PREFIX}-2-ptt.png")
        _sauver(DEST_REPO / f"{PREFIX}-2-ptt.png")

        application._afficher_masquage()
        application.tic()
        _grab(application.racine, DEST_REPO / f"{PREFIX}-3-masquage.png")
        _sauver(DEST_REPO / f"{PREFIX}-3-masquage.png")

        application._afficher_application()
        application.session_lancee = True
        application.tic()
        _grab(application.racine, DEST_REPO / f"{PREFIX}-4-local.png")
        _sauver(DEST_REPO / f"{PREFIX}-4-local.png")

        application._traiter({"type": "etat", "etat": "parole", "niveau": None})
        application.tic()
        _grab(application.racine, DEST_REPO / f"{PREFIX}-5-parole.png")
        _sauver(DEST_REPO / f"{PREFIX}-5-parole.png")

        application._traiter({"type": "etat", "etat": "escalade", "niveau": None})
        application.tic()
        _grab(application.racine, DEST_REPO / f"{PREFIX}-6-distant.png")
        _sauver(DEST_REPO / f"{PREFIX}-6-distant.png")
    finally:
        application.fermer()


def capturer_overlay() -> None:
    presence = visuel.Presence(
        visuel.analyser_arguments(["--demo", "--taille", "220", "--coin", "haut-gauche"])
    )
    try:
        presence.racine.geometry("220x220+80+40")
        presence.appliquer_etat("parole", niveau=0.7, source="demo")
        presence.dessiner()
        _grab(presence.racine, DEST_REPO / f"{PREFIX}-7-overlay-parole.png")
        _sauver(DEST_REPO / f"{PREFIX}-7-overlay-parole.png")
        presence.appliquer_etat("escalade", niveau=None, source="demo")
        presence.dessiner()
        _grab(presence.racine, DEST_REPO / f"{PREFIX}-8-overlay-escalade.png")
        _sauver(DEST_REPO / f"{PREFIX}-8-overlay-escalade.png")
        presence.appliquer_etat("repos", niveau=None, source="demo")
        presence.dessiner()
        _grab(presence.racine, DEST_REPO / f"{PREFIX}-9-overlay-repos.png")
        _sauver(DEST_REPO / f"{PREFIX}-9-overlay-repos.png")
    finally:
        presence.fermer()


if __name__ == "__main__":
    capturer_app()
    capturer_overlay()
    print("OK", flush=True)
