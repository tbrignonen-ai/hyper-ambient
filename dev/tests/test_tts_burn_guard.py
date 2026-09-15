from pathlib import Path

import pytest

from dev.scripts.tts_burn_guard import refuser_colocation_live


def _proc(tmp_path: Path, pid: int, cmdline: bytes) -> Path:
    proc = tmp_path / "proc"
    process = proc / str(pid)
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(cmdline)
    return proc


def test_burn_refuse_si_hostagent_est_colocalise(tmp_path, monkeypatch):
    monkeypatch.delenv("TTS_BURN_ALLOW_COLOCATED", raising=False)
    proc = _proc(tmp_path, 42, b"python\0dev/scripts/serve_hostagent.py\0")
    with pytest.raises(SystemExit, match="REFUS TTS BURN"):
        refuser_colocation_live(proc)


def test_burn_passe_sans_hostagent(tmp_path, monkeypatch):
    monkeypatch.delenv("TTS_BURN_ALLOW_COLOCATED", raising=False)
    proc = _proc(tmp_path, 7, b"python\0worker.py\0")
    refuser_colocation_live(proc)


def test_derogation_est_expresse(tmp_path, monkeypatch):
    monkeypatch.setenv("TTS_BURN_ALLOW_COLOCATED", "1")
    proc = _proc(tmp_path, 42, b"python\0dev/scripts/serve_hostagent.py\0")
    refuser_colocation_live(proc)
