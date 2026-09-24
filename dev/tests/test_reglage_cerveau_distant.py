"""Réglage du cerveau distant par l'utilisateur (24/09).

« Il faut pouvoir le configurer à un moment pour l'utilisateur, le modèle. »
Le mode (clé d'API, abonnement Claude, abonnement ChatGPT) et le modèle se
choisissent dans les Réglages ; la liste des modèles vient du pont, en direct.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "native" / "presence"))

import cerveau_distant as cd  # noqa: E402


def test_trois_modes_et_leurs_defauts():
    assert [m for m, _ in cd.MODES] == ["api", "abonnement-claude", "abonnement-chatgpt"]
    assert cd.MODELE_PAR_DEFAUT["abonnement-claude"] == "claude-sonnet-5"
    assert cd.MODELE_PAR_DEFAUT["abonnement-chatgpt"] == "gpt-6-luna"
    assert cd.EFFORT_PAR_DEFAUT == "low"


def test_url_du_pont_vue_depuis_l_hote():
    valeurs = {"CLI_BRIDGE_URL": "http://host.docker.internal:8766/ask",
               "CODEX_BRIDGE_URL": "http://host.docker.internal:8765/ask"}
    assert cd.url_models("abonnement-claude", valeurs) == "http://127.0.0.1:8766/models"
    assert cd.url_models("abonnement-chatgpt", valeurs) == "http://127.0.0.1:8765/models"
    assert cd.url_models("api", valeurs) is None


def test_lister_modeles_en_direct_avec_repli():
    appels = []

    def lire(url, jeton):
        appels.append((url, jeton))
        return {"models": [{"id": "gpt-6-luna", "label": "GPT-6-Luna"},
                           {"id": "gpt-6-sol", "label": "GPT-6-Sol"}]}

    valeurs = {"CODEX_BRIDGE_URL": "http://host.docker.internal:8765/ask",
               "CODEX_BRIDGE_TOKEN": "j"}
    modeles = cd.lister_modeles("abonnement-chatgpt", valeurs, lire=lire)
    assert [m["id"] for m in modeles] == ["gpt-6-luna", "gpt-6-sol"]
    assert appels == [("http://127.0.0.1:8765/models", "j")]

    def panne(url, jeton):
        raise OSError("pont éteint")

    repli = cd.lister_modeles("abonnement-claude", {"CLI_BRIDGE_URL": "x"}, lire=panne)
    assert [m["id"] for m in repli] == ["claude-sonnet-5"]


def test_enregistrer_le_choix(tmp_path):
    env_local = tmp_path / ".env.local"
    env_local.write_text("CLI_BRIDGE_TOKEN=secret\n", encoding="utf-8")
    cd.enregistrer_choix(env_local, "abonnement-chatgpt", "gpt-6-luna", "low")
    texte = env_local.read_text(encoding="utf-8")
    assert "BRAIN_DEEP=abonnement-chatgpt" in texte
    assert "BRAIN_ABONNEMENT_MODEL=gpt-6-luna" in texte
    assert "BRAIN_ABONNEMENT_EFFORT=low" in texte
    assert "CLI_BRIDGE_TOKEN=secret" in texte
    assert cd.choix_courant(env_local) == ("abonnement-chatgpt", "gpt-6-luna", "low")
