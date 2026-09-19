"""C8 — i18n EN 0.1. FR reste le défaut. Aucun réseau."""
import os

import pytest

from src.i18n import langue, questions_jev, system_prompt, t, ui
from src.mouth.normalize import nombres_en_lettres


@pytest.fixture
def lang_env(monkeypatch):
    def _set(valeur: str | None):
        monkeypatch.delenv("HA_LANG", raising=False)
        monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
        if valeur is not None:
            monkeypatch.setenv("HA_LANG", valeur)

    return _set


def test_defaut_francais_sans_variable(lang_env):
    lang_env(None)
    assert langue() == "fr"


def test_ha_lang_en_accepte_en_US(lang_env):
    lang_env("en-US")
    assert langue() == "en"


def test_langue_inconnue_retombe_sur_fr(lang_env):
    lang_env("es")
    assert langue() == "fr"


def test_annonces_outils_fr_inchangees(lang_env):
    lang_env(None)
    assert t("tools.ask_codex") == "Je demande à Codex, ça prend une vingtaine de secondes."
    assert t("tools.ask_claude") == "Je demande son analyse à Claude."
    assert t("tools.web_search") == "Je cherche ça sur le web."
    assert t("tools.default") == "Je consulte un outil."


def test_annonces_outils_en(lang_env):
    lang_env("en")
    assert "Codex" in t("tools.ask_codex")
    assert "twenty" in t("tools.ask_codex")
    assert "Claude" in t("tools.ask_claude")
    assert "web" in t("tools.web_search").lower()
    assert t("tools.default")


def test_prompt_systeme_fr_identite(lang_env):
    lang_env("fr")
    texte = system_prompt()
    assert "Hyper Ambient" in texte
    assert "français" in texte


def test_prompt_systeme_en_identite(lang_env):
    lang_env("en")
    texte = system_prompt()
    assert "Hyper Ambient" in texte
    assert "English" in texte
    assert "français" not in texte
    assert "Markdown" in texte


def test_nombres_fr_inchanges_par_defaut(lang_env):
    lang_env(None)
    assert nombres_en_lettres("à 15h30") == "à quinze heures trente"


def test_nombres_en_heures_et_entiers(lang_env):
    lang_env("en")
    assert nombres_en_lettres("at 3:30.") == "at three thirty."
    assert nombres_en_lettres("meet at 15h30.") == "meet at fifteen thirty."
    assert nombres_en_lettres("12 roses.") == "twelve roses."
    assert nombres_en_lettres("50% done.") == "fifty percent done."


def test_nombres_en_entier_en_fin_de_fragment_reste_chiffres(lang_env):
    lang_env("en")
    assert nombres_en_lettres("Thursday 2") == "Thursday 2"


def test_jev_labels_en_memes_identifiants(lang_env):
    lang_env("en")
    fr = questions_jev("fr")
    en = questions_jev("en")
    assert set(fr) == set(en)
    assert "MOTHER" in en["addressed_to_mother"]["instructions"]
    assert en["addressed_to_mother"]["instructions"] != fr["addressed_to_mother"]["instructions"]
    assert "true" in en["addressed_to_mother"]["criteria"]


def test_ui_onboarding_fr_defaut(lang_env):
    lang_env(None)
    textes = ui()
    assert textes["welcome_title"] == "Bienvenue"
    assert "présence vocale" in textes["welcome_body"]
    assert "Étape" in textes["step"].format(indice=1, total=3)


def test_ui_onboarding_en(lang_env):
    lang_env("en")
    textes = ui()
    assert textes["welcome_title"] == "Welcome"
    assert "voice" in textes["welcome_body"].lower()
    assert "Step" in textes["step"].format(indice=1, total=3)
    assert textes["skip"] == "Skip"
