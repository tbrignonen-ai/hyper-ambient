"""
talk.py : WASAPI / host API, listing etiquete, --api, chemins d'erreur audio.

Aucune carte son : tout passe par un double de sounddevice. La checklist
oreille (bip a 16 kHz, WASAPI vs MME) reste un document separe ; ici on
pince ce que pytest peut prouver sans materiel.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pytest

import native.hostagent.talk as talk
from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame


class _Flux:
    def __init__(self, journal, lever_write=False):
        self._journal = journal
        self._lever = lever_write
        self.ecrits = []
        self.ferme = False

    def start(self):
        self._journal.append("start")

    def write(self, data):
        self._journal.append("write")
        if self._lever:
            raise RuntimeError("écriture refusée")
        self.ecrits.append(data)

    def stop(self):
        self._journal.append("stop")

    def close(self):
        self.ferme = True
        self._journal.append("close")

    def abort(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


class _SoundDevice:
    def __init__(self, peripheriques, *, hostapis=None, lever_requete=None):
        self._peripheriques = list(peripheriques)
        self._hostapis = list(hostapis) if hostapis is not None else [
            {"name": "MME"},
            {"name": "Windows WASAPI"},
            {"name": "Windows DirectSound"},
            {"name": "Windows WDM-KS"},
        ]
        self.journal = []
        self.appels_output = []
        self.appels_input = []
        self.lever_requete = lever_requete
        self.flux = _Flux(self.journal)
        self.default = type("default", (), {"samplerate": SAMPLE_RATE, "device": (None, None)})()

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
        return self.flux

    def InputStream(self, **kwargs):
        self.appels_input.append(kwargs)
        return self.flux


WASAPI_MME = [
    {
        "name": "Micro MME",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 44100.0,
        "hostapi": 0,
    },
    {
        "name": "Micro WASAPI",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 48000.0,
        "hostapi": 1,
    },
    {
        "name": "HP MME",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 44100.0,
        "hostapi": 0,
    },
    {
        "name": "HP WASAPI",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 1,
    },
    {
        "name": "HP DirectSound",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 2,
    },
    {
        "name": "HP WDM-KS",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 3,
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


def test_lister_etiquette_wasapi_et_mme():
    texte = talk.lister_peripheriques(_SoundDevice(WASAPI_MME))
    assert "[Windows WASAPI]" in texte
    assert "[MME]" in texte
    assert "Micro WASAPI" in texte
    assert "HP WASAPI" in texte
    entrees, _, sorties = texte.partition("Sorties :")
    assert "Micro WASAPI" in entrees and "HP WASAPI" not in entrees
    assert "HP WASAPI" in sorties and "Micro WASAPI" not in sorties


def test_lister_etiquette_directsound_et_wdm_ks():
    texte = talk.lister_peripheriques(_SoundDevice(WASAPI_MME))
    assert "[Windows DirectSound]" in texte
    assert "[Windows WDM-KS]" in texte


def test_lister_sans_hostapis_reste_lisible():
    class Sd(_SoundDevice):
        def query_hostapis(self):
            raise RuntimeError("hostapis indisponibles")

    texte = talk.lister_peripheriques(Sd(WASAPI_MME))
    assert "Micro WASAPI" in texte
    assert "HP WASAPI" in texte
    assert "Windows WASAPI" not in texte


def test_lister_hostapi_hors_limites_pas_de_crochet():
    periphs = [{
        "name": "Orphelin",
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 99,
    }]
    texte = talk.lister_peripheriques(_SoundDevice(periphs, hostapis=[{"name": "MME"}]))
    assert "Orphelin" in texte
    assert "[" not in texte.split("Orphelin", 1)[1].split("\n", 1)[0] or "99" not in texte


def test_lister_vide_dit_aucune():
    texte = talk.lister_peripheriques(_SoundDevice([]))
    assert "(aucune)" in texte
    assert "Entrées :" in texte
    assert "Sorties :" in texte


def test_resoudre_wasapi_sortie_premier_haut_parleur():
    idx = talk.resoudre_peripherique_api(
        "wasapi", WASAPI_MME,
        [{"name": "MME"}, {"name": "Windows WASAPI"}, {"name": "Windows DirectSound"}, {"name": "Windows WDM-KS"}],
        role="max_output_channels",
    )
    assert idx == 3
    assert WASAPI_MME[idx]["name"] == "HP WASAPI"


def test_resoudre_wasapi_entree():
    idx = talk.resoudre_peripherique_api(
        "WASAPI", WASAPI_MME,
        [{"name": "MME"}, {"name": "Windows WASAPI"}],
        role="max_input_channels",
    )
    assert WASAPI_MME[idx]["name"] == "Micro WASAPI"


def test_resoudre_mme_directsound_wdm():
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}, {"name": "Windows DirectSound"}, {"name": "Windows WDM-KS"}]
    assert WASAPI_MME[talk.resoudre_peripherique_api("mme", WASAPI_MME, hostapis)]["name"] == "HP MME"
    assert WASAPI_MME[talk.resoudre_peripherique_api("directsound", WASAPI_MME, hostapis)]["name"] == "HP DirectSound"
    assert WASAPI_MME[talk.resoudre_peripherique_api("wdm-ks", WASAPI_MME, hostapis)]["name"] == "HP WDM-KS"


def test_resoudre_api_absente_code_1():
    with pytest.raises(SystemExit) as exc:
        talk.resoudre_peripherique_api("wasapi", WASAPI_MME, [{"name": "MME"}])
    assert exc.value.code == 1


def test_resoudre_wasapi_sans_sortie_code_1():
    que_micro = [p for p in WASAPI_MME if p["max_output_channels"] == 0]
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    with pytest.raises(SystemExit) as exc:
        talk.resoudre_peripherique_api("wasapi", que_micro, hostapis, role="max_output_channels")
    assert exc.value.code == 1


def test_option_api_wasapi_ouvre_le_bon_indice(monkeypatch):
    sd = _SoundDevice(WASAPI_MME)
    _lancer_main(monkeypatch, sd, "--test-sortie", "--api", "wasapi")
    assert sd.appels_output[0].get("device") == 3
    assert sd.appels_output[0].get("samplerate") == SAMPLE_RATE
    assert sd.appels_output[0].get("channels") == 2
    assert sd.appels_input == []


def test_option_api_mme_n_est_pas_wasapi(monkeypatch):
    sd = _SoundDevice(WASAPI_MME)
    _lancer_main(monkeypatch, sd, "--test-sortie", "--api", "mme")
    assert sd.appels_output[0].get("device") == 2


def test_sortie_gagne_sur_api(monkeypatch):
    sd = _SoundDevice(WASAPI_MME)
    _lancer_main(monkeypatch, sd, "--test-sortie", "--api", "wasapi", "--sortie", "2")
    assert sd.appels_output[0].get("device") == 2


def test_choisir_sortie_sans_demande_ni_api_est_defaut_systeme():
    sd = _SoundDevice(WASAPI_MME)
    assert talk.choisir_sortie(None, sd, api=None) is None
    assert sd.appels_output == []


def test_choisir_sortie_par_fragment_de_nom():
    sd = _SoundDevice(WASAPI_MME)
    idx = talk.choisir_sortie("WASAPI", sd)
    assert idx == 3


def test_choisir_sortie_fragment_inconnu_code_1():
    sd = _SoundDevice(WASAPI_MME)
    with pytest.raises(SystemExit) as exc:
        talk.choisir_sortie("nexiste-pas", sd)
    assert exc.value.code == 1


def test_tester_sortie_affiche_wasapi(capsys):
    sd = _SoundDevice(WASAPI_MME)
    n = talk.tester_sortie(sd, indice=3, secondes=0.1, frequence=440.0)
    tout = capsys.readouterr().out
    assert "HP WASAPI" in tout
    assert "Windows WASAPI" in tout
    assert "16 kHz" in tout
    assert n == int(0.1 * SAMPLE_RATE)
    assert sd.appels_output[0]["channels"] == 2
    assert sd.appels_output[0]["samplerate"] == SAMPLE_RATE


def test_tester_sortie_sans_indice_prend_kind_output():
    sd = _SoundDevice(WASAPI_MME)
    talk.tester_sortie(sd, secondes=0.05)
    assert "device" not in sd.appels_output[0]
    assert sd.appels_output[0]["channels"] == 2


def test_lister_en_cli_n_ouvre_ni_entree_ni_sortie(monkeypatch, capsys):
    sd = _SoundDevice(WASAPI_MME)
    _lancer_main(monkeypatch, sd, "--lister")
    assert sd.appels_output == []
    assert sd.appels_input == []
    out = capsys.readouterr().out
    assert "Windows WASAPI" in out
    assert "HP WASAPI" in out


def test_est_erreur_audio_distingue_connexion():
    assert talk._est_erreur_audio(RuntimeError("Error opening OutputStream: Invalid sample rate"))
    assert talk._est_erreur_audio(RuntimeError("PaErrorCode -9996"))
    assert talk._est_erreur_audio(RuntimeError("Device or resource busy"))
    assert not talk._est_erreur_audio(ConnectionRefusedError("Connection refused"))
    assert not talk._est_erreur_audio(TimeoutError("timed out"))


def test_fabrique_entree_wasapi_mono_int16_16k():
    sd = _SoundDevice(WASAPI_MME)
    factory = talk._fabrique_entree(1, sd)
    factory(lambda *_a, **_k: None)
    kwargs = sd.appels_input[0]
    assert kwargs["device"] == 1
    assert kwargs["samplerate"] == SAMPLE_RATE
    assert kwargs["channels"] == 1
    assert kwargs["dtype"] == "int16"


def test_ouvrir_sortie_wasapi_stereo_float32(capsys):
    sd = _SoundDevice(WASAPI_MME)
    flux = talk._ouvrir_sortie(sd, indice=3)
    assert flux.channels == 2
    kwargs = sd.appels_output[0]
    assert kwargs["device"] == 3
    assert kwargs["samplerate"] == SAMPLE_RATE
    assert kwargs["channels"] == 2
    assert kwargs["dtype"] == "float32"
    assert "Windows WASAPI" in capsys.readouterr().out


def test_jouer_duplique_mono_vers_stereo():
    class Sortie:
        channels = 2
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
    pcm = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    talk._jouer(sortie, pcm)
    assert sortie.blocs[0].shape == (3, 2)
    np.testing.assert_array_equal(sortie.blocs[0][:, 0], pcm)
    np.testing.assert_array_equal(sortie.blocs[0][:, 1], pcm)


def test_canaux_surround_deviennent_stereo():
    assert talk.canaux_de_sortie(8) == 2
    assert talk.canaux_de_sortie(1) == 1


def test_argparse_api_accepte_wasapi():
    import inspect

    src = inspect.getsource(talk.main)
    for nom in ("wasapi", "mme", "directsound", "wdm-ks"):
        assert nom in src


def test_tour_ignore_state_et_vide_jusqu_au_marqueur(monkeypatch):
    monkeypatch.setenv("PRESENCE", "0")
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    trame = [0.0] * FRAME_SAMPLES
    messages = [
        {"type": "state", "label": "écoute"},
        {"frames": [trame]},
        {"type": "report", "transcript": "salut", "reply": "oui"},
        {"frames": []},
    ]

    class Ws:
        def __init__(self):
            self.restants = list(messages)
            self.envoyes = []
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
        channels = 2
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
    assert ws.restants == []
    assert sortie.n == FRAME_SAMPLES
    invoke = json.loads(ws.envoyes[0])
    assert invoke["primitive"] == "audio.capture"
