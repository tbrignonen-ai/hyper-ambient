"""Statut Connexion… / Mains libres prêtes. à l'activation JeV. Sans lancer Presence."""
from __future__ import annotations

import pytest

pytest.importorskip("tkinter")

from native.presence.app import relayer_jev_pret
from test_presence_stop_mains_libres import _application


def _fermer(application) -> None:
    try:
        application._annuler_repli_jev_pret()
    except Exception:
        pass
    try:
        application.racine.destroy()
    except Exception:
        pass


def test_bascule_on_affiche_connexion(tmp_path):
    application = _application(tmp_path, mains_libres=False)
    try:
        application._basculer_mains_libres()
        assert "Connexion…" in application.texte_statut
        assert str(application.bouton.cget("state")) != "disabled"
    finally:
        _fermer(application)


def test_reception_jev_pret_affiche_pretes(tmp_path):
    application = _application(tmp_path, mains_libres=False)
    try:
        application._basculer_mains_libres()
        assert relayer_jev_pret({"type": "jev_pret"}, application._traiter)
        assert "Mains libres prêtes." in application.texte_statut
    finally:
        _fermer(application)


def test_bascule_off_efface_connexion_et_pretes(tmp_path):
    application = _application(tmp_path, mains_libres=False)
    try:
        application._basculer_mains_libres()
        relayer_jev_pret({"type": "jev_pret"}, application._traiter)
        application._basculer_mains_libres()
        assert "Connexion…" not in application.texte_statut
        assert "Mains libres prêtes." not in application.texte_statut
    finally:
        _fermer(application)
