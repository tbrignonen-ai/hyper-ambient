"""Troisième état visuel : l'appel à un harnais (25/09).

L'appel distant a sa couleur et son libellé ; l'appel à Codex ou Claude en
a désormais un à lui, distinct.
"""
from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def test_eclair_allume_et_libelle_propre_au_harnais():
    from native.presence.onboarding import eclair_allume, libelle_eclair, couleurs_eclair

    assert eclair_allume("harnais")
    assert libelle_eclair("harnais") != libelle_eclair("escalade")
    assert couleurs_eclair(True, etat="harnais") != couleurs_eclair(True, etat="escalade")


def test_le_host_signale_l_appel_harnais():
    source = (RACINE / "dev" / "scripts" / "serve_hostagent.py").read_text(encoding="utf-8")
    assert 'presence.emettre("harnais")' in source
