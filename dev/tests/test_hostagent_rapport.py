"""
Tests du message « report » sur le transport WebSocket host-agent.

La boucle vocale tient le budget NFR-01 (mic_to_audible), mais le serveur
ne renvoyait que de l'audio : la recette affichait « texte transcrit :
non fourni par le serveur ». Sans transcription ni réponse, on entend
sans voir ce qui a été compris, et on ne peut pas dire si une mauvaise
réponse vient des oreilles ou du raisonnement. mic_to_audible est un
chiffre unique, donc inexploitable pour optimiser les trois étages
(EARS / BRAIN / MOUTH) une fois le canal WebSocket compris.

Le protocole gagne UN message d'information, émis sur la session déjà
ouverte, de la forme :

    {"type": "report",
     "transcript": "<texte reconnu>",
     "reply": "<réponse du modèle>",
     "timings_ms": {"ears": float, "brain": float, "mouth": float, "total": float}}

Contrainte d'ordre — c'est le cœur de ce fichier. Ce message ne doit
jamais retarder la première trame audio. Il part APRÈS qu'au moins une
trame a quitté le serveur. Payer du confort de journalisation sur la
latence perçue serait un contresens : c'est mic_to_audible qui tient
NFR-01, pas la richesse du rapport.

Choix d'API. ``create_transport_app`` gagne un paramètre optionnel
``on_report``. On écarte le couple ``(trames, rapport)`` renvoyé par
``on_frames`` : un retour unique force à attendre le rapport (réponse
complète, timings mouth) avant d'émettre la première trame, alors que
cette trame part au premier chunk MOUTH. ``on_report`` se déclenche
après l'émission de cette trame. Les appels existants
(``test_hostagent_transport``, ``serve_hostagent``) ne passent pas
``on_report`` : ils restent valides, les tests actuels de transport
n'ont pas à être touchés.

``on_frames`` peut renvoyer la liste des trames de réponse (objets
``AudioFrame``) ; ``None``, le retour actuel, ne produit pas d'audio
sortant par le transport. Ce n'est pas un changement de signature.
"""
from __future__ import annotations

import threading

import pytest


SECRET = "partage-installation"
VOIE = "/hostagent"

TRANSCRIPT = "bonjour"
REPLY = "bonjour, je vous écoute"
TIMINGS_MS = {
    "ears": 80.0,
    "brain": 120.0,
    "mouth": 90.0,
    "total": 310.0,
}


def _adresse_de_test(websocket) -> str:
    """Fabrique de test : loopback. Le contrôle is_loopback s'applique encore."""
    return "127.0.0.1"


def _trame(valeur=0.0, taille=None):
    from src.hostagent.audio import FRAME_SAMPLES

    n = FRAME_SAMPLES if taille is None else taille
    return [float(valeur)] * n


def _trame_reponse(valeur=0.5):
    """Trame que ``on_frames`` rend au transport pour l'émission sortante."""
    import numpy as np

    from src.hostagent.audio import FRAME_SAMPLES, AudioFrame

    return AudioFrame(
        samples=np.full(FRAME_SAMPLES, float(valeur), dtype=np.float32)
    )


def _rapport():
    return {
        "transcript": TRANSCRIPT,
        "reply": REPLY,
        "timings_ms": dict(TIMINGS_MS),
    }


def _create_app(*, on_frames, on_report=None):
    """Fabrique qui passe ``on_report`` : c'est l'API ajoutée, optionnelle."""
    from src.hostagent.transport import create_transport_app

    return create_transport_app(
        secret=SECRET,
        on_frames=on_frames,
        peer_address_of=_adresse_de_test,
        on_report=on_report,
    )


def _on_frames_qui_repond(frames):
    return [_trame_reponse()]


def _on_report(frames):
    return _rapport()


def _session_prete(ws) -> None:
    ws.send_json({"type": "hello", "secret": SECRET})
    assert ws.receive_json() == {"type": "ready"}


def _invoquer_capture(ws) -> None:
    ws.send_json(
        {
            "type": "invoke",
            "primitive": "audio.capture",
            "frames": [_trame(0.0)],
        }
    )


def _est_audio(message: dict) -> bool:
    """Une trame audio utile : des échantillons, et ce n'est pas le rapport."""
    if not isinstance(message, dict) or message.get("type") == "report":
        return False
    frames = message.get("frames")
    return isinstance(frames, list) and len(frames) > 0


def _recevoir_json(ws, *, timeout_s: float = 1.5) -> dict:
    """receive_json borné : sans émission du serveur, TestClient se bloque."""
    resultat = {}

    def _cible() -> None:
        try:
            resultat["message"] = ws.receive_json()
        except Exception as exc:
            resultat["erreur"] = exc

    fil = threading.Thread(target=_cible, daemon=True)
    fil.start()
    fil.join(timeout=timeout_s)
    if fil.is_alive():
        pytest.fail(
            "le serveur n'a envoyé aucun message "
            f"en {timeout_s} s — la première trame audio, puis le rapport, "
            "doivent partir avant que le transport n'attende le client"
        )
    if "erreur" in resultat:
        raise resultat["erreur"]
    return resultat["message"]


def _lire_jusqua_rapport(ws, *, max_messages: int = 8) -> list:
    """Lit jusqu'au message report. L'audio doit apparaître avant."""
    recus = []
    for _ in range(max_messages):
        recu = _recevoir_json(ws)
        recus.append(recu)
        if recu.get("type") == "report":
            return recus
    pytest.fail("aucun message de type report reçu")


def test_le_rapport_arrive_apres_la_premiere_trame_audio():
    """Au moins une trame audio quitte le serveur avant le message report."""
    from fastapi.testclient import TestClient

    app = _create_app(
        on_frames=_on_frames_qui_repond,
        on_report=_on_report,
    )
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            _session_prete(ws)
            _invoquer_capture(ws)
            recus = _lire_jusqua_rapport(ws)

    types_vus = []
    for message in recus:
        if _est_audio(message):
            types_vus.append("audio")
        elif message.get("type") == "report":
            types_vus.append("report")

    assert "audio" in types_vus, (
        "aucune trame audio avant le rapport : le rapport ne doit pas "
        "partir en premier, ni tout seul"
    )
    assert "report" in types_vus
    assert types_vus.index("audio") < types_vus.index("report")


def test_le_rapport_porte_la_transcription_et_la_reponse():
    """Le message report expose ce qui a été compris et ce qui a été dit."""
    from fastapi.testclient import TestClient

    app = _create_app(
        on_frames=_on_frames_qui_repond,
        on_report=_on_report,
    )
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            _session_prete(ws)
            _invoquer_capture(ws)
            recus = _lire_jusqua_rapport(ws)

    rapport = next(m for m in recus if m.get("type") == "report")
    assert rapport["transcript"] == TRANSCRIPT
    assert rapport["reply"] == REPLY


def test_le_rapport_porte_les_trois_etages_et_un_total():
    """ears, brain, mouth et total sont présents, numériques et positifs."""
    from fastapi.testclient import TestClient

    app = _create_app(
        on_frames=_on_frames_qui_repond,
        on_report=_on_report,
    )
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            _session_prete(ws)
            _invoquer_capture(ws)
            recus = _lire_jusqua_rapport(ws)

    rapport = next(m for m in recus if m.get("type") == "report")
    timings = rapport["timings_ms"]
    for etage in ("ears", "brain", "mouth", "total"):
        assert etage in timings, f"timings_ms manque {etage}"
        valeur = timings[etage]
        assert isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
        assert valeur > 0


def test_le_total_est_coherent_avec_la_somme_des_etages():
    """total >= ears + brain + mouth : le transport ajoute du temps, il n'en retire pas."""
    from fastapi.testclient import TestClient

    app = _create_app(
        on_frames=_on_frames_qui_repond,
        on_report=_on_report,
    )
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            _session_prete(ws)
            _invoquer_capture(ws)
            recus = _lire_jusqua_rapport(ws)

    timings = next(m for m in recus if m.get("type") == "report")["timings_ms"]
    somme = float(timings["ears"]) + float(timings["brain"]) + float(timings["mouth"])
    # Horloge flottante : 1 ms de marge. Un total franchement sous la
    # somme signalerait deux horloges qui ne racontent pas la même histoire.
    assert float(timings["total"]) + 1.0 >= somme


def test_une_session_sans_rapport_reste_valide():
    """Sans on_report, l'audio part encore : le rapport n'est pas une obligation."""
    from fastapi.testclient import TestClient

    from src.hostagent.transport import create_transport_app

    def on_frames(frames):
        return [_trame_reponse()]

    # Appel à la forme actuelle, sans on_report : c'est la rétrocompatibilité.
    app = create_transport_app(
        secret=SECRET,
        on_frames=on_frames,
        peer_address_of=_adresse_de_test,
    )
    with TestClient(app) as client:
        with client.websocket_connect(VOIE) as ws:
            _session_prete(ws)
            _invoquer_capture(ws)
            premier = _recevoir_json(ws)
            assert _est_audio(premier)
            assert premier.get("type") != "report"

            _invoquer_capture(ws)
            second = _recevoir_json(ws)
            assert _est_audio(second)
            assert second.get("type") != "report"
