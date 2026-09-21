"""C2 — health-check : un endpoint muet classe DEGRADED et nomme le composant.

Les sondes sont stdlib (urllib). Une réponse HTTP, même 4xx/5xx, veut dire
que le process écoute. Seul un refus de connexion / timeout est une panne.
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_WORKER = ROOT / "workers" / "night_health_vault_note"
# Le conteneur ne monte que src/, dev/ et native/ : les sondes y sont hors
# d'atteinte. On saute plutot que d'echouer a la collecte.
if not _WORKER.is_dir():
    pytest.skip("sondes absentes de ce montage", allow_module_level=True)
sys.path.insert(0, str(_WORKER))

from handlers import handle_health_check, handle_vault_note  # noqa: E402

PHRASE_ALERTE_CODEX = "Le pont vers Codex ne répond plus, je continue en local."
PHRASE_REPRISE_CODEX = "Pont Codex rétabli."


class _HandlerFixe(BaseHTTPRequestHandler):
    code = 200
    body = b'{"brokers":[{"nodeId":0}],"clusterSize":1,"partitionsCount":1,"gatewayVersion":"test"}'

    def do_GET(self) -> None:
        self.send_response(self.code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.code < 400:
            self.wfile.write(self.body)

    def log_message(self, *_args: object) -> None:
        return


def _serveur(code: int = 200, body: bytes | None = None) -> tuple[ThreadingHTTPServer, str]:
    handler = type("H", (_HandlerFixe,), {"code": code})
    if body is not None:
        handler.body = body
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    hote, port = serveur.server_address[:2]
    return serveur, f"http://{hote}:{port}"


def _fermer(serveur: ThreadingHTTPServer) -> None:
    serveur.shutdown()
    serveur.server_close()


def test_health_check_degraded_quand_le_pont_codex_ne_repond_pas():
    topo, topo_url = _serveur(200)
    try:
        mort = "http://127.0.0.1:1/"
        resultat = handle_health_check(
            {
                "topologyUrl": f"{topo_url}/v2/topology",
                "endpoints": [
                    {
                        "id": "pont_codex",
                        "nom": "pont Codex",
                        "url": mort,
                    }
                ],
            }
        )
    finally:
        _fermer(topo)

    assert resultat["healthStatus"] == "DEGRADED"
    assert "pont_codex" in str(resultat.get("degradedComponents", ""))
    assert resultat["alertMessage"] == PHRASE_ALERTE_CODEX
    assert resultat["recoveryMessage"] == PHRASE_REPRISE_CODEX
    composants = json.loads(resultat["componentsJson"])
    assert any(c["id"] == "pont_codex" and c["ok"] is False for c in composants)


def test_health_check_up_si_le_pont_repond_meme_en_501():
    topo, topo_url = _serveur(200)
    pont, pont_url = _serveur(501)
    try:
        resultat = handle_health_check(
            {
                "topologyUrl": f"{topo_url}/v2/topology",
                "endpoints": [
                    {
                        "id": "pont_codex",
                        "nom": "pont Codex",
                        "url": pont_url + "/",
                    }
                ],
            }
        )
    finally:
        _fermer(topo)
        _fermer(pont)

    assert resultat["healthStatus"] == "UP"
    assert resultat.get("alertMessage") in ("", None)
    assert "pont_codex" not in str(resultat.get("degradedComponents") or "")


def test_vault_note_nomme_le_composant_et_la_phrase(tmp_path: Path):
    sorties = handle_vault_note(
        {
            "nightDate": "2026-09-19",
            "vaultDir": str(tmp_path),
            "healthStatus": "DEGRADED",
            "httpStatus": 0,
            "alertMessage": PHRASE_ALERTE_CODEX,
            "degradedComponents": "pont_codex",
            "componentsJson": json.dumps(
                [{"id": "pont_codex", "nom": "pont Codex", "ok": False, "httpStatus": 0}]
            ),
            "checkedAt": "2026-09-19T12:00:00Z",
            "latencyMs": 12,
        }
    )
    note = Path(sorties["notePath"])
    assert note.name == "2026-09-19-HEALTH.md"
    texte = note.read_text(encoding="utf-8")
    assert "DEGRADED" in texte
    assert "pont Codex" in texte
    assert PHRASE_ALERTE_CODEX in texte
    assert sorties["noteWritten"] is True
