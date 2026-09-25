"""Contrat du rendu Aqua sans serveur graphique ni Tk installé."""
import importlib.util
import sys
import types
from pathlib import Path


def test_overlay_macos_garde_alpha_et_fond_plein(monkeypatch):
    fake_tk = types.ModuleType("tkinter")
    fake_tk.TclError = type("TclError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    path = Path(__file__).resolve().parents[2] / "native/presence/platform_ui.py"
    spec = importlib.util.spec_from_file_location("platform_ui_macos_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.IS_WINDOWS = False
    module.IS_MACOS = True

    class Racine:
        def __init__(self):
            self.attrs = {}

        def overrideredirect(self, value):
            self.attrs["borderless"] = value

        def wm_attributes(self, key, value):
            self.attrs[key] = value

    racine = Racine()
    mode = module.apply_overlay_window_mode(racine)
    assert mode == "alpha"
    assert racine.attrs["-alpha"] == module.MACOS_OVERLAY_ALPHA
    assert "-transparentcolor" not in racine.attrs
    assert module.fond_canvas_pour_mode(mode, "#0c1820") == "#0c1820"
