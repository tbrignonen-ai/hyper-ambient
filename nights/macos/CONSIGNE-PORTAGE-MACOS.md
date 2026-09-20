Tu es un ingenieur Python senior. Tache : demarrer le portage macOS d'une application
vocale temps reel nommee hyper-ambient, aujourd'hui developpee sur Windows.

CONTRAINTES :
- Tu n'as AUCUN environnement macOS pour tester. Ecris du code que tu juges correct, et
  signale explicitement chaque point que tu n'as pas pu verifier.
- Python 3.11+, pas de dependance lourde nouvelle sans la justifier.
- Le code Windows existant doit continuer a fonctionner a l'identique. On veut une
  abstraction de plateforme, pas un fork.

ARCHITECTURE : un host-agent sur l'hote (seul a toucher micro et haut-parleur, via
sounddevice/PortAudio) + une UI tkinter (Presence). Le coeur tourne en conteneur Docker.

=== FICHIER 1 : native/hostagent/windows_audio.py (capture/rendu audio, 181 lignes) ===
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
import time

import numpy as np

from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

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


=== FICHIER 2 : extraits Windows-specifiques de native/presence/app.py ===
        self.bouton_mains_libres: tk.Button | None = None
        self.bouton_stop: tk.Button | None = None
        self.cadre_sante: tk.Frame | None = None
        self._dernier_sante_ts = 0.0
        self._sondes_stop = threading.Event()
        self._sondes_fil: threading.Thread | None = None
        self._phrase_reprise = ""

        self.racine = tk.Tk()
        self.racine.title("hyper-ambient")
        # Icone barre des taches / Alt-Tab : Hyper Ambient (Win32 + Tk).
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "HyperAmbient.Presence.v3"
            )
        except (AttributeError, OSError):
            pass
        self._icone_path = Path(__file__).resolve().parent / "assets" / "hyper-ambient.ico"
        self._icone_photo = None
        try:
            if self._icone_path.is_file():
                self.racine.iconbitmap(default=str(self._icone_path))
                try:
                    from tkinter import PhotoImage
                    png32 = self._icone_path.with_name("hyper-ambient-32.png")
                    if png32.is_file():
                        self._icone_photo = PhotoImage(file=str(png32))
                        self.racine.iconphoto(True, self._icone_photo)
                except tk.TclError:
                    pass
        except (OSError, tk.TclError):
            pass


        self.racine.configure(bg=FOND)
        self.racine.geometry("520x800")
        self.racine.minsize(440, 700)

# ---- autre occurrence ----

        try:
            self.racine.after(visuel.INTERVALLE_MS, self.tic)
        except tk.TclError:
            return


    def _appliquer_icone_win32(self) -> None:
        """Force l'icone fenetre/tache via WM_SETICON (Tk seul ne suffit pas toujours)."""
        try:
            path = getattr(self, "_icone_path", None)
            if not path or not path.is_file():
                return
            user32 = ctypes.windll.user32
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            LoadImageW = user32.LoadImageW
            LoadImageW.restype = ctypes.c_void_p
            h_big = LoadImageW(None, str(path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            h_small = LoadImageW(None, str(path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            if not h_big and not h_small:
                return
            hwnd = self.racine.winfo_id()
            parent = user32.GetParent(hwnd)
            if parent:
                hwnd = parent
            if h_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
            if h_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
        except (AttributeError, OSError, tk.TclError):
            pass

    def fermer(self, _event: object | None = None) -> None:
        self._sondes_stop.set()
        self.session.demander_arret()

=== FICHIER 3 : extraits Windows-specifiques de native/presence/overlay.py ===
from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
import tkinter as tk
from ctypes import Structure, byref, c_long

try:
    from ctypes import windll
except (AttributeError, ImportError):  # Linux : ctypes n'exporte pas windll
    windll = None  # type: ignore
from typing import Any

try:
    from onboarding import couleurs_eclair, eclair_allume, sommets_eclair
except ImportError:
    from native.presence.onboarding import couleurs_eclair, eclair_allume, sommets_eclair

# Jamais du noir pur ni une teinte du dessin : Windows perce cette couleur
# de part en part, y compris aux clics, et un overlap trouerait la bulle.
# Réservé à l'overlay flottant. L'app garde un champ sombre plein : le
# chroma-key sur toute la fenêtre (17 sept) rendait la présence illisible.
COULEUR_TRANSPARENTE = "#010203"
FOND_CHAMP = "#0c1820"

# 33 ms ≈ 30 images/s sans occuper le fil — after, jamais un while True.
INTERVALLE_MS = 33

TAILLE_DEFAUT = 140
PORT_DEFAUT = 8123
HOTE_UDP = "127.0.0.1"
MARGE_ECRAN = 16
DUREE_ETAT_DEMO = 4.0

# ---- autre occurrence ----


import argparse
import json
import math
import socket
import sys
import time
import tkinter as tk
from ctypes import Structure, byref, c_long

try:
    from ctypes import windll
except (AttributeError, ImportError):  # Linux : ctypes n'exporte pas windll
    windll = None  # type: ignore
from typing import Any

try:
    from onboarding import couleurs_eclair, eclair_allume, sommets_eclair
except ImportError:
    from native.presence.onboarding import couleurs_eclair, eclair_allume, sommets_eclair

# Jamais du noir pur ni une teinte du dessin : Windows perce cette couleur
# de part en part, y compris aux clics, et un overlap trouerait la bulle.
# Réservé à l'overlay flottant. L'app garde un champ sombre plein : le
# chroma-key sur toute la fenêtre (17 sept) rendait la présence illisible.
COULEUR_TRANSPARENTE = "#010203"
FOND_CHAMP = "#0c1820"

# 33 ms ≈ 30 images/s sans occuper le fil — after, jamais un while True.
INTERVALLE_MS = 33

TAILLE_DEFAUT = 140
PORT_DEFAUT = 8123
HOTE_UDP = "127.0.0.1"
MARGE_ECRAN = 16
DUREE_ETAT_DEMO = 4.0
LISSAGE_NIVEAU = 0.28

# ---- autre occurrence ----

import argparse
import json
import math
import socket
import sys
import time
import tkinter as tk
from ctypes import Structure, byref, c_long

try:
    from ctypes import windll
except (AttributeError, ImportError):  # Linux : ctypes n'exporte pas windll
    windll = None  # type: ignore
from typing import Any

try:
    from onboarding import couleurs_eclair, eclair_allume, sommets_eclair
except ImportError:
    from native.presence.onboarding import couleurs_eclair, eclair_allume, sommets_eclair

# Jamais du noir pur ni une teinte du dessin : Windows perce cette couleur
# de part en part, y compris aux clics, et un overlap trouerait la bulle.
# Réservé à l'overlay flottant. L'app garde un champ sombre plein : le
# chroma-key sur toute la fenêtre (17 sept) rendait la présence illisible.
COULEUR_TRANSPARENTE = "#010203"
FOND_CHAMP = "#0c1820"

# 33 ms ≈ 30 images/s sans occuper le fil — after, jamais un while True.
INTERVALLE_MS = 33

TAILLE_DEFAUT = 140
PORT_DEFAUT = 8123
HOTE_UDP = "127.0.0.1"
MARGE_ECRAN = 16
DUREE_ETAT_DEMO = 4.0
LISSAGE_NIVEAU = 0.28
LISSAGE_TRANSITION = 0.08

CE QUE JE VEUX, en francais, structure en sections markdown :

1. INVENTAIRE : liste precise de tout ce qui est Windows-specifique dans ce qui precede,
   et pour chaque point, si sounddevice/PortAudio le couvre deja sur macOS ou non.

2. CODE : un module `native/hostagent/platform_audio.py` qui abstrait la plateforme et
   delegue a l'implementation existante sur Windows, a CoreAudio via sounddevice sur macOS.
   Donne le fichier complet, pret a coller.

3. CODE : les gardes a poser sur les appels ctypes.windll de app.py et overlay.py pour que
   macOS ne plante pas, avec l'equivalent macOS quand il existe (icone, zone de travail
   de l'ecran, identifiant d'application). Donne des diffs precis ou des fonctions completes.

4. SPECIFICITES macOS a traiter et que le code Windows ignore : permission micro (TCC),
   lanceur (.command ou .app au lieu du .bat), icone barre de menus au lieu de la barre
   des taches, signature/notarisation, Gatekeeper. Pour chacun : ce qu'il faut faire.

5. RISQUES NON VERIFIES : ce que tu n'as pas pu tester et qui doit etre valide sur un vrai Mac,
   par ordre de risque decroissant.

Sois concret et complet. Pas de preambule.