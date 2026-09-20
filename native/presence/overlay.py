"""Présence visuelle d'hyper-ambient : une bulle qui respire, pas une fenêtre.

Le dessin vit sur l'hôte Windows — le conteneur n'a aucun accès à l'écran.
tkinter seulement : l'utilisateur a refusé PyQt, Electron et pygame.

    python native/presence/overlay.py --demo
    python native/presence/overlay.py --coin haut-gauche --taille 160
    python native/presence/overlay.py --off --port 8123
"""
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
LISSAGE_NIVEAU = 0.28
LISSAGE_TRANSITION = 0.08

ETATS = ("repos", "ecoute", "reflexion", "escalade", "parole")
COINS = ("bas-droite", "bas-gauche", "haut-droite", "haut-gauche")

# Intentions, pas un nuancier : froid et presque absent au repos, glace
# quand elle écoute, or qui tourne quand elle travaille ici, braise quand
# la question est partie au loin, chaleur vive quand c'est elle qui parle.
PALETTES: dict[str, dict[str, Any]] = {
    "repos": {
        "coeur": "#2a5868",
        "lueur": "#8ad4e6",
        "anneau": "#4e90a4",
        "periode": 5.6,
        "amplitude": 0.08,
        "alpha_min": 0.16,
        "alpha_max": 0.30,
        "vitesse_rotation": 8.0,
        "scintillement": 0.0,
        "suit_niveau": False,
    },
    "ecoute": {
        "coeur": "#7eb8c8",
        "lueur": "#d0eef4",
        "anneau": "#9cccdc",
        "periode": 1.7,
        "amplitude": 0.10,
        "alpha_min": 0.42,
        "alpha_max": 0.74,
        "vitesse_rotation": 0.0,
        "scintillement": 0.0,
        "suit_niveau": True,
    },
    "reflexion": {
        "coeur": "#c8a46c",
        "lueur": "#e8d0a0",
        "anneau": "#d4b47c",
        "periode": 2.4,
        "amplitude": 0.07,
        "alpha_min": 0.48,
        "alpha_max": 0.62,
        "vitesse_rotation": 55.0,
        "scintillement": 0.35,
        "suit_niveau": False,
    },
    "escalade": {
        "coeur": "#d87850",
        "lueur": "#f0c090",
        "anneau": "#e09060",
        "periode": 1.3,
        "amplitude": 0.14,
        "alpha_min": 0.58,
        "alpha_max": 0.82,
        "vitesse_rotation": 140.0,
        "scintillement": 0.7,
        "suit_niveau": False,
    },
    "parole": {
        "coeur": "#e8dcc8",
        "lueur": "#fff6e8",
        "anneau": "#f0e4d0",
        "periode": 0.55,
        "amplitude": 0.18,
        "alpha_min": 0.55,
        "alpha_max": 0.92,
        "vitesse_rotation": 18.0,
        "scintillement": 0.15,
        "suit_niveau": False,
    },
}


def _palette_contraste(etat: str, coeur: str, lueur: str, anneau: str) -> dict[str, Any]:
    base = dict(PALETTES[etat])
    base["coeur"] = coeur
    base["lueur"] = lueur
    base["anneau"] = anneau
    return base


# WCAG 1.4.11 : objets graphiques ≥ 3:1 contre FOND_CHAMP (malvoyants).
PALETTES_CONTRASTE: dict[str, dict[str, Any]] = {
    "repos": _palette_contraste("repos", "#7ec8dc", "#e8f8fc", "#a8e0f0"),
    "ecoute": _palette_contraste("ecoute", "#b8e8f4", "#f4fcff", "#d0f0f8"),
    "reflexion": _palette_contraste("reflexion", "#f0d090", "#fff4d0", "#f8e0a8"),
    "escalade": _palette_contraste("escalade", "#ffb080", "#ffe8c8", "#ffc898"),
    "parole": _palette_contraste("parole", "#fff6e8", "#ffffff", "#ffe8c0"),
}


def palette_pour(etat: str, contraste: bool = False) -> dict[str, Any]:
    source = PALETTES_CONTRASTE if contraste else PALETTES
    return dict(source.get(etat, source["repos"]))


def palettes(contraste: bool = False) -> dict[str, dict[str, Any]]:
    """Jeux de couleurs de la bulle. ``True`` = WCAG 1.4.11 (≥ 3:1 vs fond)."""
    source = PALETTES_CONTRASTE if contraste else PALETTES
    return {etat: dict(source[etat]) for etat in ETATS}


class RECT(Structure):
    """Aire utile Windows, pour coller la bulle au-dessus de la barre des tâches."""

    _fields_ = (
        ("left", c_long),
        ("top", c_long),
        ("right", c_long),
        ("bottom", c_long),
    )


def aire_utile(racine: tk.Tk) -> tuple[int, int, int, int]:
    """Rectangle hors barre des tâches — sa hauteur n'est pas une constante."""
    if windll is not None:
        try:
            rectangle = RECT()
            if windll.user32.SystemParametersInfoW(48, 0, byref(rectangle), 0):
                return (
                    int(rectangle.left),
                    int(rectangle.top),
                    int(rectangle.right),
                    int(rectangle.bottom),
                )
        except Exception:
            pass
    return 0, 0, racine.winfo_screenwidth(), racine.winfo_screenheight()


def vers_rgb(hex_couleur: str) -> tuple[int, int, int]:
    texte = hex_couleur.lstrip("#")
    return int(texte[0:2], 16), int(texte[2:4], 16), int(texte[4:6], 16)


def vers_hex(rgb: tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(canal))) for canal in rgb)
    # Un canal à (1, 2, 3) recollerait la clé de transparence : on l'évite.
    if (r, g, b) == (1, 2, 3):
        b = 4
    return f"#{r:02x}{g:02x}{b:02x}"


def interpoler_canal(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpoler_hex(debut: str, fin: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    da, fa = vers_rgb(debut), vers_rgb(fin)
    return vers_hex(tuple(interpoler_canal(x, y, t) for x, y in zip(da, fa)))


def melanger_palettes(actuelle: dict[str, Any], cible: dict[str, Any], t: float) -> dict[str, Any]:
    t = max(0.0, min(1.0, t))
    mixee = dict(cible)
    for cle in ("coeur", "lueur", "anneau"):
        mixee[cle] = interpoler_hex(actuelle[cle], cible[cle], t)
    for cle in (
        "periode",
        "amplitude",
        "alpha_min",
        "alpha_max",
        "vitesse_rotation",
        "scintillement",
    ):
        mixee[cle] = interpoler_canal(float(actuelle[cle]), float(cible[cle]), t)
    mixee["suit_niveau"] = cible["suit_niveau"] if t > 0.5 else actuelle["suit_niveau"]
    return mixee


def points_blob(
    cx: float,
    cy: float,
    rayon: float,
    maintenant: float,
    *,
    n: int = 16,
    irreg: float = 0.14,
    phase: float = 0.0,
    rotation: float = 0.0,
) -> tuple[float, ...]:
    """Polygone irrégulier : une forme qui respire, pas un ovale figé."""
    coords: list[float] = []
    for i in range(n):
        theta = rotation + (2.0 * math.pi * i / n)
        wobble = (
            1.0
            + irreg * math.sin(theta * 3.0 + maintenant * 0.7 + phase)
            + (irreg * 0.45) * math.sin(theta * 5.0 - maintenant * 1.1 + phase * 1.7)
        )
        r = rayon * wobble
        coords.append(cx + r * math.cos(theta))
        coords.append(cy + r * math.sin(theta))
    return tuple(coords)


def dessiner_souffle(
    toile: tk.Canvas,
    *,
    cx: float,
    cy: float,
    rayon: float,
    palette: dict[str, Any],
    maintenant: float,
    etat: str,
    souffle: float,
) -> None:
    """Onde de souffle : anneaux qui s'éloignent du cœur — le geste HA lisible."""
    periode = max(0.45, float(palette["periode"]))
    lueur = str(palette["lueur"])
    anneau = str(palette["anneau"])
    n_ondes = 3 if etat in ("parole", "escalade", "ecoute") else 2
    portee = 0.55 + 0.9 * max(0.0, min(1.0, souffle))
    for i in range(n_ondes):
        phase = (maintenant / periode + i / n_ondes) % 1.0
        r = rayon * (0.85 + portee * phase)
        largeur = max(2, int(6 * (1.0 - 0.7 * phase)))
        couleur = interpoler_hex(lueur, anneau, phase)
        toile.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="",
            outline=couleur,
            width=largeur,
            tags=("orbe", "souffle"),
        )


def dessiner_nappe(
    toile: tk.Canvas,
    *,
    largeur: float,
    hauteur: float,
    palette: dict[str, Any],
    maintenant: float,
    etat: str,
    ampleur: float = 0.38,
    etendre: bool = False,
) -> None:
    """Nappe ambiante : un corps rempli qui dérive, pas des anneaux vides."""
    cx, cy = largeur / 2.0, hauteur / 2.0
    lueur = str(palette["lueur"])
    anneau = str(palette["anneau"])
    coeur = str(palette["coeur"])
    portee = max(largeur, hauteur) if etendre else min(largeur, hauteur)
    toile.create_polygon(
        *points_blob(
            cx,
            cy,
            portee * ampleur,
            maintenant,
            n=14,
            irreg=0.14,
            phase=0.4,
        ),
        fill=interpoler_hex(coeur, lueur, 0.28),
        outline="",
        smooth=True,
        tags="nappe",
    )
    derivees = (
        (0.18, 0.16, 0.0, ampleur * 0.74),
        (0.14, 0.12, 1.7, ampleur * 0.58),
        (0.11, 0.19, 3.1, ampleur * 0.47),
    )
    for i, (amp, spd, ph, scale) in enumerate(derivees):
        ox = largeur * amp * math.sin(maintenant * spd + ph)
        oy = hauteur * amp * 0.72 * math.cos(maintenant * spd * 0.8 + ph + 0.4)
        r = portee * scale
        fill = interpoler_hex(coeur, lueur, 0.40 + 0.18 * i)
        toile.create_polygon(
            *points_blob(
                cx + ox,
                cy + oy,
                r,
                maintenant,
                n=12,
                irreg=0.18,
                phase=ph,
            ),
            fill=fill,
            outline="",
            smooth=True,
            tags="nappe",
        )
    n_rubans = 3 if etat in ("reflexion", "escalade", "parole") else 2
    for i in range(n_rubans):
        start = (maintenant * (14.0 + i * 8.0) + i * 80.0) % 360.0
        rr = portee * (ampleur + 0.04 + i * 0.10)
        toile.create_arc(
            cx - rr,
            cy - rr * 0.74,
            cx + rr,
            cy + rr * 0.74,
            start=start,
            extent=72 + i * 16,
            style=tk.ARC,
            outline=anneau if i else lueur,
            width=2 if i == 0 else 1,
            tags="nappe",
        )


def dessiner_orbe(
    toile: tk.Canvas,
    *,
    cx: float,
    cy: float,
    taille: float,
    etat: str,
    palette: dict[str, Any],
    angle: float,
    souffle: float,
    maintenant: float,
) -> None:
    """Présence vivante : blobs, halos décalés, filaments et grains en orbite."""
    rayon_base = taille * 0.28
    rayon = rayon_base * (1.0 + float(palette["amplitude"]) * (souffle * 2.0 - 1.0))
    scintil = float(palette["scintillement"])
    if scintil:
        rayon += rayon_base * 0.04 * scintil * math.sin(maintenant * 11.0)

    coeur = str(palette["coeur"])
    lueur = str(palette["lueur"])
    anneau = str(palette["anneau"])
    rotation = angle * math.pi / 180.0

    dessiner_souffle(
        toile,
        cx=cx,
        cy=cy,
        rayon=rayon,
        palette=palette,
        maintenant=maintenant,
        etat=etat,
        souffle=souffle,
    )

    toile.create_polygon(
        *points_blob(
            cx,
            cy,
            rayon * 1.12,
            maintenant,
            n=16,
            irreg=0.12,
            phase=0.2,
            rotation=rotation * 0.15,
        ),
        fill=interpoler_hex(coeur, lueur, 0.22),
        outline=anneau,
        width=max(2, int(taille * 0.025)),
        smooth=True,
        joinstyle=tk.ROUND,
        tags="orbe",
    )
    toile.create_polygon(
        *points_blob(
            cx,
            cy,
            rayon * 0.72,
            maintenant,
            n=14,
            irreg=0.13,
            phase=1.1,
            rotation=-rotation * 0.08,
        ),
        fill=coeur,
        outline=lueur,
        width=1,
        smooth=True,
        tags="orbe",
    )
    toile.create_oval(
        cx - rayon * 0.32,
        cy - rayon * 0.32,
        cx + rayon * 0.32,
        cy + rayon * 0.32,
        fill=coeur,
        outline=lueur,
        width=1,
        tags="orbe",
    )
    toile.create_oval(
        cx - rayon * 0.14,
        cy - rayon * 0.18,
        cx + rayon * 0.10,
        cy + rayon * 0.06,
        fill=lueur,
        outline="",
        tags="orbe",
    )

    epaisseur = max(2, int(taille * 0.03))
    etendue = 110 if etat == "escalade" else 64
    toile.create_arc(
        cx - rayon * 1.22,
        cy - rayon * 1.22,
        cx + rayon * 1.22,
        cy + rayon * 1.22,
        start=angle,
        extent=etendue,
        style=tk.ARC,
        outline=lueur,
        width=epaisseur,
        tags="orbe",
    )
    toile.create_arc(
        cx - rayon * 1.05,
        cy - rayon * 1.05,
        cx + rayon * 1.05,
        cy + rayon * 1.05,
        start=(-angle * 0.7 + 40.0) % 360.0,
        extent=42,
        style=tk.ARC,
        outline=anneau,
        width=max(1, epaisseur - 1),
        tags="orbe",
    )
    if etat == "escalade":
        toile.create_arc(
            cx - rayon * 0.95,
            cy - rayon * 0.95,
            cx + rayon * 0.95,
            cy + rayon * 0.95,
            start=(-angle * 1.4) % 360.0,
            extent=55,
            style=tk.ARC,
            outline=coeur,
            width=max(2, epaisseur - 1),
            tags="orbe",
        )

    n_motes = 5 if etat in ("reflexion", "escalade", "parole") else 4
    for i in range(n_motes):
        phase = maintenant * (0.55 + i * 0.12) + i * 1.1
        theta = rotation + i * (2.0 * math.pi / n_motes) + maintenant * 0.35
        rx = rayon * (1.05 + 0.18 * math.sin(phase))
        x = cx + rx * math.cos(theta)
        y = cy + rx * math.sin(theta)
        p = 1.8 + 1.2 * (0.5 + 0.5 * math.sin(phase * 2.0))
        toile.create_oval(
            x - p, y - p, x + p, y + p, fill=lueur, outline="", tags="orbe"
        )

    if scintil > 0.15:
        n_etincelles = 3 if etat == "reflexion" else 5
        for i in range(n_etincelles):
            phase = maintenant * (2.4 + i * 0.7) + i * 1.7
            visibilite = 0.5 + 0.5 * math.sin(phase * 3.0)
            if visibilite < 0.55:
                continue
            theta = rotation + i * (2.0 * math.pi / n_etincelles)
            rx = rayon * (0.9 + 0.12 * math.sin(phase))
            x = cx + rx * math.cos(theta)
            y = cy + rx * math.sin(theta)
            p = 1.6 + scintil * visibilite
            toile.create_oval(
                x - p, y - p, x + p, y + p, fill=lueur, outline="", tags="orbe"
            )


def dessiner_eclair(
    toile: tk.Canvas,
    *,
    cx: float,
    cy: float,
    taille: float,
    allume: bool,
    maintenant: float,
) -> None:
    """Icône éclair : braise vive pendant l'escalade, silhouette éteinte sinon."""
    pulsation = 0.5 + 0.5 * math.sin(maintenant * 9.0) if allume else 0.0
    fill, contour = couleurs_eclair(allume, pulsation=pulsation)
    if allume:
        halo = taille * 0.58
        toile.create_oval(
            cx - halo,
            cy - halo,
            cx + halo,
            cy + halo,
            fill="",
            outline=contour,
            width=2,
            tags="eclair",
        )
    toile.create_polygon(
        *sommets_eclair(cx, cy, taille),
        fill=fill,
        outline=contour,
        width=2 if allume else 1,
        joinstyle=tk.MITER,
        tags="eclair",
    )


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parseur = argparse.ArgumentParser(
        description="Bulle de présence d'hyper-ambient, au-dessus du bureau."
    )
    parseur.add_argument(
        "--off",
        action="store_true",
        help="démarrer masquée jusqu'au premier datagramme (ou jusqu'au défilé --demo)",
    )
    parseur.add_argument(
        "--coin",
        choices=COINS,
        default="bas-droite",
        help="coin de l'aire utile, hors barre des tâches",
    )
    parseur.add_argument(
        "--taille",
        type=int,
        default=TAILLE_DEFAUT,
        help="côté de la fenêtre carrée, en pixels",
    )
    parseur.add_argument(
        "--port",
        type=int,
        default=PORT_DEFAUT,
        help=f"port UDP local (défaut {PORT_DEFAUT})",
    )
    parseur.add_argument(
        "--stop",
        action="store_true",
        help="fermer la presence deja lancee, puis quitter",
    )
    parseur.add_argument(
        "--demo",
        action="store_true",
        help="défiler les cinq états en boucle, sans serveur",
    )
    return parseur.parse_args(argv)


def ouvrir_socket(port: int, *, obligatoire: bool) -> socket.socket | None:
    """IPv4 explicite : sous Windows, localhost préfère ::1, qui n'est pas 127.0.0.1."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    try:
        sock.bind((HOTE_UDP, port))
    except OSError as exc:
        sock.close()
        if obligatoire:
            print(
                f"Impossible d'écouter {HOTE_UDP}:{port} : {exc}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print(
            f"UDP {HOTE_UDP}:{port} occupé ({exc}) — démo visuelle seulement.",
            file=sys.stderr,
            flush=True,
        )
        return None
    return sock


class Presence:
    """Une forme, un état, une socket lue depuis after — tkinter n'est pas sûr entre fils."""

    def __init__(self, args: argparse.Namespace) -> None:
        taille = max(80, min(400, int(args.taille)))
        self.taille = taille
        self.coin = args.coin
        self.en_demo = bool(args.demo)
        self.masquee = bool(args.off) and not self.en_demo

        self.etat = "repos"
        self.palette_affichee = dict(PALETTES["repos"])
        self.niveau_cible = 0.0
        self.niveau_lisse = 0.0
        self.angle = 0.0
        self.naissance = time.perf_counter()
        self.debut_demo = self.naissance
        self.indice_demo = 0

        self.racine = tk.Tk()
        self.racine.title("hyper-ambient")
        self.racine.configure(bg=COULEUR_TRANSPARENTE)
        self.racine.overrideredirect(True)
        self.racine.attributes("-topmost", True)
        # transparentcolor perce le fond ; -alpha ne teinte que la forme restante.
        self.racine.attributes("-transparentcolor", COULEUR_TRANSPARENTE)
        # Les pixels dessinés restent opaques : le chroma-key perce le carré,
        # pas la bulle. L'alpha fenêtre du 17 (0,16 au repos) la rendait fantôme.
        self.racine.attributes("-alpha", 1.0)
        self.racine.geometry(f"{taille}x{taille}+0+0")
        self.racine.resizable(False, False)

        self.toile = tk.Canvas(
            self.racine,
            width=taille,
            height=taille,
            bg=COULEUR_TRANSPARENTE,
            highlightthickness=0,
            bd=0,
        )
        self.toile.pack(fill=tk.BOTH, expand=True)

        self.sock = ouvrir_socket(args.port, obligatoire=not self.en_demo)
        self.port = args.port

        self.racine.bind("<Escape>", self.fermer)
        self.racine.bind_all("<Escape>", self.fermer)
        self.toile.bind("<Button-3>", self.fermer)
        self.racine.bind("<Button-3>", self.fermer)
        self.racine.protocol("WM_DELETE_WINDOW", self.fermer)

        self.placer()
        if self.masquee:
            self.racine.withdraw()
        else:
            self.racine.deiconify()
            self.racine.lift()
            self.racine.attributes("-topmost", True)
            self.racine.focus_force()

        print(f"présence : {self.etat}", flush=True)
        self.racine.after(INTERVALLE_MS, self.tic)

    def placer(self) -> None:
        gauche, haut, droite, bas = aire_utile(self.racine)
        cote = self.taille
        marge = MARGE_ECRAN
        if self.coin == "bas-droite":
            x, y = droite - cote - marge, bas - cote - marge
        elif self.coin == "bas-gauche":
            x, y = gauche + marge, bas - cote - marge
        elif self.coin == "haut-droite":
            x, y = droite - cote - marge, haut + marge
        else:
            x, y = gauche + marge, haut + marge
        self.racine.geometry(f"{cote}x{cote}+{int(x)}+{int(y)}")

    def montrer(self) -> None:
        if not self.masquee:
            return
        self.masquee = False
        self.racine.deiconify()
        self.placer()
        self.racine.lift()
        self.racine.attributes("-topmost", True)
        self.racine.attributes("-transparentcolor", COULEUR_TRANSPARENTE)
        self.racine.focus_force()

    def lire_datagrammes(self) -> None:
        if self.sock is None:
            return
        dernier: dict[str, Any] | None = None
        while True:
            try:
                brut, _ = self.sock.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError:
                break
            try:
                message = json.loads(brut.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(message, dict):
                continue
            # La sortie de secours, et la seule fiable. Echap ne peut pas
            # marcher : une fenetre overrideredirect ne prend pas le focus
            # clavier. Le clic droit non plus : transparentcolor rend les pixels
            # transparents traversants, le clic file a la fenetre du dessous des
            # qu'il rate l'anneau. La transparence, qui est tout l'interet de
            # cette presence, neutralise ses deux fermetures prevues. La socket,
            # elle, est lue a chaque image quoi qu'il arrive.
            if message.get("type") == "quit":
                self.fermer()
                return
            if message.get("type") not in (None, "state"):
                continue
            etat = message.get("etat")
            if etat not in ETATS:
                continue
            dernier = message
        if dernier is None:
            return
        # Un datagramme vivant arrête le défilé : la voix réelle prime sur la répétition.
        self.en_demo = False
        niveau = dernier.get("niveau")
        valeur: float | None
        try:
            valeur = None if niveau is None else float(niveau)
        except (TypeError, ValueError):
            valeur = None
        self.appliquer_etat(str(dernier["etat"]), niveau=valeur, source="udp")
        self.montrer()

    def avancer_demo(self) -> None:
        if not self.en_demo:
            return
        indice = int((time.perf_counter() - self.debut_demo) / DUREE_ETAT_DEMO) % len(
            ETATS
        )
        if indice != self.indice_demo:
            self.indice_demo = indice
            self.appliquer_etat(ETATS[indice], niveau=None, source="demo")
        if self.etat == "ecoute":
            t = time.perf_counter() - self.naissance
            # Enveloppe irrégulière : un sinus seul ressemble à un vumètre, pas à une voix.
            self.niveau_cible = max(
                0.0,
                min(
                    1.0,
                    0.12
                    + 0.55
                    * abs(math.sin(t * 2.15))
                    * (0.45 + 0.55 * math.sin(t * 5.7 + 0.4)),
                ),
            )

    def appliquer_etat(
        self, etat: str, *, niveau: float | None, source: str
    ) -> None:
        if etat != self.etat:
            self.etat = etat
            extra = ""
            if etat == "ecoute" and source == "demo":
                extra = "  (niveau simulé)"
            print(f"présence : {etat}{extra}", flush=True)
        if niveau is None:
            if etat != "ecoute":
                self.niveau_cible = 0.0
        else:
            self.niveau_cible = max(0.0, min(1.0, niveau))

    def respiration(self, palette: dict[str, Any], maintenant: float) -> float:
        periode = max(0.2, float(palette["periode"]))
        phase = math.sin(2.0 * math.pi * maintenant / periode)
        souffle = 0.5 + 0.5 * phase
        if palette["suit_niveau"]:
            # Un reste de respiration même au silence, sinon la bulle paraît figée / plantée.
            return 0.22 * souffle + 0.78 * self.niveau_lisse
        if self.etat == "parole":
            parole = 0.5 + 0.28 * math.sin(maintenant * 7.3) + 0.18 * math.sin(
                maintenant * 13.1 + 0.7
            )
            return max(0.0, min(1.0, 0.35 * souffle + 0.65 * parole))
        return souffle

    def dessiner(self) -> None:
        cible = PALETTES[self.etat]
        self.palette_affichee = melanger_palettes(
            self.palette_affichee, cible, LISSAGE_TRANSITION
        )
        palette = self.palette_affichee
        self.niveau_lisse += LISSAGE_NIVEAU * (self.niveau_cible - self.niveau_lisse)

        maintenant = time.perf_counter() - self.naissance
        dt = INTERVALLE_MS / 1000.0
        self.angle = (self.angle + float(palette["vitesse_rotation"]) * dt) % 360.0
        souffle = self.respiration(palette, maintenant)

        try:
            self.racine.attributes("-alpha", 1.0)
        except tk.TclError:
            return

        cx = cy = self.taille / 2
        rayon_base = self.taille * 0.28
        rayon = rayon_base * (1.0 + float(palette["amplitude"]) * (souffle * 2.0 - 1.0))
        scintil = float(palette["scintillement"])
        if scintil:
            rayon += rayon_base * 0.04 * scintil * math.sin(maintenant * 11.0)

        self.toile.delete("all")
        dessiner_nappe(
            self.toile,
            largeur=self.taille,
            hauteur=self.taille,
            palette=palette,
            maintenant=maintenant,
            etat=self.etat,
        )
        dessiner_orbe(
            self.toile,
            cx=cx,
            cy=cy,
            taille=self.taille,
            etat=self.etat,
            palette=palette,
            angle=self.angle,
            souffle=souffle,
            maintenant=maintenant,
        )

        if eclair_allume(self.etat):
            dessiner_eclair(
                self.toile,
                cx=cx + rayon * 0.72,
                cy=cy - rayon * 0.78,
                taille=max(28.0, rayon * 0.7),
                allume=True,
                maintenant=maintenant,
            )

    def _ovale(
        self,
        cx: float,
        cy: float,
        rayon: float,
        *,
        fill: str = "",
        outline: str = "",
        width: int = 1,
    ) -> None:
        self.toile.create_oval(
            cx - rayon,
            cy - rayon,
            cx + rayon,
            cy + rayon,
            fill=fill,
            outline=outline,
            width=width,
        )

    def tic(self) -> None:
        self.lire_datagrammes()
        self.avancer_demo()
        if not self.masquee:
            self.dessiner()
        try:
            self.racine.after(INTERVALLE_MS, self.tic)
        except tk.TclError:
            return

    def fermer(self, _event: object | None = None) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        try:
            self.racine.destroy()
        except tk.TclError:
            pass

    def boucler(self) -> None:
        try:
            self.racine.mainloop()
        except KeyboardInterrupt:
            self.fermer()


def arreter(port: int) -> None:
    """Ferme une presence deja lancee, en lui envoyant son ordre d'arret."""
    douille = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    douille.sendto(json.dumps({"type": "quit"}).encode("utf-8"), (HOTE_UDP, port))
    douille.close()
    print("ordre d'arrêt envoyé", flush=True)


def main(argv: list[str] | None = None) -> None:
    args = analyser_arguments(argv)
    if args.stop:
        arreter(args.port)
        return
    print(
        "présence d'hyper-ambient — pour la fermer : "
        "python native/presence/overlay.py --stop",
        flush=True,
    )
    print(
        f"coin {args.coin}, {max(80, min(400, args.taille))} px, "
        f"UDP {HOTE_UDP}:{args.port}"
        + (" , démo" if args.demo else "")
        + (" , masquée" if args.off and not args.demo else ""),
        flush=True,
    )
    Presence(args).boucler()


if __name__ == "__main__":
    main()
