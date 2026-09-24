"""Relance du host-agent Mac demandée par Presence, exécutée par le superviseur.

Sur Windows, Réglages relance le host-agent par Docker. Sur Mac, le seul
propriétaire du processus est `supervise_macos.py` : Presence dépose une
demande dans le dossier de journaux (utilisateur seul, 0600), le superviseur
relance son enfant et répond. Pas de port réseau, pas de signal à un PID deviné.
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Callable

_DEMANDE = ".demande"
_REPONSE = ".reponse"


def demander_relance(dossier: Path, *, timeout: float = 240.0, pas: float = 0.25) -> bool:
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    base = dossier / f"relance-{uuid.uuid4().hex}"
    demande, reponse = base.with_suffix(_DEMANDE), base.with_suffix(_REPONSE)
    fd = os.open(demande, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if reponse.exists():
                return reponse.read_text(encoding="ascii").strip() == "ok"
            time.sleep(pas)
        return False
    finally:
        for chemin in (demande, reponse):
            try:
                chemin.unlink()
            except FileNotFoundError:
                pass


def traiter_demande(dossier: Path, relancer: Callable[[], bool]) -> bool:
    """Traite au plus une demande en attente ; True si une demande a été servie."""
    for demande in sorted(Path(dossier).glob("relance-*" + _DEMANDE)):
        reponse = demande.with_suffix(_REPONSE)
        if reponse.exists():
            continue
        try:
            ok = bool(relancer())
        except Exception:
            ok = False
        temporaire = demande.with_suffix(".tmp")
        temporaire.write_text("ok" if ok else "echec", encoding="ascii")
        os.replace(temporaire, reponse)
        return True
    return False
