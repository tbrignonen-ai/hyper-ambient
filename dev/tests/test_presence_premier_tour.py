"""C10 — première question souvent sans réponse.

Cause : l'UI arme l'écoute (tenu, bulle « écoute ») alors que le fil
session n'a pas encore ouvert le WebSocket. Un appui-relâche pendant
« Connexion… » ne reste pas dans ``threading.Event`` : ``_boucle_tours``
n'a rien vu, aucune trame ne part, EARS n'est jamais appelé.

Sans carte son, sans serveur : on pince le contrat UI et la perte
d'un pulse PTT déjà relâché.
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import pytest


class FausseCapture:
    def __init__(self) -> None:
        self.demarrages = 0

    def start(self) -> None:
        self.demarrages += 1

    def stop(self):
        return []


class FauxWs:
    def send(self, _brut: str) -> None:
        raise AssertionError("aucune trame ne doit partir : le pulse PTT est déjà mort")

    def recv(self) -> str:
        raise AssertionError("recv ne doit pas être atteint")


class FausseSortie:
    def abort(self) -> None:
        return None


def test_un_appui_deja_relache_est_invisible_pour_la_boucle():
    """Un PTT terminé avant ``_boucle_tours`` ne démarre pas le micro.

    C'est la mécanique du premier tour perdu : l'Event ne file pas les
    pulses. Après le correctif UI, ce chemin n'est plus joignable depuis
    le bouton (l'appui est refusé tant que le canal n'est pas prêt).
    """
    from native.presence.app import SessionVocale

    session = SessionVocale(
        queue.Queue(),
        url="ws://127.0.0.1:9/hostagent",
        device=None,
        sortie=None,
        raccourci_label="Espace",
    )
    capture = FausseCapture()
    session.tenu.set()
    session.tenu.clear()

    def tuer() -> None:
        time.sleep(0.35)
        session.arreter.set()

    threading.Thread(target=tuer, daemon=True).start()
    session._boucle_tours(FauxWs(), capture, FausseSortie())
    assert capture.demarrages == 0


def _application(tmp_path: Path):
    """Ouvre Presence sans lancer le fil audio. Skip si Tcl flake (Python 3.13)."""
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")

    from native.presence.app import Application, analyser_arguments

    args = analyser_arguments(
        ["--onboarding", "--config", str(tmp_path / "presence.json")]
    )
    derniere: Exception | None = None
    application = None
    for _ in range(3):
        try:
            application = Application(args)
            break
        except tk.TclError as exc:
            derniere = exc
    if application is None:
        pytest.skip(f"Tk indisponible : {derniere}")
    application.session_lancee = True
    application._afficher_application()
    application.racine.withdraw()
    application.racine.update_idletasks()
    return application


def test_appui_avant_canal_pret_n_arme_pas_lecoute(tmp_path: Path):
    """Le bouton Parler ne doit pas feindre l'écoute tant que le WS n'est pas prêt.

    Le chemin inverse (canal prêt → l'appui arme ``tenu``) est pincé dans
    la même fenêtre : un second ``Tk()`` flake sous Python 3.13 (init.tcl).
    """
    application = _application(tmp_path)
    try:
        assert application.session.ws is None
        application.enfoncer()
        assert application.enfonce is False
        assert not application.session.tenu.is_set()
        assert "prêt" in application.texte_statut.lower()

        application.session.canal_pret.set()
        application.enfoncer()
        assert application.enfonce is True
        assert application.session.tenu.is_set()
        application.relacher()
        assert application.enfonce is False
        assert not application.session.tenu.is_set()
    finally:
        application.fermer()
