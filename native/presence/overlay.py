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
from ctypes import Structure, byref, c_long, windll
from typing import Any

# Jamais du noir pur ni une teinte du dessin : Windows perce cette couleur
# de part en part, y compris aux clics, et un overlap trouerait la bulle.
COULEUR_TRANSPARENTE = "#010203"

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
        "coeur": "#142830",
        "lueur": "#1c3848",
        "anneau": "#243c50",
        "periode": 5.6,
        "amplitude": 0.05,
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
        self.racine.attributes("-alpha", PALETTES["repos"]["alpha_min"])
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

        alpha = interpoler_canal(
            float(palette["alpha_min"]), float(palette["alpha_max"]), souffle
        )
        try:
            self.racine.attributes("-alpha", max(0.08, min(1.0, alpha)))
        except tk.TclError:
            return

        cx = cy = self.taille / 2
        rayon_base = self.taille * 0.28
        rayon = rayon_base * (1.0 + float(palette["amplitude"]) * (souffle * 2.0 - 1.0))
        scintil = float(palette["scintillement"])
        if scintil:
            rayon += rayon_base * 0.04 * scintil * math.sin(maintenant * 11.0)

        coeur = palette["coeur"]
        lueur = palette["lueur"]
        anneau = palette["anneau"]

        self.toile.delete("all")
        # Trois ovaires concentriques plutôt qu'un dégradé : Canvas n'en a pas,
        # et empiler des disques donne assez de halo pour une présence, pas un bouton.
        self._ovale(cx, cy, rayon * 1.55, outline=lueur, width=2)
        self._ovale(cx, cy, rayon * 1.22, outline=anneau, width=max(3, int(self.taille * 0.045)))
        self._ovale(cx, cy, rayon * 0.62, fill=coeur, outline=anneau, width=1)
        self._ovale(cx, cy, rayon * 0.22, fill=lueur, outline="")

        if float(palette["vitesse_rotation"]) > 12.0:
            epaisseur = max(2, int(self.taille * 0.03))
            etendue = 72 if self.etat != "escalade" else 110
            self.toile.create_arc(
                cx - rayon * 1.22,
                cy - rayon * 1.22,
                cx + rayon * 1.22,
                cy + rayon * 1.22,
                start=self.angle,
                extent=etendue,
                style=tk.ARC,
                outline=lueur,
                width=epaisseur,
            )
            if self.etat == "escalade":
                self.toile.create_arc(
                    cx - rayon * 0.95,
                    cy - rayon * 0.95,
                    cx + rayon * 0.95,
                    cy + rayon * 0.95,
                    start=(-self.angle * 1.4) % 360.0,
                    extent=55,
                    style=tk.ARC,
                    outline=coeur,
                    width=max(2, epaisseur - 1),
                )

        if scintil > 0.15:
            n_etincelles = 3 if self.etat == "reflexion" else 5
            for i in range(n_etincelles):
                phase = maintenant * (2.4 + i * 0.7) + i * 1.7
                visibilite = 0.5 + 0.5 * math.sin(phase * 3.0)
                if visibilite < 0.55:
                    continue
                theta = self.angle * math.pi / 180.0 + i * (2.0 * math.pi / n_etincelles)
                rx = rayon * (0.9 + 0.12 * math.sin(phase))
                x = cx + rx * math.cos(theta)
                y = cy + rx * math.sin(theta)
                p = 1.6 + scintil * visibilite
                self.toile.create_oval(
                    x - p, y - p, x + p, y + p, fill=lueur, outline=""
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


def main(argv: list[str] | None = None) -> None:
    args = analyser_arguments(argv)
    print(
        "présence d'hyper-ambient — Échap ou clic droit pour fermer",
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
