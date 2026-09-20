## 3. Gardes de plateforme pour `app.py` et `overlay.py`

### 3.0 — Helper commun : `native/presence/platform_ui.py`

On ne disperse pas les `if sys.platform` dans l'UI. Tout passe par ce module, qui ne lève jamais : une UI doit démarrer même sans icône et sans transparence.

```python
"""Aides d'interface spécifiques à la plateforme, pour Presence.

Regroupe les appels qui n'ont de sens que sur un OS donné : identité
d'application, icônes, fenêtre toujours au premier plan, transparence.
Le code appelant (app.py, overlay.py) ne teste jamais ``sys.platform``
lui-même.

Aucune fonction ne lève. Sur plateforme inconnue ou en cas d'échec, on
retombe sur un comportement neutre : mieux vaut une app sans icône et
sans chroma-key qu'une app qui ne démarre pas.

Non vérifié : je n'ai pas de Mac. Les chemins macOS (icphoto/PNG,
-alpha, -topmost, NSScreen) sont écrits d'après la doc Tk Aqua et
pyobjc, mais restent à valider sur matériel réel — voir section 5.
"""
from __future__ import annotations

import sys
from pathlib import Path

import tkinter as tk

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

APP_ID = "HyperAmbient.Presence.v3"

# Couleur-clé du chroma-key Windows. Sur macOS, Aqua ne sait pas percer
# une couleur : cette constante ne sert plus qu'à Windows.
COULEUR_TRANSPARENTE = "#010203"

# Repli macOS quand -transparentcolor n'existe pas : transparence globale
# de la fenêtre. 1.0 = bulle totalement opaque (coins carrés visibles) ;
# < 1.0 = bulle translucide uniforme. Compromis assumé phase 1.
MACOS_OVERLAY_ALPHA = 0.97


# --------------------------------------------------------------------------
# Identité applicative
# --------------------------------------------------------------------------
def set_app_identity(app_id: str = APP_ID) -> None:
    """Déclare l'identité de l'application au shell.

    Windows : AppUserModelID (regroupement barre des tâches / Alt-Tab,
    icône). macOS : rien à faire depuis le code — l'identité vient du
    bundle ``.app`` (CFBundleIdentifier) ; voir section 4. Linux : rien.
    """
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        pass


# --------------------------------------------------------------------------
# Icônes
# --------------------------------------------------------------------------
def _icone_candidats(assets_dir: Path) -> list[Path]:
    """Candidats icône, par ordre de préférence, selon la plateforme."""
    if IS_WINDOWS:
        return [
            assets_dir / "hyper-ambient.ico",
            assets_dir / "hyper-ambient-32.png",
        ]
    # PhotoImage sous Aqua ne sait pas lire un .ico : on veut du PNG.
    # (Et Tk >= 8.6 pour le canal alpha — le Tk 8.5 du Python système
    # macOS ne lit pas le PNG dans PhotoImage ; voir section 4/5.)
    return [
        assets_dir / "hyper-ambient-256.png",
        assets_dir / "hyper-ambient-128.png",
        assets_dir / "hyper-ambient-32.png",
    ]


def apply_window_icon(root, assets_dir: Path):
    """Applique l'icône fenêtre/Dock à une racine Tk. Retourne la PhotoImage.

    Windows : ``iconbitmap`` accepte le .ico ; on double d'un ``iconphoto``
    PNG si présent (meilleur rendu HiDPI). macOS / Linux : ``iconbitmap``
    ne supporte pas le .ico, on utilise exclusivement ``iconphoto`` avec
    un PNG. Sous macOS cela règle l'icône de la fenêtre ; l'icône du Dock
    vient du bundle .app (CFBundleIconFile), pas d'ici.

    Garde une référence sur ``root._icone_photo`` : sans ça, Tk collecte
    l'image et l'icône disparaît.
    """
    try:
        candidats = [p for p in _icone_candidats(Path(assets_dir)) if p.is_file()]
        if not candidats:
            return None

        if IS_WINDOWS and candidats[0].suffix.lower() == ".ico":
            try:
                root.iconbitmap(default=str(candidats[0]))
            except (OSError, tk.TclError):
                pass

        photo = None
        for chemin in candidats:
            if chemin.suffix.lower() == ".png":
                try:
                    photo = tk.PhotoImage(file=str(chemin))
                    break
                except (OSError, tk.TclError):
                    continue

        if photo is not None:
            root.iconphoto(True, photo)
            root._icone_photo = photo  # noqa: SLF001 — anti-GC volontaire
        return photo
    except (OSError, tk.TclError):
        return None


def force_win32_window_icon(root, ico_path: Path | None) -> None:
    """Force WM_SETICON (Tk seul ne suffit pas toujours). Windows only.

    No-op sur macOS/Linux : platform_ui filtre en amont, le module
    appelant n'a plus de ``ctypes.windll`` à garder.
    """
    if not IS_WINDOWS:
        return
    try:
        if ico_path is None or not Path(ico_path).is_file():
            return
        import ctypes

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1

        LoadImageW = user32.LoadImageW
        LoadImageW.restype = ctypes.c_void_p
        h_big = LoadImageW(None, str(ico_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        h_small = LoadImageW(None, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if not h_big and not h_small:
            return

        hwnd = root.winfo_id()
        parent = user32.GetParent(hwnd)
        if parent:
            hwnd = parent
        if h_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
        if h_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
    except (AttributeError, OSError, tk.TclError):
        pass


# --------------------------------------------------------------------------
# Fenêtre overlay : bordeless, toujours au premier plan, transparence
# --------------------------------------------------------------------------
def apply_overlay_window_mode(root, *, always_on_top: bool = True) -> str:
    """Configure la fenêtre overlay. Retourne le mode de transparence
    effectif : ``"chromakey"`` | ``"alpha"`` | ``"opaque"``.

    - ``"chromakey"`` : Windows, -transparentcolor établi. L'appelant
      peint le fond du canvas avec COULEUR_TRANSPARENTE.
    - ``"alpha"``     : macOS. Pas de percement couleur ; fenêtre entière
      translucide via -alpha. Fond du canvas = couleur pleine, mais toute
      la bulle (fond + dessin + texte) est atténuée.
    - ``"opaque"``    : repli ultime. Fond plein, coins carrés visibles.

    Pour la vraie parité macOS (transparence par pixel + coins arrondis),
    voir macos_overlay_native.py en 3.3 — Aqua ne connaît pas
    -transparentcolor.
    """
    try:
        root.overrideredirect(True)
    except tk.TclError:
        pass

    if always_on_top:
        try:
            root.wm_attributes("-topmost", True)
        except tk.TclError:
            # Aqua : -topmost est censé être supporté, mais peu fiable
            # (voir section 5, risque Spaces / plein écran).
            pass

    if IS_WINDOWS:
        try:
            root.wm_attributes("-transparentcolor", COULEUR_TRANSPARENTE)
            return "chromakey"
        except tk.TclError:
            pass

    if IS_MACOS:
        try:
            root.wm_attributes("-alpha", MACOS_OVERLAY_ALPHA)
            return "alpha"
        except tk.TclError:
            return "opaque"

    return "opaque"


# --------------------------------------------------------------------------
# Zone de travail (barre des tâches / menu bar + Dock exclus)
# --------------------------------------------------------------------------
class _RECT(ctypes_structure):
    pass  # défini paresseusement ci-dessous pour éviter ctypes hors Windows


def _workarea_windows() -> tuple[int, int, int, int] | None:
    """SPI_GETWORKAREA. ctypes importé localement : jamais évalué ailleurs."""
    import ctypes
    from ctypes import wintypes  # noqa: F401 — dispo seulement sur Windows

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = RECT()
    SPI_GETWORKAREA = 0x0030
    if ctypes.windll.user32.SystemParametersInfoW(  # noqa: DUO105
        SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
    ):
        return (
            rect.left,
            rect.top,
            rect.right - rect.left,
            rect.bottom - rect.top,
        )
    return None


def _workarea_macos_native() -> tuple[int, int, int, int] | None:
    """NSScreen.visibleFrame via pyobjc, si le paquet est installé.

    visibleFrame exclut la barre de menus ET le Dock, quelle que soit sa
    position. Sans pyobjc on retombe sur une estimation (voir appelant).
    Coordonnées : Cocoa a l'origine en bas-gauche, Tk en haut-gauche.
    """
    try:
        import Cocoa  # pyobjc
    except ImportError:
        return None
    try:
        ecran = Cocoa.NSScreen.mainScreen()
        vf = ecran.visibleFrame()
        plein = ecran.frame()
        y_tk = plein.size.height - (vf.origin.y + vf.size.height)
        return (
            int(vf.origin.x),
            int(y_tk),
            int(vf.size.width),
            int(vf.size.height),
        )
    except Exception:
        return None


def screen_workarea(root) -> tuple[int, int, int, int] | None:
    """Rectangle utilisable (x, y, w, h) en coordonnées Tk, ou None.

    Windows : SPI_GETWORKAREA. macOS : NSScreen.visibleFrame (pyobjc) ou,
    à défaut, estimation Tk (barre de menus ~24 pt ; Dock ignoré). Linux :
    None — Tk n'expose pas les panels, l'appelant utilise tout l'écran.
    """
    if IS_WINDOWS:
        return _workarea_windows()
    if IS_MACOS:
        natif = _workarea_macos_native()
        if natif is not None:
            return natif
        try:
            return (0, 24, root.winfo_screenwidth(), root.winfo_screenheight() - 24)
        except tk.TclError:
            return None
    return None
```

> Retire la classe `_RECT` factice plus haut si tu préfères : elle n'est là que pour documenter que `ctypes` n'est importé qu'à l'intérieur de `_workarea_windows`. Le point dur : **aucun `ctypes.windll` au niveau module** de `platform_ui.py`.

---

### 3.1 — `app.py` : diffs précis

**Import en tête de fichier** (même style que le `try/except` d'`overlay.py` pour `onboarding`) :

```diff
+try:
+    import platform_ui
+except ImportError:
+    from native.presence import platform_ui
+
-import ctypes   # retirer si c'est le seul usage (windll)
```

**Bloc d'initialisation fenêtre** :

```diff
         self.racine = tk.Tk()
         self.racine.title("hyper-ambient")
-        # Icone barre des taches / Alt-Tab : Hyper Ambient (Win32 + Tk).
-        try:
-            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
-                "HyperAmbient.Presence.v3"
-            )
-        except (AttributeError, OSError):
-            pass
-        self._icone_path = Path(__file__).resolve().parent / "assets" / "hyper-ambient.ico"
-        self._icone_photo = None
-        try:
-            if self._icone_path.is_file():
-                self.racine.iconbitmap(default=str(self._icone_path))
-                try:
-                    from tkinter import PhotoImage
-                    png32 = self._icone_path.with_name("hyper-ambient-32.png")
-                    if png32.is_file():
-                        self._icone_photo = PhotoImage(file=str(png32))
-                        self.racine.iconphoto(True, self._icone_photo)
-                except tk.TclError:
-                    pass
-        except (OSError, tk.TclError):
-            pass
+        # Identité shell (Windows) + icône fenêtre/Dock : délègue à
+        # platform_ui, qui sait quoi faire par OS. `_icone_path` reste le
+        # .ico Windows (utilisé par _appliquer_icone_win32) ; platform_ui
+        # choisit seul les PNG sur macOS/Linux.
+        platform_ui.set_app_identity()
+        self._icone_path = (
+            Path(__file__).resolve().parent / "assets" / "hyper-ambient.ico"
+        )
+        self._icone_photo = platform_ui.apply_window_icon(
+            self.racine, self._icone_path.parent
+        )
```

**`_appliquer_icone_win32` devient un wrapper** (les appelants existants sont inchangés) :

```diff
     def _appliquer_icone_win32(self) -> None:
-        """Force l'icone fenetre/tache via WM_SETICON (Tk seul ne suffit pas toujours)."""
-        try:
-            path = getattr(self, "_icone_path", None)
-            if not path or not path.is_file():
-                return
-            user32 = ctypes.windll.user32
-            IMAGE_ICON = 1
-            LR_LOADFROMFILE = 0x0010
-            WM_SETICON = 0x0080
-            ICON_SMALL, ICON_BIG = 0, 1
-            LoadImageW = user32.LoadImageW
-            LoadImageW.restype = ctypes.c_void_p
-            h_big = LoadImageW(None, str(path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
-            h_small = LoadImageW(None, str(path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
-            if not h_big and not h_small:
-                return
-            hwnd = self.racine.winfo_id()
-            parent = user32.GetParent(hwnd)
-            if parent:
-                hwnd = parent
-            if h_small:
-                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
-            if h_big:
-                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
-        except (AttributeError, OSError, tk.TclError):
-            pass
+        """Force WM_SETICON (Windows). No-op sur macOS/Linux."""
+        platform_ui.force_win32_window_icon(
+            self.racine, getattr(self, "_icone_path", None)
+        )
```

**Action asset à ne pas oublier** : macOS ne peut pas consommer `hyper-ambient.ico` via Tk. Génère, depuis l'ico existant (ou depuis une source 1024 px), au minimum `assets/hyper-ambient-256.png` et `assets/hyper-ambient-128.png`. Commande indicative (sur n'importe quelle machine, hors Mac) :

```bash
# si ImageMagick est dispo ; sinon exporter depuis l'outil graphique
magick assets/hyper-ambient.ico -define png:include-chunk=none \
       assets/hyper-ambient-256.png
magick assets/hyper-ambient.ico -define png:include-chunk=none \
       assets/hyper-ambient-128.png
```

---

### 3.2 — `overlay.py` : le point critique, la transparence

#### 3.2.1 Pourquoi le chroma-key Windows ne se transpose pas

`COULEUR_TRANSPARENTE = "#010203"` + `wm_attributes("-transparentcolor", ...)` est une primitive **Windows only** de Tk (fenêtre layered + `SetLayeredWindowAttributes`). Sur Aqua :

- `-transparentcolor` n'existe pas → `TclError: bad attribute "-transparentcolor"` si appelé.
- `-alpha` existe mais s'applique à **toute la fenêtre** : fond, dessin, texte. On ne peut pas percer une couleur tout en gardant le reste opaque.
- `PhotoImage` sait porter un canal alpha PNG (Tk 8.6+), mais cela ne rend pas le **fond de la fenêtre** transparent.

Donc **il n'y a pas d'équivalent Tk du chroma-key sur macOS**. Trois réponses possibles, par ordre de coût :

1. **Repli Tk « bulle opaque/translucide »** — zéro dépendance, à faire **maintenant**.
2. **Vraie fenêtre transparente via pyobjc/NSWindow** — dépendance légère, parité visuelle réelle, mais réécriture du rendu.
3. **Garder Tk et accepter la non-parité** en phase 1.

Je code (1) immédiatement et donne la trajectoire (2).

#### 3.2.2 Diff central — configuration de la fenêtre

Le bloc Windows (ici représenté ; adapte au nom réel de ta méthode) :

```diff
-        self.racine.overrideredirect(True)
-        self.racine.wm_attributes("-topmost", True)
-        self.racine.wm_attributes("-transparentcolor", COULEUR_TRANSPARENTE)
-        self.canvas = tk.Canvas(
-            self.racine, bg=COULEUR_TRANSPARENTE, highlightthickness=0, bd=0
-        )
+        # Transparence + toujours-au-premier-plan : dispatch plateforme.
+        # Retourne "chromakey" (Windows), "alpha" (macOS) ou "opaque".
+        self._mode_transparence = platform_ui.apply_overlay_window_mode(self.racine)
+        self._fond_canvas = (
+            COULEUR_TRANSPARENTE
+            if self._mode_transparence == "chromakey"
+            else FOND_CHAMP
+        )
+        self.canvas = tk.Canvas(
+            self.racine, bg=self._fond_canvas, highlightthickness=0, bd=0
+        )
```

**Audit obligatoire du rendu** : dans la boucle de dessin (`tic`, `_dessiner`, etc.), **chaque** occurrence de `COULEUR_TRANSPARENTE` utilisée comme couleur de fond/gomme doit devenir `self._fond_canvas`. En mode `"alpha"`/`"opaque"`, peindre avec `COULEUR_TRANSPARENTE` ne gommerait rien (ce serait presque du noir). Concrètement :

```diff
-        self.canvas.itemconfig(self._fond, fill=COULEUR_TRANSPARENTE)
+        self.canvas.itemconfig(self._fond, fill=self._fond_canvas)
```

Et idem pour tout `create_rectangle(..., fill=COULEUR_TRANSPARENTE, ...)`.

#### 3.2.3 Diff — zone de travail et appels Win32 résiduels

```diff
-        # AVANT (Win32 direct) : explose si windll est None (macOS/Linux)
-        if windll is not None:
-            rect = RECT()
-            windll.user32.SystemParametersInfoW(0x0030, 0, byref(rect), 0)
-            droite, bas = rect.right, rect.bottom
-        else:
-            droite = self.racine.winfo_screenwidth()
-            bas = self.racine.winfo_screenheight()
+        # APRÈS : plus aucun windll dans overlay.py
+        wa = platform_ui.screen_workarea(self.racine)
+        if wa is None:
+            wa = (0, 0, self.racine.winfo_screenwidth(), self.racine.winfo_screenheight())
+        _x, _y, _largeur_wa, hauteur_wa = wa
```

Pour **tout** autre appel `windll.*` resté dans le fichier (non visible dans l'extrait fourni), le patron de garde est :

```python
def _un_truc_win32_specifique(root):
    """Repli neutre hors Windows. ctypes importé localement : jamais
    évalué sur macOS/Linux."""
    if not platform_ui.IS_WINDOWS:
        return None
    import ctypes

    user32 = ctypes.windll.user32
    # ... logique Win32 inchangée ...
```

Quand tu as fini la migration, **retire de `overlay.py`** :

```diff
-from ctypes import Structure, byref, c_long
-
-try:
-    from ctypes import windll
-except (AttributeError, ImportError):  # Linux : ctypes n'exporte pas windll
-    windll = None  # type: ignore
+try:
+    import platform_ui
+except ImportError:
+    from native.presence import platform_ui
```

`Structure`, `byref`, `c_long` sont des noms standards de `ctypes`, disponibles partout : leur présence ne casse pas macOS. Mais si plus rien ne les utilise, les garder entretient la confusion. Le vrai danger était `windll` (déjà gardé) et ses **usages** (à migrer).

#### 3.2.3bis — `-topmost` sur macOS

`wm_attributes("-topmost", True)` est censé être supporté par Aqua, mais il est notoirement peu fiable (perte du niveau lors d'un changement de Space, en plein écran, ou sous Mission Control). Si le comportement s'avère insuffisant sur Mac, la seule bascule fiable est native :

```python
# dans macos_overlay_native.MacNativeOverlay.__init__
self.win.setLevel_(Cocoa.NSFloatingWindowLevel)          # ou kCGScreenSaverWindowLevel
self.win.setCollectionBehavior_(Cocoa.NSWindowCollectionBehaviorCanJoinAllSpaces)
```

Cela implique d'abandonner la fenêtre Tk pour l'overlay — voir ci-dessous.

#### 3.3 — Trajectoire parité réelle : `native/presence/macos_overlay_native.py` (optionnel, phase 2)

Si le repli « bulle opaque/translucide » est jugé insuffisant, la seule façon d'obtenir sur macOS une fenêtre sans fond, aux coins arrondis, toujours au premier plan, est une `NSWindow` pilotée via **pyobjc**. C'est une dépendance nouvelle mais **légère et justifiée** : c'est un wrapper Python fin sur des frameworks déjà présents sur le Mac, rien à bundler, et il n'y a pas d'alternative (Tk pur ne peut pas). On la garde **strictement optionnelle** : si `Cocoa` est absent, on reste sur le repli Tk.

```python
"""Overlay natif macOS (NSWindow transparente, toujours au premier plan).

Pourquoi ce module existe
-------------------------
Tk/Aqua ne connaît pas ``-transparentcolor`` (chroma-key Windows). En Tk
pur, impossible de percer une couleur dans la fenêtre. La seule façon
d'avoir une bulle au fond réellement transparent, aux coins arrondis et
au-dessus de tout (y compris en plein écran), est une NSWindow bordeless
non-opaque, pilotée via pyobjc.

Dépendance optionnelle : ``pip install pyobjc-cocoa``. Si le paquet est
absent, ``disponible()`` renvoie False et l'appelant retombe sur le repli
Tk (platform_ui.apply_overlay_window_mode). pyobjc n'est donc jamais
imposé.

Portée : ce module remplace la *fenêtre*, pas la logique de l'overlay. Le
portage du dessin (l'éclair, les sommets, les niveaux) vers CoreGraphics
ou des CALayers est un chantier séparé — à ne lancer que si le repli
opaque de la phase 1 est jugé insuffisant.

NON VÉRIFIÉ : aucun test sur Mac. Les constantes pyobjc, la conversion de
coordonnées et le collection behavior sont à valider (section 5).
"""
from __future__ import annotations


def disponible() -> bool:
    """True si pyobjc/cocoa est importable."""
    try:
        import Cocoa  # noqa: F401
    except ImportError:
        return False
    return True


class MacNativeOverlay:
    """Fenêtre flottante transparente, coins arrondis, click-through."""

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        import Cocoa

        self._C = Cocoa
        ecran = Cocoa.NSScreen.mainScreen()
        self._h_ecran = ecran.frame().size.height
        self._h = h

        rect = Cocoa.NSMakeRect(
            float(x), self._vers_cocoa_y(y, h), float(w), float(h)
        )
        self.win = Cocoa.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            Cocoa.NSWindowStyleMaskBorderless,
            Cocoa.NSBackingStoreBuffered,
            False,
        )
        self.win.setOpaque_(False)
        self.win.setBackgroundColor_(Cocoa.NSColor.clearColor())
        self.win.setHasShadow_(False)
        self.win.setIgnoresMouseEvents_(True)  # click-through, comme l'overlay Windows
        self.win.setLevel_(Cocoa.NSFloatingWindowLevel)
        self.win.setCollectionBehavior_(
            Cocoa.NSWindowCollectionBehaviorCanJoinAllSpaces
        )
        self.win.orderFrontRegardless()

    # -- coordonnées : Cocoa