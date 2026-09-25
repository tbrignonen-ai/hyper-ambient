"""La libération Mac ne vise que les .command créés par Presence."""
import json
import signal

import pytest

from native import consoles_presence as cp


@pytest.mark.parametrize("harnais,reprise", [("codex", "resume"), ("claude", "--resume")])
def test_libere_seulement_descendance_du_command_presence(tmp_path, monkeypatch, harnais, reprise):
    dossier = tmp_path / "mother-harnais-abc"
    dossier.mkdir()
    (dossier / "session.json").write_text(json.dumps({"harnais": harnais, "session": "s-1"}))
    (dossier / "pid").write_text("101")
    (dossier / "tty").write_text("/dev/ttys001")
    processus = {
        101: (1, f"/bin/sh {dossier / 'reprendre.command'}"),
        102: (101, f"/opt/homebrew/bin/{harnais} {reprise} s-1"),
        103: (1, f"/opt/homebrew/bin/{harnais} {reprise} s-1"),  # Terminal user
    }
    signaux, fenetres = [], []
    monkeypatch.setattr(cp.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(cp, "_processus_macos", lambda: processus)
    monkeypatch.setattr(cp.os, "kill", lambda pid, sig: signaux.append((pid, sig)))
    monkeypatch.setattr(cp, "_fermer_fenetre_macos", fenetres.append)
    monkeypatch.setattr(cp.sys, "platform", "darwin")

    assert cp.liberer_session("s-1", harnais)
    assert signaux == [(102, signal.SIGTERM), (102, signal.SIGKILL),
                       (101, signal.SIGTERM)]
    assert fenetres == ["/dev/ttys001"]
    assert not cp.liberer_session("autre", harnais)


def test_refuse_pid_reutilise_et_commande_sans_cli_attendu(tmp_path, monkeypatch):
    dossier = tmp_path / "mother-harnais-abc"
    dossier.mkdir()
    (dossier / "session.json").write_text('{"harnais":"codex","session":"s-1"}')
    (dossier / "pid").write_text("101")
    (dossier / "tty").write_text("/dev/ttys001")
    appels = []
    monkeypatch.setattr(cp.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(cp.os, "kill", lambda *args: appels.append(args))
    user = {101: (1, "/bin/zsh"), 102: (101, "codex resume s-1")}
    assert not cp.liberer_console_macos(dossier, processus=user)
    autre = {101: (1, f"/bin/sh {dossier / 'reprendre.command'}"),
             102: (101, "codex resume autre")}
    assert not cp.liberer_console_macos(dossier, processus=autre)
    assert appels == []


def test_pid_reutilise_apres_term_ne_recoit_pas_kill(tmp_path, monkeypatch):
    dossier = tmp_path / "mother-harnais-abc"
    dossier.mkdir()
    (dossier / "session.json").write_text('{"harnais":"codex","session":"s-1"}')
    (dossier / "pid").write_text("101")
    (dossier / "tty").write_text("/dev/ttys001")
    initial = {101: (1, f"/bin/sh {dossier / 'reprendre.command'}"),
               102: (101, "codex resume s-1")}
    remplace = {101: initial[101], 102: (1, "zsh")}
    sondes = iter([initial, remplace])
    signaux = []
    monkeypatch.setattr(cp.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(cp, "_processus_macos", lambda: next(sondes))
    monkeypatch.setattr(cp.time, "sleep", lambda _: None)
    monkeypatch.setattr(cp.os, "kill", lambda pid, sig: signaux.append((pid, sig)))
    monkeypatch.setattr(cp, "_fermer_fenetre_macos", lambda _: None)
    assert cp.liberer_console_macos(dossier)
    assert signaux == [(102, signal.SIGTERM), (101, signal.SIGTERM)]


def test_applescript_ferme_seulement_fenetre_a_un_onglet_matching(monkeypatch):
    appels = []
    monkeypatch.setattr(cp.subprocess, "run", lambda cmd, **kw: appels.append(cmd))
    cp._fermer_fenetre_macos("/dev/ttys001")
    assert appels[0][0] == "osascript"
    assert "(count of tabs of w) is 1" in appels[0][2]
    assert "(tty of t as text) is targetTTY" in appels[0][2]
    assert appels[0][3] == "/dev/ttys001"
