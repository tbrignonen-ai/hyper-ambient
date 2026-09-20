## 1. INVENTAIRE

| Élément | Fichier | Spécifique Windows ? | Couvert par sounddevice/PortAudio sur macOS ? |
|---|---|---|---|
| `sd.InputStream`, `sd.query_devices` | `windows_audio.py` | Non (PortAudio est multiplateforme) | **Oui** – backend CoreAudio automatique |
| Nom du module `windows_audio.py` | — | Oui (nom trompeur) | Non – à abstraire |
| `_default_stream_factory` (int16, 1 canal, `SAMPLE_RATE`) | `windows_audio.py` | Non | **Oui**, mais le taux d’échantillonnage imposé doit être supporté par le device CoreAudio (risque de resampling/échec) |
| `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID` | `app.py` | **Oui** (Win32/COM Shell) | Non – macOS n’a pas d’équivalent tkinter ; l’identité vient du `Info.plist` du bundle `.app` |
| `iconbitmap(... .ico)` | `app.py` | Partiellement | Tkignore `.ico` sur macOS ; `iconphoto` (PNG) est **cross-platform** et suffit |
| `_appliquer_icone_win32` (`LoadImageW`, `SendMessageW`, `GetParent`) | `app.py` | **Oui** (user32) | Non – macOS n’a pas d’API tkinter pour forcer l’icône fenêtre au-delà de `iconphoto` |
| `from ctypes import windll` + `Structure`, `byref`, `c_long` | `overlay.py` | Oui (import conditionnel déjà présent) | Non – doit rester `None` sur macOS et ne jamais être appelé |
| `COULEUR_TRANSPARENTE` / chroma-key (`#010203`) | `overlay.py` | **Oui** (layered window Windows) | Non – Tk macOS ne supporte pas `-transparentcolor` ni `SetLayeredWindowAttributes` |
| `print(..., flush=True)` dans le callback audio | `windows_audio.py` | Non | **Oui**, mais sur un thread temps réel macOS un flush bloquant peut pénaliser la latence (à vérifier) |

---

## 2. CODE — `native/hostagent/platform_audio.py`

Abstraction unique : sur Windows elle **délègue** à l’implémentation historique `windows_audio` (inchangée). Sur macOS/Linux elle fournit la même API via sounddevice/PortAudio, avec une gestion d’erreur spécifique TCC.

```python
"""Abstraction plateforme pour la capture/rendu audio du host-agent.

Windows : délègue à ``windows_audio`` (implémentation historique, inchangée).
macOS   : CoreAudio via sounddevice/PortAudio, même API. La logique de
découpage et de timestamps est identique ; seule la fabrique de flux et
la gestion des erreurs diffèrent (permission TCC microphone).

NON VÉRIFIÉ SUR macOS : ce module n'a pas pu être testé sur un vrai Mac.
Points à valider : permission TCC, sample rate imposé au device CoreAudio,
comportement du callback temps réel.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

from src.hostagent.audio import FRAME_SAMPLES, SAMPLE_RATE, AudioFrame

_EST_WINDOWS = sys.platform == "win32"

if _EST_WINDOWS:
    # ------------------------------------------------------------------
    # Windows : on réutilise l'implémentation existante telle quelle.
    # ------------------------------------------------------------------
    from .windows_audio import (  # type: ignore[attr-defined]
        AudioFrame,
        FRAME_SAMPLES,
        SAMPLE_RATE,
        PushToTalkCapture,
        _next_stamp,
        _lister_peripheriques_entree,
        frames_from_samples,
    )

    # Alias public stable pour les appelants du host-agent.
    lister_peripheriques_entree = _lister_peripheriques_entree

else:
    # ------------------------------------------------------------------
    # POSIX (macOS / Linux). sounddevice/PortAudio expose la même API ;
    # le backend CoreAudio sur macOS exige en revanche la permission TCC.
    # ------------------------------------------------------------------

    _dernier_stamp: float = float("-inf")

    def _next_stamp() -> float:
        """Prochain stamp monotone, strictement supérieur au précédent."""
        global _dernier_stamp
        maintenant