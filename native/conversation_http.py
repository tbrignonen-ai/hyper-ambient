"""Routes de conversation communes aux ponts Claude et Codex (mode abonnement).

    GET  /models       les modèles proposés par le harnais, pour les Réglages
    POST /prechauffer  {model, effort, system} : démarre la session d'avance
    POST /chat         {model, effort, messages} : une réplique, diffusée en
                       lignes JSON {"delta": ...} puis {"done": true}
    GET  /sessions?q=  la session du harnais qui répond le mieux (vide : la
                       dernière), pour « reprends la session qui parle de X »

Chaque pont fournit sa fabrique de sessions et sa liste de modèles ; le
contrat HTTP est le même, donc le cerveau `abonnement` parle aux deux.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger("conversation")

ROUTES = {("GET", "/models"), ("POST", "/chat"), ("POST", "/prechauffer")}


def _corps(handler) -> dict:
    longueur = int(handler.headers.get("Content-Length") or 0)
    return json.loads(handler.rfile.read(longueur) or b"{}")


def servir(
    handler,
    *,
    autorise: Callable[[Any], bool],
    sessions: Callable[[str, str], Any],
    modeles: Callable[[], list],
    defaut: str,
    effort_defaut: str = "low",
    catalogue: Optional[Callable[[str], Optional[dict]]] = None,
) -> bool:
    """Traite la requête si elle est une route de conversation ; sinon False."""
    adresse = urlsplit(handler.path)
    if catalogue is not None and (handler.command, adresse.path) == ("GET", "/sessions"):
        if not autorise(handler.headers.get("Authorization")):
            handler._send(401, {"ok": False, "error": "non autorise"})
            return True
        requete = (parse_qs(adresse.query).get("q") or [""])[0]
        try:
            session = catalogue(requete)
        except Exception as exc:
            logger.warning(f"sessions : {type(exc).__name__}: {exc}")
            session = None
        handler._send(200, {"ok": True, "session": session})
        return True
    if (handler.command, handler.path) not in ROUTES:
        return False
    if not autorise(handler.headers.get("Authorization")):
        handler._send(401, {"ok": False, "error": "non autorise"})
        return True
    if handler.path == "/models":
        handler._send(200, {"ok": True, "models": modeles(), "default": defaut})
        return True
    try:
        payload = _corps(handler)
        modele = (payload.get("model") or defaut).strip()
        effort = (payload.get("effort") or effort_defaut).strip()
    except Exception:
        handler._send(400, {"ok": False, "error": "requete illisible"})
        return True
    if handler.path == "/prechauffer":
        sessions(modele, effort).prechauffer(payload.get("system") or "")
        handler._send(200, {"ok": True})
        return True

    handler.send_response(200)
    handler.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
    handler.end_headers()

    def ecrire(objet: dict) -> None:
        handler.wfile.write((json.dumps(objet, ensure_ascii=False) + "\n").encode("utf-8"))
        handler.wfile.flush()

    try:
        for morceau in sessions(modele, effort).repondre(list(payload.get("messages") or [])):
            ecrire({"delta": morceau})
        ecrire({"done": True})
    except Exception as exc:
        logger.warning(f"chat : {type(exc).__name__}: {exc}")
        ecrire({"error": type(exc).__name__})
    return True
