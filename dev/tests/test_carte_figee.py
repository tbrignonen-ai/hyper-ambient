"""P0-2 : la carte figee (Granite / Whisper large-v3 / Magpie Sofia) persiste.

Cause racine : les reglages live sont dans /tmp/relance_hostagent.sh.
Un reboot via relancer_routeur.sh ou .env.local (router / Qwen3 / Supertonic)
revient a Pocket/Estelle + MiniCPM. Le chargeur d'outils (C1) ignore
volontairement MOUTH_*/EARS_*/BRAIN_*/MODEL — la carte a son propre chargeur.
"""
from __future__ import annotations

from pathlib import Path

from test_hostagent_env_local import serve_hostagent

RACINE = Path(__file__).resolve().parents[2]
CARTE = RACINE / "dev" / "scripts" / "carte_figee.env"

ANCIENNE = {
    "BRAIN_SERVICE": "router",
    "BRAIN_MODEL": "MiniMaxAI/MiniMax-M3",
    "MODEL": "/workspace/models/gguf/MiniCPM5-2B-Q4_K_M.gguf",
    "EARS_BACKEND": "qwen3",
    "EARS_MODEL": "0.6B",
    "EARS_COMPUTE_TYPE": "q4",
    "MOUTH_BACKEND": "supertonic",
    "MOUTH_VOICE_NAME": "estelle",
    "MOUTH_DEVICE": "cpu",
}


def test_carte_figee_ecrase_l_ancienne_carte(tmp_path):
    env = dict(ANCIENNE)
    injectees = serve_hostagent.charger_carte_figee(chemin=CARTE, environ=env)

    assert "BRAIN_SERVICE" in injectees
    assert env["BRAIN_SERVICE"] == "llamacpp"
    assert env["BRAIN_MODEL"] == "mother-local"
    assert env["MODEL"].endswith("granite-4.2-3b-Q4_K_M.gguf")
    assert env["EARS_BACKEND"] == "faster-whisper"
    assert env["EARS_MODEL"] == "large-v3"
    assert env["EARS_LANGUAGE"] == "fr"
    assert env["EARS_DEVICE"] == "cuda"
    assert env["EARS_COMPUTE_TYPE"] == "int8_float16"
    assert env["EARS_HOTWORDS"] == "MOTHER Codex Camunda Claude"
    assert env["MOUTH_BACKEND"] == "magpie"
    assert env["MOUTH_VOICE_NAME"] == "Sofia"
    assert env["MOUTH_DEVICE"] == "cuda"
    assert env["MOUTH_LANGUAGE"] == "fr"


def test_carte_figee_n_injecte_aucun_secret(tmp_path):
    chemin = tmp_path / "carte.env"
    chemin.write_bytes(
        b"BRAIN_SERVICE=llamacpp\n"
        b"HF_TOKEN=ne-pas-injecter\n"
        b"CODEX_BRIDGE_TOKEN=jeton-secret\n"
        b"BRAIN_API_KEY=cle-secrete\n"
        b"MOUTH_BACKEND=magpie\n"
    )
    env: dict[str, str] = {}
    serve_hostagent.charger_carte_figee(chemin=chemin, environ=env)
    assert env["BRAIN_SERVICE"] == "llamacpp"
    assert env["MOUTH_BACKEND"] == "magpie"
    assert "HF_TOKEN" not in env
    assert "CODEX_BRIDGE_TOKEN" not in env
    assert "BRAIN_API_KEY" not in env


def test_carte_figee_off_ne_touche_rien():
    env = dict(ANCIENNE)
    env["CARTE_FIGEE"] = "0"
    injectees = serve_hostagent.charger_carte_figee(chemin=CARTE, environ=env)
    assert injectees == []
    assert env["BRAIN_SERVICE"] == "router"
    assert env["MOUTH_BACKEND"] == "supertonic"


def test_carte_figee_respecte_force():
    env = dict(ANCIENNE)
    env["MOUTH_DEVICE_FORCE"] = "cpu"
    serve_hostagent.charger_carte_figee(chemin=CARTE, environ=env)
    assert env["MOUTH_DEVICE"] == "cpu"
    assert env["MOUTH_BACKEND"] == "magpie"


def test_charger_env_local_laisse_la_carte_au_chargeur_carte(tmp_path):
    """C1 inchangé : .env.local ne deplace pas les cles modele."""
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(
        b"BRAIN_SERVICE=llamacpp\n"
        b"CODEX_BRIDGE_TOKEN=jeton-ok\n"
        b"MOUTH_BACKEND=magpie\n"
    )
    env: dict[str, str] = {}
    serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert env == {"CODEX_BRIDGE_TOKEN": "jeton-ok"}
    serve_hostagent.charger_carte_figee(chemin=CARTE, environ=env)
    assert env["BRAIN_SERVICE"] == "llamacpp"
    assert env["MOUTH_BACKEND"] == "magpie"
    assert env["CODEX_BRIDGE_TOKEN"] == "jeton-ok"
