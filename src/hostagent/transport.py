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

import inspect

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


def _json_trames_sortantes(trames) -> dict:
    """Même encodage qu'à l'aller : listes de flottants, une par trame."""
    return {
        "type": "invoke",
        "primitive": "audio.render",
        "frames": [trame.samples.tolist() for trame in trames],
    }


def create_transport_app(
    secret: str,
    on_frames,
    journal=None,
    peer_address_of=None,
    on_report=None,
    on_options=None,
):
    """Application FastAPI exposant LocalChannel sur WS /hostagent.

    ``peer_address_of(websocket) -> str`` est injectée en test. Par
    défaut elle lit ``websocket.client.host``. Le contrôle de localité
    s'exécute toujours sur l'adresse fournie, jamais contourné.

    ``on_frames`` peut renvoyer une liste de ``AudioFrame`` : le
    transport les émet alors. ``None``, le retour actuel, ne produit
    pas d'audio sortant par ce chemin.

    ``on_report(frames) -> dict`` est optionnel. On l'appelle après
    qu'au moins une trame a quitté le serveur, jamais avant : le
    rapport ne doit pas retarder la première voix (NFR-01). Absent,
    ou ``on_frames`` qui ne rend rien : pas de message ``report``.

    ``on_options(message)`` reçoit le hello (flag optionnel) puis les
    messages ``{"type":"options",...}`` sans fermer la session.
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
            if on_options is not None:
                on_options(premier)

            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    await _fermer_admission(websocket)
                    return
                kind = message.get("type")
                if kind == "options":
                    if on_options is not None:
                        on_options(message)
                    continue
                if kind != "invoke":
                    await _fermer_admission(websocket)
                    return
                if "mains_libres" in message and on_options is not None:
                    on_options(
                        {
                            "type": "options",
                            "mains_libres": message.get("mains_libres") is True,
                        }
                    )
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
                trames_sortantes = on_frames(decoded)
                # `on_frames` peut rendre une coroutine. On l'attend ICI, dans
                # la tâche du point d'entrée ASGI, au lieu de la laisser courir
                # ailleurs : depuis starlette 1.6 / uvicorn 0.52, uvicorn ferme
                # le transport dès que l'application ASGI rend la main. Un envoi
                # depuis une tâche extérieure arrive alors sur un socket déjà
                # fermé — `ClientDisconnected` — et la voix se perd en silence.
                # Mesuré le 13 septembre : zéro trame reçue de bout en bout, sur
                # la version commitée comme sur celle du jour.
                if inspect.isawaitable(trames_sortantes):
                    trames_sortantes = await trames_sortantes
                audio_emis = False
                if trames_sortantes:
                    await websocket.send_json(
                        _json_trames_sortantes(trames_sortantes)
                    )
                    audio_emis = True
                # Le rapport part après la première trame, jamais avant :
                # journaliser ne doit pas faire attendre la voix.
                if on_report is not None and audio_emis:
                    rapport = on_report(decoded)
                    if rapport:
                        await websocket.send_json(
                            {**rapport, "type": "report"}
                        )
        except WebSocketDisconnect:
            return

    return app
