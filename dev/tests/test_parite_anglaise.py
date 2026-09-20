"""Parité anglaise : mêmes clés, pas de reliquat FR, HA_LANG=en bascule.

Les jeux de clés se comparent entre tables, jamais listés à la main.
fr / en / es sont les trois langues annoncées. Aucun réseau.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from native.presence.onboarding import ui_presence
from src.i18n import langue, questions_jev
from src.mouth.reveil import PHRASES_REVEIL, phrase_de_reveil
from src.mouth.secours import phrase_de_secours

LANGUES = ("fr", "en", "es")
_ACCENT_FR = re.compile(r"[àâäéèêëïîôùûüçÀÂÄÉÈÊËÏÎÔÙÛÜÇ]")
# Identiques par nature (URL, mot international), pas des reliquats.
_EN_IDENTIQUE_FR_OK = frozenset({"ui.feedback_url", "ui.stop"})


@pytest.fixture
def lang_env(monkeypatch):
    def _set(valeur: str | None):
        monkeypatch.delenv("HA_LANG", raising=False)
        monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
        if valeur is not None:
            monkeypatch.setenv("HA_LANG", valeur)

    return _set


def _feuilles(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        for cle, valeur in obj.items():
            chemin = f"{prefix}.{cle}" if prefix else str(cle)
            yield from _feuilles(valeur, chemin)
    elif isinstance(obj, (list, tuple)):
        for indice, valeur in enumerate(obj):
            yield from _feuilles(valeur, f"{prefix}[{indice}]")
    else:
        yield prefix, obj


def _chemins(obj: Any) -> set[str]:
    return {chemin for chemin, _ in _feuilles(obj)}


def _tables_ui() -> dict[str, dict[str, str]]:
    import src.i18n as i18n

    return dict(i18n._TABLES)


def _phrases_secours() -> dict[str, dict[str, str]]:
    import src.mouth.secours as secours

    return dict(secours._PHRASES)


def test_ui_cles_identiques_entre_tables():
    """Une langue qui perd une clé fait échouer ce test — pas de liste manuelle."""
    tables = _tables_ui()
    assert "fr" in tables and "en" in tables
    jeux = {code: set(table) for code, table in tables.items()}
    reference = jeux["fr"]
    for code, cles in jeux.items():
        assert cles == reference, f"{code} diverge : {cles ^ reference}"


@pytest.mark.xfail(reason="table UI es absente de src.i18n — hors périmètre", strict=True)
def test_ui_table_espagnol_presente():
    assert "es" in _tables_ui()


def test_ui_presence_memes_cles_via_ha_lang(lang_env):
    jeux = {}
    for code in LANGUES:
        lang_env(code)
        jeux[code] = set(ui_presence())
    reference = jeux["fr"]
    for code, cles in jeux.items():
        assert cles == reference, f"ui_presence {code} diverge : {cles ^ reference}"


def test_ui_cles_presence_suivent_la_table_ui(lang_env):
    lang_env("fr")
    cles_ui = {cle.removeprefix("ui.") for cle in _tables_ui()["fr"] if cle.startswith("ui.")}
    assert set(ui_presence()) == cles_ui


def test_questions_jev_cles_identiques_dans_les_trois_tables():
    jeux = {code: _chemins(questions_jev(code)) for code in LANGUES}
    reference = jeux["fr"]
    for code, cles in jeux.items():
        assert cles == reference, f"questions_jev {code} diverge : {cles ^ reference}"


def test_aucune_valeur_vide_ui_et_jev():
    tables = _tables_ui()
    for code, table in tables.items():
        for chemin, valeur in _feuilles(table):
            assert isinstance(valeur, str) and valeur.strip(), (
                f"UI {code}.{chemin} vide"
            )
    for code in LANGUES:
        for chemin, valeur in _feuilles(questions_jev(code)):
            if isinstance(valeur, str):
                assert valeur.strip(), f"JeV {code}.{chemin} vide"


def test_anglais_ui_sans_reliquat_francais():
    tables = _tables_ui()
    assert "en" in tables
    identiques = []
    accents = []
    for cle, francais in tables["fr"].items():
        anglais = tables["en"].get(cle, "")
        if anglais == francais and cle not in _EN_IDENTIQUE_FR_OK:
            identiques.append(cle)
        if _ACCENT_FR.search(anglais):
            accents.append(cle)
    assert not identiques, f"EN calque FR : {identiques}"
    assert not accents, f"EN avec accent FR : {accents}"


def test_anglais_jev_sans_reliquat_francais():
    fr = questions_jev("fr")
    en = questions_jev("en")
    feuilles_en = dict(_feuilles(en))
    for chemin, valeur in feuilles_en.items():
        if not isinstance(valeur, str) or chemin.endswith(".type"):
            continue
        assert valeur.strip(), f"EN JeV vide : {chemin}"
        assert not _ACCENT_FR.search(valeur), f"EN JeV accent FR : {chemin}"
    for chemin, valeur_fr in _feuilles(fr):
        if not isinstance(valeur_fr, str) or chemin.endswith(".type"):
            continue
        assert feuilles_en.get(chemin) != valeur_fr, f"EN JeV calque FR : {chemin}"


@pytest.mark.xfail(
    reason="questions_jev('es') rend le français — hors périmètre",
    strict=True,
)
def test_questions_jev_es_n_est_pas_le_francais():
    es = questions_jev("es")["addressed_to_mother"]["instructions"]
    fr = questions_jev("fr")["addressed_to_mother"]["instructions"]
    assert es != fr


def test_ha_lang_en_bascule_ui_presence(lang_env):
    lang_env("fr")
    francais = ui_presence()
    lang_env("en")
    anglais = ui_presence()
    assert langue() == "en"
    assert francais["welcome_title"] == "Bienvenue"
    assert anglais["welcome_title"] == "Welcome"
    assert anglais["skip"] == "Skip"
    assert anglais["speak"] == "Talk"
    assert set(francais) == set(anglais)


def test_ha_lang_en_bascule_questions_jev(lang_env):
    lang_env("en")
    anglais = questions_jev()
    lang_env("fr")
    francais = questions_jev()
    assert set(anglais) == set(francais)
    assert anglais["direct_interpellation"]["instructions"] != (
        francais["direct_interpellation"]["instructions"]
    )
    assert "address" in anglais["direct_interpellation"]["instructions"].lower()


def test_ha_lang_en_bascule_secours(lang_env):
    cas = dict(
        transcript="",
        reply="ok",
        brain_injoignable=False,
        duree_audio_s=0.0,
    )
    lang_env("en")
    anglais = phrase_de_secours(**cas, langue=langue())
    lang_env("fr")
    francais = phrase_de_secours(**cas, langue=langue())
    assert anglais is not None and francais is not None
    assert anglais != francais
    assert "hear" in anglais.lower() or "didn't" in anglais.lower()


def test_ha_lang_en_bascule_reveil(lang_env):
    lang_env("en")
    anglais = phrase_de_reveil(langue=langue())
    assert anglais in PHRASES_REVEIL["en"]
    lang_env("fr")
    francais = phrase_de_reveil(langue=langue())
    assert francais in PHRASES_REVEIL["fr"]


def test_secours_cles_identiques_fr_en_es():
    phrases = _phrases_secours()
    absentes = [code for code in LANGUES if code not in phrases]
    assert not absentes, f"tables secours absentes : {absentes}"
    jeux = {code: set(phrases[code]) for code in LANGUES}
    reference = jeux["fr"]
    for code, cles in jeux.items():
        assert cles == reference, f"secours {code} diverge : {cles ^ reference}"
        for valeur in phrases[code].values():
            assert valeur.strip()
            if code != "fr":
                assert valeur not in phrases["fr"].values()


def test_reveil_cles_identiques_fr_en_es():
    absentes = [code for code in LANGUES if code not in PHRASES_REVEIL]
    assert not absentes, f"tables réveil absentes : {absentes}"
    longueurs = {code: len(PHRASES_REVEIL[code]) for code in LANGUES}
    assert len(set(longueurs.values())) == 1
    for code in LANGUES:
        for phrase in PHRASES_REVEIL[code]:
            assert phrase.strip()
        if code != "fr":
            assert set(PHRASES_REVEIL[code]).isdisjoint(PHRASES_REVEIL["fr"])
