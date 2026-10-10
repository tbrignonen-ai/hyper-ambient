"""Thème central de Presence : police par plateforme, contraste AA, usage."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
PRESENCE = RACINE / "native" / "presence"
for chemin in (str(RACINE), str(PRESENCE)):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from native.presence import theme  # noqa: E402


# --- Police ----------------------------------------------------------------------

def test_windows_garde_segoe_ui():
    assert theme.famille_police("win32") == "Segoe UI"
    assert theme.famille_police("win32", famille_systeme=".AppleSystemUIFont") == "Segoe UI"


def test_macos_prend_la_police_systeme():
    assert theme.famille_police("darwin", famille_systeme=".AppleSystemUIFont") == ".AppleSystemUIFont"
    assert theme.famille_police("darwin") == "Helvetica Neue"
    assert theme.famille_police("darwin") != "Segoe UI"


def test_linux_a_un_defaut_sain():
    assert theme.famille_police("linux") == "DejaVu Sans"
    assert theme.famille_police("linux", famille_systeme="Cantarell") == "Cantarell"


def test_police_rend_un_tuple_tk(monkeypatch):
    monkeypatch.setattr(theme, "_famille_systeme", None)
    monkeypatch.setattr(theme, "_demander_famille_systeme", lambda: None)
    assert theme.police("corps", "win32") == ("Segoe UI", 12)
    assert theme.police("affiche", "win32") == ("Segoe UI", 24, "bold")
    assert theme.police("lien", "win32") == ("Segoe UI", 9, "underline")
    # Un point de plus sur Mac : Tk y compte à 72 ppp.
    assert theme.police("corps", "darwin") == ("Helvetica Neue", 13)


def test_police_utilise_la_famille_rapportee_par_tk(monkeypatch):
    monkeypatch.setattr(theme, "_famille_systeme", None)
    monkeypatch.setattr(theme, "_demander_famille_systeme", lambda: ".AppleSystemUIFont")
    assert theme.police("titre", "darwin")[0] == ".AppleSystemUIFont"


def test_echelle_hierarchisee():
    tailles = [theme.ECHELLE[r][0] for r in ("affiche", "titre", "sous_titre", "corps", "texte", "petit", "legende")]
    assert tailles == sorted(tailles, reverse=True)
    assert min(tailles) >= 9  # plus de texte en 8 points


def test_espacements_croissants():
    valeurs = list(theme.ESPACE.values())
    assert valeurs == sorted(valeurs) and len(set(valeurs)) == len(valeurs)


# --- Contraste -----------------------------------------------------------------

def test_formule_de_contraste():
    assert theme.contraste("#000000", "#ffffff") == pytest.approx(21.0)
    assert theme.contraste("#777777", "#777777") == pytest.approx(1.0)


@pytest.mark.parametrize(("encre", "fond"), theme.PAIRES_TEXTE)
def test_texte_courant_au_niveau_aa(encre, fond):
    assert theme.contraste(encre, fond) >= theme.SEUIL_AA, (encre, fond)


def test_le_fond_suit_la_bulle():
    pytest.importorskip("tkinter")
    from native.presence import overlay

    assert theme.FOND == overlay.FOND_CHAMP


def test_les_palettes_contraste_de_la_bulle_restent_completes():
    pytest.importorskip("tkinter")
    from native.presence import overlay

    assert set(overlay.PALETTES_CONTRASTE) == set(overlay.PALETTES)
    for etat in overlay.ETATS:
        assert overlay.palette_pour(etat, contraste=True)["coeur"].startswith("#")


def test_couleurs_des_harnais_couvrent_les_etats():
    from native.presence import onboarding_llm

    assert set(theme.COULEURS_HARNAIS) == {onboarding_llm.VERT, onboarding_llm.GRIS, onboarding_llm.ROUGE}


# --- Usage : plus de couleur ni de police en dur dans les écrans ------------------

FICHIERS_ECRANS = ("app.py", "reglages_ui.py", "onboarding.py", "onboarding_llm_ui.py")


@pytest.mark.parametrize("nom", FICHIERS_ECRANS)
def test_aucune_police_segoe_en_dur(nom):
    source = (PRESENCE / nom).read_text(encoding="utf-8")
    assert "Segoe UI" not in source


@pytest.mark.parametrize("nom", FICHIERS_ECRANS)
def test_aucune_couleur_hexadecimale_en_dur(nom):
    source = (PRESENCE / nom).read_text(encoding="utf-8")
    assert re.findall(r"[\"']#[0-9a-fA-F]{6}[\"']", source) == []
