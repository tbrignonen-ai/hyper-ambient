"""
Tests du transport WebSocket qui expose LocalChannel sur le réseau local.

Le port 8001 est mappé dans docker-compose.yml (« WebSocket (host-agent
transport) ») mais rien ne l'écoute : c'est la surface que
``create_transport_app`` doit combler. ADR-004 : les événements passent
par un canal textuel inspectable. L'audio devrait passer par mémoire
partagée ; le mode dégradé tout-WebSocket, prévu par la même ADR quand
la mémoire partagée est indisponible, est notre cas (conteneur dans une
VM Docker Windows). On teste ce mode, pas un contournement.

Encodage des trames dans le JSON : liste de flottants, une liste par
trame (longueur FRAME_SAMPLES). C'est lisible dans un proxy, un journal
ou un test sans décodeur — ADR-004 veut un canal inspectable. Un blob
base64 de float32 serait plus compact et opaque ; on le refuse.

Adresse vue par le transport : TestClient de Starlette pose
``websocket.client.host = "testclient"``, qui n'est pas une IP.
``LocalChannel.authenticate`` décide la localité par
``ipaddress.ip_address(...).is_loopback``, donc « testclient » est
refusé avant même le secret. On n'ajoute PAS de drapeau ``skip_check`` :
un tel drapeau vivrait jusqu'en production et viderait ADR-016 règle 3.

Choix : ``create_transport_app`` accepte ``peer_address_of(websocket) -> str``.
En production, la fabrique par défaut lit l'adresse réelle du socket.
En test, on injecte ``"127.0.0.1"``. Le contrôle de localité s'exécute
toujours, sur l'adresse fournie par la fabrique — jamais contourné.
"""
from __future__ import annotations

import json

import pytest


SECRET = "partage-installation"
VOIE = "/hostagent"


def _adresse_de_test(websocket) -> str:
    """Fabrique de test : loopback. Le contrôle is_loopback s'applique encore."""
    return "127.0.0.1"


def _create_app(*, secret=SECRET, on_frames=None, journal=None):
    from src.hostagent.transport import create_transport_app

    return create_transport_app(
        secret=secret,
        on_frames=on_frames if on_frames is not None else (lambda frames: None),
        journal=journal,
        peer_address_of=_adresse_de_test,
    )


def _trame(valeur=0.0, taille=None):
    from src.hostagent.audio import FRAME_SAMPLES

    n = FRAME_SAMPLES if taille is None else taille
    return [float(valeur)] * n


def _echantillons(trame):
    return trame.samples if hasattr(trame, "samples") else trame


def _attendre_fermeture(ws) -> None:
    """La session doit mourir. Un message d'erreur optionnel n'est pas un ready."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        for _ in range(8):
            recu = ws.receive_json()
            assert recu.get("type") != "ready"
        pytest.fail("la connexion est restée ouverte")


def test_la_poignee_de_main_exige_le_secret_partage():
    """Mauvais secret : la connexion est fermée. Bon secret : {"type": "ready"}."""
    from fastapi.testclient import TestClient

    app = _create_app()

    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            ws.send_json({"type": "hello", "secret": "mauvais-secret"})
            _attendre_fermeture(ws)

        with client.websocket_connect(VOIE) as ws:
            ws.send_json({"type": "hello", "secret": SECRET})
            assert ws.receive_json() == {"type": "ready"}


def test_un_message_avant_la_poignee_de_main_est_refuse():
    """Un invoke sans hello préalable est refusé et la connexion est fermée."""
    from fastapi.testclient import TestClient

    app = _create_app()

    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            ws.send_json(
                {
                    "type": "invoke",
                    "primitive": "audio.capture",
                    "frames": [_trame()],
                }
            )
            _attendre_fermeture(ws)


def test_seules_les_primitives_du_contrat_sont_acceptees():
    """invoke « shell » : refus nommé. Le transport réutilise is_permitted."""
    import inspect

    from src.hostagent import transport
    from src.hostagent.contract import is_permitted

    assert is_permitted("shell") is False
    source = inspect.getsource(transport)
    assert "is_permitted" in source

    from fastapi.testclient import TestClient

    app = _create_app()
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            ws.send_json({"type": "hello", "secret": SECRET})
            assert ws.receive_json() == {"type": "ready"}
            ws.send_json({"type": "invoke", "primitive": "shell", "frames": []})
            erreur = ws.receive_json()
            assert erreur.get("type") == "error"
            assert "shell" in json.dumps(erreur)


def test_les_trames_audio_recues_sont_transmises_au_coeur():
    """on_frames reçoit les trames décodées : le bon nombre, FRAME_SAMPLES chacune."""
    from src.hostagent.audio import FRAME_SAMPLES

    from fastapi.testclient import TestClient

    recues = []

    def on_frames(frames):
        recues.extend(frames)

    app = _create_app(on_frames=on_frames)
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            ws.send_json({"type": "hello", "secret": SECRET})
            assert ws.receive_json() == {"type": "ready"}
            ws.send_json(
                {
                    "type": "invoke",
                    "primitive": "audio.capture",
                    "frames": [_trame(0.0), _trame(0.5)],
                }
            )

    assert len(recues) == 2
    for trame in recues:
        assert len(_echantillons(trame)) == FRAME_SAMPLES
    assert float(_echantillons(recues[0])[0]) == 0.0
    assert float(_echantillons(recues[1])[0]) == 0.5


def test_une_trame_de_mauvaise_taille_est_refusee_sans_tuer_la_connexion():
    """100 échantillons : erreur nommée InvalidFrameSizeError, session encore ouverte."""
    from src.hostagent.audio import FRAME_SAMPLES

    from fastapi.testclient import TestClient

    recues = []

    def on_frames(frames):
        recues.extend(frames)

    app = _create_app(on_frames=on_frames)
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            ws.send_json({"type": "hello", "secret": SECRET})
            assert ws.receive_json() == {"type": "ready"}
            ws.send_json(
                {
                    "type": "invoke",
                    "primitive": "audio.capture",
                    "frames": [_trame(taille=100)],
                }
            )
            erreur = ws.receive_json()
            assert erreur.get("type") == "error"
            assert "InvalidFrameSizeError" in json.dumps(erreur)
            assert recues == []

            ws.send_json(
                {
                    "type": "invoke",
                    "primitive": "audio.capture",
                    "frames": [_trame(0.25)],
                }
            )

    assert len(recues) == 1
    assert len(_echantillons(recues[0])) == FRAME_SAMPLES


def test_le_transport_journalise_chaque_invocation():
    """Chaque invocation acceptée est enregistrée dans le journal injecté (ADR-016 règle 4)."""
    from fastapi.testclient import TestClient

    journal = []
    app = _create_app(journal=journal)

    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            ws.send_json({"type": "hello", "secret": SECRET})
            assert ws.receive_json() == {"type": "ready"}
            ws.send_json(
                {
                    "type": "invoke",
                    "primitive": "audio.capture",
                    "frames": [_trame()],
                }
            )
            ws.send_json(
                {
                    "type": "invoke",
                    "primitive": "audio.render",
                    "frames": [_trame()],
                }
            )
            ws.send_json({"type": "invoke", "primitive": "shell", "frames": []})
            erreur = ws.receive_json()
            assert erreur.get("type") == "error"

    assert journal == ["audio.capture", "audio.render"]
    assert "shell" not in journal
