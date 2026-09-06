"""
talk.py : canaux audio, tour WebSocket, host API, finally de main (vague H).

D/F ont pince WASAPI, secret, poignee, USB, presence UDP. Ici le contrat
**canaux** encore nu :

  - 3+ sorties → stereo nominale, mot « canaux »,
  - duplex dans les deux sections,
  - `query_hostapis` qui leve → listing sans etiquette,
  - `_tour` relais `state`, deux paquets audio, type inconnu,
  - `_fabrique_entree` mono int16,
  - KeyboardInterrupt ferme quand meme la sortie,
  - `paerrorcode` reconnu comme audio.

Aucune carte son, aucun WebSocket reel, aucun llama-server.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pytest

import native.hostagent.talk as talk
from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame


class _Flux:
    def __init__(self, journal, *, lever_start=False):
        self._journal = journal
        self.ecrits = []
        self.ferme = False
        self.channels = 2
        self.stopped = False
        self._lever_start = lever_start

    def start(self):
        self._journal.append("start")
        if self._lever_start:
            raise RuntimeError("Error opening OutputStream: Invalid sample rate")

    def write(self, data):
        self._journal.append("write")
        self.ecrits.append(np.asarray(data))

    def stop(self):
        self.stopped = True
        self._journal.append("stop")

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
        lever_hostapis=None,
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
        self.lever_hostapis = lever_hostapis
        self.flux = flux or _Flux(self.journal)
        self.default = type("default", (), {"samplerate": SAMPLE_RATE, "device": (0, 0)})()

    def query_hostapis(self):
        if self.lever_hostapis is not None:
            raise self.lever_hostapis
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
        "name": "HP surround",
        "max_input_channels": 0,
        "max_output_channels": 8,
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
    {
        "name": "Micro mono MME",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 16000.0,
        "hostapi": 0,
    },
]


def _frame():
    return AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32))


# -- canaux -------------------------------------------------------------------


def test_canaux_trois_et_plus_deviennent_stereo():
    assert talk.canaux_de_sortie(3) == 2
    assert talk.canaux_de_sortie(6) == 2
    assert talk.canaux_de_sortie(2) == 2
    assert talk.canaux_de_sortie(1) == 1


def test_canaux_zero_et_none_code_1(capsys):
    for valeur in (0, None):
        with pytest.raises(SystemExit) as exc:
            talk.canaux_de_sortie(valeur)
        assert exc.value.code == 1
    assert "canal" in capsys.readouterr().out.lower()


def test_etaler_mono_reste_une_colonne():
    pcm = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    out = talk.etaler(pcm, 1)
    assert out.shape == (3, 1)
    assert out.dtype == np.float32
    np.testing.assert_array_equal(out[:, 0], pcm)


def test_etaler_stereo_duplique():
    pcm = np.array([0.5, -0.5], dtype=np.float32)
    out = talk.etaler(pcm, 2)
    assert out.shape == (2, 2)
    np.testing.assert_array_equal(out[:, 0], pcm)
    np.testing.assert_array_equal(out[:, 1], pcm)


def test_lister_huit_canaux_au_pluriel():
    texte = talk.lister_peripheriques(_SoundDevice(PERIPHS))
    assert "8 canaux" in texte
    assert "8 canal," not in texte
    assert "1 canal" in texte
    assert "1 canaux" not in texte


def test_lister_duplex_dans_les_deux_sections():
    texte = talk.lister_peripheriques(_SoundDevice(PERIPHS))
    entrees, sorties = texte.split("Sorties :", 1)
    assert "Casque USB" in entrees
    assert "Casque USB" in sorties
    assert "HP surround" not in entrees
    assert "USB Desk Microphone" not in sorties


def test_lister_query_hostapis_qui_leve_sans_etiquette():
    sd = _SoundDevice(PERIPHS, lever_hostapis=RuntimeError("PortAudio hostapis"))
    texte = talk.lister_peripheriques(sd)
    assert "Casque USB" in texte
    assert "WASAPI" not in texte
    assert "Traceback" not in texte


def test_lister_hostapi_hors_liste_sans_crochet_wasapi():
    periphs = [{
        "name": "Fantome",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 16000.0,
        "hostapi": 99,
    }]
    ligne = [
        l for l in talk.lister_peripheriques(_SoundDevice(periphs)).splitlines()
        if "Fantome" in l
    ][0]
    assert "WASAPI" not in ligne


def test_ouvrir_sortie_surround_annonce_deux_canaux(capsys):
    sd = _SoundDevice(PERIPHS)
    flux = talk._ouvrir_sortie(sd, indice=2)
    assert sd.appels_output[0]["channels"] == 2
    assert sd.appels_output[0]["samplerate"] == SAMPLE_RATE
    assert sd.appels_output[0]["device"] == 2
    assert flux.channels == 2
    out = capsys.readouterr().out
    assert "2 canaux" in out
    assert "16 kHz" in out


def test_ouvrir_sortie_indice_envoie_device():
    sd = _SoundDevice(PERIPHS)
    talk._ouvrir_sortie(sd, indice=3)
    assert sd.appels_output[0]["device"] == 3
    assert sd.appels_output[0]["dtype"] == "float32"


def test_fabrique_entree_mono_int16_indice():
    sd = _SoundDevice(PERIPHS)
    factory = talk._fabrique_entree(1, sd)
    flux = factory(lambda *a, **k: None)
    assert sd.appels_input[0]["device"] == 1
    assert sd.appels_input[0]["channels"] == 1
    assert sd.appels_input[0]["dtype"] == "int16"
    assert sd.appels_input[0]["samplerate"] == SAMPLE_RATE
    assert flux is sd.flux


def test_resoudre_indice_numerique_et_fragment():
    idx = talk._resoudre_indice("2", PERIPHS, canaux="max_output_channels", role="de sortie")
    assert idx == 2
    idx2 = talk._resoudre_indice("casque", PERIPHS, canaux="max_output_channels", role="de sortie")
    assert idx2 == 3


def test_resoudre_indice_inconnu_code_1(capsys):
    with pytest.raises(SystemExit) as exc:
        talk._resoudre_indice("nexiste-pas", PERIPHS, canaux="max_output_channels", role="de sortie")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "nexiste-pas" in out
    assert "--lister" in out


def test_choisir_sortie_par_api_wasapi(capsys):
    sd = _SoundDevice(PERIPHS)
    idx = talk.choisir_sortie(None, sd, api="wasapi")
    assert idx == 2
    assert "HP surround" in capsys.readouterr().out


def test_choisir_sortie_demande_gagne_sur_api():
    sd = _SoundDevice(PERIPHS)
    idx = talk.choisir_sortie("3", sd, api="mme")
    assert idx == 3


# -- tour / canal WebSocket ---------------------------------------------------


def test_tour_state_appelle_relayer(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    seen = []
    monkeypatch.setattr(talk, "relayer_etat", lambda m: seen.append(m))
    trame = [0.0] * FRAME_SAMPLES

    class Ws:
        def __init__(self):
            self.restants = [
                {"type": "state", "label": "écoute"},
                {"frames": [trame]},
                {"frames": []},
            ]
            self.envoyes = []

        def send(self, brut):
            self.envoyes.append(json.loads(brut))

        def recv(self):
            return json.dumps(self.restants.pop(0))

    class Sortie:
        channels = 1

        def write(self, bloc):
            pass

    class Capture:
        def start(self):
            pass

        def stop(self):
            return [_frame()]

    talk._tour(Ws(), Capture(), Sortie())
    assert seen == [{"type": "state", "label": "écoute"}]


def test_tour_deux_paquets_audio_avant_marqueur(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    sleeps = []
    monkeypatch.setattr(talk.time, "sleep", lambda s: sleeps.append(s))
    a = [0.1] * FRAME_SAMPLES
    b = [0.2] * FRAME_SAMPLES

    class Ws:
        def __init__(self):
            self.restants = [
                {"frames": [a]},
                {"type": "state", "label": "parle"},
                {"frames": [b, b]},
                {"frames": []},
            ]
            self.envoyes = []

        def send(self, brut):
            self.envoyes.append(brut)

        def recv(self):
            return json.dumps(self.restants.pop(0))

    class Sortie:
        channels = 1

        def __init__(self):
            self.n = 0

        def write(self, bloc):
            self.n += np.asarray(bloc).shape[0]

    sortie = Sortie()
    talk._tour(Ws(), type("C", (), {"start": lambda self: None, "stop": lambda self: [_frame()]})(), sortie)
    assert sortie.n == FRAME_SAMPLES * 3
    assert sleeps == [0.25]
    assert "mic_to_audible" in capsys.readouterr().out


def test_tour_type_inconnu_sans_frames_continue(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")

    class Ws:
        def __init__(self):
            self.restants = [
                {"type": "pong"},
                {"hello": True},
                {"frames": []},
            ]

        def send(self, brut):
            pass

        def recv(self):
            return json.dumps(self.restants.pop(0))

    talk._tour(
        Ws(),
        type("C", (), {"start": lambda self: None, "stop": lambda self: [_frame()]})(),
        type("S", (), {"channels": 1, "write": lambda self, b: None})(),
    )
    assert "Aucune trame de réponse" in capsys.readouterr().out


def test_tour_state_puis_error_n_ecrit_pas(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")

    class Ws:
        def __init__(self):
            self.restants = [
                {"type": "state", "label": "écoute"},
                {"type": "error", "message": "down"},
            ]

        def send(self, brut):
            pass

        def recv(self):
            return json.dumps(self.restants.pop(0))

    class Sortie:
        channels = 1

        def write(self, bloc):
            raise AssertionError("pas de restitution sur error")

    talk._tour(
        Ws(),
        type("C", (), {"start": lambda self: None, "stop": lambda self: [_frame()]})(),
        Sortie(),
    )
    assert "Erreur du transport" in capsys.readouterr().out


def test_poignee_ready_avec_champs_extra(capsys):
    class Ws:
        def __init__(self):
            self.envoyes = []

        def send(self, brut):
            self.envoyes.append(json.loads(brut))

        def recv(self):
            return json.dumps({"type": "ready", "version": 2, "extra": True})

    talk._poignee_de_main(Ws(), "s")
    assert "Canal prêt." in capsys.readouterr().out


def test_relayer_reutilise_la_douille(monkeypatch):
    monkeypatch.setenv("PRESENCE", "1")
    created = []

    class FakeSock:
        def __init__(self):
            self.n = 0
            self.blocking = True

        def setblocking(self, flag):
            self.blocking = flag

        def sendto(self, data, addr):
            self.n += 1

    sock = FakeSock()
    talk._douille_presence = sock

    def factory(*a, **k):
        created.append(1)
        return FakeSock()

    monkeypatch.setattr("socket.socket", factory)
    try:
        talk.relayer_etat({"type": "state", "n": 1})
        talk.relayer_etat({"type": "state", "n": 2})
        assert created == []
        assert sock.n == 2
    finally:
        talk._douille_presence = None


def test_presence_chaine_vide_n_est_pas_off(monkeypatch):
    monkeypatch.setenv("PRESENCE", "")
    monkeypatch.setenv("PRESENCE_PORT", "8123")
    envoyes = []

    class FakeSock:
        def setblocking(self, flag):
            pass

        def sendto(self, data, addr):
            envoyes.append(addr)

    talk._douille_presence = FakeSock()
    try:
        talk.relayer_etat({"type": "state"})
        assert envoyes == [("127.0.0.1", talk.PORT_PRESENCE)]
    finally:
        talk._douille_presence = None


# -- erreurs audio / main -----------------------------------------------------


def test_est_erreur_audio_paerrorcode():
    assert talk._est_erreur_audio(RuntimeError("PaErrorCode -9996"))
    assert talk._est_erreur_audio(RuntimeError("device or resource busy"))
    assert talk._est_erreur_audio(RuntimeError("Error opening OutputStream: boom"))
    assert not talk._est_erreur_audio(RuntimeError("timed out"))
    assert not talk._est_erreur_audio(ConnectionRefusedError("refused"))


def test_decrire_erreur_inputstream_reste_francais():
    phrase = talk.decrire_erreur_peripherique(
        RuntimeError("Error opening InputStream: Device or resource busy"),
    )
    assert "occup" in phrase.lower()
    assert "InputStream" not in phrase
    assert "PortAudio" not in phrase


def test_keyboardinterrupt_ferme_la_sortie(monkeypatch, capsys):
    sd = _SoundDevice(PERIPHS)
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(
        talk, "_importer_websockets",
        lambda: (lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt())),
    )
    monkeypatch.setattr(sys, "argv", ["talk.py"])
    talk.main()
    assert "stop" in sd.journal
    assert "close" in sd.journal
    assert sd.flux.ferme is True
    assert "Arrêt." in capsys.readouterr().out


def test_connexion_refusee_ferme_quand_meme_la_sortie(monkeypatch, capsys):
    sd = _SoundDevice(PERIPHS)
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(
        talk, "_importer_websockets",
        lambda: (lambda *a, **k: (_ for _ in ()).throw(ConnectionRefusedError("refused"))),
    )
    monkeypatch.setattr(sys, "argv", ["talk.py"])
    with pytest.raises(SystemExit) as exc:
        talk.main()
    assert exc.value.code == 1
    assert sd.flux.ferme is True
    assert "Impossible de joindre" in capsys.readouterr().out


def test_url_cli_par_defaut_est_ipv4():
    assert talk.URL_DEFAUT == "ws://127.0.0.1:8001/hostagent"


def test_jouer_stereo_deux_colonnes_identiques():
    class Sortie:
        channels = 2

        def __init__(self):
            self.blocs = []

        def write(self, bloc):
            self.blocs.append(np.asarray(bloc))

    sortie = Sortie()
    pcm = np.array([0.25, -0.25, 0.0], dtype=np.float32)
    talk._jouer(sortie, pcm)
    assert sortie.blocs[0].shape == (3, 2)
    np.testing.assert_array_equal(sortie.blocs[0][:, 0], sortie.blocs[0][:, 1])
