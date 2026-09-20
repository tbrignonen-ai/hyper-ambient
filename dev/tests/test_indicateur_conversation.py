"""Indicateur visuel d'état de conversation (mains libres). Sans lancer Presence."""
from __future__ import annotations

import pytest

pytest.importorskip("tkinter")

from native.presence.app import relayer_conversation
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


def _texte_indicateur(application) -> str:
    ligne = getattr(application, "ligne_conversation", None)
    if ligne is None:
        return ""
    return str(ligne.cget("text") or "")


def test_reception_conversation_ouverte_affiche_libelle(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        assert relayer_conversation(
            {"type": "conversation", "ouverte": True, "restant_s": 24.0},
            application._traiter,
        )
        texte = _texte_indicateur(application)
        assert "En conversation" in texte
        assert "24" in texte
        assert "Dis mon nom" not in texte
    finally:
        _fermer(application)


def test_reception_conversation_fermee_affiche_invitation(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        relayer_conversation(
            {"type": "conversation", "ouverte": True, "restant_s": 24.0},
            application._traiter,
        )
        assert relayer_conversation(
            {"type": "conversation", "ouverte": False, "restant_s": 0.0},
            application._traiter,
        )
        texte = _texte_indicateur(application)
        assert "Dis mon nom pour me parler" in texte
        assert "En conversation" not in texte
    finally:
        _fermer(application)


def test_mains_libres_off_aucun_libelle(tmp_path):
    application = _application(tmp_path, mains_libres=False)
    try:
        relayer_conversation(
            {"type": "conversation", "ouverte": True, "restant_s": 24.0},
            application._traiter,
        )
        texte = _texte_indicateur(application)
        assert "En conversation" not in texte
        assert "Dis mon nom" not in texte
    finally:
        _fermer(application)


def test_decompte_saffiche(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        relayer_conversation(
            {"type": "conversation", "ouverte": True, "restant_s": 24.4},
            application._traiter,
        )
        assert "24" in _texte_indicateur(application)
        relayer_conversation(
            {"type": "conversation", "ouverte": True, "restant_s": 7.2},
            application._traiter,
        )
        texte = _texte_indicateur(application)
        assert "7" in texte
        assert "24" not in texte
    finally:
        _fermer(application)
