"""Presence démarre elle-même les ponts de harnais (24/09).

Un utilisateur qui a configuré Codex ou Claude Code ouvre hyper-ambient par
n'importe quel chemin (raccourci, lanceur, double-clic) : les ponts doivent
suivre. Un pont ne démarre que s'il a son jeton ET que le CLI est installé ;
un pont déjà en écoute n'est pas empilé.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "native" / "presence"))

import ponts  # noqa: E402


def test_pont_demarre_si_jeton_et_cli_presents():
    choisis = ponts.ponts_a_demarrer(
        {"CODEX_BRIDGE_TOKEN": "abc", "CLI_BRIDGE_TOKEN": "def"},
        port_ouvert=lambda port: False,
        trouver=lambda exe: f"C:/bin/{exe}.exe",
    )
    assert [p.module for p in choisis] == [
        "native.codexbridge.bridge",
        "native.clibridge.bridge",
    ]


def test_pont_saute_sans_jeton_sans_cli_ou_deja_en_ecoute():
    choisis = ponts.ponts_a_demarrer(
        {"CODEX_BRIDGE_TOKEN": "", "CLI_BRIDGE_TOKEN": "def"},
        port_ouvert=lambda port: False,
        trouver=lambda exe: None,
    )
    assert choisis == []
    choisis = ponts.ponts_a_demarrer(
        {"CODEX_BRIDGE_TOKEN": "abc", "CLI_BRIDGE_TOKEN": "def"},
        port_ouvert=lambda port: port == 8765,
        trouver=lambda exe: exe,
    )
    assert [p.port for p in choisis] == [8766]


def test_demarrer_passe_le_jeton_au_seul_processus_du_pont(tmp_path):
    lances = []

    def popen(cmd, **kw):
        lances.append((cmd, kw))

    env_local = tmp_path / ".env.local"
    env_local.write_text("CLI_BRIDGE_TOKEN=secret\n", encoding="utf-8")
    noms = ponts.demarrer_ponts(
        tmp_path,
        journal_dir=tmp_path,
        port_ouvert=lambda port: False,
        trouver=lambda exe: exe,
        popen=popen,
    )
    assert noms == ["Claude Code"]
    cmd, kw = lances[0]
    assert cmd[-2:] == ["-m", "native.clibridge.bridge"]
    assert kw["env"]["CLI_BRIDGE_TOKEN"] == "secret"
    assert kw["cwd"] == str(tmp_path)
