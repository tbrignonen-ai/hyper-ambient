"""Les ponts lancent Claude et Codex sans console (24/09).

« Une fenêtre vide Claude a ouvert au début. » Le pont tourne sous pythonw,
sans console ; sous Windows, un programme console lancé sans le drapeau
CREATE_NO_WINDOW s'en ouvre une, vide, au premier plan.
"""
import inspect
import subprocess

from native import sans_console


def test_drapeau_sous_windows(monkeypatch):
    monkeypatch.setattr(sans_console.os, "name", "nt")
    assert sans_console.options() == {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    monkeypatch.setattr(sans_console.os, "name", "posix")
    assert sans_console.options() == {}


def test_tous_les_lancements_des_ponts_passent_sans_console():
    from native.clibridge import bridge as pont_claude
    from native.clibridge import conversation as conv_claude
    from native.codexbridge import bridge as pont_codex
    from native.codexbridge import conversation as conv_codex

    for module in (pont_claude, pont_codex):
        lanceur = getattr(module, "run_cli", None) or getattr(module, "run_codex")
        assert "sans_console.options()" in inspect.getsource(lanceur)
    for session in (conv_claude.SessionClaude._demarrer, conv_codex.SessionCodex._demarrer):
        assert "sans_console.options()" in inspect.getsource(session)
