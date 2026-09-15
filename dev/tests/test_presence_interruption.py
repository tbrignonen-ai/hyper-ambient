"""
PRESENCE : rappuyer sur Parler coupe la voix (15 sept).

Thomas : « on peut pas l'interrompre, quand tu cliques sur le bouton elle
continue ». `consommer_reponse` jouait tout jusqu'au marqueur de fin sans
regarder le bouton. Attendu : des l'appui, plus rien n'est joue, le tampon de
la carte est jete, la capture demarre, et la socket est quand meme videe
jusqu'au marqueur — sinon le tour suivant lirait la fin de celui-ci.
"""
import json

import pytest

pytest.importorskip("tkinter")  # la fenetre ne tourne que sur l hote Windows
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "native" / "presence"))

import native.presence.app as app  # noqa: E402


class FauxWs:
    def __init__(self, messages):
        self.messages = [json.dumps(m) for m in messages]

    def recv(self):
        return self.messages.pop(0)


class FausseSortie:
    def __init__(self):
        self.jete = 0

    def abort(self):
        self.jete += 1


def test_appui_pendant_la_reponse_coupe_et_ecoute():
    tenu = threading.Event()
    joues, captures = [], []

    class FauxMoteur:
        _reposer = staticmethod(lambda sortie: None)

        @staticmethod
        def _jouer(sortie, echantillons):
            joues.append(list(echantillons))
            tenu.set()  # Thomas appuie pendant le premier paquet

    app.moteur = FauxMoteur
    ws = FauxWs([{"frames": [[0.1]]}, {"frames": [[0.2]]}, {"frames": [[0.3]]},
                 {"type": "report", "transcript": "t", "reply": "r"}, {"frames": []}])
    sortie = FausseSortie()

    interrompu = app.consommer_reponse(
        ws, sortie, 0.0, lambda m: None, threading.Event(),
        interrompre=tenu, sur_interruption=lambda: captures.append(1),
    )

    assert interrompu is True
    assert joues == [[0.1]]
    assert sortie.jete == 1
    assert captures == [1]
    assert ws.messages == []


def test_sans_appui_tout_est_joue():
    joues = []

    class FauxMoteur:
        _reposer = staticmethod(lambda sortie: None)

        @staticmethod
        def _jouer(sortie, echantillons):
            joues.append(list(echantillons))

    app.moteur = FauxMoteur
    ws = FauxWs([{"frames": [[0.1]]}, {"frames": [[0.2]]}, {"frames": []}])
    interrompu = app.consommer_reponse(
        ws, FausseSortie(), 0.0, lambda m: None, threading.Event(),
        interrompre=threading.Event(),
    )
    assert interrompu is False
    assert joues == [[0.1], [0.2]]
