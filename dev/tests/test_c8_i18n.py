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


def test_prompt_systeme_fr_calibre_longueur_et_stop(lang_env):
    lang_env("fr")
    texte = system_prompt().lower()
    assert "une phrase" in texte
    assert "deux" in texte and "quatre" in texte
    assert "explique" in texte
    assert "développe" in texte
    assert "pourquoi" in texte
    assert "je peux aussi" in texte
    assert "sinon" in texte
    assert "veux-tu que" in texte
    assert "féminin" in texte
    assert "liste" in texte


def test_prompt_systeme_en_identite(lang_env):
    lang_env("en")
    texte = system_prompt()
    assert "Hyper Ambient" in texte
    assert "English" in texte
    assert "français" not in texte
    assert "Markdown" in texte


def test_prompt_systeme_en_calibre_longueur_et_stop(lang_env):
    lang_env("en")
    texte = system_prompt().lower()
    assert "one sentence" in texte
    assert "two" in texte and "four" in texte
    assert "explain" in texte
    assert "why" in texte
    assert "i can also" in texte
    assert "would you like" in texte
    assert "list" in texte
    assert "markdown" in texte


def test_voice_system_prompt_aligne_sur_soul():
    from src.mouth.normalize import VOICE_SYSTEM_PROMPT

    texte = VOICE_SYSTEM_PROMPT.lower()
    assert "hyper ambient" in texte or "hyper-ambient" in texte
    assert "une phrase" in texte
    assert "je peux aussi" in texte
    assert "veux-tu que" in texte
    assert "liste" in texte


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
    # `addressed_to_mother` a ete remplacee par le jeu V2 decompose ; la
    # question du nom porte desormais l'identite du produit.
    assert "Hyper Ambient" in en["assistant_name_spoken"]["instructions"]
    assert (
        en["assistant_name_spoken"]["instructions"]
        != fr["assistant_name_spoken"]["instructions"]
    )
    assert "true" in en["assistant_name_spoken"]["criteria"]


def test_ui_onboarding_fr_defaut(lang_env):
    lang_env(None)
    textes = ui()
    assert textes["welcome_title"] == "Bienvenue"
    assert "présence vocale" in textes["welcome_body"]
    assert "Étape" in textes["step"].format(indice=1, total=4)
    assert "ON" in textes["hands_free_on"]
    assert "OFF" in textes["hands_free_off"]


def test_ui_onboarding_en(lang_env):
    lang_env("en")
    textes = ui()
    assert textes["welcome_title"] == "Welcome"
    assert "voice" in textes["welcome_body"].lower()
    assert "Step" in textes["step"].format(indice=1, total=4)
    assert textes["skip"] == "Skip"
    assert "ON" in textes["hands_free_on"]
    assert "OFF" in textes["hands_free_off"]
