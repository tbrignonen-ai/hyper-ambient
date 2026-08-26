"""
Tests de la capture appuyer-pour-parler du host-agent Windows.

Ces tests tournent dans le conteneur, sans périphérique audio (pas de
``/dev/snd``, pas d'ALSA sous Docker Desktop Windows) et sans le paquet
``sounddevice``. La logique est testable parce que l'accès au matériel
passe par une fabrique de flux injectée, jamais par un import de
``sounddevice`` en tête de module. Ici, la fabrique rend un flux
synthétique : on ne touche jamais au matériel.

Asymétrie int16 / float32, intentionnelle
-----------------------------------------
``AudioFrame`` (src.hostagent.audio) refuse tout dtype autre que
float32 : une conversion implicite masquerait une erreur de
configuration du périphérique, et on ne s'en apercevrait qu'à l'oreille.
La carte son, elle, rend typiquement de l'int16. La conversion vers
float32 normalisé dans [-1, 1] (32767 → ~1.0, -32768 → ~-1.0) est le
rôle explicite de cette couche frontière, et d'elle seule. Ce n'est
pas une exception à la règle du cœur : c'est le bord du système.
"""
from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest


class _FluxSynthetique:
    """Flux d'entrée injectable : fabrique ``(callback) -> stream``.

    Même surface minimale qu'un ``InputStream`` : ``start``, ``stop``,
    ``close``. ``pousser`` simule le périphérique. Les échantillons ne
    sont livrés au callback que si le flux est démarré — un son poussé
    avant ``start`` ou après ``stop`` est perdu, comme sur un micro
    qu'on n'écoute pas.
    """

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
        """Simule l'arrivée d'échantillons depuis le périphérique."""
        if self._demarre and self._callback is not None:
            data = np.asarray(echantillons).reshape(-1)
            self._callback(data, data.size, None, None)


def _imports_hors_fonctions(source: str) -> list[str]:
    """Noms importés au niveau module, y compris dans un ``try`` de tête."""
    arbre = ast.parse(source)
    noms: list[str] = []

    def visiter(noeuds) -> None:
        for noeud in noeuds:
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
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
            elif isinstance(noeud, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
                visiter(noeud.body)
                visiter(getattr(noeud, "orelse", []))

    visiter(arbre.body)
    return noms


def test_le_module_s_importe_sans_peripherique_audio():
    """L'import ne lève pas là où sounddevice est absent : le pilote est paresseux."""
    import native.hostagent.windows_audio as windows_audio

    assert hasattr(windows_audio, "PushToTalkCapture")
    assert hasattr(windows_audio, "frames_from_samples")

    source = inspect.getsource(windows_audio)
    for nom in _imports_hors_fonctions(source):
        assert nom.split(".")[0] != "sounddevice"


def test_un_flux_est_decoupe_en_trames_de_20_ms():
    """Une seconde à 16 kHz produit exactement 50 trames de FRAME_SAMPLES échantillons."""
    from native.hostagent.windows_audio import frames_from_samples
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

    assert SAMPLE_RATE == 16000
    assert FRAME_SAMPLES == 320
    assert FRAME_SAMPLES / SAMPLE_RATE == 0.02

    echantillons = np.zeros(SAMPLE_RATE, dtype=np.float32)
    trames = frames_from_samples(echantillons, stamper=lambda: 0.0)

    assert len(trames) == SAMPLE_RATE // FRAME_SAMPLES
    assert len(trames) == 50
    for trame in trames:
        assert type(trame) is AudioFrame
        assert trame.samples.dtype == np.float32
        assert trame.samples.shape == (FRAME_SAMPLES,)


def test_un_reste_incomplet_n_est_pas_emis_en_trame_courte():
    """16 100 échantillons donnent 50 trames, pas 51 : le reliquat n'est jamais émis tronqué."""
    from native.hostagent.windows_audio import frames_from_samples
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE

    echantillons = np.zeros(SAMPLE_RATE + 100, dtype=np.float32)
    trames = frames_from_samples(echantillons, stamper=lambda: 0.0)

    assert SAMPLE_RATE + 100 == 16100
    assert 16100 // FRAME_SAMPLES == 50
    assert 16100 % FRAME_SAMPLES == 100
    assert len(trames) == 50
    for trame in trames:
        assert trame.samples.shape == (FRAME_SAMPLES,)


def test_appuyer_pour_parler_ne_capture_qu_entre_start_et_stop():
    """Le son émis avant start ou après stop n'apparaît pas dans les trames rendues."""
    from native.hostagent.windows_audio import PushToTalkCapture
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE

    avant = np.full(FRAME_SAMPLES, 0.5, dtype=np.float32)
    pendant = np.full(SAMPLE_RATE, 0.25, dtype=np.float32)
    apres = np.full(FRAME_SAMPLES, -0.5, dtype=np.float32)

    flux = _FluxSynthetique()
    capture = PushToTalkCapture(stream_factory=flux)

    flux.pousser(avant)
    capture.start()
    flux.pousser(pendant)
    trames = capture.stop()
    flux.pousser(apres)

    assert len(trames) == SAMPLE_RATE // FRAME_SAMPLES
    attendu = np.full(FRAME_SAMPLES, 0.25, dtype=np.float32)
    for trame in trames:
        assert np.allclose(trame.samples, attendu)
        assert not np.allclose(trame.samples, 0.5)
        assert not np.allclose(trame.samples, -0.5)


def test_les_echantillons_int16_sont_convertis_en_float32_normalise():
    """La frontière convertit int16 → float32 ∈ [-1, 1] ; AudioFrame refuse cette conversion."""
    from native.hostagent.windows_audio import frames_from_samples
    from src.hostagent.audio import FRAME_SAMPLES, AudioFrame, InvalidSampleDtypeError

    with pytest.raises(InvalidSampleDtypeError):
        AudioFrame(samples=np.zeros(FRAME_SAMPLES, dtype=np.int16))

    positif = np.full(FRAME_SAMPLES, 32767, dtype=np.int16)
    negatif = np.full(FRAME_SAMPLES, -32768, dtype=np.int16)
    trames = frames_from_samples(
        np.concatenate([positif, negatif]),
        stamper=lambda: 0.0,
    )

    assert len(trames) == 2
    assert trames[0].samples.dtype == np.float32
    assert trames[1].samples.dtype == np.float32
    assert np.allclose(trames[0].samples, np.float32(32767) / np.float32(32768))
    assert np.allclose(trames[1].samples, np.float32(-1.0))


def test_les_horodatages_des_trames_sont_strictement_croissants():
    """Chaque trame reçoit un stamp du stamper, strictement supérieur au précédent."""
    from native.hostagent.windows_audio import frames_from_samples
    from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE

    horloge = {"tick": 0.0}

    def stamper():
        horloge["tick"] += 1.0
        return horloge["tick"]

    echantillons = np.zeros(SAMPLE_RATE, dtype=np.float32)
    trames = frames_from_samples(echantillons, stamper)
    stamps = [trame.stamp for trame in trames]

    assert len(stamps) == SAMPLE_RATE // FRAME_SAMPLES
    assert stamps == [float(indice) for indice in range(1, 51)]
    assert all(stamps[i] < stamps[i + 1] for i in range(len(stamps) - 1))
