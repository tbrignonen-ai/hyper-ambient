"""C2 — bandeau Presence : apparaît en DEGRADED, disparaît au retour UP.

Sans GUI réelle pour le contrat (couleurs, texte, rôle alerte).
Avec Tk uniquement pour vérifier que le widget est bien posé / retiré.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from native.presence.sante import (
    PHRASE_ALERTE_CODEX,
    PHRASE_REPRISE_CODEX,
    bandeau_depuis_etat,
    contraste_relatif,
    lire_snapshot,
)


def test_bandeau_apparait_quand_degraded():
    bandeau = bandeau_depuis_etat(
        {
            "healthStatus": "DEGRADED",
            "alertMessage": PHRASE_ALERTE_CODEX,
            "recoveryMessage": PHRASE_REPRISE_CODEX,
        }
    )
    assert bandeau["visible"] is True
    assert bandeau["texte"] == PHRASE_ALERTE_CODEX
    assert bandeau["role"] == "alert"
    assert bandeau["takefocus"] is True
    assert contraste_relatif(bandeau["fg"], bandeau["bg"]) >= 4.5


def test_bandeau_disparait_quand_up_et_garde_la_reprise():
    bandeau = bandeau_depuis_etat(
        {
            "healthStatus": "UP",
            "alertMessage": "",
            "recoveryMessage": PHRASE_REPRISE_CODEX,
        }
    )
    assert bandeau["visible"] is False
    assert bandeau["texte_reprise"] == PHRASE_REPRISE_CODEX


def test_lire_snapshot_json(tmp_path: Path):
    chemin = tmp_path / "sante.json"
    chemin.write_text(
        json.dumps(
            {
                "healthStatus": "DEGRADED",
                "alertMessage": PHRASE_ALERTE_CODEX,
            }
        ),
        encoding="utf-8",
    )
    etat = lire_snapshot(chemin)
    assert etat["healthStatus"] == "DEGRADED"
    assert bandeau_depuis_etat(etat)["visible"] is True


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


def test_bandeau_presence_apparait_et_disparait(tmp_path: Path):
    _ouvrir_tk()
    from native.presence.app import Application, analyser_arguments

    snapshot = tmp_path / "sante.json"
    snapshot.write_text(
        json.dumps(
            {
                "healthStatus": "DEGRADED",
                "alertMessage": PHRASE_ALERTE_CODEX,
                "recoveryMessage": PHRASE_REPRISE_CODEX,
            }
        ),
        encoding="utf-8",
    )
    args = analyser_arguments(
        [
            "--onboarding",
            "--config",
            str(tmp_path / "presence.json"),
            "--sante",
            str(snapshot),
        ]
    )
    application = Application(args)
    application.session_lancee = True
    try:
        application._afficher_application()
        application.racine.withdraw()
        application.appliquer_etat_sante(lire_snapshot(snapshot))
        application.racine.update_idletasks()
        assert application.bandeau_alerte is not None
        assert application.bandeau_alerte.winfo_manager()
        assert PHRASE_ALERTE_CODEX in application.bandeau_alerte.cget("text")
        assert str(application.bandeau_alerte.cget("takefocus")) in ("1", "true")

        snapshot.write_text(
            json.dumps(
                {
                    "healthStatus": "UP",
                    "alertMessage": "",
                    "recoveryMessage": PHRASE_REPRISE_CODEX,
                }
            ),
            encoding="utf-8",
        )
        application.appliquer_etat_sante(lire_snapshot(snapshot))
        application.racine.update_idletasks()
        assert application.bandeau_alerte is None or not application.bandeau_alerte.winfo_manager()
        assert PHRASE_REPRISE_CODEX in application.ligne_etat.cget("text")
    finally:
        application.fermer()
