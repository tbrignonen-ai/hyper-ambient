"""Barge-in vocal en mains libres, et Stop qui ne tue plus le mode.

Sans périphérique, sans Presence lancée. Capture continue à flux
synthétique ; SessionVocale pincée sur le contrat de lecture.
"""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

import numpy as np
import pytest

from src.hostagent.audio import SAMPLE_RATE


class _FluxSynthetique:
    def __init__(self) -> None:
        self._callback = None
        self._demarre = False

    def __call__(self, callback):
        self._callback = callback
        return self

    def start(self) -> None:
        self._demarre = True

    def stop(self) -> None:
        self._demarre = False

    def close(self) -> None:
        pass

    def pousser(self, echantillons) -> None:
        if self._demarre and self._callback is not None:
            data = np.asarray(echantillons).reshape(-1)
            self._callback(data, data.size, None, None)


def _rms(echantillons: np.ndarray) -> float:
    arr = np.asarray(echantillons, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(arr))))


def _au_rms(signal: np.ndarray, cible: float) -> np.ndarray:
    actuel = _rms(signal)
    if actuel <= 0.0:
        return np.zeros(signal.size, dtype=np.int16)
    scaled = signal.astype(np.float64) * (cible / actuel)
    return np.clip(scaled, -32767, 32767).astype(np.int16)


def _voix(ms: int, amplitude: int = 8000) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    signal = np.zeros(n, dtype=np.float64)
    for harm in range(1, 12):
        signal += (1.0 / harm) * np.sin(2.0 * np.pi * 150.0 * harm * t)
    enveloppe = 0.65 + 0.35 * np.sin(2.0 * np.pi * 3.0 * t)
    signal *= enveloppe
    pic = np.max(np.abs(signal)) or 1.0
    scaled = np.clip(signal / pic * amplitude, -32767, 32767)
    return scaled.astype(np.int16)


def _bruit_blanc(ms: int, rms_cible: float) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    brut = np.random.default_rng(1).standard_normal(n)
    return _au_rms(brut, rms_cible)


def _sinus(ms: int, hz: float, rms_cible: float) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    return _au_rms(np.sin(2.0 * np.pi * hz * t), rms_cible)


def _silence(ms: int) -> np.ndarray:
    n = int(SAMPLE_RATE * ms / 1000.0)
    return np.zeros(n, dtype=np.int16)


def _nouvelle_capture(monkeypatch):
    monkeypatch.setenv("TURN_SILENCE_MS", "700")
    from native.hostagent.windows_audio import CaptureContinue

    flux = _FluxSynthetique()
    capture = CaptureContinue(stream_factory=flux)
    capture.start()
    flux.pousser(_silence(500))
    return capture, flux


def test_constante_facteur_seuil_lecture():
    from native.hostagent.windows_audio import FACTEUR_SEUIL_LECTURE

    assert FACTEUR_SEUIL_LECTURE == 2.5


def test_regime_lecture_existe_et_ne_suspend_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    assert callable(getattr(capture, "regime_lecture"))
    capture.regime_lecture(True)
    assert capture._suspendu is False
    flux.pousser(_silence(100))
    assert capture.segment_pret() is False
    capture.stop()


def test_euh_100ms_ne_declenche_pas_en_lecture(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_voix(100))
    flux.pousser(_silence(200))
    assert capture.barge_in.is_set() is False
    assert capture.segment_pret() is False
    capture.stop()


def test_voix_400ms_forte_et_bande_declenche_barge_in(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_voix(400, amplitude=8000))
    assert capture.barge_in.is_set() is True
    assert capture._tour or capture._preambule
    capture.stop()


def test_voix_sous_seuil_lecture_ne_declenche_pas(monkeypatch):
    """Le seuil calibre (silence → plancher 150) × 2,5 = 375.

    Une voix à RMS 250 passerait en régime normal, pas pendant la lecture.
    """
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_au_rms(_voix(500).astype(np.float64), 250.0))
    assert capture.barge_in.is_set() is False
    capture.stop()


def test_bruit_fort_hors_bande_ne_declenche_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_bruit_blanc(500, 8000.0))
    assert capture.barge_in.is_set() is False
    capture.stop()


def test_grave_50hz_fort_ne_declenche_pas(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_sinus(500, 50.0, 8000.0))
    assert capture.barge_in.is_set() is False
    capture.stop()


def test_barge_in_conserve_laudio_comme_debut_du_tour(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_voix(400, amplitude=8000))
    assert capture.barge_in.is_set() is True
    n_avant = len(capture._tour)
    assert n_avant > 0
    capture.regime_lecture(False)
    assert len(capture._tour) == n_avant
    flux.pousser(_voix(400, amplitude=8000))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True
    segment = capture.prendre_segment()
    assert len(segment) >= n_avant
    capture.stop()


def test_sortir_du_regime_sans_barge_in_jette_lecho(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    capture.regime_lecture(True)
    flux.pousser(_voix(100, amplitude=8000))
    assert capture.barge_in.is_set() is False
    capture.regime_lecture(False)
    assert capture._tour == []
    assert capture._preambule == []
    capture.stop()


def test_instantane_expose_seuil_rms_accumulation(monkeypatch):
    capture, flux = _nouvelle_capture(monkeypatch)
    snap = capture.instantane()
    assert "seuil" in snap
    assert "rms" in snap
    assert "accumulation" in snap
    from native.hostagent.windows_audio import PLANCHER_RMS

    assert snap["seuil"] >= PLANCHER_RMS
    capture.regime_lecture(True)
    flux.pousser(_voix(400, amplitude=8000))
    snap = capture.instantane()
    assert snap["accumulation"] is True
    assert snap["rms"] > 0.0
    capture.stop()


def test_ligne_pouls_ml_porte_les_chiffres():
    pytest.importorskip("tkinter")
    from native.presence.app import ligne_pouls_ml

    class Capture:
        def instantane(self):
            return {
                "seuil": 150.0,
                "rms": 42.0,
                "accumulation": True,
                "suspendue": False,
            }

    ligne = ligne_pouls_ml(
        Capture(), n_segments=4, en_lecture=False, couper=True
    )
    assert ligne.startswith("ML : vivante, 4 segment(s) envoye(s)")
    assert "lecture=non" in ligne
    assert "suspendue=non" in ligne
    assert "seuil=150" in ligne
    assert "rms=42" in ligne
    assert "accumulation=oui" in ligne
    assert "couper=oui" in ligne


class FauxWs:
    def __init__(self, messages):
        self.messages = [json.dumps(m) for m in messages]
        self.envois = []

    def send(self, brut: str) -> None:
        self.envois.append(brut)

    def recv(self):
        if not self.messages:
            raise AssertionError("recv au-delà du contrat")
        return self.messages.pop(0)


class FausseSortie:
    def __init__(self):
        self.jete = 0

    def abort(self) -> None:
        self.jete += 1


class CaptureEspion:
    def __init__(self) -> None:
        self.regimes: list[bool] = []
        self.suspensions = 0
        self.reprises = 0
        self.barge_in = threading.Event()
        self._suspendu = False

    def regime_lecture(self, actif: bool, on_barge_in=None) -> None:
        self.regimes.append(bool(actif))
        self._on_barge_in = on_barge_in
        if actif:
            self._suspendu = False

    def suspendre(self) -> None:
        self.suspensions += 1
        self._suspendu = True

    def reprendre(self) -> None:
        self.reprises += 1
        self._suspendu = False

    def instantane(self) -> dict:
        return {
            "seuil": 150.0,
            "rms": 10.0,
            "accumulation": False,
            "suspendue": self._suspendu,
        }


def _session():
    from native.presence.app import SessionVocale

    return SessionVocale(
        queue.Queue(),
        url="ws://127.0.0.1:9/hostagent",
        device=None,
        sortie=None,
        raccourci_label="Espace",
        mains_libres=True,
    )


def test_expedier_desarme_un_stop_stale_avant_le_tour():
    pytest.importorskip("tkinter")
    import native.presence.app as app

    joues = []

    class FauxMoteur:
        _reposer = staticmethod(lambda sortie: None)

        @staticmethod
        def _jouer(sortie, echantillons):
            joues.append(list(echantillons))

    app.moteur = FauxMoteur
    session = _session()
    session.couper.set()
    capture = CaptureEspion()
    ws = FauxWs([{"frames": [[0.1]]}, {"frames": []}])
    sortie = FausseSortie()
    trames = [type("T", (), {"samples": np.zeros(320, dtype=np.float32)})()]

    session._expedier_tour_continu(ws, capture, sortie, trames)

    assert joues == [[0.1]]
    assert sortie.jete == 0
    assert not session.couper.is_set()


def test_expedier_arme_regime_lecture_sans_suspendre():
    pytest.importorskip("tkinter")
    import native.presence.app as app

    joues = []

    class FauxMoteur:
        _reposer = staticmethod(lambda sortie: None)

        @staticmethod
        def _jouer(sortie, echantillons):
            joues.append(list(echantillons))

    app.moteur = FauxMoteur
    session = _session()
    capture = CaptureEspion()
    ws = FauxWs([{"frames": [[0.1]]}, {"frames": []}])
    sortie = FausseSortie()
    trames = [type("T", (), {"samples": np.zeros(320, dtype=np.float32)})()]

    session._expedier_tour_continu(ws, capture, sortie, trames)

    assert capture.suspensions == 0
    assert True in capture.regimes
    assert False in capture.regimes
    assert joues == [[0.1]]


def test_barge_in_vocal_coupe_la_voix_sans_jeter_la_capture():
    pytest.importorskip("tkinter")
    import native.presence.app as app

    capture = CaptureEspion()
    sortie = FausseSortie()

    class FauxMoteur:
        _reposer = staticmethod(lambda s: None)

        @staticmethod
        def _jouer(s, echantillons):
            capture.barge_in.set()

    app.moteur = FauxMoteur
    ws = FauxWs([{"frames": [[0.1]]}, {"frames": [[0.2]]}, {"frames": []}])
    barge = app.consommer_reponse(
        ws,
        sortie,
        0.0,
        lambda m: None,
        threading.Event(),
        interrompre=app.evenement_interruption_lecture(threading.Event(), capture),
        couper=threading.Event(),
        sur_interruption=lambda: app.apres_barge_in(capture),
    )
    assert barge is True
    assert sortie.jete == 1
    assert capture.reprises == 0
    assert ws.messages == []


def _application(tmp_path: Path, *, mains_libres: bool = True):
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    from native.presence.app import Application, analyser_arguments
    from native.presence.onboarding import (
        ConfigurationPresence,
        enregistrer_configuration,
    )

    chemin = tmp_path / "presence.json"
    enregistrer_configuration(
        ConfigurationPresence(onboarding_termine=True, mains_libres=mains_libres),
        chemin,
    )
    args = analyser_arguments(["--onboarding", "--config", str(chemin)])
    try:
        application = Application(args)
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    application.session_lancee = True
    application._afficher_application()
    application.racine.withdraw()
    application.racine.update_idletasks()
    return application


def test_stop_en_lecture_coupe_sans_tuer_mains_libres(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        application._conversation_ouverte = True
        application._conversation_restant_s = 41.0
        application.session.en_lecture.set()
        application.couper_voix()
        assert application.session.couper.is_set()
        assert application.configuration.mains_libres is True
        assert application.session.mains_libres is True
        assert application._conversation_ouverte is True
        assert application._conversation_restant_s == 41.0
    finally:
        application.fermer()


def test_stop_juste_apres_lecture_n_arme_pas_couper(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        application._conversation_ouverte = True
        application._conversation_restant_s = 41.0
        application.session.en_lecture.clear()
        application.couper_voix()
        assert application.session.couper.is_set()
        assert application.configuration.mains_libres is True
        assert application.session.mains_libres is True
        assert application._conversation_ouverte is True
        assert application._conversation_restant_s == 41.0
    finally:
        application.fermer()
