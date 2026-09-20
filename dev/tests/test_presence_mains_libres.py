"""Mains libres (JeV) : config, i18n, wizard, bouton Presence, filtre host-agent."""
from __future__ import annotations

import json

import pytest

from native.presence.onboarding import (
    ETAPES_WIZARD,
    ConfigurationPresence,
    charger_configuration,
    enregistrer_configuration,
    message_options,
    normaliser_configuration,
    terminer_onboarding,
)


def test_mains_libres_defaut_false_pour_garder_le_ptt():
    assert ConfigurationPresence().mains_libres is False
    assert normaliser_configuration({}).mains_libres is False
    assert normaliser_configuration({"mains_libres": "oui"}).mains_libres is False


def test_mains_libres_persiste_dans_presence_json(tmp_path):
    chemin = tmp_path / "presence.json"
    enregistrer_configuration(
        ConfigurationPresence(onboarding_termine=True, mains_libres=True),
        chemin,
    )
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    assert brut["mains_libres"] is True
    assert charger_configuration(chemin).mains_libres is True


def test_terminer_onboarding_ne_force_pas_mains_libres():
    actuelle = ConfigurationPresence(mains_libres=False, raccourci_ptt="ctrl-space")
    terminee = terminer_onboarding(actuelle)
    assert terminee.onboarding_termine is True
    assert terminee.mains_libres is False
    assert terminer_onboarding(actuelle, mains_libres=True).mains_libres is True


def test_wizard_a_une_etape_mains_libres():
    assert "mains_libres" in ETAPES_WIZARD
    assert ETAPES_WIZARD[0] == "bienvenue"
    assert ETAPES_WIZARD.index("mains_libres") == 1


def test_message_options_porte_le_flag():
    assert message_options(True) == {"type": "options", "mains_libres": True}
    assert message_options(False) == {"type": "options", "mains_libres": False}


def test_i18n_labels_mains_libres_fr_en(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "fr")
    from src.i18n import t, ui

    textes = ui()
    assert "ON" in textes["hands_free_on"]
    assert "OFF" in textes["hands_free_off"]
    assert "Mains libres" in textes["hands_free_title"]
    assert "Activer" in textes["hands_free_enable"]
    assert "Plus tard" in textes["hands_free_later"]
    assert "Parler" in textes["hands_free_on"]
    assert "micro" in textes["hands_free_hint"].lower()
    assert "adresse" in t("ui.hands_free").lower() or "JeV" in t("ui.hands_free")

    monkeypatch.setenv("HA_LANG", "en")
    from src.i18n import ui as ui_en

    en = ui_en()
    assert "ON" in en["hands_free_on"]
    assert "OFF" in en["hands_free_off"]
    assert "Hands-free" in en["hands_free_title"] or "Hands free" in en["hands_free_title"]
    assert en["hands_free_later"]
    assert en["hands_free_enable"]


def test_jev_ignore_seulement_si_mains_libres():
    from src.ears.jev_reflexe import JevEvaluation, JevSignals
    from test_hostagent_env_local import serve_hostagent

    evaluation = JevEvaluation(
        answers={},
        signals=JevSignals(
            addressed_to_mother=False,
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
            named_harness=None,
        ),
    )
    assert serve_hostagent.jev_ignore_tour(evaluation) is True
    assert serve_hostagent.jev_doit_ignorer(evaluation, mains_libres=False) is False
    assert serve_hostagent.jev_doit_ignorer(evaluation, mains_libres=True) is True
    assert serve_hostagent.jev_doit_ignorer(None, mains_libres=True) is False


def _ouvrir_tk():
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    try:
        racine = tk.Tk()
        racine.withdraw()
        racine.destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")


def _textes_widgets(widget) -> list[str]:
    textes: list[str] = []
    try:
        texte = widget.cget("text")
        if texte:
            textes.append(str(texte))
    except Exception:
        pass
    for enfant in widget.winfo_children():
        textes.extend(_textes_widgets(enfant))
    return textes


def test_etape_onboarding_propose_activer_ou_plus_tard(tmp_path):
    _ouvrir_tk()
    from native.presence.app import Application, analyser_arguments

    args = analyser_arguments(
        ["--onboarding", "--config", str(tmp_path / "presence.json")]
    )
    try:
        import tkinter as tk
        application = Application(args)
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    application.session_lancee = True
    try:
        application.racine.withdraw()
        application._afficher_mains_libres()
        application.racine.update_idletasks()
        textes = _textes_widgets(application.conteneur)
        assert any("2 sur 4" in t for t in textes)
        assert any("Activer" in t for t in textes)
        assert any("Plus tard" in t for t in textes)
        assert application.configuration.mains_libres is False
    finally:
        application.fermer()


def test_bouton_mains_libres_visible_avec_focus(tmp_path):
    _ouvrir_tk()
    from native.presence.app import Application, analyser_arguments
    from native.presence.onboarding import enregistrer_configuration, ConfigurationPresence

    chemin = tmp_path / "presence.json"
    enregistrer_configuration(
        ConfigurationPresence(onboarding_termine=True, mains_libres=False),
        chemin,
    )
    args = analyser_arguments(["--onboarding", "--config", str(chemin)])
    try:
        import tkinter as tk
        application = Application(args)
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    application.session_lancee = True
    application._afficher_application()
    try:
        application.racine.withdraw()
        application.racine.update_idletasks()
        bouton = application.bouton_mains_libres
        assert bouton is not None
        assert str(bouton.cget("takefocus")) in ("1", "true")
        assert bouton.cget("highlightthickness")
        assert "OFF" in bouton.cget("text")
        application._basculer_mains_libres()
        assert application.configuration.mains_libres is True
        assert "ON" in application.bouton_mains_libres.cget("text")
        assert "Parler" in application.bouton_mains_libres.cget("text")
        textes = _textes_widgets(application.conteneur)
        assert any("micro" in t.lower() for t in textes)
        lue = charger_configuration(chemin)
        assert lue.mains_libres is True
    finally:
        application.fermer()
