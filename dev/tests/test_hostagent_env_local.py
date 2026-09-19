"""Propagation de `.env.local` vers le process host-agent.

Cause racine du boot 19 sept : `serve_hostagent.py` ne lit que `os.getenv`.
Le process a ete lance sans `relancer_routeur.sh`, et `docker start` ne
recharge pas `env_file`. Les jetons existent dans le fichier monte, absents
de l'environnement. `.env.local` mixte CRLF/LF (CLI_BRIDGE_TOKEN en CRLF) :
un chargeur naif colle un `\\r` au jeton.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

RACINE = Path(__file__).resolve().parents[2]


def _charger_serve_hostagent():
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        for nom in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
            sys.modules.setdefault(nom, MagicMock(name=nom))
    chemin = RACINE / "dev" / "scripts" / "serve_hostagent.py"
    spec = importlib.util.spec_from_file_location("serve_hostagent_env_local", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_hostagent = _charger_serve_hostagent()

CLES_OUTILS = (
    "CODEX_BRIDGE_TOKEN",
    "CLI_BRIDGE_TOKEN",
    "SEARXNG_URL",
    "TAVILY_API_KEY",
    "BRAVE_API_KEY",
    "EXA_API_KEY",
    "JINA_API_KEY",
    "SERPER_API_KEY",
    "CODEX_BRIDGE_URL",
    "CLI_BRIDGE_URL",
    "MUSE_BRIDGE_URL",
    "TYPESAFE_API_KEY",
)


def _fichier_env(tmp_path: Path, lignes: list[bytes]) -> Path:
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(b"".join(lignes))
    return chemin


def test_env_local_crlf_injecte_le_jeton_sans_retour_chariot(tmp_path, monkeypatch):
    """Repro : ligne Windows `KEY=value\\r\\n` → getenv doit rendre value, pas value\\r."""
    for cle in CLES_OUTILS:
        monkeypatch.delenv(cle, raising=False)
    chemin = _fichier_env(
        tmp_path,
        [
            b"CODEX_BRIDGE_TOKEN=jeton-codex-64\n",
            b"CLI_BRIDGE_TOKEN=jeton-claude-40\r\n",
            b"SEARXNG_URL=http://host.docker.internal:8080\n",
        ],
    )
    env: dict[str, str] = {}
    injectees = serve_hostagent.charger_env_local(chemin=chemin, environ=env)

    assert "CLI_BRIDGE_TOKEN" in injectees
    assert env["CLI_BRIDGE_TOKEN"] == "jeton-claude-40"
    assert "\r" not in env["CLI_BRIDGE_TOKEN"]
    assert env["CODEX_BRIDGE_TOKEN"] == "jeton-codex-64"
    assert env["SEARXNG_URL"] == "http://host.docker.internal:8080"


def test_env_local_remplit_une_variable_vide_mais_deja_posee(tmp_path):
    """Docker env_file peut poser une cle vide : ce n'est pas une valeur utile."""
    chemin = _fichier_env(tmp_path, [b"CODEX_BRIDGE_TOKEN=jeton-reel\n"])
    env = {"CODEX_BRIDGE_TOKEN": ""}
    serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert env["CODEX_BRIDGE_TOKEN"] == "jeton-reel"


def test_env_local_n_ecrase_pas_un_jeton_deja_present(tmp_path):
    chemin = _fichier_env(tmp_path, [b"CODEX_BRIDGE_TOKEN=depuis-fichier\n"])
    env = {"CODEX_BRIDGE_TOKEN": "depuis-process"}
    serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert env["CODEX_BRIDGE_TOKEN"] == "depuis-process"


def test_env_local_n_injecte_que_les_cles_outils(tmp_path):
    """Correctif minimal : jetons/URL d'outils, pas tout le dotenv."""
    chemin = _fichier_env(
        tmp_path,
        [
            b"ALIAS=mother-local\n",
            b"HF_TOKEN=ne-pas-injecter\n",
            b"CODEX_BRIDGE_TOKEN=jeton-ok\n",
        ],
    )
    env: dict[str, str] = {}
    serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert env == {"CODEX_BRIDGE_TOKEN": "jeton-ok"}


def test_env_local_n_ecrit_jamais_les_cles_modele(tmp_path):
    """Arbitrage Claude 19 sept : MOUTH_*/EARS_*/BRAIN_*/MODEL restent a la carte."""
    chemin = _fichier_env(
        tmp_path,
        [
            b"MOUTH_BACKEND=piper\n",
            b"EARS_MODEL=large-v3-turbo\n",
            b"BRAIN_MODEL=quelque-chose\n",
            b"MODEL=/workspace/models/gguf/interdit.gguf\n",
            b"CODEX_BRIDGE_TOKEN=jeton-ok\n",
        ],
    )
    env: dict[str, str] = {}
    serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert "MOUTH_BACKEND" not in env
    assert "EARS_MODEL" not in env
    assert "BRAIN_MODEL" not in env
    assert "MODEL" not in env
    assert env["CODEX_BRIDGE_TOKEN"] == "jeton-ok"


def test_registre_voit_les_outils_apres_chargement_env_local(tmp_path, monkeypatch):
    """Sans charger le fichier, construire_registre reste vide — c'est le bug live."""
    for cle in CLES_OUTILS:
        monkeypatch.delenv(cle, raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    chemin = _fichier_env(
        tmp_path,
        [
            b"CODEX_BRIDGE_TOKEN=jeton-codex\n",
            b"CLI_BRIDGE_TOKEN=jeton-claude\r\n",
            b"SEARXNG_URL=http://host.docker.internal:8080\n",
        ],
    )
    assert len(serve_hostagent.construire_registre(client=object())) == 1

    env: dict[str, str] = {}
    serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    for cle, val in env.items():
        monkeypatch.setenv(cle, val)
    registre = serve_hostagent.construire_registre(client=object())
    assert serve_hostagent.verifier_registre(registre) == {
        "ask_claude",
        "ask_codex",
        "web_search",
        "calculer",
    }


def test_registre_expose_le_web_avec_un_repli_avec_cle(monkeypatch):
    for cle in CLES_OUTILS:
        monkeypatch.delenv(cle, raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "cle-de-test")

    registre = serve_hostagent.construire_registre(client=object())
    assert serve_hostagent.verifier_registre(registre) == {"web_search", "calculer"}
