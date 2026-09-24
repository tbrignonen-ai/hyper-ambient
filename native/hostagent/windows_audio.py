"""Capture audio native du host-agent, sur l'hôte Windows.

Ce module vit ici, pas dans le conteneur, parce que Docker Desktop
Windows n'expose aucun périphérique audio : le conteneur tourne dans une
VM, sans ``/dev/snd`` et sans ALSA. ADR-006 en tire l'architecture à
deux composants — le cœur dans le conteneur, le host-agent sur l'hôte,
seul à toucher le micro et le haut-parleur.

Il n'a le droit de faire que ``audio.capture`` et ``audio.render``.
ADR-016 règle 2 : aucune primitive d'exécution, pas de shell, pas de
spawn, pas d'accès fichier arbitraire.

Asymétrie int16 / float32, intentionnelle
-----------------------------------------
Cette couche est au contact du matériel, qui rend typiquement de l'int16.
La conversion vers float32 normalisé dans [-1, 1] (division par 32768.0)
est donc légitime, et d'elle seule. ``AudioFrame``, en aval, refuse cette
conversion : un int16 qui arriverait jusqu'à lui ne peut être qu'une
erreur de configuration, et une conversion implicite la masquerait.
"""
from __future__ import annotations

import math
import os
import threading
import time

import numpy as np

from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

# RMS int16 en dessous duquel un bloc n'est jamais de la parole (souffle, bits).
# Mesure du 23 sept, micro USB PnP : bruit 0–10, voix normale 45–80 RMS.
# À 150 puis à 60, seule une voix forte ouvrait un tour : mains libres muet.
# Le filtre de bande parole (``_trame_voix``) écarte déjà ventilateur et bruit,
# et le calage relève le seuil à 2,5 × le bruit dans une pièce plus bruyante.
PLANCHER_RMS = float(os.environ.get("HA_PLANCHER_RMS") or 35.0)
# Pendant la lecture, l'ancien plancher × 2,5 reste le minimum : sa propre
# voix rendue par les enceintes ne doit pas déclencher un barge-in.
PLANCHER_LECTURE_RMS = 375.0
# Seuil = max(PLANCHER_RMS, bruit_ambiant * FACTEUR) après ~500 ms de calage.
FACTEUR = 2.5
# Pendant la lecture : seuil relevé (anti-écho) sans sourdine totale.
FACTEUR_SEUIL_LECTURE = 2.5

# Bande parole : fondamentale voisée (~85 Hz) jusqu'aux formants (~3400 Hz).
BANDE_VOIX_BAS_HZ = 85.0
BANDE_VOIX_HAUT_HZ = 3400.0
# Rapport énergie_bande / énergie_totale au-delà duquel la trame est de la parole.
RATIO_BANDE_VOIX = 0.60

_CALIBRAGE_MS = 500.0
_DEBUT_TOUR_MS = 150.0
# Barge-in vocal : un « euh » ou un raclement ne doit pas couper la lecture.
_DEBUT_BARGE_IN_MS = 400.0
# Whisper hallucine sous ~1 s (segments 1,06–1,12 s → « Realise par Neo035 »).
# Le plancher avait été porté à 700 ms ; mesure du 24/09 : « Hyper ambiant »
# dit seul dure 480 ms et était jeté — le mains libres ne répondait plus à son
# nom. Retour à 400 ms : l'hôte jette désormais lui-même les segments de bruit
# (src/ears/silence.py), le plancher n'a plus à le faire.
_MIN_SEGMENT_MS = 400.0
_MAX_SEGMENT_MS = 15_000.0
_TRAME_MS = 1000.0 * FRAME_SAMPLES / SAMPLE_RATE

# Même principe que src.hostagent.audio._next_stamp : time.monotonic, et
# math.nextafter si deux lectures tombent dans la même graduation.
_last_stamp: float = float("-inf")


def _next_stamp() -> float:
    """Prochain stamp monotone, strictement supérieur au précédent."""
    global _last_stamp
    now = time.monotonic()
    if now <= _last_stamp:
        now = math.nextafter(_last_stamp, math.inf)
    _last_stamp = now
    return now


def _vers_float32(echantillons) -> np.ndarray:
    """Convertit int16 → float32 ∈ [-1, 1] ; laisse le float32 intact."""
    arr = np.asarray(echantillons).reshape(-1)
    if arr.dtype == np.int16:
        return arr.astype(np.float32) / np.float32(32768.0)
    return np.ascontiguousarray(arr, dtype=np.float32)


def frames_from_samples(samples, stamper=None, leftover=None):
    """Découpe en trames de FRAME_SAMPLES. Un reste incomplet n'est pas émis.

    Le reliquat est conservé dans ``leftover`` (liste d'un tableau) pour
    le tour suivant. Sans ``leftover``, il est simplement écarté — jamais
    émis tronqué, ``AudioFrame`` le refuserait et une trame courte
    désalignerait le flux.
    """
    if stamper is None:
        stamper = _next_stamp
    convertis = _vers_float32(samples)
    if leftover:
        convertis = np.concatenate([leftover[0], convertis])
    n_complet = (convertis.size // FRAME_SAMPLES) * FRAME_SAMPLES
    trames = []
    for debut in range(0, n_complet, FRAME_SAMPLES):
        chunk = np.array(
            convertis[debut : debut + FRAME_SAMPLES],
            dtype=np.float32,
            copy=True,
        )
        trames.append(AudioFrame(samples=chunk, stamp=stamper()))
    reste = np.array(convertis[n_complet:], dtype=np.float32, copy=True)
    if leftover is not None:
        leftover[:] = [reste]
    return trames


def _default_stream_factory(callback):
    """Fabrique le flux d'entrée réel. Import paresseux de sounddevice."""
    import sounddevice as sd

    return sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        callback=callback,
    )


class PushToTalkCapture:
    """Capture appuyer-pour-parler : ne retient que ce qui arrive entre start et stop.

    Le matériel n'est jamais atteint depuis la logique : ``stream_factory``
    est injectable. Les tests y branchent une source synthétique.
    """

    def __init__(self, stream_factory=None) -> None:
        self._stream_factory = (
            stream_factory if stream_factory is not None else _default_stream_factory
        )
        self._stream = None
        self._trames: list[AudioFrame] = []
        self._leftover: list = [np.zeros(0, dtype=np.float32)]
        self._actif = False
        self._t_start: float | None = None
        self._t_premier_chunk: float | None = None

    def _on_audio(self, indata, frames, time_info, status) -> None:
        if not self._actif:
            return
        if self._t_premier_chunk is None:
            self._t_premier_chunk = time.monotonic()
            attente_ms = 0.0
            if self._t_start is not None:
                attente_ms = (self._t_premier_chunk - self._t_start) * 1000.0
            print(
                f"C10 t={self._t_premier_chunk:.3f} MIC_CHUNK "
                f"n={getattr(indata, 'size', frames)} attente_ms={attente_ms:.0f}",
                flush=True,
            )
        self._trames.extend(
            frames_from_samples(indata, stamper=_next_stamp, leftover=self._leftover)
        )

    def start(self) -> None:
        """Ouvre le flux et commence à retenir les échantillons."""
        self._trames = []
        self._leftover = [np.zeros(0, dtype=np.float32)]
        self._t_premier_chunk = None
        self._actif = True
        self._t_start = time.monotonic()
        print(f"C10 t={self._t_start:.3f} MIC_START", flush=True)
        self._stream = self._stream_factory(self._on_audio)
        self._stream.start()

    def stop(self) -> list[AudioFrame]:
        """Arrête le flux et rend les trames capturées depuis start()."""
        self._actif = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return self._trames


def _silence_ms_tour() -> float:
    brut = os.environ.get("TURN_SILENCE_MS", "800")
    try:
        return max(0.0, float(brut))
    except (TypeError, ValueError):
        return 800.0


def _rms_int16(echantillons: np.ndarray) -> float:
    """RMS du bloc, ramené en unités int16 (le callback est temps réel)."""
    arr = np.asarray(echantillons).reshape(-1)
    if arr.size == 0:
        return 0.0
    if arr.dtype == np.int16:
        carres = arr.astype(np.float64)
    else:
        carres = arr.astype(np.float64) * 32768.0
    return float(np.sqrt(np.mean(np.square(carres))))


def _trame_voix(echantillons: np.ndarray) -> bool:
    """Vrai si l'énergie de la trame est concentrée dans la bande parole.

    FFT réelle sur 20 ms (320 échantillons à 16 kHz). Rejette ventilateur
    et grave continu (< 85 Hz), sifflements et clavier (> 3400 Hz),
    souffle large bande (rapport sous RATIO_BANDE_VOIX).
    """
    arr = np.asarray(echantillons).reshape(-1)
    if arr.size == 0:
        return False
    spectre = np.square(np.abs(np.fft.rfft(arr.astype(np.float64))))
    freqs = np.fft.rfftfreq(arr.size, d=1.0 / SAMPLE_RATE)
    energie_totale = float(np.sum(spectre))
    if energie_totale <= 0.0:
        return False
    dans_bande = (freqs >= BANDE_VOIX_BAS_HZ) & (freqs <= BANDE_VOIX_HAUT_HZ)
    energie_bande = float(np.sum(spectre[dans_bande]))
    return (energie_bande / energie_totale) >= RATIO_BANDE_VOIX


class CaptureContinue:
    """Flux ouvert en permanence : tours découpés au silence, sans fermer le micro.

    Le callback audio ne fait que du calcul court et un verrou bref sur le
    tampon partagé — pas de print par bloc.
    """

    def __init__(self, stream_factory=None) -> None:
        self._stream_factory = (
            stream_factory if stream_factory is not None else _default_stream_factory
        )
        self._stream = None
        self._lock = threading.Lock()
        self._actif = False
        self._suspendu = False
        self._silence_ms = _silence_ms_tour()
        self.barge_in = threading.Event()
        self._reset_etat()

    def _reset_etat(self) -> None:
        self._leftover: list = [np.zeros(0, dtype=np.float32)]
        self._prets: list[list[AudioFrame]] = []
        self._tour: list[AudioFrame] = []
        self._preambule: list[AudioFrame] = []
        self._calibrage_ms = 0.0
        self._somme_rms = 0.0
        self._seuil = PLANCHER_RMS
        self._calibre = False
        self._above_ms = 0.0
        self._below_ms = 0.0
        self._tour_ms = 0.0
        self._silence_ms = _silence_ms_tour()
        self._regime_lecture = False
        self._dernier_rms = 0.0
        self._rms_max = 0.0
        self._on_barge_in = None
        self.barge_in.clear()
        # Énoncés jetés comme trop courts : visibles dans le pouls (24/09).
        self._rejets_courts = 0
        self._dernier_rejet_ms = 0.0

    def start(self) -> None:
        """Ouvre le flux et le laisse ouvert jusqu'à stop()."""
        with self._lock:
            deja = self._stream is not None
            self._reset_etat()
            self._actif = True
            self._suspendu = False
            if deja:
                return
        self._stream = self._stream_factory(self._on_audio)
        self._stream.start()

    def stop(self) -> list[AudioFrame]:
        """Ferme le flux. Les segments non pris sont abandonnés."""
        with self._lock:
            self._actif = False
            restes = [trame for segment in self._prets for trame in segment]
            self._prets = []
            self._tour = []
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return restes

    def suspendre(self) -> None:
        """Cesse d'accumuler sans fermer le flux (anti-écho pendant la lecture)."""
        with self._lock:
            self._suspendu = True
            self._preambule = []
            self._tour = []
            self._above_ms = 0.0
            self._below_ms = 0.0
            self._tour_ms = 0.0
            self._leftover = [np.zeros(0, dtype=np.float32)]

    def reprendre(self) -> None:
        """Reprend l'accumulation ; l'état VAD repart propre (seuil conservé)."""
        with self._lock:
            self._suspendu = False
            self._preambule = []
            self._tour = []
            self._above_ms = 0.0
            self._below_ms = 0.0
            self._tour_ms = 0.0
            self._leftover = [np.zeros(0, dtype=np.float32)]

    def regime_lecture(self, actif: bool, on_barge_in=None) -> None:
        """Écoute exigeante pendant la TTS : pas de sourdine, seuil relevé.

        ``on_barge_in`` est appelé une fois, hors verrou, quand 400 ms de
        voix (bande 85–3400 Hz, RMS ≥ seuil × FACTEUR_SEUIL_LECTURE) sont
        réunies. L'audio déjà capté est conservé comme début du tour
        suivant si on quitte le régime après un barge-in.
        """
        with self._lock:
            if actif:
                self._regime_lecture = True
                self._suspendu = False
                self._on_barge_in = on_barge_in
                self.barge_in.clear()
                self._preambule = []
                self._tour = []
                self._above_ms = 0.0
                self._below_ms = 0.0
                self._tour_ms = 0.0
                self._leftover = [np.zeros(0, dtype=np.float32)]
                return
            conserver = self.barge_in.is_set()
            self._regime_lecture = False
            self._on_barge_in = None
            if conserver:
                return
            self._preambule = []
            self._tour = []
            self._above_ms = 0.0
            self._below_ms = 0.0
            self._tour_ms = 0.0
            self._leftover = [np.zeros(0, dtype=np.float32)]

    def instantane(self) -> dict:
        """Snapshot VAD pour le pouls ML : seuil, dernier RMS, accumulation.

        ``rms_max`` est le pic depuis la lecture précédente, puis repart à
        zéro : c'est lui qui dit si la voix a franchi le seuil.
        """
        with self._lock:
            pic, self._rms_max = self._rms_max, 0.0
            return {
                "seuil": float(self._seuil),
                "rms": float(self._dernier_rms),
                "rms_max": float(pic),
                "accumulation": bool(self._tour or self._preambule),
                "suspendue": bool(self._suspendu),
                "regime_lecture": bool(self._regime_lecture),
                "rejets_courts": int(self._rejets_courts),
                "dernier_rejet_ms": float(self._dernier_rejet_ms),
            }

    def segment_pret(self) -> bool:
        with self._lock:
            return bool(self._prets)

    def prendre_segment(self) -> list[AudioFrame]:
        """Rend les trames du tour écoulé et les retire, sans fermer le flux."""
        with self._lock:
            if not self._prets:
                return []
            return self._prets.pop(0)

    def forcer_fin(self) -> None:
        """Clôt le tour en cours sans attendre le silence (bouton Parler)."""
        with self._lock:
            self._cloturer(forcer=True)

    def _on_audio(self, indata, frames, time_info, status) -> None:
        if not self._actif:
            return
        arr = np.asarray(indata).reshape(-1)
        callback_barge = None
        with self._lock:
            self._dernier_rms = _rms_int16(arr)
            if not self._actif or self._suspendu:
                return
            trames = frames_from_samples(
                arr, stamper=_next_stamp, leftover=self._leftover
            )
            for trame in trames:
                if self._ingerer(trame):
                    callback_barge = self._on_barge_in
        if callback_barge is not None:
            try:
                callback_barge()
            except Exception:
                pass

    def _ingerer(self, trame: AudioFrame) -> bool:
        """Ingère une trame. True si un barge-in vocal vient d'être déclaré."""
        rms = _rms_int16(trame.samples)
        self._dernier_rms = rms
        self._rms_max = max(self._rms_max, rms)
        if not self._calibre:
            self._somme_rms += rms
            self._calibrage_ms += _TRAME_MS
            n = max(1.0, self._calibrage_ms / _TRAME_MS)
            if self._calibrage_ms >= _CALIBRAGE_MS:
                bruit = self._somme_rms / n
                self._seuil = max(PLANCHER_RMS, bruit * FACTEUR)
                self._calibre = True
            return False

        seuil = self._seuil
        debut_ms = _DEBUT_TOUR_MS
        if self._regime_lecture:
            seuil = max(self._seuil * FACTEUR_SEUIL_LECTURE, PLANCHER_LECTURE_RMS)
            debut_ms = _DEBUT_BARGE_IN_MS
        au_dessus = rms >= seuil and _trame_voix(trame.samples)
        if not self._tour:
            if au_dessus:
                self._preambule.append(trame)
                self._above_ms += _TRAME_MS
                if self._above_ms >= debut_ms:
                    self._tour = self._preambule
                    self._tour_ms = self._above_ms
                    self._preambule = []
                    self._below_ms = 0.0
                    if self._regime_lecture and not self.barge_in.is_set():
                        self.barge_in.set()
                        return True
            else:
                self._preambule = []
                self._above_ms = 0.0
            return False

        self._tour.append(trame)
        self._tour_ms += _TRAME_MS
        if au_dessus:
            self._below_ms = 0.0
        else:
            self._below_ms += _TRAME_MS
            if self._below_ms >= self._silence_ms:
                self._cloturer()
                return False
        if self._tour_ms >= _MAX_SEGMENT_MS:
            self._cloturer()
        return False

    def _cloturer(self, *, forcer: bool = False) -> None:
        trames = self._tour
        duree = self._tour_ms
        silence_final = self._below_ms
        self._tour = []
        self._preambule = []
        self._above_ms = 0.0
        self._below_ms = 0.0
        self._tour_ms = 0.0
        if not trames:
            return
        # Le silence qui clôt le tour ne compte pas : 500 ms de voix + 700 ms
        # de silence ne doivent pas passer le plancher (Whisper hallucine).
        if not forcer and (duree - silence_final) < _MIN_SEGMENT_MS:
            self._rejets_courts += 1
            self._dernier_rejet_ms = duree - silence_final
            return
        self._prets.append(trames)


def _lister_peripheriques_entree() -> None:
    """Liste les périphériques d'entrée et celui qui serait choisi.

    N'ouvre aucun flux, ne capture rien, ne se connecte à rien :
    lecture de l'inventaire PortAudio seulement. Échoue proprement
    si sounddevice est absent.
    """
    try:
        import sounddevice as sd
    except ImportError:
        print(
            "sounddevice est absent : ce programme liste le matériel "
            "audio de l'hôte Windows et ne peut pas s'exécuter là où "
            "le paquet n'est pas installé (conteneur, CI)."
        )
        raise SystemExit(1)

    try:
        peripheriques = sd.query_devices()
        choisi = sd.query_devices(kind="input")
    except Exception as exc:
        print(f"Impossible d'interroger les périphériques audio : {exc}")
        raise SystemExit(1)

    print("Périphériques d'entrée disponibles :")
    for indice, peripherique in enumerate(peripheriques):
        if peripherique["max_input_channels"] > 0:
            print(f"  [{indice}] {peripherique['name']}")
    print(f"Périphérique qui serait choisi : {choisi['name']}")


if __name__ == "__main__":
    _lister_peripheriques_entree()
