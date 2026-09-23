"""Annonce de mandat hors tour : jouée tout de suite, jamais décalée.

Séance du 23 sept : Codex répond pendant que Présence attend l'appui (mode
bouton). L'hôte pousse l'annonce — trames puis marqueur vide — mais la
boucle ne lit pas la socket hors tour. L'annonce reste en file 18 minutes,
puis le tour suivant la lit comme sa propre réponse : chaque réponse
entendue appartient ensuite à la question d'avant.
"""
from __future__ import annotations

import json
import queue
import threading
import time


class WsScripte:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = [json.dumps(m) for m in messages]
        self.envoyes: list[str] = []

    def recv(self, timeout: float | None = None) -> str:
        if self.messages:
            return self.messages.pop(0)
        time.sleep(timeout or 0.05)
        raise TimeoutError

    def send(self, brut: str) -> None:
        self.envoyes.append(brut)


class CaptureMuette:
    def start(self) -> None:
        return None

    def stop(self):
        return []


class SortieNotee:
    def __init__(self) -> None:
        self.jouees: list[list[float]] = []

    def abort(self) -> None:
        return None


def test_annonce_arrivee_entre_deux_tours_est_jouee_et_consommee(monkeypatch):
    from native.presence import app

    sortie = SortieNotee()
    class FauxMoteur:
        @staticmethod
        def _jouer(s, echantillons):
            s.jouees.append(list(echantillons))

        @staticmethod
        def _reposer(_s):
            return None

    monkeypatch.setattr(app, "moteur", FauxMoteur)

    session = app.SessionVocale(
        queue.Queue(),
        url="ws://127.0.0.1:9/hostagent",
        device=None,
        sortie=None,
        raccourci_label="Espace",
    )
    ws = WsScripte(
        [
            {"frames": [[0.1, 0.2], [0.3]]},
            {"frames": [[0.4]]},
            {"frames": []},
        ]
    )

    def tuer() -> None:
        time.sleep(0.6)
        session.arreter.set()

    threading.Thread(target=tuer, daemon=True).start()
    session._boucle_tours(ws, CaptureMuette(), sortie)

    assert ws.messages == [], "l'annonce et son marqueur doivent quitter la socket"
    assert [x for bloc in sortie.jouees for x in bloc] == [0.1, 0.2, 0.3, 0.4]


class ConnectionClosed(Exception):
    """Même nom que l'exception de ``websockets`` : fermeture de la socket."""


class WsFermee:
    def __init__(self) -> None:
        self.lectures = 0

    def recv(self, timeout: float | None = None) -> str:
        self.lectures += 1
        raise ConnectionClosed("received 1012 (service restart)")

    def send(self, _brut: str) -> None:
        raise ConnectionClosed("received 1012 (service restart)")


def test_socket_fermee_hors_tour_remonte_pour_se_reconnecter():
    """Séance du 23 sept : après une relance du host-agent, la lecture hors
    tour avalait la fermeture et bouclait sur une socket morte — Présence ne
    se reconnectait jamais, ni au bouton ni en mains libres."""
    import pytest

    from native.presence import app

    session = app.SessionVocale(
        queue.Queue(),
        url="ws://127.0.0.1:9/hostagent",
        device=None,
        sortie=None,
        raccourci_label="Espace",
    )
    ws = WsFermee()

    def tuer() -> None:
        time.sleep(1.0)
        session.arreter.set()

    threading.Thread(target=tuer, daemon=True).start()
    with pytest.raises(ConnectionClosed):
        session._boucle_tours(ws, CaptureMuette(), SortieNotee())
    assert ws.lectures == 1
