"""
talk.py n'a jamais vu un vrai micro.

Toutes nos mesures passent par verify_hostagent_loop.py, qui rejoue un
WAV. talk.py, lui, attend qu'on appuie sur Entrée : on ne peut pas le
faire tourner en autonome cette nuit, et donc on ne peut pas garantir
qu'il marchera samedi, quand la solution sera présentée à l'équipe.

Ce qu'on peut faire : le rendre diagnosticable. Si quelque chose casse
vendredi soir, il faut qu'on sache en dix secondes si c'est le micro,
le format, ou le haut-parleur — pas qu'on lise une trace Python à deux
heures de la réunion.

Trois outils, rien d'autre. Lister (entrées ET sorties : aujourd'hui
les sorties sont invisibles, donc un haut-parleur mort est
indistinguable d'un micro mort). Traduire une exception PortAudio en
une phrase qui nomme le problème et dit quoi faire. Jouer un bip : si
on l'entend, la restitution va, le problème est ailleurs. Et deux
options en ligne de commande qui font ça puis sortent, sans ouvrir de
WebSocket — le matériel se diagnostique même quand le conteneur est
éteint.

Le livrable n'est pas l'atelier ``--lister`` / ``--test-sortie``. Samedi
on lancera ``python native/hostagent/talk.py`` tout court : si le micro
est occupé ou le haut-parleur refuse 16 kHz, la phrase française doit
sortir de ce chemin-là, à la place de l'anglais PortAudio.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

import numpy as np
import pytest

import native.hostagent.talk as talk
from src.hostagent.audio import SAMPLE_RATE

# Termes d'atelier : les entendre dans la phrase, c'est relire une trace.
_JARGON = ("traceback", "portaudio")

# Deux micros, un haut-parleur. Les canaux du haut-parleur valent 8
# (pas 2) pour que le chiffre ne se confonde ni avec l'indice [2], ni
# avec un 2 déjà présent dans un taux. Les taux sont choisis pour que
# chaque périphérique ait le sien.
_DEUX_ENTREES_UNE_SORTIE = [
    {
        "name": "Micro USB",
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 44100.0,
    },
    {
        "name": "Micro interne",
        "max_input_channels": 2,
        "max_output_channels": 0,
        "default_samplerate": 48000.0,
    },
    {
        "name": "Haut-parleurs",
        "max_input_channels": 0,
        "max_output_channels": 8,
        "default_samplerate": 96000.0,
    },
]


def _sans_accent(texte: str) -> str:
    decomp = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decomp if unicodedata.category(c) != "Mn")


def _contient_nombre(texte: str, n: int | float) -> bool:
    """Le nombre apparaît comme un jeton, pas comme un chiffre au milieu d'un taux."""
    if isinstance(n, float) and n == int(n):
        n = int(n)
    return re.search(rf"\b{n}\b", texte) is not None


def _decouper_sections(texte: str) -> tuple[str, str]:
    """Isole le bloc des entrées et celui des sorties, sans chevauchement."""
    brut = _sans_accent(texte).lower()
    i_entree = brut.find("entree")
    i_sortie = brut.find("sortie")
    assert i_entree >= 0, (
        f"aucune section d'entrées (le mot « entrée » doit apparaître) dans {texte!r}"
    )
    assert i_sortie >= 0, (
        f"aucune section de sorties (le mot « sortie » doit apparaître) dans {texte!r}"
    )
    assert i_entree != i_sortie, "entrées et sorties doivent être deux sections distinctes"

    def morceau(debut: int, autre: int) -> str:
        fin = autre if autre > debut else len(texte)
        return texte[debut:fin]

    return morceau(i_entree, i_sortie), morceau(i_sortie, i_entree)


class _FluxSortie:
    """Même surface minimale qu'un ``OutputStream`` : start, write, stop, close.

    Le journal est partagé avec le double sounddevice pour vérifier
    l'ordre ouvrir-puis-fermer, y compris quand ``write`` lève.
    """

    def __init__(self, journal: list[str], *, lever_a_lecriture: bool = False) -> None:
        self._journal = journal
        self._lever = lever_a_lecriture
        self.ecrits: list = []
        self.ferme = False

    def start(self) -> None:
        self._journal.append("start")

    def write(self, data) -> None:
        self._journal.append("write")
        if self._lever:
            raise RuntimeError("écriture refusée")
        self.ecrits.append(data)

    def stop(self) -> None:
        self._journal.append("stop")

    def close(self) -> None:
        self.ferme = True
        self._journal.append("close")

    def abort(self) -> None:
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


class _SoundDevice:
    """Double de ``sounddevice`` : query_devices + OutputStream, rien d'autre."""

    def __init__(
        self,
        peripheriques: list[dict],
        *,
        hostapis: list[dict] | None = None,
        lever_a_lecriture: bool = False,
        lever_a_l_ouverture: Exception | None = None,
        lever_a_la_requete: Exception | None = None,
        lever_a_l_entree: Exception | None = None,
    ) -> None:
        self._peripheriques = list(peripheriques)
        self._hostapis = list(hostapis) if hostapis is not None else [{"name": "MME"}, {"name": "Windows WASAPI"}]
        self.journal: list[str] = []
        self.appels_output: list[dict] = []
        self.appels_input: list[dict] = []
        self.lever_a_l_ouverture = lever_a_l_ouverture
        self.lever_a_la_requete = lever_a_la_requete
        self.lever_a_l_entree = lever_a_l_entree
        self.flux = _FluxSortie(self.journal, lever_a_lecriture=lever_a_lecriture)
        self.default = type("default", (), {"samplerate": SAMPLE_RATE, "device": (None, None)})()

    def query_hostapis(self):
        return list(self._hostapis)

    def query_devices(self, *args, **kwargs):
        if self.lever_a_la_requete is not None:
            raise self.lever_a_la_requete
        if args:
            return self._peripheriques[args[0]]
        if "kind" in kwargs:
            kind = kwargs["kind"]
            for indice, peripherique in enumerate(self._peripheriques):
                if kind == "input" and peripherique["max_input_channels"] > 0:
                    return peripherique
                if kind == "output" and peripherique["max_output_channels"] > 0:
                    return peripherique
            raise ValueError(f"aucun périphérique {kind}")
        return list(self._peripheriques)

    def OutputStream(self, **kwargs):
        self.journal.append("open")
        self.appels_output.append(kwargs)
        if self.lever_a_l_ouverture is not None:
            raise self.lever_a_l_ouverture
        return self.flux

    def InputStream(self, **kwargs):
        self.appels_input.append(kwargs)
        if self.lever_a_l_entree is not None:
            raise self.lever_a_l_entree
        return self.flux


def _lister(sd) -> str:
    from native.hostagent.talk import lister_peripheriques

    return lister_peripheriques(sd)


def _decrire(exc: BaseException) -> str:
    from native.hostagent.talk import decrire_erreur_peripherique

    return decrire_erreur_peripherique(exc)


def _tester_sortie(sd, **kwargs) -> int:
    from native.hostagent.talk import tester_sortie

    return tester_sortie(sd, **kwargs)


def _exiger_phrase_humaine(phrase, exc: BaseException) -> str:
    """Une phrase, en français, qui ne trahit pas l'atelier."""
    assert phrase is not None, "une exception inconnue doit quand même se dire"
    assert isinstance(phrase, str), f"attendu str, reçu {type(phrase).__name__}"
    assert phrase.strip(), "une chaîne blanche n'est pas une phrase utile"
    texte = phrase.strip()
    bas = texte.lower()
    for terme in _JARGON:
        assert terme not in bas, (
            f"« {terme} » est du jargon d'atelier : l'opérateur n'a pas à "
            f"le lire vendredi soir ({phrase!r})"
        )
    nom_classe = type(exc).__name__
    assert nom_classe not in texte, (
        f"le nom de classe {nom_classe} a fuité dans la phrase ({phrase!r})"
    )
    assert "\n" not in texte, (
        f"une phrase, pas un pavé : des retours à la ligne trahissent une trace ({phrase!r})"
    )
    return texte


def _pas_de_connexion(*_args, **_kwargs):
    raise AssertionError(
        "une option de diagnostic ne doit ouvrir aucune connexion WebSocket"
    )


def _lancer_main(monkeypatch, sd, *options) -> None:
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: _pas_de_connexion)
    monkeypatch.setattr(sys, "argv", ["talk.py", *options])
    try:
        talk.main()
    except SystemExit as exc:
        assert exc.code in (0, None), (
            f"le diagnostic doit sortir proprement, pas avec le code {exc.code}"
        )


def _imprimer(capsys) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


class _WsPret:
    """Poignée de main minimale : ready, puis plus rien. Pas de réseau."""

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def send(self, *_args, **_kwargs) -> None:
        pass

    def recv(self):
        return json.dumps({"type": "ready"})


# --- resoudre_peripherique_api & option --api -----------------------------


def test_resoudre_peripherique_api_trouve_le_bon_indice():
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    peripheriques = [
        {"name": "HP MME", "max_output_channels": 2, "hostapi": 0},
        {"name": "HP WASAPI", "max_output_channels": 2, "hostapi": 1},
    ]
    idx_wasapi = talk.resoudre_peripherique_api("wasapi", peripheriques, hostapis, role="max_output_channels")
    assert idx_wasapi == 1

    idx_mme = talk.resoudre_peripherique_api("mme", peripheriques, hostapis, role="max_output_channels")
    assert idx_mme == 0


def test_resoudre_peripherique_api_echec_bruyant_si_api_absente():
    hostapis = [{"name": "MME"}]
    peripheriques = [{"name": "HP MME", "max_output_channels": 2, "hostapi": 0}]
    with pytest.raises(SystemExit) as exc:
        talk.resoudre_peripherique_api("wasapi", peripheriques, hostapis, role="max_output_channels")
    assert exc.value.code == 1


def test_option_api_transmise_a_la_sortie(monkeypatch):
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    peripheriques = [
        {"name": "HP MME", "max_output_channels": 2, "hostapi": 0},
        {"name": "HP WASAPI", "max_output_channels": 2, "hostapi": 1},
    ]
    sd = _SoundDevice(peripheriques, hostapis=hostapis)
    _lancer_main(monkeypatch, sd, "--test-sortie", "--api", "wasapi")
    assert sd.appels_output, "--test-sortie n'a pas ouvert de flux"
    assert sd.appels_output[0].get("device") == 1



def test_lister_peripheriques_separe_entrees_et_sorties():
    """Deux micros, un haut-parleur : les trois apparaissent, chacun dans sa section.

    C'est précisément ce que le code actuel ne fait pas : il ne liste
    que les entrées, donc un problème de haut-parleur est invisible.
    """
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    texte = _lister(sd)
    assert isinstance(texte, str) and texte.strip()

    entrees, sorties = _decouper_sections(texte)

    assert "Micro USB" in entrees
    assert "Micro interne" in entrees
    assert "Haut-parleurs" not in entrees
    assert _contient_nombre(entrees, 0)
    assert _contient_nombre(entrees, 1)
    assert _contient_nombre(entrees, 1)
    assert _contient_nombre(entrees, 2)
    assert _contient_nombre(entrees, 44100)
    assert _contient_nombre(entrees, 48000)

    assert "Haut-parleurs" in sorties
    assert "Micro USB" not in sorties
    assert "Micro interne" not in sorties
    assert _contient_nombre(sorties, 2)
    assert _contient_nombre(sorties, 8)
    assert _contient_nombre(sorties, 96000)


def test_lister_peripheriques_rend_une_chaine_sans_imprimer(capsys):
    """Une fonction qui rend du texte se teste ; une fonction qui imprime, non."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    texte = _lister(sd)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert "Micro USB" in texte
    assert "Haut-parleurs" in texte


def test_un_peripherique_duplex_apparait_dans_les_deux_sections():
    """Un casque USB est à la fois micro et haut-parleur : les deux faces doivent se voir.

    C'est le périphérique de démo le plus probable. S'il n'apparaît
    que du côté entrée, on reproduit le bug d'aujourd'hui.
    """
    sd = _SoundDevice(
        [
            {
                "name": "Casque USB",
                "max_input_channels": 1,
                "max_output_channels": 2,
                "default_samplerate": 48000.0,
            }
        ]
    )
    entrees, sorties = _decouper_sections(_lister(sd))
    assert "Casque USB" in entrees
    assert "Casque USB" in sorties
    assert _contient_nombre(entrees, 1)
    assert _contient_nombre(sorties, 2)


# --- decrire_erreur_peripherique --------------------------------------------


class _ErreurPortAudioPiege(Exception):
    """Nom volontairement piège : « PortAudio » ne doit pas fuiter dans la phrase."""


def test_decrire_erreur_distingue_trois_familles():
    """Absent, occupé, format : trois phrases différentes. Même famille, même phrase.

    Vendredi soir on ne distingue pas une exception d'une autre à la
    classe : on lit le texte. Les deux formulations de chaque famille
    doivent donc rendre la même instruction, sinon l'opérateur croit
    à trois pannes là où il n'y en a qu'une.
    """
    absent_a = _decrire(_ErreurPortAudioPiege("PortAudio Error: Invalid device"))
    absent_b = _decrire(_ErreurPortAudioPiege("PortAudio Error: Device unavailable"))
    occupe_a = _decrire(
        _ErreurPortAudioPiege("PortAudio Error: Device or resource busy")
    )
    occupe_b = _decrire(_ErreurPortAudioPiege("PortAudio Error: device in use"))
    format_a = _decrire(
        _ErreurPortAudioPiege("Error opening OutputStream: Invalid sample rate")
    )
    format_b = _decrire(
        _ErreurPortAudioPiege("Error opening InputStream: Invalid number of channels")
    )

    for phrase, exc_texte in (
        (absent_a, "Invalid device"),
        (absent_b, "Device unavailable"),
        (occupe_a, "Device or resource busy"),
        (occupe_b, "in use"),
        (format_a, "Invalid sample rate"),
        (format_b, "Invalid number of channels"),
    ):
        _exiger_phrase_humaine(phrase, _ErreurPortAudioPiege(exc_texte))

    assert absent_a == absent_b
    assert occupe_a == occupe_b
    assert format_a == format_b
    assert len({absent_a, occupe_a, format_a}) == 3

    def normalise(phrase: str) -> str:
        return _sans_accent(phrase).lower()

    assert "peripherique" in normalise(absent_a)
    assert any(m in normalise(absent_a) for m in ("absent", "invalide", "introuvable", "indisponible"))
    assert any(m in normalise(occupe_a) for m in ("occup", "application", "utilise"))
    assert any(
        m in normalise(format_a) for m in ("taux", "canal", "format", "echantillon")
    )


def test_decrire_erreur_est_une_phrase_francaise_sans_jargon():
    """Ni Traceback, ni PortAudio, ni le nom de classe : une phrase, et quoi faire."""
    exc = _ErreurPortAudioPiege("PortAudio Error: Invalid device")
    phrase = _exiger_phrase_humaine(_decrire(exc), exc)
    assert len(phrase) >= 40, (
        "nommer le problème ET dire quoi faire : au-dessous de 40 "
        f"caractères, ce n'est qu'une étiquette ({phrase!r})"
    )
    # L'anglais PortAudio n'est pas une traduction.
    assert "Invalid device" not in phrase
    assert "PortAudio Error" not in phrase


def test_decrire_erreur_inconnue_reste_utile():
    """Une exception hors des trois familles rend quand même une phrase, jamais vide."""
    exc = RuntimeError("xyzzy-imprevu-42")
    phrase = _exiger_phrase_humaine(_decrire(exc), exc)
    assert phrase != str(exc), (
        "recopier le message brut n'est pas une phrase utile : "
        "il faut dire quoi faire"
    )
    assert len(phrase) >= 40


# --- tester_sortie ----------------------------------------------------------


def test_canaux_de_sortie_nominal_stereo_et_mono():
    assert talk.canaux_de_sortie(1) == 1
    assert talk.canaux_de_sortie(2) == 2
    assert talk.canaux_de_sortie(6) == 2
    assert talk.canaux_de_sortie(8) == 2


def test_canaux_de_sortie_echec_bruyant_si_zero_ou_absent():
    with pytest.raises(SystemExit) as exc1:
        talk.canaux_de_sortie(0)
    assert exc1.value.code == 1

    with pytest.raises(SystemExit) as exc2:
        talk.canaux_de_sortie(None)
    assert exc2.value.code == 1


def test_etaler_forme_et_colonnes():
    pcm = np.array([0.1, -0.2, 0.5], dtype=np.float32)
    mono = talk.etaler(pcm, 1)
    assert mono.shape == (3, 1)
    assert mono.dtype == np.float32
    np.testing.assert_array_equal(mono[:, 0], pcm)

    stereo = talk.etaler(pcm, 2)
    assert stereo.shape == (3, 2)
    assert stereo.dtype == np.float32
    np.testing.assert_array_equal(stereo[:, 0], pcm)
    np.testing.assert_array_equal(stereo[:, 1], pcm)


def test_tester_sortie_joue_un_signal_non_silencieux_de_la_bonne_duree():
    """Le bip dure secondes × SAMPLE_RATE, et ce n'est pas du silence.

    On pince le taux à 16 kHz : c'est celui de ``_ouvrir_sortie``,
    donc celui de la démo. Un bip à 48 kHz qui passe ne prouve pas
    que la restitution du tour vocal passera.
    """
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    secondes = 0.2
    n = _tester_sortie(sd, indice=2, secondes=secondes, frequence=440.0)

    assert sd.appels_output, "le flux de sortie n'a pas été ouvert"
    kwargs = sd.appels_output[0]
    assert kwargs.get("samplerate") == SAMPLE_RATE, (
        f"tester_sortie doit jouer au taux de la démo ({SAMPLE_RATE} Hz), "
        f"pas au défaut du périphérique ({kwargs.get('samplerate')!r})"
    )
    assert kwargs.get("device") == 2

    attendu = int(secondes * SAMPLE_RATE)
    assert n == attendu
    assert n == 3200
    assert kwargs.get("channels") == 2

    blocs = [np.asarray(b) for b in sd.flux.ecrits]
    assert blocs, "rien n'a été écrit sur la sortie"
    assert blocs[0].shape == (attendu, 2)
    frames = sum(b.shape[0] for b in blocs)
    assert frames == attendu

    pcm = np.concatenate([b.reshape(b.shape[0], -1)[:, 0] for b in blocs])
    assert np.max(np.abs(pcm)) > 0.05, "le signal est silencieux : on n'entendrait pas le bip"
    assert np.std(pcm) > 0.01, "un palier constant n'est pas une tonalité"


def test_tester_sortie_ferme_le_flux_meme_si_lecriture_leve():
    """Ouvert, puis fermé. Même si write lève : sinon le périphérique reste pris."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE, lever_a_lecriture=True)
    try:
        _tester_sortie(sd, secondes=0.2, frequence=440.0)
    except (ImportError, AttributeError):
        raise
    except Exception:
        pass

    assert "open" in sd.journal, "le flux de sortie n'a pas été ouvert"
    assert "close" in sd.journal, "le flux de sortie n'a pas été fermé"
    assert sd.journal.index("open") < sd.journal.index("close")
    assert sd.flux.ferme


# --- options en ligne de commande -------------------------------------------


def test_lister_en_ligne_de_commande_n_ouvre_pas_de_websocket(monkeypatch, capsys):
    """``--lister`` fait son travail puis sort : le conteneur peut être éteint."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    _lancer_main(monkeypatch, sd, "--lister")
    captured = capsys.readouterr()
    assert "Micro USB" in captured.out
    assert "Haut-parleurs" in captured.out


def test_test_sortie_en_ligne_de_commande_n_ouvre_pas_de_websocket(monkeypatch):
    """``--test-sortie`` joue le bip puis sort, sans poignée de main WebSocket."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    _lancer_main(monkeypatch, sd, "--test-sortie")
    assert "open" in sd.journal, "--test-sortie n'a pas ouvert de flux de sortie"
    assert "close" in sd.journal, "--test-sortie n'a pas refermé le flux"


def test_un_format_refuse_par_la_sortie_se_dit_en_une_phrase(monkeypatch, capsys):
    """Vendredi soir : le haut-parleur refuse 16 kHz. Une phrase, pas une trace.

    Sans ce câblage, ``--test-sortie`` dump Python et on a perdu les
    dix secondes. La phrase doit être celle de ``decrire_erreur_peripherique``,
    pour que l'oreille et l'écran disent la même chose.
    """
    exc = _ErreurPortAudioPiege(
        "Error opening OutputStream: Invalid sample rate [PaErrorCode -9997]"
    )
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE, lever_a_l_ouverture=exc)
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: _pas_de_connexion)
    monkeypatch.setattr(sys, "argv", ["talk.py", "--test-sortie"])
    try:
        talk.main()
    except SystemExit as sortie:
        assert sortie.code in (0, 1, None)
    except _ErreurPortAudioPiege:
        pytest.fail(
            "l'exception PortAudio a traversé main() : elle doit être "
            "traduite par decrire_erreur_peripherique, pas relancée"
        )

    captured = capsys.readouterr()
    tout = captured.out + captured.err
    assert "Traceback" not in tout
    attendu = _decrire(exc)
    assert attendu in tout, (
        f"la phrase de diagnostic doit apparaître sur stdout/stderr\n"
        f"attendu : {attendu!r}\nreçu : {tout!r}"
    )


# --- chemin normal : la phrase doit sortir de `python talk.py` --------------


def test_choisir_peripherique_dit_une_phrase_si_portaudio_leve(capsys):
    """query_devices lève : phrase française, pas l'anglais, pas de trace.

    C'est le premier point d'accroche du lancement normal.
    """
    exc = _ErreurPortAudioPiege(
        "Error opening InputStream: Invalid device [PaErrorCode -9996]"
    )
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE, lever_a_la_requete=exc)
    with pytest.raises(SystemExit) as sortie:
        talk.choisir_peripherique(None, sd)
    assert sortie.value.code == 1

    tout = _imprimer(capsys)
    assert "Traceback" not in tout
    attendu = _decrire(exc)
    assert attendu in tout, (
        f"la phrase de diagnostic doit remplacer l'anglais PortAudio\n"
        f"attendu : {attendu!r}\nreçu : {tout!r}"
    )
    assert "Invalid device" not in tout
    assert "--lister" in tout


def test_lancement_normal_dit_une_phrase_si_la_sortie_refuse(monkeypatch, capsys):
    """``python talk.py`` tout court, le HP refuse 16 kHz : phrase, pas connexion.

    C'est l'objection : câbler seulement ``--test-sortie``, c'est
    construire l'atelier. Samedi on lance sans option.
    """
    exc = _ErreurPortAudioPiege(
        "Error opening OutputStream: Invalid sample rate [PaErrorCode -9997]"
    )
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE, lever_a_l_ouverture=exc)
    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: _pas_de_connexion)
    monkeypatch.setattr(sys, "argv", ["talk.py"])
    try:
        talk.main()
    except SystemExit as sortie:
        assert sortie.code in (0, 1, None)
    except _ErreurPortAudioPiege:
        pytest.fail(
            "l'exception PortAudio a traversé main() : elle doit être "
            "traduite par decrire_erreur_peripherique, pas relancée"
        )

    tout = _imprimer(capsys)
    assert "Traceback" not in tout
    attendu = _decrire(exc)
    assert attendu in tout, (
        f"la phrase doit sortir du lancement normal\n"
        f"attendu : {attendu!r}\nreçu : {tout!r}"
    )
    assert "Impossible de joindre" not in tout
    assert "--test-sortie" in tout


def test_fabrique_entree_dit_une_phrase_si_le_micro_est_occupe(capsys):
    """InputStream lève à l'ouverture du micro : phrase, pas de trace."""
    exc = _ErreurPortAudioPiege(
        "Error opening InputStream: Device or resource busy"
    )
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE, lever_a_l_entree=exc)
    factory = talk._fabrique_entree(0, sd)
    with pytest.raises(SystemExit):
        factory(lambda *_a, **_k: None)

    tout = _imprimer(capsys)
    assert "Traceback" not in tout
    attendu = _decrire(exc)
    assert attendu in tout, (
        f"la phrase de diagnostic doit remplacer l'anglais PortAudio\n"
        f"attendu : {attendu!r}\nreçu : {tout!r}"
    )
    assert "Device or resource busy" not in tout
    assert "--lister" in tout


def test_boucle_principale_dit_une_phrase_si_lerreur_est_audio(monkeypatch, capsys):
    """Un PortAudio qui fuit jusqu'au ``except Exception`` : périphérique, pas URL.

    Filet du tour : si write ou start lèvent après la poignée de main,
    on ne doit pas dire que le conteneur est injoignable.
    """
    exc = _ErreurPortAudioPiege(
        "Error opening OutputStream: Invalid sample rate [PaErrorCode -9997]"
    )
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)

    def _lever(*_a, **_k):
        raise exc

    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: (lambda *_a, **_k: _WsPret()))
    monkeypatch.setattr(talk, "_tour", _lever)
    monkeypatch.setattr(sys, "argv", ["talk.py"])
    try:
        talk.main()
    except SystemExit as sortie:
        assert sortie.code in (0, 1, None)
    except _ErreurPortAudioPiege:
        pytest.fail(
            "l'exception audio a traversé main() : le except Exception "
            "doit la traduire, pas la relancer"
        )

    tout = _imprimer(capsys)
    assert "Traceback" not in tout
    attendu = _decrire(exc)
    assert attendu in tout, (
        f"la phrase de diagnostic doit sortir du except de la boucle\n"
        f"attendu : {attendu!r}\nreçu : {tout!r}"
    )
    assert "Impossible de joindre" not in tout


def test_erreur_de_connexion_reste_impossible_de_joindre(monkeypatch, capsys):
    """Le message d'URL existant reste : on ne le remplace pas par un périphérique."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    refus = ConnectionRefusedError("Connection refused")

    def _connecter(*_a, **_k):
        raise refus

    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: _connecter)
    monkeypatch.setattr(sys, "argv", ["talk.py"])
    try:
        talk.main()
    except SystemExit:
        pass
    except ConnectionRefusedError:
        pytest.fail("l'échec de connexion doit rester géré par main()")

    tout = _imprimer(capsys)
    assert "Impossible de joindre" in tout
    assert _decrire(refus) not in tout


def test_test_sortie_honore_option_sortie(monkeypatch):
    """``--sortie`` vise le haut-parleur, symétrique de ``--device`` pour le micro."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    _lancer_main(monkeypatch, sd, "--test-sortie", "--sortie", "2")
    assert sd.appels_output, "--test-sortie n'a pas ouvert de flux de sortie"
    assert sd.appels_output[0].get("device") == 2


def test_lancement_normal_honore_option_sortie(monkeypatch):
    """L'ouverture normale du flux de sortie écoute ``--sortie``, pas seulement le bip."""
    sd = _SoundDevice(_DEUX_ENTREES_UNE_SORTIE)
    refus = ConnectionRefusedError("Connection refused")

    def _connecter(*_a, **_k):
        raise refus

    monkeypatch.setattr(talk, "_importer_sounddevice", lambda: sd)
    monkeypatch.setattr(talk, "_importer_websockets", lambda: _connecter)
    monkeypatch.setattr(sys, "argv", ["talk.py", "--sortie", "Haut"])
    try:
        talk.main()
    except SystemExit:
        pass

    assert sd.appels_output, "le lancement normal n'a pas ouvert de flux de sortie"
    assert sd.appels_output[0].get("device") == 2
    assert sd.appels_output[0].get("channels") == 2


# --- Le tour doit se vider entierement de la socket ------------------------
#
# Le serveur envoie, dans l'ordre : des paquets audio, un rapport, puis un
# marqueur de fin vide. Le client sortait de sa boucle des qu'un message
# n'avait pas de trames -- donc SUR LE RAPPORT -- en laissant le marqueur de
# fin dans la socket. Le tour suivant lisait ce residu au lieu de sa propre
# reponse et annoncait « aucune trame de reponse ». Observe en session reelle :
# un tour sur deux muet, et un mic_to_audible de 13 ms, qui mesurait en fait
# l'arrivee du residu du tour precedent.

from src.hostagent.audio import FRAME_SAMPLES, AudioFrame  # noqa: E402


class _SocketFactice:
    """Rejoue une sequence de messages serveur, et compte ce qui reste."""

    def __init__(self, messages):
        self.restants = list(messages)
        self.envoyes = []

    def send(self, brut):
        self.envoyes.append(brut)

    def recv(self):
        if not self.restants:
            raise AssertionError("le client a lu au-dela du marqueur de fin")
        return json.dumps(self.restants.pop(0))


class _CaptureFactice:
    """Rend toujours quelques trames, comme un micro qui a entendu quelque chose."""

    def __init__(self, nb_trames=3):
        self.nb_trames = nb_trames

    def start(self):
        pass

    def stop(self):
        return [
            AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.float32))
            for _ in range(self.nb_trames)
        ]


class _SortieFactice:
    """Haut-parleur factice : retient ce qui lui a ete ecrit."""

    def __init__(self):
        self.joues = []

    def write(self, bloc):
        arr = np.asarray(bloc)
        self.joues.append(arr.size)
        self.derniere_forme = arr.shape


def _sequence_de_tour(n_paquets=2):
    trame = [0.0] * FRAME_SAMPLES
    messages = [{"frames": [trame]} for _ in range(n_paquets)]
    messages.append(
        {
            "type": "report",
            "transcript": "bonjour",
            "reply": "bonjour, je t'ecoute",
            "timings_ms": {"ears": 1.0, "brain": 2.0, "mouth": 3.0, "total": 6.0},
        }
    )
    messages.append({"frames": []})
    return messages


@pytest.fixture
def sans_entree(monkeypatch):
    """`_tour` attend deux appuis sur Entree ; en test on les fournit."""
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")


def test_un_tour_consomme_le_rapport_et_le_marqueur_de_fin(sans_entree):
    ws = _SocketFactice(_sequence_de_tour())
    sortie = _SortieFactice()
    sortie.channels = 2

    talk._tour(ws, _CaptureFactice(), sortie)

    assert ws.restants == [], (
        "le tour doit vider sa reponse entiere : un residu decale le tour suivant"
    )
    assert getattr(sortie, "derniere_forme", None) == (FRAME_SAMPLES, 2)


def test_deux_tours_enchaines_ne_se_decalent_pas(sans_entree):
    ws = _SocketFactice(_sequence_de_tour() + _sequence_de_tour())
    sortie = _SortieFactice()

    talk._tour(ws, _CaptureFactice(), sortie)
    apres_premier = len(sortie.joues)
    talk._tour(ws, _CaptureFactice(), sortie)

    assert len(sortie.joues) > apres_premier, (
        "le second tour doit restituer son propre audio, pas le residu du premier"
    )
    assert ws.restants == []
