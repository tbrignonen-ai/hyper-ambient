"""Transport WebSocket qui expose LocalChannel sur le réseau local.

Le cœur vit dans un conteneur, le host-agent sur l'hôte : c'est
l'architecture à deux composants d'ADR-006. Sous Windows, le conteneur
n'a pas accès au micro ; les primitives d'hôte doivent donc traverser
le réseau local. Le port 8001 est déjà mappé, rien ne l'écoutait.

ADR-004 refuse le WebSocket pour l'audio : les événements passent par
un canal textuel inspectable, l'audio par mémoire partagée. La même ADR
prévoit toutefois un mode dégradé tout-WebSocket quand la mémoire
partagée est indisponible — le cas d'une VM Docker. Ce module est ce
mode, pas un contournement.

Deux sortes de refus, et elles ne se valent pas. Un refus d'admission
(mauvais secret, adresse non locale, message avant la poignée de main,
primitive hors contrat) ferme la connexion : c'est une tentative, pas
une erreur. Un refus de donnée (trame de mauvaise taille ou de mauvais
dtype) répond une erreur nommée et garde la session ouverte : une trame
abîmée ne doit pas couper le micro en pleine conversation. Cette
distinction est le cœur du module.
"""
from __future__ import annotations

import numpy as np
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from src.hostagent.audio import AudioFrame, InvalidFrameSizeError, InvalidSampleDtypeError
from src.hostagent.channel import ChannelRefused, LocalChannel
from src.hostagent.contract import is_permitted


def _peer_address_from_socket(websocket: WebSocket) -> str:
    """Adresse réelle du pair, lue sur le socket."""
    return websocket.client.host


def _fermer_admission(websocket: WebSocket):
    """Ferme sans négocier : l'admission a échoué."""
    return websocket.close()


def _trame_depuis_json(raw: object) -> AudioFrame:
    """Décode une liste JSON de flottants ; AudioFrame valide taille et dtype."""
    return AudioFrame(samples=np.asarray(raw, dtype=np.float32))


def create_transport_app(
    secret: str,
    on_frames,
    journal=None,
    peer_address_of=None,
):
    """Application FastAPI exposant LocalChannel sur WS /hostagent.

    ``peer_address_of(websocket) -> str`` est injectée en test. Par
    défaut elle lit ``websocket.client.host``. Le contrôle de localité
    s'exécute toujours sur l'adresse fournie, jamais contourné.
    """
    app = FastAPI()
    canal = LocalChannel(secret, journal=journal)
    adresse_du_pair = (
        peer_address_of if peer_address_of is not None else _peer_address_from_socket
    )

    @app.websocket("/hostagent")
    async def hostagent(websocket: WebSocket) -> None:
        await websocket.accept()
        peer_address = adresse_du_pair(websocket)
        try:
            premier = await websocket.receive_json()
            if not isinstance(premier, dict) or premier.get("type") != "hello":
                await _fermer_admission(websocket)
                return
            try:
                canal.authenticate(peer_address, premier.get("secret"))
            except ChannelRefused:
                await _fermer_admission(websocket)
                return
            await websocket.send_json({"type": "ready"})

            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict) or message.get("type") != "invoke":
                    await _fermer_admission(websocket)
                    return
                primitive = message.get("primitive")
                if not isinstance(primitive, str) or not is_permitted(primitive):
                    await websocket.send_json(
                        {"type": "error", "primitive": primitive}
                    )
                    await _fermer_admission(websocket)
                    return
                try:
                    decoded = [
                        _trame_depuis_json(raw)
                        for raw in (message.get("frames") or [])
                    ]
                except (InvalidFrameSizeError, InvalidSampleDtypeError) as exc:
                    await websocket.send_json(
                        {"type": "error", "error": type(exc).__name__}
                    )
                    continue
                canal.handle(message)
                on_frames(decoded)
        except WebSocketDisconnect:
            return

    return app
