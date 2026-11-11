"""Le port 8000 annonce la carte, pas une boucle qui tourne."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.core.api import app
from src.core.statut import CARTE, parser_env, statut_public


def test_la_carte_figee_est_annoncee_comme_non_vivante():
    etat = statut_public(parser_env(CARTE.read_text(encoding="utf-8")))
    assert etat["live"] is False
    assert etat["role"] == "placeholder"
    assert "8001" in etat["live_loop"]
    assert etat["card"]["ears"] == "large-v3"
    assert etat["card"]["mouth_voice"] == "Sofia"
    assert etat["card"]["brain_local"] == "granite-4.2-3b-Q4_K_M.gguf"
    assert etat["card"]["brain_model"] == "MiniMaxAI/MiniMax-M3"


def test_une_carte_absente_reste_un_etat_vide(tmp_path: Path):
    etat = statut_public({})
    assert etat["status"] == "ok"
    assert etat["card"]["ears"] == ""


def test_le_point_status_sert_cette_carte():
    client = TestClient(app)
    reponse = client.get("/status")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["live"] is False
    assert corps["card"]["mouth_backend"] == "magpie"
