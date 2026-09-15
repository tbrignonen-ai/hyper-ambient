"""
talk.py : deuxieme nappe d'edges hors WASAPI-oreille (vague F).

La nappe D (test_talk_diagnostic_wasapi.py) pince listing etiquete, --api,
--sortie prioritaire, bip 16 kHz. Ici : secret, URL IPv4, poignee de main,
_tour (trames vides, error, JSON, rapport muet, sleep), presence UDP,
choisir_peripherique (USB prefere, indice, fragment, defaut), lire_secret,
importeurs absents, _jouer vide, OutputStream qui leve, stop qui leve.
Aucune carte son, aucun WebSocket reel.
"""
from __future__ import annotations

import json
import socket
import sys

import numpy as np
import pytest

import native.hostagent.talk as talk
from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame


class _Flux:
    def __init__(self, journal, *, lever_write=False, lever_stop=False, lever_start=False):
        self._journal = journal
        self._lever_write = lever_write
        self._lever_stop = lever_stop
        self._lever_start = lever_start
        self.ecrits = []
        self.ferme = False
        self.channels = 2

    def start(self):
        self._journal.append("start")
        if self._lever_start:
            raise RuntimeError("Error opening OutputStream: Invalid sample rate")

    def write(self, data):
        self._journal.append("write")
        if self._lever_write:
            raise RuntimeError("écriture refusée")
        self.ecrits.append(data)

    def stop(self):
        self._journal.append("stop")
        if self._lever_stop:
            raise RuntimeError("stop casse")

    def close(self):
        self.ferme = True
        self._journal.append("close")


class _SoundDevice:
    def __init__(
        self,
        peripheriques,
        *,
        hostapis=None,
        lever_requete=None,
        lever_ouverture=None,
        default_in=None,
        flux=None,
    ):
        self._peripheriques = list(peripheriques)
        self._hostapis = list(hostapis) if hostapis is not None else [
            {"name": "MME"},
            {"name": "Windows WASAPI"},
        ]
        self.journal = []
        self.appels_output = []
        self.appels_input = []
        self.lever_requete = lever_requete
        self.lever_ouverture = lever_ouverture
        self.flux = flux or _Flux(self.journal)
        self.default = type("default", (), {"samplerate": SAMPLE_RATE, "device": (default_in, 0)})()

    def query_hostapis(self):
        return list(self._hostapis)

    def query_devices(self, *args, **kwargs):
        if self.lever_requete is not None:
            raise self.lever_requete
        if args:
            return self._peripheriques[args[0]]
        if "kind" in kwargs:
            kind = kwargs["kind"]
            for p in self._peripheriques:
                if kind == "input" and p["max_input_channels"] > 0:
                    return p
                if kind == "output" and p["max_output_channels"] > 0:
                    return p
            raise ValueError(f"aucun périphérique {kind}")
        return list(self._peripheriques)

    def OutputStream(self, **kwargs):
        self.journal.append("open")
        self.appels_output.append(kwargs)
        if self.lever_ouverture is not None:
            raise self.lever_ouverture
        return self.flux

    def InputStream(self, **kwargs):
        self.appels_input.append(kwargs)
        return self.flux


PERIPHS = [
    {
        "name": "Carte interne",
        "max_input_channels": 2,
        "max_output_channels": 0,
        "default_samplerate": 44100.0,
        "hostapi": 0,
    },
    {
        "name": "USB Desk Microphone (Rift)",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 48000.0,
        "hostapi": 1,
    },
    {
        "name": "HP interne",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 1,
    },
    {
        "name": "Casque USB",
        "max_input_channels": 1,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 1,
    },
]


def _lancer_main(monkeypatch, sd, *options):
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("diagnostic : pas de WebSocket")
    ))
    monkeypatch.setattr(sys, "argv", ["talk.py", *options])
    try:
        talk.main()
    except SystemExit as exc:
        assert exc.code in (0, None), f"code {exc.code}"


# -- constantes / secret / URL ------------------------------------------------


def test_url_defaut_est_ipv4_pas_localhost():
    assert talk.URL_DEFAUT.startswith("ws://127.0.0.1:")
    assert "localhost" not in talk.URL_DEFAUT
    assert "::1" not in talk.URL_DEFAUT
    assert talk.URL_DEFAUT.endswith("/hostagent")


def test_micro_prefere_inclut_usb_pnp_et_usb_desk():
    assert "USB PnP" in talk.NOM_MICRO_PREFERE
    assert "USB Desk Microphone" in talk.NOM_MICRO_PREFERE


def test_lire_secret_prend_l_env(monkeypatch, capsys):
    monkeypatch.setenv("MOTHER_HOSTAGENT_SECRET", "s3cret-demo")
    assert talk.lire_secret() == "s3cret-demo"
    assert capsys.readouterr().err == ""


def test_lire_secret_sans_env_avertit_et_prend_le_dev(monkeypatch, capsys):
    monkeypatch.delenv("MOTHER_HOSTAGENT_SECRET", raising=False)
    assert talk.lire_secret() == talk.SECRET_DEVELOPPEMENT
    err = capsys.readouterr().err
    assert "ATTENTION" in err
    assert "partage-installation" in err


def test_sample_rate_demo_est_16000():
    assert SAMPLE_RATE == 16000


# -- listing / resolution -----------------------------------------------------


def test_lister_dit_canal_au_singulier():
    texte = talk.lister_peripheriques(_SoundDevice(PERIPHS))
    assert "1 canal" in texte
    assert "2 canaux" in texte
    assert "1 canaux" not in texte


def test_lister_hostapi_non_entier_sans_crochet():
    periphs = [{
        "name": "Etrange",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": "1",
    }]
    ligne = [
        l for l in talk.lister_peripheriques(_SoundDevice(periphs)).splitlines()
        if "Etrange" in l
    ][0]
    assert "[" not in ligne or "Windows" not in ligne


def test_lister_hostapi_none_sans_etiquette():
    periphs = [{
        "name": "SansAPI",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 16000.0,
        "hostapi": None,
    }]
    texte = talk.lister_peripheriques(_SoundDevice(periphs))
    assert "SansAPI" in texte
    assert "Windows WASAPI" not in texte.split("SansAPI", 1)[1].split("\n", 1)[0]


def test_resoudre_api_strip_et_casse():
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    idx = talk.resoudre_peripherique_api("  WaSaPi  ", PERIPHS, hostapis)
    assert PERIPHS[idx]["name"] == "HP interne"


def test_resoudre_api_premier_du_role_gagne():
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    idx = talk.resoudre_peripherique_api(
        "wasapi", PERIPHS, hostapis, role="max_output_channels",
    )
    assert idx == 2
    idx_in = talk.resoudre_peripherique_api(
        "wasapi", PERIPHS, hostapis, role="max_input_channels",
    )
    assert idx_in == 1


def test_choisir_peripherique_prefere_le_usb_desk(capsys):
    sd = _SoundDevice(PERIPHS)
    idx = talk.choisir_peripherique(None, sd)
    assert idx == 1
    assert "USB Desk Microphone" in capsys.readouterr().out


def test_choisir_peripherique_prefere_usb_pnp_tronque_mme(capsys):
    periphs = [
        {
            "name": "Mappeur de sons Microsoft - Input",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
            "hostapi": 0,
        },
        {
            "name": "Microphone (2- USB PnP Sound De",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
            "hostapi": 0,
        },
        {
            "name": "Digital-In (Sound Blaster Z)",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
            "hostapi": 0,
        },
    ]
    sd = _SoundDevice(periphs)
    idx = talk.choisir_peripherique(None, sd)
    assert idx == 1
    assert "USB PnP Sound De" in capsys.readouterr().out


def test_choisir_peripherique_priorite_usb_pnp_sur_usb_desk(capsys):
    periphs = [
        {
            "name": "USB Desk Microphone (Rift)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "hostapi": 1,
        },
        {
            "name": "Microphone (2- USB PnP Sound Device)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "hostapi": 1,
        },
    ]
    sd = _SoundDevice(periphs)
    idx = talk.choisir_peripherique(None, sd)
    assert idx == 1
    assert "USB PnP Sound Device" in capsys.readouterr().out


def test_choisir_peripherique_override_chaine_unique(monkeypatch, capsys):
    monkeypatch.setattr(talk, "NOM_MICRO_PREFERE", "Micro Custom")
    periphs = [
        {
            "name": "Microphone Standard",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
        {
            "name": "Mon Micro Custom Studio",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        },
    ]
    sd = _SoundDevice(periphs)
    idx = talk.choisir_peripherique(None, sd)
    assert idx == 1
    assert "Mon Micro Custom Studio" in capsys.readouterr().out


def test_choisir_peripherique_par_indice(capsys):
    sd = _SoundDevice(PERIPHS)
    idx = talk.choisir_peripherique("0", sd)
    assert idx == 0
    assert "Carte interne" in capsys.readouterr().out


def test_choisir_peripherique_par_fragment_insensible_a_la_casse(capsys):
    sd = _SoundDevice(PERIPHS)
    idx = talk.choisir_peripherique("casque", sd)
    assert idx == 3
    assert "Casque USB" in capsys.readouterr().out


def test_choisir_peripherique_fragment_inconnu_code_1(capsys):
    sd = _SoundDevice(PERIPHS)
    with pytest.raises(SystemExit) as exc:
        talk.choisir_peripherique("nexiste-pas", sd)
    assert exc.value.code == 1
    assert "nexiste-pas" in capsys.readouterr().out


def test_choisir_peripherique_defaut_systeme_si_pas_de_usb(capsys):
    sans_usb = [p for p in PERIPHS if "USB Desk" not in p["name"]]
    sd = _SoundDevice(sans_usb)
    idx = talk.choisir_peripherique(None, sd)
    assert sans_usb[idx]["name"] == "Carte interne"
    assert "défaut système" in capsys.readouterr().out


def test_choisir_peripherique_fallback_default_device():
    """kind=input rend un nom absent de la liste → sd.default.device[0]."""
    periphs = [{
        "name": "Micro fantome",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 16000.0,
        "hostapi": 0,
    }]

    class Sd(_SoundDevice):
        def query_devices(self, *args, **kwargs):
            if kwargs.get("kind") == "input":
                return {"name": "Pas dans la liste", "max_input_channels": 1}
            return super().query_devices(*args, **kwargs)

    sd = Sd(periphs, default_in=7)
    assert talk.choisir_peripherique(None, sd) == 7


def test_choisir_sortie_par_indice_numerique(capsys):
    sd = _SoundDevice(PERIPHS)
    idx = talk.choisir_sortie("2", sd)
    assert idx == 2
    assert "HP interne" in capsys.readouterr().out


def test_choisir_sortie_requete_qui_leve_phrase_francaise(capsys):
    sd = _SoundDevice(PERIPHS, lever_requete=RuntimeError("Invalid device"))
    with pytest.raises(SystemExit) as exc:
        talk.choisir_sortie("2", sd)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "périphérique" in out.lower() or "peripherique" in out.lower()
    assert "Invalid device" not in out
    assert "Traceback" not in out


# -- flux sortie / jouer ------------------------------------------------------


def test_jouer_tableau_vide_n_ecrit_pas():
    class Sortie:
        channels = 2
        def __init__(self):
            self.n = 0
        def write(self, bloc):
            self.n += 1

    sortie = Sortie()
    talk._jouer(sortie, np.array([], dtype=np.float32))
    assert sortie.n == 0


def test_jouer_sans_attr_channels_reste_mono():
    class Sortie:
        def __init__(self):
            self.blocs = []
            self.active = False
        def start(self):
            self.active = True
        def stop(self):
            self.active = False
        def write(self, bloc):
            self.blocs.append(np.asarray(bloc))

    sortie = Sortie()
    talk._jouer(sortie, np.array([0.5, -0.5], dtype=np.float32))
    assert sortie.blocs[0].shape == (2, 1)
    # Le demarrage paresseux fait partie du contrat de `_jouer` depuis le
    # 8 septembre : un flux laisse actif dans le silence souffle en underflow.
    assert sortie.active is True


def test_ouvrir_sortie_sans_indice_n_envoie_pas_device(capsys):
    sd = _SoundDevice(PERIPHS)
    flux = talk._ouvrir_sortie(sd, indice=None)
    assert "device" not in sd.appels_output[0]
    assert flux.channels == 2
    assert "16 kHz" in capsys.readouterr().out


def test_ouvrir_sortie_qui_leve_se_dit_en_francais(capsys):
    sd = _SoundDevice(
        PERIPHS,
        lever_ouverture=RuntimeError("Error opening OutputStream: Device or resource busy"),
    )
    with pytest.raises(SystemExit) as exc:
        talk._ouvrir_sortie(sd, indice=2)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "occup" in out.lower()
    assert "Device or resource busy" not in out


def test_tester_sortie_ferme_meme_si_stop_leve():
    flux = _Flux([], lever_stop=True)
    sd = _SoundDevice(PERIPHS, flux=flux)
    n = talk.tester_sortie(sd, indice=2, secondes=0.05)
    assert n == int(0.05 * SAMPLE_RATE)
    assert "close" in flux._journal
    assert flux.ferme is True


def test_tester_sortie_requete_qui_leve(capsys):
    sd = _SoundDevice(PERIPHS, lever_requete=RuntimeError("Device unavailable"))
    with pytest.raises(SystemExit) as exc:
        talk.tester_sortie(sd, indice=2)
    assert exc.value.code == 1
    assert "--lister" in capsys.readouterr().out


def test_canaux_negatif_est_un_echec_bruyant(capsys):
    with pytest.raises(SystemExit) as exc:
        talk.canaux_de_sortie(-1)
    assert exc.value.code == 1
    assert "canal" in capsys.readouterr().out.lower()


def test_est_erreur_audio_marqueurs_restants():
    assert talk._est_erreur_audio(RuntimeError("Invalid device"))
    assert talk._est_erreur_audio(RuntimeError("device unavailable"))
    assert talk._est_erreur_audio(RuntimeError("in use by Zoom"))
    assert talk._est_erreur_audio(RuntimeError("Error opening InputStream: boom"))
    assert talk._est_erreur_audio(RuntimeError("invalid number of channels"))
    assert not talk._est_erreur_audio(RuntimeError("Connection refused"))
    assert not talk._est_erreur_audio(OSError("Network is unreachable"))


# -- poignee / tour / presence ------------------------------------------------


def test_poignee_ready(capsys):
    class Ws:
        def __init__(self):
            self.envoyes = []
        def send(self, brut):
            self.envoyes.append(brut)
        def recv(self):
            return json.dumps({"type": "ready"})

    ws = Ws()
    talk._poignee_de_main(ws, "secret-x")
    assert json.loads(ws.envoyes[0]) == {"type": "hello", "secret": "secret-x"}
    assert "Canal prêt." in capsys.readouterr().out


def test_poignee_illisible_code_1(capsys):
    class Ws:
        def send(self, brut):
            pass
        def recv(self):
            return "pas-du-json"

    with pytest.raises(SystemExit) as exc:
        talk._poignee_de_main(Ws(), "s")
    assert exc.value.code == 1
    assert "illisible" in capsys.readouterr().out.lower()


def test_poignee_refusee_si_pas_ready(capsys):
    class Ws:
        def send(self, brut):
            pass
        def recv(self):
            return json.dumps({"type": "error", "reason": "bad secret"})

    with pytest.raises(SystemExit) as exc:
        talk._poignee_de_main(Ws(), "s")
    assert exc.value.code == 1
    assert "refus" in capsys.readouterr().out.lower()


def test_tour_aucune_trame_ne_envoie_pas(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    sleeps = []
    monkeypatch.setattr(talk.time, "sleep", lambda s: sleeps.append(s))

    class Ws:
        def __init__(self):
            self.envoyes = []
        def send(self, brut):
            self.envoyes.append(brut)
        def recv(self):
            raise AssertionError("pas de recv si aucune trame")

    class Capture:
        def start(self):
            pass
        def stop(self):
            return []

    talk._tour(Ws(), Capture(), type("S", (), {"channels": 1, "write": lambda *a, **k: None})())
    assert "Aucune trame capturée" in capsys.readouterr().out
    assert sleeps == []


def test_tour_type_error_ne_joue_pas(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    sleeps = []
    monkeypatch.setattr(talk.time, "sleep", lambda s: sleeps.append(s))

    class Ws:
        def __init__(self):
            self.envoyes = []
            self.restants = [{"type": "error", "message": "brain down"}]
        def send(self, brut):
            self.envoyes.append(brut)
        def recv(self):
            return json.dumps(self.restants.pop(0))

    class Capture:
        def start(self):
            pass
        def stop(self):
            return [AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32))]

    class Sortie:
        channels = 1
        def write(self, bloc):
            raise AssertionError("pas de restitution sur error")

    talk._tour(Ws(), Capture(), Sortie())
    assert "Erreur du transport" in capsys.readouterr().out
    assert sleeps == []


def test_tour_json_illisible_abandonne(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")

    class Ws:
        def send(self, brut):
            pass
        def recv(self):
            return "{{{{"

    class Capture:
        def start(self):
            pass
        def stop(self):
            return [AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32))]

    talk._tour(Ws(), Capture(), type("S", (), {"channels": 1, "write": lambda *a, **k: None})())
    assert "illisible" in capsys.readouterr().out.lower()


def test_tour_rapport_vide_ne_imprime_pas_les_labels(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    sleeps = []
    monkeypatch.setattr(talk.time, "sleep", lambda s: sleeps.append(s))

    class Ws:
        def __init__(self):
            self.envoyes = []
            self.restants = [
                {"type": "report", "transcript": "  ", "reply": ""},
                {"frames": None},
                {"frames": []},
            ]
        def send(self, brut):
            self.envoyes.append(json.loads(brut))
        def recv(self):
            return json.dumps(self.restants.pop(0))

    class Capture:
        def start(self):
            pass
        def stop(self):
            return [AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32))]

    talk._tour(Ws(), Capture(), type("S", (), {"channels": 1, "write": lambda *a, **k: None})())
    out = capsys.readouterr().out
    assert "compris :" not in out
    assert "réponse :" not in out
    assert "Aucune trame de réponse" in out
    assert sleeps == []


def test_tour_audio_appelle_sleep_et_mesure(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    sleeps = []
    monkeypatch.setattr(talk.time, "sleep", lambda s: sleeps.append(s))

    trame = [0.1] * FRAME_SAMPLES

    class Ws:
        def __init__(self):
            self.envoyes = []
            self.restants = [
                {"frames": [trame]},
                {"type": "report", "transcript": "salut", "reply": "oui"},
                {"frames": []},
            ]
        def send(self, brut):
            self.envoyes.append(json.loads(brut))
        def recv(self):
            return json.dumps(self.restants.pop(0))

    class Capture:
        def start(self):
            pass
        def stop(self):
            return [AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32))]

    class Sortie:
        channels = 1
        def __init__(self):
            self.n = 0
            self.active = False
        def start(self):
            self.active = True
        def stop(self):
            self.active = False
        def write(self, bloc):
            self.n += np.asarray(bloc).shape[0]

    ws, sortie = Ws(), Sortie()
    talk._tour(ws, Capture(), sortie)
    out = capsys.readouterr().out
    assert "mic_to_audible" in out
    assert "compris : salut" in out
    assert "réponse : oui" in out
    assert sleeps == [0.25]
    assert sortie.n == FRAME_SAMPLES
    invoke = ws.envoyes[0]
    assert invoke["type"] == "invoke"
    assert invoke["primitive"] == "audio.capture"
    assert isinstance(invoke["frames"][0], list)


def test_relayer_presence_off_n_ouvre_pas_de_socket(monkeypatch):
    monkeypatch.setenv("PRESENCE", "0")
    talk._douille_presence = None
    try:
        talk.relayer_etat({"type": "state", "label": "écoute"})
        assert talk._douille_presence is None
    finally:
        talk._douille_presence = None


def test_relayer_envoie_udp_local_non_bloquant(monkeypatch):
    monkeypatch.setenv("PRESENCE", "1")
    monkeypatch.setenv("PRESENCE_PORT", "8123")
    envoyes = []

    class FakeSock:
        def __init__(self, *a, **k):
            self.blocking = True
        def setblocking(self, flag):
            self.blocking = flag
        def sendto(self, data, addr):
            envoyes.append((data, addr))

    talk._douille_presence = None
    monkeypatch.setattr(socket, "socket", lambda *a, **k: FakeSock())
    try:
        talk.relayer_etat({"type": "state", "label": "écoute"})
        assert talk._douille_presence.blocking is False
        brut, addr = envoyes[0]
        assert addr == ("127.0.0.1", talk.PORT_PRESENCE)
        assert json.loads(brut.decode("utf-8"))["label"] == "écoute"
    finally:
        talk._douille_presence = None


def test_relayer_oserror_est_avale(monkeypatch):
    monkeypatch.setenv("PRESENCE", "1")

    class FakeSock:
        def setblocking(self, flag):
            pass
        def sendto(self, data, addr):
            raise OSError("personne n'écoute")

    talk._douille_presence = FakeSock()
    try:
        talk.relayer_etat({"type": "state"})
    finally:
        talk._douille_presence = None


def test_port_presence_est_fige_a_l_import():
    """PORT_PRESENCE est lu une fois au chargement du module, pas a chaque relais."""
    assert isinstance(talk.PORT_PRESENCE, int)
    assert talk.PORT_PRESENCE > 0


# -- importeurs / argparse ----------------------------------------------------


def test_importer_sounddevice_absent(monkeypatch, capsys):
    import builtins

    orig = builtins.__import__

    def boom(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sounddevice":
            raise ImportError("missing")
        return orig(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", boom)
    with pytest.raises(SystemExit) as exc:
        talk._importer_sounddevice()
    assert exc.value.code == 1
    assert "sounddevice" in capsys.readouterr().out.lower()


def test_importer_websockets_absent(monkeypatch, capsys):
    import builtins

    orig = builtins.__import__

    def boom(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "websockets.sync.client" or name == "websockets":
            raise ImportError("missing")
        return orig(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", boom)
    with pytest.raises(SystemExit) as exc:
        talk._importer_websockets()
    assert exc.value.code == 1
    out = capsys.readouterr().out.lower()
    assert "websockets" in out
    assert "pip install" in out


def test_argparse_refuse_api_inconnue(monkeypatch):
    sd = _SoundDevice(PERIPHS)
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(sys, "argv", ["talk.py", "--api", "asio"])
    with pytest.raises(SystemExit) as exc:
        talk.main()
    assert exc.value.code == 2


def test_lister_qui_leve_reste_une_phrase(monkeypatch, capsys):
    sd = _SoundDevice(PERIPHS, lever_requete=RuntimeError("Invalid device"))
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: (_ for _ in ()).throw(
        AssertionError("pas de ws")
    ))
    monkeypatch.setattr(sys, "argv", ["talk.py", "--lister"])
    with pytest.raises(SystemExit) as exc:
        talk.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Invalid device" not in out
    assert "Traceback" not in out
    assert "--lister" in out
