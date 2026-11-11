"""
hyper-ambient API — FastAPI server for HTTP and WebSocket.

GET /status annonce la carte. Les autres routes ne sont pas la boucle
vivante : elles répondent 501 et indiquent le host-agent sur le port 8001.
"""
import os
import logging
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="hyper-ambient",
    description="Local ambient voice — French, English, Spanish — answers out loud",
    version="0.1.0"
)

# Pas une session. Le client qui se trompe de port doit le voir.
_HORS_SERVICE = {
    "live": False,
    "detail": "Le tour vivant est le host-agent, ws://127.0.0.1:8001/hostagent.",
}


@app.get("/status")
async def status():
    """Carte configurée. Le tour vivant est le host-agent, port 8001."""
    from src.core.statut import statut_public

    etat = statut_public()
    etat["version"] = "0.1.0"
    return etat


@app.post("/capabilities")
async def negotiate_capabilities(request: dict):
    """
    Negotiate which capability levels are available for this context.

    Request:
        {
            "profile": "PROFILE_MEDIUM",
            "languages": ["fr"],
            "require": ["EARS-L2", "TURN-L2", "MOUTH-L2"],
            "prefer": ["BRAIN", "ACOUSTIC-L1"]
        }

    Response:
        {
            "available": ["EARS-L1", "TURN-L1", "MOUTH-L1"],
            "unavailable": ["BRAIN", "ACOUSTIC-L1"],
            "fallbacks": {"TURN-L2": "TURN-L1 (VAD)"}
        }
    """
    logger.info(f"Capability negotiation: {request}")
    return JSONResponse(status_code=501, content=_HORS_SERVICE)


@app.post("/converse")
async def start_conversation(request: dict):
    """
    Start a new conversation session.

    Request:
        {
            "profile": "PROFILE_MEDIUM",
            "capabilities": ["EARS-L1", "TURN-L1", "MOUTH-L1", "BRAIN"],
            "brain_service": "anthropic"
        }

    Response:
        {
            "session_id": "sess_...",
            "ws_url": "ws://localhost:8001/ws/sess_..."
        }
    """
    logger.info(f"Starting conversation: {request}")
    return JSONResponse(status_code=501, content=_HORS_SERVICE)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket stream for audio frames and real-time events.

    Messages (client → server):
        {"type": "audio", "data": <base64 audio chunk>}
        {"type": "text", "data": "user input"}
        {"type": "control", "command": "pause|resume|stop"}

    Messages (server → client):
        {"type": "transcript", "partial": "...", "confidence": 0.8}
        {"type": "turn_candidate", "confidence": 0.7}
        {"type": "synthesis", "data": <base64 audio chunk>}
        {"type": "brain_response", "text": "..."}
        {"type": "acoustic_event", "event": "laughter"}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info(f"WebSocket refused: {session_id}")
    await websocket.send_json({"type": "error", **_HORS_SERVICE})
    await websocket.close()


@app.get("/audit")
async def get_audit_log(limit: int = 100):
    """
    Retrieve audit log entries (GATE-controlled).

    Only accessible if GATE mode allows.
    """
    return JSONResponse(status_code=501, content=_HORS_SERVICE)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
