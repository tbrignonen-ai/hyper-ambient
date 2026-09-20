"""Stop TTS + mains libres en toggle (pas hold). Sans lancer Presence."""
from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from native.presence.app import (
    action_appui_parler,
    consommer_reponse,
    echap_coupe_la_voix,
    est_repetition_clavier,
    libelle_bouton_parler,
    relache_termine_lecoute,
)
from native.presence.onboarding import sequences_relache_extra


def test_appui_parler_hold_vs_toggle():
    assert action_appui_parler(mains_libres=False, ecoute_active=False) == "hold"
    assert action_appui_parler(mains_libres=False, ecoute_active=True) == "hold"
    assert action_appui_parler(mains_libres=True, ecoute_active=False) == "start"
    assert action_appui_parler(mains_libres=True, ecoute_active=True) == "send"


def test_relache_ne_termine_pas_en_mains_libres():
    assert relache_termine_lecoute(False) is True
    assert relache_termine_lecoute(True) is False


def test_libelle_bouton_parler_ecoute_puis_envoyer():
    u = {
        "speak": "Parler",
        "speaking": "Parler…",
        "listening_toggle": "Écoute…",
        "tap_to_send": "Appuie pour envoyer",
    }
    assert libelle_bouton_parler(
        mains_libres=False, ecoute_active=False, touche_enfoncee=False, textes=u
    ) == "Parler"
    assert libelle_bouton_parler(
        mains_libres=False, ecoute_active=False, touche_enfoncee=True, textes=u
    ) == "Parler…"
    assert libelle_bouton_parler(
        mains_libres=True, ecoute_active=False, touche_enfoncee=False, textes=u
    ) == "Parler"
    assert libelle_bouton_parler(
        mains_libres=True, ecoute_active=True, touche_enfoncee=True, textes=u
    ) == "Écoute…"
    assert libelle_bouton_parler(
        mains_libres=True, ecoute_active=True, touche_enfoncee=False, textes=u
    ) == "Appuie pour envoyer"


def test_repetition_clavier_pas_clic_souris():
    class Clavier:
        keysym = "space"

    class Souris:
        keysym = "??"

    assert est_repetition_clavier(True, Clavier()) is True
    assert est_repetition_clavier(True, Souris()) is False
    assert est_repetition_clavier(True, None) is True
    assert est_repetition_clavier(False, Clavier()) is False


def test_ctrl_space_a_un_relache_sans_modificateur():
    assert sequences_relache_extra("space") == ()
    assert sequences_relache_extra("ctrl-space") == ("<KeyRelease-space>",)


def test_echap_coupe_si_lecture_sinon_quitte():
    assert echap_coupe_la_voix(True) is True
    assert echap_coupe_la_voix(False) is False


def test_i18n_stop_et_etats_ecoute_envoi_fr_en(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "fr")
    from src.i18n import t, ui

    fr = ui()
    assert fr["stop"]
    assert "Interrompue" in fr["interrupted"]
    assert "Écoute" in fr["listening_toggle"]
    assert "Envoi" in fr["sending"]
    assert "Appuie pour envoyer" in fr["tap_to_send"]
    assert "réappuie" in fr["listening_tap_send"].lower()
    assert "appuy" in fr["hands_free_on"].lower() or "Parler" in fr["hands_free_on"]
    assert "mainten" not in fr["hands_free_hint"].lower()
    assert "micro" in fr["hands_free_hint"].lower()
    assert "Stop" in t("ui.stop") or "Arrêt" in t("ui.stop")

    monkeypatch.setenv("HA_LANG", "en")
    from src.i18n import ui as ui_en

    en = ui_en()
    assert en["stop"]
    assert "interrupt" in en["interrupted"].lower()
    assert "listen" in en["listening_toggle"].lower()
    assert "send" in en["sending"].lower()
    assert "press" in en["tap_to_send"].lower() and "send" in en["tap_to_send"].lower()
    assert "press again" in en["listening_tap_send"].lower()
    assert "hold" not in en["hands_free_on"].lower()
    assert "hold" not in en["hands_free_hint"].lower()


class FauxWs:
    def __init__(self, messages):
        self.messages = [json.dumps(m) for m in messages]

    def recv(self):
        return self.messages.pop(0)


class FausseSortie:
    def __init__(self):
        self.jete = 0

    def abort(self):
        self.jete += 1


def test_stop_coupe_sans_demarrer_la_capture():
    joues, captures, statuts = [], [], []

    class FauxMoteur:
        _reposer = staticmethod(lambda sortie: None)

        @staticmethod
        def _jouer(sortie, echantillons):
            joues.append(list(echantillons))

    import native.presence.app as app

    app.moteur = FauxMoteur
    couper = threading.Event()
    couper.set()
    ws = FauxWs(
        [
            {"frames": [[0.1]]},
            {"frames": [[0.2]]},
            {"type": "report", "transcript": "t", "reply": "r"},
            {"frames": []},
        ]
    )
    barge = consommer_reponse(
        ws,
        FausseSortie(),
        0.0,
        lambda m: statuts.append(m),
        threading.Event(),
        interrompre=threading.Event(),
        couper=couper,
        sur_interruption=lambda: captures.append(1),
    )
    assert barge is False
    assert joues == []
    assert captures == []
    assert any(
        "Interrompue" in str(m.get("texte") or "")
        for m in statuts
        if m.get("type") == "statut"
    )
    assert ws.messages == []


def test_stop_en_cours_de_paquet_jette_le_tampon():
    joues, captures = [], []
    couper = threading.Event()
    sortie = FausseSortie()

    class FauxMoteur:
        _reposer = staticmethod(lambda s: None)

        @staticmethod
        def _jouer(s, echantillons):
            joues.append(list(echantillons))
            couper.set()

    import native.presence.app as app

    app.moteur = FauxMoteur
    ws = FauxWs([{"frames": [[0.1]]}, {"frames": [[0.2]]}, {"frames": []}])
    barge = consommer_reponse(
        ws,
        sortie,
        0.0,
        lambda m: None,
        threading.Event(),
        interrompre=threading.Event(),
        couper=couper,
        sur_interruption=lambda: captures.append(1),
    )
    assert barge is False
    assert joues == [[0.1]]
    assert sortie.jete == 1
    assert captures == []


def _application(tmp_path: Path, *, mains_libres: bool = False):
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    from native.presence.app import Application, analyser_arguments
    from native.presence.onboarding import ConfigurationPresence, enregistrer_configuration

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


def test_ui_stop_hold_et_toggle(tmp_path):
    application = _application(tmp_path, mains_libres=False)
    try:
        bouton = application.bouton_stop
        assert bouton is not None
        assert str(bouton.cget("takefocus")) in ("1", "true")
        assert bouton.cget("highlightthickness")
        assert bouton.cget("text")
        application.session.canal_pret.set()
        application.couper_voix()
        assert application.session.couper.is_set()
        assert "Interrompue" in application.texte_statut

        application.session.couper.clear()
        quitte = []
        vrai_fermer = application.fermer
        application.fermer = lambda *_a, **_k: quitte.append(True)
        application.session.en_lecture.set()
        assert application._echap() == "break"
        assert application.session.couper.is_set()
        assert quitte == []
        application.session.en_lecture.clear()
        application.session.couper.clear()
        application._echap()
        assert quitte == [True]
        application.fermer = vrai_fermer

        application.enfoncer()
        assert application.session.tenu.is_set()
        application.relacher()
        assert not application.session.tenu.is_set()

        application._basculer_mains_libres()
        assert application.configuration.mains_libres is True
        application.enfoncer()
        assert application.session.tenu.is_set()
        application.relacher()
        assert application.session.tenu.is_set()
        assert "Écoute" in application.texte_statut
        application.enfoncer()
        assert not application.session.tenu.is_set()
        assert "Envoi" in application.texte_statut
        application.relacher()
        assert not application.session.tenu.is_set()
    finally:
        try:
            application.racine.destroy()
        except Exception:
            pass


def test_boucle_reste_en_ecoute_tant_que_tenu(tmp_path):
    from native.presence.app import SessionVocale

    class Capture:
        def __init__(self):
            self.demarrages = 0
            self.arrets = 0

        def start(self):
            self.demarrages += 1

        def stop(self):
            self.arrets += 1
            return []

    class Ws:
        def send(self, _brut: str) -> None:
            raise AssertionError("pas d'envoi : aucune trame")

        def recv(self) -> str:
            raise AssertionError("recv hors contrat")

    session = SessionVocale(
        queue.Queue(),
        url="ws://127.0.0.1:9/hostagent",
        device=None,
        sortie=None,
        raccourci_label="Espace",
        mains_libres=True,
    )
    capture = Capture()
    session.tenu.set()

    def tuer() -> None:
        time.sleep(0.25)
        assert capture.demarrages == 1
        assert capture.arrets == 0
        session.tenu.clear()
        time.sleep(0.12)
        session.arreter.set()

    threading.Thread(target=tuer, daemon=True).start()
    session._boucle_tours(Ws(), capture, FausseSortie())
    assert capture.demarrages == 1
    assert capture.arrets == 1


class _EvtEspace:
    keysym = "space"


class _EvtSouris:
    keysym = "??"


def test_bascule_sync_session_et_relache_affiche_envoyer(tmp_path):
    application = _application(tmp_path, mains_libres=False)
    journaux: list[str] = []
    import native.presence.app as app_mod

    vrai = app_mod.journaliser
    try:
        app_mod.journaliser = lambda *a, **_k: journaux.append(" ".join(str(x) for x in a))
        application.session.canal_pret.set()
        assert application.session.mains_libres is False
        application._basculer_mains_libres()
        assert application.configuration.mains_libres is True
        assert application.session.mains_libres is True
        application.enfoncer()
        assert application.ecoute_basculee is True
        assert any("mains_libres=ON start" in ligne for ligne in journaux)
        assert "Écoute" in application.bouton.cget("text")
        application.relacher()
        assert application.session.tenu.is_set()
        assert "Appuie pour envoyer" in application.bouton.cget("text")
        assert "réappuie" in application.texte_statut.lower()
        application.enfoncer()
        assert any("mains_libres=ON send" in ligne for ligne in journaux)
        assert "Envoi" in application.texte_statut
    finally:
        app_mod.journaliser = vrai
        try:
            application.racine.destroy()
        except Exception:
            pass


def test_raccourci_marche_si_focus_sur_bouton_mains_libres(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        application.session.canal_pret.set()
        application.bouton_mains_libres.focus_set()
        application.racine.update_idletasks()
        assert application._focus_autorise_ptt() is True
        assert application._espace_enfonce(_EvtEspace()) == "break"
        assert application.session.tenu.is_set()
        assert application.ecoute_basculee is True
        assert application._espace_relache(_EvtEspace()) == "break"
        assert application.session.tenu.is_set()
        assert application._espace_enfonce(_EvtEspace()) == "break"
        assert not application.session.tenu.is_set()
    finally:
        try:
            application.racine.destroy()
        except Exception:
            pass


def test_clic_souris_envoie_malgre_touche_coincee(tmp_path):
    application = _application(tmp_path, mains_libres=True)
    try:
        application.session.canal_pret.set()
        application.enfoncer()
        application._touche_parler_enfoncee = True
        application.enfoncer(_EvtSouris())
        assert not application.session.tenu.is_set()
        assert application.ecoute_basculee is False
    finally:
        try:
            application.racine.destroy()
        except Exception:
            pass
