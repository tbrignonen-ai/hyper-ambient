"""Aides d'interface spécifiques à la plateforme, pour Presence.

Regroupe tout ce qui n'a de sens que sur un OS donné : identité
d'application, icônes, fenêtre bordeless toujours au premier plan,
transparence, zone de travail de l'écran. Le code appelant (``app.py``,
``overlay.py``) ne teste plus ``sys.platform`` lui-même et ne touche plus
``ctypes.windll`` : chaque garde vit ici, une seule fois.

Aucune fonction ne lève. Sur plateforme inconnue ou en cas d'échec, on
retombe sur un comportement neutre : mieux vaut une app sans icône et
sans chroma-key qu'une app qui ne démarre pas.

Règle dure : **aucun ``ctypes.windll`` au niveau module**. ``ctypes``
n'est importé qu'à l'intérieur de ``_workarea_windows`` et de
``force_win32_window_icon``, toutes deux derrière ``IS_WINDOWS`` — hors
Windows ``ctypes`` n'exporte pas ``windll`` et un import de tête ferait
tomber le module entier, donc l'UI avec lui.

Transparence de l'overlay : le chroma-key Windows (``-transparentcolor``,
fenêtre layered + ``SetLayeredWindowAttributes``) n'a **aucun équivalent
Tk sous Aqua**. ``-alpha`` existe mais s'applique à toute la fenêtre —
fond, dessin et texte — sans percer de couleur. Le repli phase 1 est donc
une bulle uniformément translucide (``MACOS_OVERLAY_ALPHA``) ; la parité
au pixel et les coins arrondis exigeront une ``NSWindow`` via pyobjc
(étude §3.3, hors de ce périmètre).

NON VÉRIFIÉ : aucun Mac disponible pendant l'écriture. ``iconphoto`` en
PNG sous Aqua, ``-alpha``, ``-topmost`` (notoirement peu fiable selon les
Spaces, le plein écran et Mission Control) et ``NSScreen.visibleFrame``
sont écrits d'après la doc Tk Aqua et pyobjc, et restent à valider sur
matériel réel (étude §5.3 et §5.6).
"""
from __future__ import annotations

import sys
from pathlib import Path

import tkinter as tk

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Identité shell Windows (regroupement barre des tâches / Alt-Tab). Sur
# macOS l'identité vient du bundle .app (CFBundleIdentifier), pas du code.
APP_ID = "HyperAmbient.Presence.v3"

# Clé du chroma-key Windows. Jamais du noir pur ni une teinte du dessin :
# Windows perce cette couleur de part en part, y compris aux clics. Sous
# Aqua elle ne perce rien — elle ne sert plus qu'à Windows.
COULEUR_TRANSPARENTE = "#010203"

# Repli macOS quand -transparentcolor n'existe pas : transparence globale
# de la fenêtre. 1.0 = bulle totalement opaque (carré et coins visibles) ;
# < 1.0 = bulle translucide uniforme, fond compris. Compromis assumé
# phase 1 : lisible, zéro dépendance, mais pas une découpe au pixel.
MACOS_OVERLAY_ALPHA = 0.97

# Barre de menus macOS quand NSScreen n'est pas disponible : ~24 pt. Le
# Dock n'est alors pas exclu — estimation assumée, voir
# _workarea_macos_estimee.
HAUTEUR_BARRE_MENUS_MACOS = 24


# --------------------------------------------------------------------------
# Identité applicative
# --------------------------------------------------------------------------
def set_app_identity(app_id: str = APP_ID) -> None:
    """Déclare l'identité de l'application au shell. No-op hors Windows.

    Windows : AppUserModelID, pour le regroupement barre des tâches /
    Alt-Tab et l'icône. macOS : rien à faire depuis le code — l'identité
    vient du ``Info.plist`` du bundle .app. Linux : rien.
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
    # PhotoImage sous Aqua ne sait pas lire un .ico : que du PNG. Les deux
    # noms en 256/128 n'existent pas encore dans assets/ (à générer depuis
    # le master, étude §3.1) ; ``hyper-ambient.png`` est le master 256 px
    # actuel. Les absents sont filtrés par is_file() plus bas.
    return [
        assets_dir / "hyper-ambient-256.png",
        assets_dir / "hyper-ambient.png",
        assets_dir / "hyper-ambient-128.png",
        assets_dir / "hyper-ambient-48.png",
        assets_dir / "hyper-ambient-32.png",
    ]


def apply_window_icon(root, assets_dir: Path | str):
    """Applique l'icône fenêtre (et barre des tâches / Dock) à une racine Tk.

    Retourne la ``PhotoImage`` posée, ou ``None`` si aucun candidat n'a pu
    être chargé — l'app démarre quand même.

    Windows : ``iconbitmap`` accepte le .ico ; on double d'un ``iconphoto``
    PNG quand il existe (meilleur rendu HiDPI). macOS / Linux :
    ``iconbitmap`` ne supporte pas le .ico, donc ``iconphoto`` seul. Sous
    Aqua cela règle l'icône de la fenêtre ; celle du Dock vient du bundle
    .app (CFBundleIconFile), pas d'ici.

    La référence est conservée sur ``root._icone_photo`` : sans ça Tk
    collecte l'image et l'icône disparaît.
    """
    try:
        dossier = Path(assets_dir)
        candidats = [p for p in _icone_candidats(dossier) if p.is_file()]
        if not candidats:
            return None

        if IS_WINDOWS and candidats[0].suffix.lower() == ".ico":
            try:
                root.iconbitmap(default=str(candidats[0]))
            except (OSError, tk.TclError):
                pass

        photo = None
        for chemin in candidats:
            if chemin.suffix.lower() != ".png":
                continue
            try:
                # master explicite : sans lui PhotoImage exige une racine Tk
                # par défaut déjà créée, et lève RuntimeError sinon.
                photo = tk.PhotoImage(file=str(chemin), master=root)
                break
            except (OSError, tk.TclError, RuntimeError):
                continue

        if photo is not None:
            root.iconphoto(True, photo)
            root._icone_photo = photo  # anti-GC volontaire
        return photo
    except Exception:
        # Contrat du module : l'icône est cosmétique, l'UI démarre quand même.
        # Filet volontairement large — les échecs réels varient avec la
        # plateforme, la version de Tk et l'état de la racine.
        return None


def force_win32_window_icon(root, ico_path: Path | str | None) -> None:
    """Force WM_SETICON (Tk seul ne suffit pas toujours). Windows only.

    No-op sur macOS/Linux : il n'existe aucune API Aqua pour imposer
    l'icône d'une fenêtre au-delà d'``iconphoto``.
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
    """Configure la fenêtre overlay. Retourne le mode de transparence effectif.

    ``"chromakey"``
        Windows : ``-transparentcolor`` établi. L'appelant peint le fond du
        canvas avec ``COULEUR_TRANSPARENTE`` et les pixels dessinés restent
        opaques.
    ``"alpha"``
        macOS : pas de percement couleur possible ; la fenêtre entière est
        translucide (``MACOS_OVERLAY_ALPHA``). L'appelant doit peindre le
        fond du canvas en couleur pleine — peindre ``COULEUR_TRANSPARENTE``
        ne gommerait rien, ce serait presque du noir.
    ``"opaque"``
        Repli ultime (Linux, ou Aqua qui refuse ``-alpha``) : fond plein,
        carré et coins visibles.

    L'appelant ne doit **pas** toucher ``-alpha`` après cet appel : c'est
    précisément le levier de transparence macOS, et le remettre à 1.0
    annulerait le repli.
    """
    try:
        root.overrideredirect(True)
    except tk.TclError:
        pass

    if always_on_top:
        try:
            root.wm_attributes("-topmost", True)
        except tk.TclError:
            # Aqua est censé supporter -topmost, mais il est peu fiable
            # (changement de Space, plein écran, Mission Control).
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


def fond_canvas_pour_mode(mode: str, repli: str) -> str:
    """Couleur de fond du canvas, selon le mode rendu par apply_overlay_window_mode.

    ``repli`` est la couleur pleine de l'appelant (``overlay.FOND_CHAMP``) :
    elle sert dès que le chroma-key n'est pas disponible.
    """
    return COULEUR_TRANSPARENTE if mode == "chromakey" else repli


# --------------------------------------------------------------------------
# Zone de travail (barre des tâches / barre de menus + Dock exclus)
# --------------------------------------------------------------------------
def _workarea_windows() -> tuple[int, int, int, int] | None:
    """SPI_GETWORKAREA. ``ctypes`` importé ici : jamais évalué hors Windows."""
    import ctypes

    class RECT(ctypes.Structure):
        _fields_ = (
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        )

    SPI_GETWORKAREA = 0x0030
    rectangle = RECT()
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETWORKAREA, 0, ctypes.byref(rectangle), 0
        )
    except (AttributeError, OSError):
        return None
    if not ok:
        return None
    gauche, haut = int(rectangle.left), int(rectangle.top)
    return (
        gauche,
        haut,
        int(rectangle.right) - gauche,
        int(rectangle.bottom) - haut,
    )


def _workarea_macos_native() -> tuple[int, int, int, int] | None:
    """NSScreen.visibleFrame via pyobjc, si le paquet est installé.

    ``visibleFrame`` exclut la barre de menus ET le Dock, quelle que soit
    sa position. Coordonnées : Cocoa a l'origine en bas-gauche, Tk en
    haut-gauche — d'où la conversion sur Y. Sans pyobjc (dépendance
    optionnelle, jamais imposée en phase 1) on rend None et l'appelant
    estime.
    """
    try:
        import Cocoa  # pyobjc
    except ImportError:
        return None
    try:
        ecran = Cocoa.NSScreen.mainScreen()
        utile = ecran.visibleFrame()
        plein = ecran.frame()
        y_tk = plein.size.height - (utile.origin.y + utile.size.height)
        return (
            int(utile.origin.x),
            int(y_tk),
            int(utile.size.width),
            int(utile.size.height),
        )
    except Exception:
        return None


def _workarea_macos_estimee(root) -> tuple[int, int, int, int] | None:
    """Sans pyobjc : tout l'écran moins la barre de menus. Le Dock est ignoré."""
    try:
        return (
            0,
            HAUTEUR_BARRE_MENUS_MACOS,
            root.winfo_screenwidth(),
            root.winfo_screenheight() - HAUTEUR_BARRE_MENUS_MACOS,
        )
    except (tk.TclError, AttributeError):
        return None


def screen_workarea(root) -> tuple[int, int, int, int] | None:
    """Rectangle utilisable ``(x, y, largeur, hauteur)`` en coordonnées Tk.

    Windows : SPI_GETWORKAREA. macOS : NSScreen.visibleFrame (pyobjc) ou,
    à défaut, écran moins la barre de menus. Linux : None — Tk n'expose
    pas les panels, l'appelant prend tout l'écran.
    """
    if IS_WINDOWS:
        return _workarea_windows()
    if IS_MACOS:
        natif = _workarea_macos_native()
        if natif is not None:
            return natif
        return _workarea_macos_estimee(root)
    return None


def aire_utile(racine) -> tuple[int, int, int, int]:
    """Bords de la zone utilisable ``(gauche, haut, droite, bas)``, jamais None.

    Même contrat que ``overlay.aire_utile`` — c'est le remplaçant direct du
    bloc ``windll.user32.SystemParametersInfoW`` de l'overlay, à ce détail
    près qu'il ne rend jamais None : hors Windows, ou si le système refuse
    de répondre, on retombe sur l'écran entier.
    """
    aire = screen_workarea(racine)
    if aire is None:
        try:
            return 0, 0, racine.winfo_screenwidth(), racine.winfo_screenheight()
        except (tk.TclError, AttributeError):
            return 0, 0, 0, 0
    x, y, largeur, hauteur = aire
    return x, y, x + largeur, y + hauteur
