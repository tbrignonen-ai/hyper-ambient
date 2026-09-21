"""
Test configuration and fixtures for hyper-ambient.
"""
import gc
import threading
from pathlib import Path
import sys

import pytest

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _joindre_fils_reglages() -> None:
    actuel = threading.current_thread()
    for fil in threading.enumerate():
        if fil is actuel:
            continue
        if fil.name == "reglages-sonde":
            fil.join(timeout=2.0)


def relacher_racine_tk(tk_mod, racine) -> None:
    """Fils d'abord, GC des StringVar sur le fil Tk, puis destroy.

    L'ordre inverse laisse ``Variable.__del__`` parler à un interpréteur
    mort, parfois depuis un fil daemon : Windows fatal 0x80000003.
    """
    _joindre_fils_reglages()
    gc.collect()
    if racine is not None:
        try:
            racine.destroy()
        except tk_mod.TclError:
            pass
    try:
        tk_mod._default_root = None
    except Exception:
        pass
    gc.collect()


@pytest.fixture
def racine_tk():
    """Une racine Tk par test, détruite sans laisser de référence Tcl."""
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    derniere: Exception | None = None
    racine = None
    for _ in range(3):
        try:
            racine = tk.Tk()
            break
        except tk.TclError as exc:
            derniere = exc
            racine = None
    if racine is None:
        pytest.skip(f"Tk indisponible : {derniere}")
    racine.withdraw()
    try:
        yield tk, racine
    finally:
        relacher_racine_tk(tk, racine)


@pytest.fixture
def audio_device_available():
    """Check if audio device is available (e.g., /dev/snd in container)."""
    import os
    return os.path.exists("/dev/snd") or sys.platform == "win32"


@pytest.fixture
def gpu_available():
    """Check if CUDA GPU is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


@pytest.fixture
def models_dir():
    """Return path to models directory."""
    return Path(__file__).parent.parent.parent / "models"
