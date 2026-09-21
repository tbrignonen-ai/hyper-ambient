"""Contrat du poseur de raccourcis Windows.

Lecture seule : aucun bureau, aucun menu Demarrer, aucun registre.
mother-core-dev ne monte pas packaging/ (seulement dev/, native/, src/).
Les assertions sur le .ps1 et le README sautent dans ce conteneur ;
elles tournent des que l'arbre complet est visible (hote, CI complete).
"""
from __future__ import annotations

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "packaging" / "windows" / "installer_raccourcis.ps1"
README = RACINE / "packaging" / "windows" / "README.md"
LANCEUR = RACINE / "native" / "presence" / "hyper-ambient.bat"


@pytest.fixture
def script() -> str:
    if not SCRIPT.is_file():
        pytest.skip("packaging/ n'est pas monte dans mother-core-dev")
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture
def readme() -> str:
    if not README.is_file():
        pytest.skip("packaging/ n'est pas monte dans mother-core-dev")
    return README.read_text(encoding="utf-8")


def test_le_lanceur_vise_par_le_raccourci_existe():
    """Le .lnk pointera vers ce .bat ; s'il manque, le raccourci est mort."""
    assert LANCEUR.is_file(), f"manque {LANCEUR}"
    texte = LANCEUR.read_text(encoding="utf-8", errors="replace")
    assert "native\\presence\\app.py" in texte or "native/presence/app.py" in texte


def test_script_et_readme_sont_au_bon_endroit():
    if not SCRIPT.is_file() or not README.is_file():
        pytest.skip("packaging/ n'est pas monte dans mother-core-dev")
    assert SCRIPT.is_file()
    assert README.is_file()


def test_script_se_deduit_de_son_emplacement(script: str):
    assert "$PSScriptRoot" in script
    assert "MyInvocation" in script or "Split-Path" in script


def test_script_pointe_vers_le_bat_avec_repertoire_de_travail(script: str):
    assert "hyper-ambient.bat" in script
    assert "native" in script and "presence" in script
    assert "WorkingDirectory" in script


def test_script_cible_bureau_et_programmes_utilisateur(script: str):
    assert "GetFolderPath" in script
    assert "'Desktop'" in script or '"Desktop"' in script
    assert "'Programs'" in script or '"Programs"' in script
    assert "CommonDesktop" not in script
    assert "CommonPrograms" not in script
    assert "AllUsers" not in script
    assert "RunAsAdministrator" not in script
    assert "Verb RunAs" not in script


def test_script_accepte_supprimer_en_switch(script: str):
    assert "param(" in script
    assert "[switch]$Supprimer" in script or "[switch] $Supprimer" in script


def test_script_idempotent_un_seul_lnk_par_emplacement(script: str):
    assert "hyper-ambient.lnk" in script
    assert "CreateShortcut" in script
    assert script.count("hyper-ambient.lnk") >= 2


def test_script_icone_assets_sinon_python(script: str):
    assert "assets" in script
    assert "hyper-ambient.ico" in script
    assert "python" in script.lower()


def test_script_forme_powershell_pas_cmd(script: str):
    assert "Set-Location" in script
    assert "cd /d" not in script
    assert "cmd.exe" not in script.lower()
    for ligne in script.splitlines():
        compact = ligne.strip().lower()
        if compact.startswith("start ") and "start-process" not in compact:
            raise AssertionError(f"start cmd.exe interdit : {ligne}")


def test_script_chemins_via_joinpath_ou_literalpath(script: str):
    assert "Join-Path" in script
    assert "-LiteralPath" in script


def test_script_echoue_avec_un_message_sans_trace(script: str):
    assert "catch" in script
    assert "exit 1" in script
    assert "Echec" in script or "échec" in script.lower()


def test_readme_tient_en_dix_lignes_et_reste_honnete(readme: str):
    assert len(readme.splitlines()) <= 10
    texte = readme.lower()
    assert "installer_raccourcis.ps1" in texte
    assert "-supprimer" in texte
    assert "raccourci" in texte
    assert "produit" in texte
    assert "docker" in texte
    assert "mother-core-dev" in texte
    assert "pyinstaller" not in texte
    assert ".exe" not in texte
