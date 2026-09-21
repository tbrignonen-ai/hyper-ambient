"""TAQUET PRODUIT — carte figée, EN 0.1, a11y, feedback, pythonw.

Sans réseau, sans secrets, sans GUI obligatoire.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]


def test_carte_figee_charge_granite_whisper_magpie_sofia():
    from test_hostagent_env_local import serve_hostagent

    env = {
        "BRAIN_SERVICE": "router",
        "EARS_BACKEND": "qwen3",
        "MOUTH_BACKEND": "supertonic",
        "MOUTH_VOICE_NAME": "estelle",
    }
    injectees = serve_hostagent.charger_carte_figee(
        chemin=RACINE / "dev" / "scripts" / "carte_figee.env",
        environ=env,
    )
    assert "BRAIN_SERVICE" in injectees
    assert env["BRAIN_SERVICE"] == "router"
    assert env["BRAIN_MODEL"] == "MiniMaxAI/MiniMax-M3"
    assert env["BRAIN_MODEL_LOCAL"] == "mother-local"
    assert env["MODEL"].endswith("granite-4.2-3b-Q4_K_M.gguf")
    assert env["EARS_BACKEND"] == "faster-whisper"
    assert env["EARS_MODEL"] == "large-v3"
    assert env["MOUTH_BACKEND"] == "magpie"
    assert env["MOUTH_VOICE_NAME"] == "Sofia"
    assert env["MOUTH_DEVICE"] == "cuda"


def test_assurer_stdio_pythonw_ecrit_dans_un_journal(tmp_path: Path):
    """pythonw : stdout/stderr None + fd C fermés → print avant ws.send mourait.

    Preuve C13 : rattacher les flux (y compris fd 1/2) avant l'audio.
    """
    journal = tmp_path / "presence.log"
    script = tmp_path / "probe_stdio.py"
    script.write_text(
        "\n".join(
            [
                "import sys",
                f"sys.path.insert(0, r'{RACINE}')",
                "from pathlib import Path",
                "from native.presence.app import assurer_stdio",
                "sys.stdout = None",
                "sys.stderr = None",
                f"assurer_stdio(Path(r'{journal}'))",
                "print('ping-c13', flush=True)",
                "import os",
                "os.write(1, b'fd1-c13\\n')",
            ]
        ),
        encoding="utf-8",
    )
    termine = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(RACINE),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert termine.returncode == 0, termine.stderr
    texte = journal.read_text(encoding="utf-8")
    assert "ping-c13" in texte
    assert "fd1-c13" in texte


def test_presence_accepte_un_journal_d_instance(tmp_path: Path):
    """Le profil portable peut séparer sa trace de celle de l'instance courante."""
    pytest.importorskip("tkinter")
    from native.presence.app import analyser_arguments

    journal = tmp_path / "presence-test.log"
    args = analyser_arguments(["--journal", str(journal)])
    assert args.journal == journal


def test_i18n_trou_canal_pret_et_ecoute_en(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "en")
    from src.i18n import t, ui

    textes = ui()
    assert "ready" in textes["channel_ready"].lower()
    assert "{raccourci}" in textes["channel_ready"]
    assert "Talk" in textes["channel_ready"] or "hold" in textes["channel_ready"].lower()
    assert "listening" in textes["listening"].lower()
    assert "feedback" in textes["feedback"].lower() or "issue" in textes["feedback"].lower()
    assert "hands" in textes["hands_free"].lower() or "JeV" in textes["hands_free"]
    pret = t("ui.channel_ready", raccourci="Space")
    assert "Space" in pret
    assert "Parler" not in pret


def test_i18n_fr_defaut_canal_pret_inchange(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    from src.i18n import t

    assert "Canal prêt" in t("ui.channel_ready", raccourci="Espace")
    assert "Espace" in t("ui.channel_ready", raccourci="Espace")
    assert "Écoute" in t("ui.listening")


def test_url_feedback_ouvre_issues_github():
    from native.presence.onboarding import URL_FEEDBACK, ouvrir_feedback, url_nouvelle_issue

    assert URL_FEEDBACK.startswith("https://github.com/tbrignonen-ai/hyper-ambient/issues")
    assert "issues" in url_nouvelle_issue()
    ouvert = {"url": None}

    def _ouvrir(cible: str) -> bool:
        ouvert["url"] = cible
        return True

    assert ouvrir_feedback(ouvrir=_ouvrir) is True
    assert ouvert["url"] == URL_FEEDBACK


def test_a11y_contraste_persiste_dans_presence_json(tmp_path: Path):
    from native.presence.onboarding import (
        ConfigurationPresence,
        charger_configuration,
        enregistrer_configuration,
    )

    attendue = ConfigurationPresence(
        onboarding_termine=True,
        raccourci_ptt="ctrl-space",
        langue="en",
        contraste=True,
    )
    chemin = tmp_path / "presence.json"
    enregistrer_configuration(attendue, chemin)
    lue = charger_configuration(chemin)
    assert lue.contraste is True
    assert lue.langue == "en"
    assert lue.raccourci_ptt == "ctrl-space"
    assert lue.mains_libres is False


def test_palettes_a11y_respectent_wcag_non_textuel():
    from native.presence.overlay import FOND_CHAMP, palettes
    from native.presence.onboarding import couleurs_eclair
    from native.presence.reglages_ui import (
        FOND_VITRE,
        PASTILLE_KO,
        PASTILLE_MUET,
        PASTILLE_OK,
    )
    from native.presence.sante import contraste_relatif

    for etat, palette in palettes(True).items():
        for cle in ("coeur", "lueur", "anneau"):
            ratio = contraste_relatif(palette[cle], FOND_CHAMP)
            assert ratio >= 3.0, f"{etat}.{cle}={palette[cle]} ratio={ratio:.2f}"
    fill_off, contour_off = couleurs_eclair(False, a11y=True)
    assert contraste_relatif(fill_off, "#102028") >= 3.0
    assert contraste_relatif(contour_off, "#102028") >= 3.0
    for nom, couleur in (
        ("ok", PASTILLE_OK),
        ("muet", PASTILLE_MUET),
        ("ko", PASTILLE_KO),
    ):
        ratio = contraste_relatif(couleur, FOND_VITRE)
        assert ratio >= 3.0, f"pastille {nom}={couleur} ratio={ratio:.2f}"
    assert len({PASTILLE_OK, PASTILLE_MUET, PASTILLE_KO}) == 3
