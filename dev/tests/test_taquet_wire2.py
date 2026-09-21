"""TAQUET WIRE2 — branchements host-agent : JeV, hotwords, C11, C12, C4, C8.

Sans réseau, sans secrets, sans chargement GPU.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.brain.openai_compat import LlamaCppBrain
from src.ears.jev_reflexe import JevEvaluation, JevSignals
from test_hostagent_env_local import CLES_OUTILS, serve_hostagent

RACINE = Path(__file__).resolve().parents[2]
CARTE = RACINE / "dev" / "scripts" / "carte_figee.env"
RELANCE = RACINE / "dev" / "scripts" / "relance_hostagent.sh"


def _evaluation(*, addressed: bool, harness: str | None = None) -> JevEvaluation:
    return JevEvaluation(
        answers={},
        signals=JevSignals(
            addressed_to_mother=addressed,
            real_interruption=False,
            phrase_finished=True,
            transcription_uncertain=False,
            expected_response_length="few_sentences",
            tone="calm",
            frustration=None,
            needs_current_information=False,
            refers_to_context=False,
            requests_memory=False,
            sensitive_local_action=False,
            contains_personal_data=False,
            named_harness=harness,
        ),
    )


def test_ha_lang_injecte_depuis_env_local_sans_secret(tmp_path, monkeypatch):
    """C8 EN 0.1 : le host-agent doit lire HA_LANG dans .env.local (pas seulement Presence)."""
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(
        b"HA_LANG=en\r\nHYPER_AMBIENT_LANG=en\nHF_TOKEN=ne-pas-injecter\n"
    )
    env: dict[str, str] = {}
    injectees = serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert "HA_LANG" in injectees
    assert env["HA_LANG"] == "en"
    assert "\r" not in env["HA_LANG"]
    assert env["HYPER_AMBIENT_LANG"] == "en"
    assert "HF_TOKEN" not in env


def test_boot_sans_ha_lang_retombe_sur_le_francais(monkeypatch):
    """Régression C8 : le relanceur exporte HA_LANG vide si la clé est absente."""
    env: dict[str, str] = {}
    monkeypatch.setattr(serve_hostagent, "charger_env_local", lambda **_kwargs: [])
    monkeypatch.setattr(serve_hostagent, "charger_carte_figee", lambda **_kwargs: [])

    serve_hostagent._appliquer_env_boot(environ=env)

    assert env["HA_LANG"] == "fr"
    assert env["HYPER_AMBIENT_LANG"] == "fr"
    assert env["EARS_LANGUAGE"] == "fr"
    assert env["MOUTH_LANGUAGE"] == "fr"


def test_langue_inconnue_est_journalisee_et_retombe_sur_le_francais(capsys):
    env: dict[str, str] = {}

    resultat = serve_hostagent.synchroniser_langue_assistante("zz", environ=env)

    assert resultat["language"] == "fr"
    assert env["HA_LANG"] == "fr"
    assert "ATTENTION : HA_LANG invalide" in capsys.readouterr().err


def test_langue_assistante_synchronise_oreille_cerveau_et_bouche():
    """Le changement de langue ne laisse aucune des trois voies en arrière."""
    env = {
        "HA_LANG": "fr",
        "HYPER_AMBIENT_LANG": "fr",
        "EARS_LANGUAGE": "fr",
        "MOUTH_LANGUAGE": "fr",
    }

    resultat = serve_hostagent.synchroniser_langue_assistante("en", environ=env)

    assert resultat == {"language": "en", "ears": "en", "mouth": "en", "accent": False}
    assert env == {
        "HA_LANG": "en",
        "HYPER_AMBIENT_LANG": "en",
        "EARS_LANGUAGE": "en",
        "MOUTH_LANGUAGE": "en",
    }


def test_accent_explicite_survit_au_changement_de_langue():
    """Une bouche volontairement anglaise reste anglaise quand le texte passe en FR."""
    env = {
        "HA_LANG": "en",
        "HYPER_AMBIENT_LANG": "en",
        "EARS_LANGUAGE": "en",
        "MOUTH_LANGUAGE": "en",
        "MOUTH_LANGUAGE_FORCE": "en",
    }

    resultat = serve_hostagent.synchroniser_langue_assistante("fr", environ=env)

    assert resultat == {"language": "fr", "ears": "fr", "mouth": "en", "accent": True}
    assert env["HA_LANG"] == env["HYPER_AMBIENT_LANG"] == env["EARS_LANGUAGE"] == "fr"
    assert env["MOUTH_LANGUAGE"] == "en"


def test_option_langue_met_a_jour_whisper_et_magpie_sans_redemarrage(monkeypatch):
    """Les deux modèles présents à la dégustation changent leur paramètre à chaud."""
    monkeypatch.setenv("HA_LANG", "fr")
    monkeypatch.setenv("HYPER_AMBIENT_LANG", "fr")
    monkeypatch.setenv("EARS_LANGUAGE", "fr")
    monkeypatch.setenv("MOUTH_LANGUAGE", "fr")
    pipeline = serve_hostagent.HostPipeline()
    pipeline.asr = SimpleNamespace(language="fr")
    pipeline.tts = type("MagpieTTS", (), {"language": "fr"})()

    status = pipeline.on_options({"type": "options", "language": "en"})

    assert status == {
        "type": "language_status",
        "language": "en",
        "ears": "en",
        "mouth": "en",
        "accent": False,
        "state": "ready",
    }
    assert pipeline.asr.language == pipeline.tts.language == "en"


def test_relance_exporte_ha_lang():
    texte = RELANCE.read_text(encoding="utf-8")
    assert "HA_LANG=" in texte
    assert "export HA_LANG" in texte
    assert "HYPER_AMBIENT_LANG" in texte


def test_relance_surcharge_mouth_voice_name_depuis_env_local():
    """.env.local gagne via MOUTH_VOICE_NAME_FORCE, sinon la carte reste le défaut."""
    texte = RELANCE.read_text(encoding="utf-8")
    assert "lire_env_local MOUTH_VOICE_NAME" in texte
    assert "MOUTH_VOICE_NAME_FORCE" in texte
    assert "lire_carte MOUTH_VOICE_NAME" in texte
    idx_local = texte.index("lire_env_local MOUTH_VOICE_NAME")
    idx_force = texte.index("export MOUTH_VOICE_NAME_FORCE")
    idx_carte = texte.index("lire_carte MOUTH_VOICE_NAME")
    assert idx_local < idx_force < idx_carte


def test_relance_surcharge_accent_depuis_env_local():
    """L'accent explicite gagne ; MOUTH_LANGUAGE historique ne fige pas la langue."""
    texte = RELANCE.read_text(encoding="utf-8")
    assert "lire_env_local MOUTH_ACCENT" in texte
    assert "MOUTH_LANGUAGE_FORCE" in texte
    assert "lire_carte MOUTH_LANGUAGE" in texte
    idx_local = texte.index("lire_env_local MOUTH_ACCENT")
    idx_force = texte.index("export MOUTH_LANGUAGE_FORCE")
    idx_carte = texte.index("lire_carte MOUTH_LANGUAGE")
    assert idx_local < idx_force < idx_carte
    assert idx_local < texte.index("lire_carte MOUTH_LANGUAGE")


def test_dry_run_rapporte_carte_figee_c11_c12_jev_en(tmp_path, monkeypatch):
    for cle in CLES_OUTILS:
        monkeypatch.delenv(cle, raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.setenv("HA_LANG", "en")
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "cle-de-test")
    env_local = tmp_path / ".env.local"
    env_local.write_bytes(b"HA_LANG=en\nBRAVE_API_KEY=cle-de-test\n")
    isole = {"HA_LANG": "en", "BRAVE_API_KEY": "cle-de-test"}

    rapport = serve_hostagent.rapport_branchements(
        environ=isole,
        env_local=env_local,
        carte=CARTE,
    )
    texte = serve_hostagent.formatter_rapport(rapport)
    assert rapport["brain_service"] == "router"
    assert rapport["ears_model"] == "large-v3"
    assert rapport["ears_hotwords"] == "Hyper Ambient"
    assert rapport["mouth_backend"] == "magpie"
    assert rapport["mouth_voice"] == "Sofia"
    assert rapport["mouth_device"] == "cuda"
    assert rapport["lang"] == "en"
    assert rapport["identite"] is True
    assert "calculer" in rapport["outils"]
    assert "web_search" in rapport["outils"]
    assert rapport["jev"] is True
    assert "I'll calculate that." in rapport["annonce_calculer"]
    assert "granite-4.2-3b" in rapport["model_basename"]
    assert "Sofia" in texte
    assert "Hyper Ambient" in texte
    assert "large-v3" in texte


def test_c11_identite_en_si_ha_lang_en(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "en")
    brain = LlamaCppBrain()
    system = brain._payload("Hello", None, 0.2, True, None)["messages"][0]["content"]
    assert "Hyper Ambient" in system
    assert "English" in system
    assert "français" not in system
    assert "Markdown" in system


def test_c11_identite_fr_par_defaut(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    brain = LlamaCppBrain()
    system = brain._payload("Bonjour", None, 0.2, True, None)["messages"][0]["content"]
    assert "Hyper Ambient" in system
    assert "français" in system


def test_jev_ignore_et_harnais_observation_seulement():
    assert serve_hostagent.jev_ignore_tour(None) is False
    assert serve_hostagent.jev_ignore_tour(_evaluation(addressed=False)) is True
    assert serve_hostagent.jev_ignore_tour(_evaluation(addressed=True, harness="codex")) is False


def test_annonce_calculer_suit_ha_lang(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "en")
    assert serve_hostagent.annonce_outil("calculer") == "I'll calculate that."
    monkeypatch.setenv("HA_LANG", "fr")
    assert serve_hostagent.annonce_outil("calculer") == "Je calcule ça."


def test_c4_brave_sans_tavily_expose_web_search(monkeypatch):
    for cle in CLES_OUTILS:
        monkeypatch.delenv(cle, raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "cle-de-test")
    registre = serve_hostagent.construire_registre(client=object())
    assert serve_hostagent.verifier_registre(registre) == {"web_search", "calculer"}
