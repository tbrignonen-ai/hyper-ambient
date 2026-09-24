"""Abstraction plateforme de la capture audio du host-agent.

Un seul point d'entrée pour les appelants (``talk.py``, ``app.py``, les
scripts de recette) : ``PushToTalkCapture``, ``CaptureContinue``,
``frames_from_samples``, ``lister_peripheriques_entree``. ADR-006 garde
son architecture à deux composants — le cœur en conteneur, le host-agent
seul à toucher le micro — seul le bord matériel change d'OS.

Windows
    Délégation pure à ``native.hostagent.windows_audio``, inchangé : les
    noms publics sont *les objets eux-mêmes*, pas des copies ni des
    sous-classes. Le chemin de la démonstration ne change pas d'un
    octet de comportement.

macOS / Linux
    Même API, même logique. ``windows_audio`` porte un nom trompeur mais
    ne contient aucun code Windows : numpy, ``time``, ``threading``,
    ``os``, et ``sounddevice`` importé à l'intérieur des fonctions. Il
    s'importe donc tel quel sur macOS/Linux, et on lui *prend* la
    logique en héritant plutôt que de la recopier — un seul VAD, un seul
    découpage en trames de 20 ms, aucune divergence possible entre les
    deux OS. Seuls changent la fabrique de flux (CoreAudio via PortAudio)
    et la lecture des erreurs : sur macOS un refus TCC (permission
    microphone) doit remonter comme un état explicite et actionnable,
    pas comme un traceback.

NON VÉRIFIÉ SUR macOS — aucun matériel disponible pendant l'écriture :
  * un refus TCC remonte-t-il une ``PortAudioError`` franche, ou un
    callback muet qui ne livre que des zéros ? Dans le second cas
    ``micro_accessible()`` répond True et l'app tourne en micro mort
    (étude §5.1) ;
  * tous les devices CoreAudio (USB, AirPods, agrégats) acceptent-ils
    ``int16`` + 16 kHz imposés, sans ré-échantillonnage caché qui
    désalignerait le flux ? (étude §5.2) ;
  * coût du ``print(..., flush=True)`` hérité du callback sur un fil
    temps réel macOS.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

# Même bootstrap que ``native/presence/app.py`` : le host-agent tourne sur
# l'hôte, lancé depuis n'importe quel répertoire, et importe ``src.*``.
_RACINE = Path(__file__).resolve().parents[2]
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from src.hostagent.audio import (  # noqa: E402  — ré-exporté pour les appelants
    FRAME_SAMPLES,
    SAMPLE_RATE,
    AudioFrame,
)

EST_WINDOWS = sys.platform == "win32"
EST_MACOS = sys.platform == "darwin"

# Le contrat : ces quatre noms existent sur toutes les plateformes, avec
# la même signature et la même sémantique.
API_PUBLIQUE = (
    "PushToTalkCapture",
    "CaptureContinue",
    "frames_from_samples",
    "lister_peripheriques_entree",
)


class ErreurMicroIndisponible(RuntimeError):
    """Le micro n'a pas pu être ouvert : device absent, format refusé, permission.

    Sur macOS la cause la plus probable est la permission TCC. L'appelant
    (host-agent) doit transformer cette exception en état métier vers
    Presence — pas crasher, et surtout pas continuer en silence (étude
    §4.1). ADR-016 règle 2 : c'est l'UI qui ouvre les Réglages système,
    jamais le host-agent.
    """


def _message_erreur_micro(exc: BaseException) -> str:
    """Message d'échec d'ouverture, avec la piste TCC sur macOS."""
    texte = str(exc) or exc.__class__.__name__
    if not EST_MACOS:
        return f"Micro inutilisable : {texte}"
    return (
        f"Micro inutilisable : {texte}. Si macOS n'a jamais autorisé "
        "l'accès, ou si l'autorisation a été retirée : Réglages système → "
        "Confidentialité et sécurité → Microphone. L'autorisation est "
        "attribuée à l'exécutable qui lance le host-agent (python3 hors "
        "bundle, ou le bundle .app signé) — changer d'interpréteur la fait "
        "redemander."
    )


if EST_WINDOWS:
    # ------------------------------------------------------------------
    # Windows : l'implémentation historique, ré-exportée telle quelle.
    # Aucune surcouche, aucun wrapper : identité des objets garantie.
    # ------------------------------------------------------------------
    from native.hostagent.windows_audio import (  # noqa: F401
        CaptureContinue,
        PushToTalkCapture,
        frames_from_samples,
    )
    from native.hostagent.windows_audio import (
        _default_stream_factory as _fabrique_flux,
    )
    from native.hostagent.windows_audio import (
        _lister_peripheriques_entree as lister_peripheriques_entree,
    )

else:
    # ------------------------------------------------------------------
    # macOS / Linux : la logique est héritée de windows_audio (portable),
    # seul le contact avec CoreAudio/ALSA est réécrit ici.
    # ------------------------------------------------------------------
    from native.hostagent.windows_audio import (  # noqa: F401
        frames_from_samples,
    )
    from native.hostagent.windows_audio import (
        CaptureContinue as _CaptureContinueBase,
        PushToTalkCapture as _PushToTalkBase,
    )
    from native.hostagent.windows_audio import (
        _lister_peripheriques_entree as _lister_base,
    )

    def _flux_replie(sd, callback, device=None):
        """Format matériel CoreAudio puis SoXR continu vers 16 kHz mono int16."""
        import numpy as np
        import soxr

        info = sd.query_devices(device) if device is not None else sd.query_devices(kind="input")
        rate = int(round(float(info["default_samplerate"])))
        if rate < SAMPLE_RATE:
            raise ValueError(f"Fréquence d'entrée insuffisante : {rate} Hz")
        resampler = soxr.ResampleStream(rate, SAMPLE_RATE, 1, dtype="float32", quality="HQ")

        def converted(indata, frames, time_info, status):
            source = np.asarray(indata, dtype=np.float32).reshape(-1)
            output = resampler.resample_chunk(source)
            pcm = np.clip(np.round(output * 32767.0), -32768, 32767).astype(np.int16)
            if pcm.size:
                callback(pcm, int(pcm.size), time_info, status)

        kwargs = {"samplerate": rate, "channels": 1, "dtype": "float32", "callback": converted}
        if device is not None:
            kwargs["device"] = device
        return sd.InputStream(**kwargs)

    class _FluxAvecRepli:
        def __init__(self, sd, callback, stream, device=None):
            self.sd, self.callback, self.stream, self.device = sd, callback, stream, device

        def start(self):
            try:
                return self.stream.start()
            except Exception as original:
                try:
                    self.stream.close()
                    self.stream = _flux_replie(self.sd, self.callback, self.device)
                    return self.stream.start()
                except Exception as exc:
                    raise ErreurMicroIndisponible(_message_erreur_micro(exc)) from original

        def stop(self):
            return self.stream.stop()

        def close(self):
            return self.stream.close()

    def _fabrique_flux(callback, *, device=None):
        """Ouvre le flux d'entrée CoreAudio (macOS) / ALSA-Pulse (Linux).

        Paramètres identiques à ``windows_audio._default_stream_factory`` :
        16 kHz, mono, int16 — ce que ``frames_from_samples`` attend en
        entrée. Import de sounddevice paresseux, comme ailleurs : ce
        module doit rester importable dans le conteneur et en CI, où le
        paquet n'est pas installé.
        """
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise ErreurMicroIndisponible(
                "sounddevice est absent de cet environnement : sans lui le "
                "host-agent ne peut ni capturer ni restituer d'audio "
                "(pip install sounddevice)."
            ) from exc
        try:
            kwargs = {"samplerate": SAMPLE_RATE, "channels": 1, "dtype": "int16", "callback": callback}
            if device is not None:
                kwargs["device"] = device
            stream = sd.InputStream(**kwargs)
            return _FluxAvecRepli(sd, callback, stream, device) if EST_MACOS else stream
        except Exception as exc:  # PortAudioError, OSError CoreAudio, refus TCC
            if EST_MACOS and hasattr(sd, "query_devices"):
                try:
                    return _FluxAvecRepli(sd, callback, _flux_replie(sd, callback, device), device)
                except Exception:
                    pass
            raise ErreurMicroIndisponible(_message_erreur_micro(exc)) from exc

    class PushToTalkCapture(_PushToTalkBase):
        """Appuyer-pour-parler : logique héritée inchangée, flux CoreAudio."""

        def __init__(self, stream_factory=None) -> None:
            super().__init__(
                stream_factory if stream_factory is not None else _fabrique_flux
            )

        def start(self) -> None:
            try:
                super().start()
            except Exception as exc:
                self._actif = False
                if self._stream is not None:
                    try:
                        self._stream.close()
                    finally:
                        self._stream = None
                raise ErreurMicroIndisponible(_message_erreur_micro(exc)) from exc

    class CaptureContinue(_CaptureContinueBase):
        """Écoute continue segmentée : logique héritée inchangée."""

        def __init__(self, stream_factory=None) -> None:
            super().__init__(
                stream_factory if stream_factory is not None else _fabrique_flux
            )

        def start(self) -> None:
            try:
                super().start()
            except Exception as exc:
                self._actif = False
                if self._stream is not None:
                    try:
                        self._stream.close()
                    finally:
                        self._stream = None
                raise ErreurMicroIndisponible(_message_erreur_micro(exc)) from exc

    def lister_peripheriques_entree() -> None:
        """Inventaire PortAudio des entrées et du périphérique qui serait pris.

        La lecture est celle de ``windows_audio`` — l'inventaire PortAudio
        est le même partout. Seule la branche « sounddevice absent » est
        reprise ici : son message parle de l'hôte Windows, ce qui serait
        faux devant un utilisateur macOS.
        """
        try:
            import sounddevice  # noqa: F401
        except ImportError:
            print(
                "sounddevice est absent : ce programme liste le matériel "
                "audio de l'hôte et ne peut pas s'exécuter là où le paquet "
                "n'est pas installé (conteneur, CI)."
            )
            if EST_MACOS:
                print(
                    "Sur macOS, l'accès au micro est de plus soumis à la "
                    "permission TCC : Réglages système → Confidentialité et "
                    "sécurité → Microphone."
                )
            raise SystemExit(1)
        _lister_base()


DELAI_SONDE_MICRO_S = 2.5


def micro_accessible(device=None) -> bool:
    """Sonde bornée : ouverture, démarrage, puis callback observé.

    Étude §4.1 : sans pyobjc, tenter l'ouverture est le seul moyen de
    savoir si le micro est utilisable. Sur macOS elle démarre le flux et
    attend un callback borné ; silence et refus TCC restent indiscernables.
    Appelée depuis le host-agent, elle doit déboucher sur un état métier
    vers Presence, pas sur un ``SystemExit``.
    """
    if EST_WINDOWS:
        try:
            flux = _fabrique_flux(lambda *args: None)
        except ErreurMicroIndisponible as exc:
            print(f"[micro] {exc}", flush=True)
            return False
        try:
            flux.close()
        except Exception:
            pass
        return True
    event = threading.Event()
    try:
        flux = _fabrique_flux(lambda *args: event.set(), device=device)
    except ErreurMicroIndisponible as exc:
        print(f"[micro] {exc}", flush=True)
        return False
    try:
        flux.start()
        # AirPods et micros USB mettent parfois plus d'une seconde à livrer
        # le premier bloc ; 0,5 s bloquait la séance sur un faux refus.
        if not event.wait(DELAI_SONDE_MICRO_S):
            print("[micro] Accès non établi : aucun callback audio observé.", flush=True)
            return False
        return True
    except Exception as exc:
        print(f"[micro] {_message_erreur_micro(exc)}", flush=True)
        return False
    finally:
        try:
            flux.stop()
        except Exception:
            pass
        try:
            flux.close()
        except Exception:
            pass


if __name__ == "__main__":
    lister_peripheriques_entree()
