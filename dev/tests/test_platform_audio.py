"""Abstraction plateforme de la capture audio : délégation Windows, branche macOS.

Ces tests tournent SUR WINDOWS, sans périphérique audio et sans
``sounddevice`` : la logique est testable parce que l'accès au matériel
passe par une fabrique de flux injectée — patron repris de
``test_windows_audio.py`` et ``test_ecoute_continue.py``.

Trois choses sont vérifiées :

1. sur Windows, l'abstraction **est** l'implémentation historique. On
   contrôle l'identité des objets, pas seulement le comportement : rien ne
   peut avoir changé pour le chemin de la démonstration, et la branche
   Windows ne contient que des ré-exports ;
2. l'API publique est complète et utilisable ;
3. la branche macOS/Linux se charge et fonctionne. Le fichier compile,
   puis il est exécuté avec ``sys.platform`` forcé à ``darwin`` : le code
   du portage est donc réellement exercé ici, à la fabrique de flux près
   (CoreAudio est injoignable depuis Windows, elle est bouchonnée).

Ce qui reste non vérifiable faute de Mac est listé dans le rapport
``nights/macos/2026-09-20-OUT-QWEN-PORTAGE.md``.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import py_compile
import sys
import types
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]
CHEMIN_PLATFORM_AUDIO = RACINE / "native" / "hostagent" / "platform_audio.py"

# Le contrat annoncé par le brief : ces quatre noms, sur toutes les plateformes.
API_PUBLIQUE = (
    "PushToTalkCapture",
    "CaptureContinue",
    "frames_from_samples",
    "lister_peripheriques_entree",
)


class _FluxSynthetique:
    """Flux d'entrée injectable : fabrique ``(callback) -> stream``.

    Même surface minimale qu'un ``InputStream`` : ``start``, ``stop``,
    ``close``. ``pousser`` simule le périphérique ; les échantillons ne
    sont livrés au callback que si le flux est démarré.
    """

    def __init__(self) -> None:
        self._callback = None
        self._demarre = False
        self.stops = 0
        self.closes = 0

    def __call__(self, callback):
        self._callback = callback
        return self

    def start(self) -> None:
        self._demarre = True

    def stop(self) -> None:
        self._demarre = False
        self.stops += 1

    def close(self) -> None:
        self.closes += 1

    def pousser(self, echantillons) -> None:
        if self._demarre and self._callback is not None:
            data = np.asarray(echantillons).reshape(-1)
            self._callback(data, data.size, None, None)


def _silence(ms: int) -> np.ndarray:
    from src.hostagent.audio import SAMPLE_RATE

    return np.zeros(int(SAMPLE_RATE * ms / 1000.0), dtype=np.int16)


def _parole(ms: int, amplitude: int = 8000) -> np.ndarray:
    """Signal voisé : 150 Hz + harmoniques, enveloppe variable (pas du DC)."""
    from src.hostagent.audio import SAMPLE_RATE

    n = int(SAMPLE_RATE * ms / 1000.0)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    signal = np.zeros(n, dtype=np.float64)
    for harm in range(1, 12):
        signal += (1.0 / harm) * np.sin(2.0 * np.pi * 150.0 * harm * t)
    enveloppe = 0.65 + 0.35 * np.sin(2.0 * np.pi * 3.0 * t)
    signal *= enveloppe
    pic = np.max(np.abs(signal)) or 1.0
    return np.clip(signal / pic * amplitude, -32767, 32767).astype(np.int16)


def _charger_avec_plateforme(monkeypatch, plateforme: str = "darwin"):
    """Exécute ``platform_audio.py`` comme si l'OS était ``plateforme``.

    La branche est choisie sur ``sys.platform`` à l'import : on charge donc
    le fichier sous un nom distinct, plateforme forcée, sans l'inscrire
    dans ``sys.modules`` (personne d'autre ne doit tomber dessus). Les
    modules dont il dépend sont importés *avant* le patch : rien de
    sensible à la plateforme n'est rechargé pendant qu'elle est mentie.
    """
    import native.hostagent.windows_audio  # noqa: F401
    import src.hostagent.audio  # noqa: F401

    monkeypatch.setattr(sys, "platform", plateforme)
    spec = importlib.util.spec_from_file_location(
        f"platform_audio_{plateforme}", CHEMIN_PLATFORM_AUDIO
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _imports_hors_fonctions(source: str) -> list[str]:
    """Noms importés au niveau module, y compris dans les branches de tête."""
    arbre = ast.parse(source)
    noms: list[str] = []

    def visiter(noeuds) -> None:
        for noeud in noeuds:
            if isinstance(
                noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if isinstance(noeud, ast.Import):
                noms.extend(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                noms.append(noeud.module)
            elif isinstance(noeud, ast.Try):
                visiter(noeud.body)
                visiter(noeud.orelse)
                visiter(noeud.finalbody)
                for handler in noeud.handlers:
                    visiter(handler.body)
            elif isinstance(
                noeud, (ast.If, ast.For, ast.While, ast.With, ast.AsyncFor, ast.AsyncWith)
            ):
                visiter(noeud.body)
                visiter(getattr(noeud, "orelse", []))

    visiter(arbre.body)
    return noms


def _branche_windows() -> ast.If:
    """Le ``if EST_WINDOWS:`` de tête de module."""
    arbre = ast.parse(CHEMIN_PLATFORM_AUDIO.read_text(encoding="utf-8"))
    for noeud in arbre.body:
        if (
            isinstance(noeud, ast.If)
            and isinstance(noeud.test, ast.Name)
            and noeud.test.id == "EST_WINDOWS"
        ):
            return noeud
    raise AssertionError("aucune branche `if EST_WINDOWS:` dans platform_audio.py")


# --------------------------------------------------------------------------
# Le fichier lui-même
# --------------------------------------------------------------------------
def test_le_fichier_compile_dans_les_deux_branches():
    """Aucune erreur de syntaxe — la branche macOS n'est jamais exécutée ici."""
    py_compile.compile(str(CHEMIN_PLATFORM_AUDIO), doraise=True)


def test_aucun_import_de_sounddevice_au_niveau_module():
    """Le module reste importable en conteneur et en CI, sans périphérique."""
    for nom in _imports_hors_fonctions(CHEMIN_PLATFORM_AUDIO.read_text(encoding="utf-8")):
        assert nom.split(".")[0] != "sounddevice"


def test_la_branche_windows_ne_fait_que_reexporter():
    """Sous Windows, aucune définition : que des imports de windows_audio."""
    branche = _branche_windows()
    assert branche.body, "la branche Windows est vide"
    for noeud in branche.body:
        assert isinstance(noeud, ast.ImportFrom), ast.dump(noeud)[:120]
        assert noeud.module == "native.hostagent.windows_audio"


# --------------------------------------------------------------------------
# API publique
# --------------------------------------------------------------------------
def test_l_api_publique_est_complete():
    import native.hostagent.platform_audio as platform_audio

    assert platform_audio.API_PUBLIQUE == API_PUBLIQUE
    for nom in API_PUBLIQUE:
        assert hasattr(platform_audio, nom), f"{nom} manque à l'API publique"

    assert inspect.isclass(platform_audio.PushToTalkCapture)
    assert inspect.isclass(platform_audio.CaptureContinue)
    assert callable(platform_audio.frames_from_samples)
    assert callable(platform_audio.lister_peripheriques_entree)

    for methode in ("start", "stop"):
        assert callable(getattr(platform_audio.PushToTalkCapture, methode))
        assert callable(getattr(platform_audio.CaptureContinue, methode))
    # Surface mains libres consommée par native/presence/app.py.
    for methode in (
        "segment_pret",
        "prendre_segment",
        "suspendre",
        "reprendre",
        "forcer_fin",
    ):
        assert callable(getattr(platform_audio.CaptureContinue, methode))


def test_le_module_s_importe_sans_peripherique_audio():
    """L'import ne touche ni au micro ni à sounddevice."""
    import native.hostagent.platform_audio as platform_audio
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE

    assert platform_audio.SAMPLE_RATE == SAMPLE_RATE == 16000
    assert platform_audio.FRAME_SAMPLES == FRAME_SAMPLES == 320
    assert platform_audio.AudioFrame is not None


# --------------------------------------------------------------------------
# Délégation Windows : le chemin de la démonstration
# --------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="délégation Windows")
def test_sur_windows_l_abstraction_est_windows_audio_lui_meme():
    """Identité des objets, pas simple égalité de comportement."""
    import native.hostagent.platform_audio as platform_audio
    import native.hostagent.windows_audio as windows_audio

    assert platform_audio.EST_WINDOWS is True
    assert platform_audio.PushToTalkCapture is windows_audio.PushToTalkCapture
    assert platform_audio.CaptureContinue is windows_audio.CaptureContinue
    assert platform_audio.frames_from_samples is windows_audio.frames_from_samples
    assert (
        platform_audio.lister_peripheriques_entree
        is windows_audio._lister_peripheriques_entree
    )
    assert platform_audio._fabrique_flux is windows_audio._default_stream_factory


@pytest.mark.skipif(sys.platform != "win32", reason="délégation Windows")
def test_sur_windows_la_capture_passe_par_windows_audio(monkeypatch):
    """Un flux synthétique traverse l'abstraction comme l'implémentation."""
    import native.hostagent.platform_audio as platform_audio
    import native.hostagent.windows_audio as windows_audio
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

    flux = _FluxSynthetique()
    capture = platform_audio.PushToTalkCapture(stream_factory=flux)
    assert isinstance(capture, windows_audio.PushToTalkCapture)

    capture.start()
    flux.pousser(_silence(1000))
    trames = capture.stop()

    assert len(trames) == SAMPLE_RATE // FRAME_SAMPLES == 50
    for trame in trames:
        assert type(trame) is AudioFrame
        assert trame.samples.dtype == np.float32
        assert trame.samples.shape == (FRAME_SAMPLES,)
    assert (flux.stops, flux.closes) == (1, 1)


# --------------------------------------------------------------------------
# Branche macOS / Linux : chargée et exercée depuis Windows
# --------------------------------------------------------------------------
def test_la_branche_macos_se_charge_et_expose_la_meme_api(monkeypatch):
    macos = _charger_avec_plateforme(monkeypatch, "darwin")

    assert macos.EST_WINDOWS is False
    assert macos.EST_MACOS is True
    assert macos.API_PUBLIQUE == API_PUBLIQUE
    for nom in API_PUBLIQUE:
        assert hasattr(macos, nom), f"{nom} manque à la branche macOS"
    assert inspect.isclass(macos.PushToTalkCapture)
    assert inspect.isclass(macos.CaptureContinue)
    assert callable(macos.frames_from_samples)
    assert callable(macos.lister_peripheriques_entree)


def test_la_branche_macos_herite_de_la_logique_sans_la_recopier(monkeypatch):
    """Une seule implémentation du VAD : les deux OS ne peuvent pas diverger."""
    import native.hostagent.windows_audio as windows_audio

    macos = _charger_avec_plateforme(monkeypatch, "darwin")

    assert issubclass(macos.PushToTalkCapture, windows_audio.PushToTalkCapture)
    assert issubclass(macos.CaptureContinue, windows_audio.CaptureContinue)
    assert macos.frames_from_samples is windows_audio.frames_from_samples
    # La fabrique de flux, elle, est bien spécifique : CoreAudio, pas WASAPI.
    assert macos._fabrique_flux is not windows_audio._default_stream_factory


def test_la_capture_macos_decoupe_un_flux_synthese_en_trames(monkeypatch):
    macos = _charger_avec_plateforme(monkeypatch, "darwin")
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

    flux = _FluxSynthetique()
    capture = macos.PushToTalkCapture(stream_factory=flux)
    capture.start()
    flux.pousser(_silence(1000))
    trames = capture.stop()

    assert len(trames) == SAMPLE_RATE // FRAME_SAMPLES == 50
    for trame in trames:
        assert type(trame) is AudioFrame
        assert trame.samples.dtype == np.float32
        assert trame.samples.shape == (FRAME_SAMPLES,)
    assert (flux.stops, flux.closes) == (1, 1)


def test_l_ecoute_continue_macos_segmente_la_parole_puis_le_silence(monkeypatch):
    """Le VAD hérité fonctionne à l'identique sous la classe macOS."""
    monkeypatch.setenv("TURN_SILENCE_MS", "700")
    macos = _charger_avec_plateforme(monkeypatch, "darwin")

    flux = _FluxSynthetique()
    capture = macos.CaptureContinue(stream_factory=flux)
    capture.start()
    flux.pousser(_silence(500))  # calibrage du bruit ambiant
    assert capture.segment_pret() is False

    flux.pousser(_parole(800))
    flux.pousser(_silence(700))
    assert capture.segment_pret() is True

    segment = capture.prendre_segment()
    assert capture.segment_pret() is False
    assert segment
    for trame in segment:
        assert trame.samples.shape == (320,)
    capture.stop()


def test_la_branche_linux_se_charge_aussi(monkeypatch):
    linux = _charger_avec_plateforme(monkeypatch, "linux")

    assert linux.EST_WINDOWS is False
    assert linux.EST_MACOS is False
    for nom in API_PUBLIQUE:
        assert hasattr(linux, nom), f"{nom} manque à la branche Linux"
    assert "Microphone" not in linux._message_erreur_micro(Exception("device absent"))


# --------------------------------------------------------------------------
# Permission micro (TCC) : l'échec doit être explicite, pas un traceback
# --------------------------------------------------------------------------
def test_un_refus_coreaudio_devient_une_erreur_actionnable(monkeypatch):
    """Étude §4.1 : le host-agent ne doit ni crasher ni tourner en micro mort."""
    macos = _charger_avec_plateforme(monkeypatch, "darwin")

    faux = types.ModuleType("sounddevice")

    class _ErreurPortAudio(Exception):
        pass

    def _ouvrir(**_kwargs):
        raise _ErreurPortAudio("Error opening stream: Device unavailable")

    faux.PortAudioError = _ErreurPortAudio
    faux.InputStream = _ouvrir
    monkeypatch.setitem(sys.modules, "sounddevice", faux)

    with pytest.raises(macos.ErreurMicroIndisponible) as info:
        macos._fabrique_flux(lambda *args: None)

    message = str(info.value)
    assert "Micro inutilisable" in message
    assert "Device unavailable" in message  # la cause d'origine n'est pas perdue
    assert "Microphone" in message  # la piste TCC, propre à macOS
    assert isinstance(info.value.__cause__, _ErreurPortAudio)

    assert macos.micro_accessible() is False


def test_la_sonde_micro_ouvre_un_flux_aux_bons_parametres(monkeypatch):
    """16 kHz, mono, int16 : ce que frames_from_samples attend en entrée."""
    macos = _charger_avec_plateforme(monkeypatch, "darwin")
    from src.hostagent.audio import SAMPLE_RATE

    faux = types.ModuleType("sounddevice")
    demandes: list[dict] = []

    class _Flux:
        def close(self) -> None:
            pass

    def _ouvrir(**kwargs):
        demandes.append(kwargs)
        return _Flux()

    faux.InputStream = _ouvrir
    monkeypatch.setitem(sys.modules, "sounddevice", faux)

    assert macos.micro_accessible() is True
    assert len(demandes) == 1
    demande = demandes[0]
    assert demande["samplerate"] == SAMPLE_RATE
    assert demande["channels"] == 1
    assert demande["dtype"] == "int16"
    assert callable(demande["callback"])


def test_lister_les_entrees_sans_sounddevice_ne_parle_pas_de_windows(monkeypatch, capsys):
    """Le message d'absence du paquet vient de la branche, pas de windows_audio."""
    macos = _charger_avec_plateforme(monkeypatch, "darwin")
    monkeypatch.setitem(sys.modules, "sounddevice", None)

    with pytest.raises(SystemExit) as info:
        macos.lister_peripheriques_entree()

    assert info.value.code == 1
    sortie = capsys.readouterr().out
    assert "Windows" not in sortie
    assert "sounddevice" in sortie
    assert "Microphone" in sortie  # la piste TCC est rappelée
