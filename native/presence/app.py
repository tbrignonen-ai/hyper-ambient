"""Application fenêtrée d'hyper-ambient : appuyer-pour-parler, sans terminal.

Le moteur (poignée de main, micro, restitution) vit déjà dans
``native/hostagent/talk.py``. Le dessin de la bulle vit déjà dans
``native/presence/overlay.py``. Ce fichier n'ajoute que le cadre : une
fenêtre tkinter *normale* (barre de titre, croix), un bouton qu'on
maintient, et le relais vers l'interface par une file — tkinter n'est
pas sûr entre fils, donc le réseau et l'audio ne touchent jamais un
widget.

    python native/presence/app.py
"""
from __future__ import annotations

import argparse
import json
import math
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parents[2]
_ICI = Path(__file__).resolve().parent
for _chemin in (str(_ROOT), str(_ICI)):
    if _chemin not in sys.path:
        sys.path.insert(0, _chemin)

from native.hostagent import talk as moteur
import overlay as visuel

# Fond opaque : contrairement à l'overlay, cette fenêtre n'est pas percée
# par transparentcolor. Un fond proche du repos, pas du noir pur, pour que
# la bulle reste lisible sans recoller la clé de transparence de l'overlay.
FOND = "#0c141c"
ENCRE = "#d8e4ec"
ENCRE_SOURDE = "#8aa0b0"
TAILLE_BULLE = 200


def consommer_reponse(
    ws,
    sortie,
    t_fin_parole: float,
    deposer: Callable[[dict[str, Any]], None],
    arreter: threading.Event,
) -> None:
    """Lit la socket jusqu'au marqueur vide, restitue, et relaye l'état.

    Le serveur envoie, dans l'ordre : des paquets audio, puis un rapport,
    puis un marqueur de fin vide. Sortir dès qu'un message n'a pas de
    trames revenait à sortir SUR LE RAPPORT, en laissant le marqueur dans
    la socket — le tour suivant le lisait à la place de sa propre réponse,
    et restait muet. Seul ``frames == []`` termine le tour.
    """
    premier_son = None
    while not arreter.is_set():
        # Recv bloquant, comme talk.py : un timeout ici n'aide pas, et close()
        # depuis l'arrêt de la fenêtre débloque avec ConnectionClosed.
        try:
            brut = ws.recv()
        except Exception:
            return
        try:
            message = json.loads(brut)
        except json.JSONDecodeError:
            deposer({"type": "statut", "texte": "Message illisible."})
            return
        if not isinstance(message, dict):
            continue
        if message.get("type") == "error":
            deposer({"type": "erreur", "texte": f"Erreur du transport : {message}"})
            return
        if message.get("type") == "state":
            deposer(
                {
                    "type": "etat",
                    "etat": message.get("etat"),
                    "niveau": message.get("niveau"),
                }
            )
            continue
        if message.get("type") == "report":
            deposer(
                {
                    "type": "rapport",
                    "transcript": message.get("transcript") or "",
                    "reply": message.get("reply") or "",
                }
            )
            continue
        recues = message.get("frames")
        if recues is None:
            continue
        if not recues:
            break
        a_jouer: list[float] = []
        for brute in recues:
            a_jouer.extend(brute)
        if premier_son is None:
            premier_son = time.perf_counter()
            deposer(
                {
                    "type": "premier_son",
                    "ms": (premier_son - t_fin_parole) * 1000.0,
                }
            )
        try:
            moteur._jouer(sortie, a_jouer)
        except Exception as exc:
            # Restituer ne doit pas abandonner la socket : le marqueur vide
            # arriverait au tour suivant, qui resterait muet.
            print(f"restitution : {exc}", flush=True)

    if premier_son is None and not arreter.is_set():
        deposer({"type": "statut", "texte": "Aucune trame de réponse — rien à restituer."})
    elif premier_son is not None:
        time.sleep(0.25)
        deposer({"type": "etat", "etat": "repos", "niveau": None})


class Bulle:
    """La forme ronde de l'overlay, dessinée dans un Canvas d'une fenêtre normale.

    On réutilise palettes, lissage et respiration ; on abandonne -alpha et
    transparentcolor, qui n'ont de sens que pour une fenêtre percée.
    """

    def __init__(self, toile: tk.Canvas, taille: int) -> None:
        self.toile = toile
        self.taille = taille
        self.etat = "repos"
        self.palette_affichee = dict(visuel.PALETTES["repos"])
        self.niveau_cible = 0.0
        self.niveau_lisse = 0.0
        self.angle = 0.0
        self.naissance = time.perf_counter()

    def appliquer_etat(self, etat: str, *, niveau: float | None) -> None:
        if etat not in visuel.ETATS:
            return
        self.etat = etat
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
            return 0.22 * souffle + 0.78 * self.niveau_lisse
        if self.etat == "parole":
            parole = (
                0.5
                + 0.28 * math.sin(maintenant * 7.3)
                + 0.18 * math.sin(maintenant * 13.1 + 0.7)
            )
            return max(0.0, min(1.0, 0.35 * souffle + 0.65 * parole))
        return souffle

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

    def dessiner(self) -> None:
        cible = visuel.PALETTES[self.etat]
        self.palette_affichee = visuel.melanger_palettes(
            self.palette_affichee, cible, visuel.LISSAGE_TRANSITION
        )
        palette = self.palette_affichee
        self.niveau_lisse += visuel.LISSAGE_NIVEAU * (
            self.niveau_cible - self.niveau_lisse
        )

        maintenant = time.perf_counter() - self.naissance
        dt = visuel.INTERVALLE_MS / 1000.0
        self.angle = (self.angle + float(palette["vitesse_rotation"]) * dt) % 360.0
        souffle = self.respiration(palette, maintenant)

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
        self._ovale(cx, cy, rayon * 1.55, outline=lueur, width=2)
        self._ovale(
            cx,
            cy,
            rayon * 1.22,
            outline=anneau,
            width=max(3, int(self.taille * 0.045)),
        )
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


class SessionVocale(threading.Thread):
    """Réseau + micro + haut-parleur, hors du fil tkinter.

    ``tenu`` est l'état du bouton (ou de la barre d'espace), posé par
    l'interface. On capture tant qu'il est levé, on envoie à la descente.
    """

    def __init__(
        self,
        file_ui: queue.Queue,
        *,
        url: str,
        device: str | None,
        sortie: str | None,
    ) -> None:
        super().__init__(name="session-vocale", daemon=True)
        self.file_ui = file_ui
        self.url = url
        self.device = device
        self.nom_sortie = sortie
        self.arreter = threading.Event()
        self.tenu = threading.Event()
        self.ws = None

    def deposer(self, message: dict[str, Any]) -> None:
        if not self.arreter.is_set():
            self.file_ui.put(message)

    def demander_arret(self) -> None:
        self.arreter.set()
        self.tenu.clear()
        ws = self.ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def run(self) -> None:
        try:
            self._servir()
        except SystemExit as exc:
            # talk.py sort par SystemExit quand le micro ou websockets manque.
            self.deposer({"type": "erreur", "texte": f"Arrêt audio : {exc}"})
        except Exception as exc:
            self.deposer({"type": "erreur", "texte": f"{exc}"})

    def _servir(self) -> None:
        try:
            sd = moteur._importer_sounddevice()
            connect = moteur._importer_websockets()
        except SystemExit:
            self.deposer(
                {
                    "type": "erreur",
                    "texte": "sounddevice ou websockets absent sur l'hôte.",
                }
            )
            return
        secret = moteur.lire_secret()
        try:
            indice = moteur.choisir_peripherique(self.device, sd)
            capture = moteur.PushToTalkCapture(
                stream_factory=moteur._fabrique_entree(indice, sd)
            )
            indice_sortie = moteur.choisir_sortie(self.nom_sortie, sd)
            sortie = moteur._ouvrir_sortie(sd, indice=indice_sortie)
        except SystemExit:
            self.deposer(
                {
                    "type": "erreur",
                    "texte": "Périphérique audio indisponible. Vérifiez le micro.",
                }
            )
            return

        try:
            while not self.arreter.is_set():
                try:
                    with connect(self.url, max_size=16 * 1024 * 1024) as ws:
                        self.ws = ws
                        try:
                            moteur._poignee_de_main(ws, secret)
                        except SystemExit:
                            self.deposer(
                                {
                                    "type": "erreur",
                                    "texte": (
                                        "Poignée de main refusée. "
                                        "Le serveur tourne-t-il sur le port 8001 ?"
                                    ),
                                }
                            )
                            self.arreter.wait(2.0)
                            continue
                        self.deposer(
                            {
                                "type": "statut",
                                "texte": "Canal prêt. Maintenez Parler ou Espace.",
                            }
                        )
                        print("CANAL_PRET", flush=True)
                        self._boucle_tours(ws, capture, sortie)
                except Exception as exc:
                    if self.arreter.is_set():
                        break
                    if moteur._est_erreur_audio(exc):
                        texte = moteur.decrire_erreur_peripherique(exc)
                    else:
                        texte = f"Impossible de joindre {self.url} : {exc}"
                    print(texte, flush=True)
                    self.deposer({"type": "erreur", "texte": texte})
                    self.arreter.wait(2.0)
                finally:
                    self.ws = None
        finally:
            try:
                sortie.stop()
            except Exception:
                pass
            try:
                sortie.close()
            except Exception:
                pass

    def _boucle_tours(self, ws, capture, sortie) -> None:
        while not self.arreter.is_set():
            while not self.arreter.is_set() and not self.tenu.is_set():
                self.tenu.wait(0.2)
            if self.arreter.is_set():
                return
            capture.start()
            self.deposer({"type": "statut", "texte": "Écoute… relâchez pour envoyer."})
            while not self.arreter.is_set() and self.tenu.is_set():
                time.sleep(0.03)
            trames = capture.stop()
            t_fin_parole = time.perf_counter()
            if self.arreter.is_set():
                return
            if not trames:
                self.deposer(
                    {
                        "type": "statut",
                        "texte": "Aucune trame capturée (parole trop courte).",
                    }
                )
                self.deposer({"type": "etat", "etat": "repos", "niveau": None})
                continue
            self.deposer(
                {
                    "type": "statut",
                    "texte": f"{len(trames)} trames envoyées, attente de la réponse…",
                }
            )
            print(f"envoi : {len(trames)} trames", flush=True)
            ws.send(
                json.dumps(
                    {
                        "type": "invoke",
                        "primitive": "audio.capture",
                        "frames": [trame.samples.tolist() for trame in trames],
                    }
                )
            )
            consommer_reponse(ws, sortie, t_fin_parole, self.deposer, self.arreter)
            print("tour : terminé", flush=True)


class Application:
    """Fenêtre normale : bulle, bouton maintenu, transcripts, ligne d'état."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.file_ui: queue.Queue = queue.Queue()
        self.session = SessionVocale(
            self.file_ui,
            url=args.url,
            device=args.device,
            sortie=args.sortie,
        )
        self.enfonce = False
        self.dernier_delai_ms: float | None = None
        self.texte_statut = "Connexion…"

        self.racine = tk.Tk()
        self.racine.title("hyper-ambient")
        self.racine.configure(bg=FOND)
        self.racine.geometry("460x720")
        self.racine.minsize(400, 640)
        # Fenêtre normale : pas d'overrideredirect, la croix doit fermer.
        self.racine.protocol("WM_DELETE_WINDOW", self.fermer)

        cadre = tk.Frame(self.racine, bg=FOND)
        cadre.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        self.toile = tk.Canvas(
            cadre,
            width=TAILLE_BULLE,
            height=TAILLE_BULLE,
            bg=FOND,
            highlightthickness=0,
            bd=0,
        )
        self.toile.pack(pady=(8, 4))
        self.bulle = Bulle(self.toile, TAILLE_BULLE)

        # takefocus=0 : un Button tkinter avale Espace pour s'activer.
        # On veut Press/Release, pas un clic simulé qui raterait le maintien.
        self.bouton = tk.Button(
            cadre,
            text="Parler",
            font=("Segoe UI", 18, "bold"),
            bg=visuel.PALETTES["repos"]["anneau"],
            fg=ENCRE,
            activebackground=visuel.PALETTES["ecoute"]["coeur"],
            activeforeground="#0c141c",
            relief=tk.RAISED,
            bd=3,
            padx=28,
            pady=16,
            takefocus=0,
        )
        self.bouton.pack(pady=12, fill=tk.X)
        self.bouton.bind("<ButtonPress-1>", self.enfoncer)
        self.bouton.bind("<ButtonRelease-1>", self.relacher)

        tk.Label(
            cadre,
            text="Compris",
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))
        self.zone_compris = self._zone_texte(cadre)

        tk.Label(
            cadre,
            text="Réponse",
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))
        self.zone_reponse = self._zone_texte(cadre)

        self.ligne_etat = tk.Label(
            cadre,
            text=self._composer_statut(),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.ligne_etat.pack(fill=tk.X, pady=(12, 0), side=tk.BOTTOM)

        self.racine.bind_all("<KeyPress-space>", self._espace_enfonce)
        self.racine.bind_all("<KeyRelease-space>", self._espace_relache)
        self.racine.bind_all("<Escape>", lambda _e: self.fermer())

        print("UI_PRETE", flush=True)
        self.session.start()
        self.racine.after(visuel.INTERVALLE_MS, self.tic)

    def _zone_texte(self, parent: tk.Misc) -> tk.Text:
        zone = tk.Text(
            parent,
            height=5,
            wrap=tk.WORD,
            bg="#142028",
            fg=ENCRE,
            insertbackground=ENCRE,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            padx=8,
            pady=6,
            state=tk.DISABLED,
            takefocus=0,
        )
        zone.pack(fill=tk.BOTH, expand=True)
        return zone

    def _ecrire_zone(self, zone: tk.Text, texte: str) -> None:
        zone.configure(state=tk.NORMAL)
        zone.delete("1.0", tk.END)
        if texte:
            zone.insert("1.0", texte)
        zone.configure(state=tk.DISABLED)

    def _composer_statut(self) -> str:
        if self.dernier_delai_ms is None:
            return self.texte_statut
        return f"{self.texte_statut}  ·  premier son : {self.dernier_delai_ms:.0f} ms"

    def _afficher_statut(self, texte: str | None = None) -> None:
        if texte is not None:
            self.texte_statut = texte
        self.ligne_etat.configure(text=self._composer_statut())

    def enfoncer(self, _event: object | None = None) -> None:
        if self.enfonce:
            return
        self.enfonce = True
        self.session.tenu.set()
        self.bulle.appliquer_etat("ecoute", niveau=None)
        self.bouton.configure(
            relief=tk.SUNKEN,
            text="Parler…",
            bg=visuel.PALETTES["ecoute"]["coeur"],
            fg="#0c141c",
        )
        print("bouton : enfoncé", flush=True)

    def relacher(self, _event: object | None = None) -> None:
        if not self.enfonce:
            return
        self.enfonce = False
        self.session.tenu.clear()
        self.bouton.configure(
            relief=tk.RAISED,
            text="Parler",
            bg=visuel.PALETTES["repos"]["anneau"],
            fg=ENCRE,
        )
        print("bouton : relâché", flush=True)

    def _espace_enfonce(self, event: tk.Event) -> str | None:
        # Repeat clavier : KeyPress se répète tant que la touche reste enfoncée.
        if event.keysym != "space":
            return None
        self.enfoncer()
        return "break"

    def _espace_relache(self, event: tk.Event) -> str | None:
        if event.keysym != "space":
            return None
        self.relacher()
        return "break"

    def _traiter(self, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == "etat":
            etat = message.get("etat")
            niveau = message.get("niveau")
            valeur: float | None
            try:
                valeur = None if niveau is None else float(niveau)
            except (TypeError, ValueError):
                valeur = None
            if isinstance(etat, str):
                self.bulle.appliquer_etat(etat, niveau=valeur)
        elif kind == "rapport":
            self._ecrire_zone(self.zone_compris, str(message.get("transcript") or "").strip())
            self._ecrire_zone(self.zone_reponse, str(message.get("reply") or "").strip())
        elif kind == "premier_son":
            try:
                self.dernier_delai_ms = float(message["ms"])
            except (KeyError, TypeError, ValueError):
                return
            self._afficher_statut("Réponse en cours.")
        elif kind == "statut":
            self._afficher_statut(str(message.get("texte") or ""))
        elif kind == "erreur":
            self._afficher_statut(str(message.get("texte") or "Erreur."))

    def tic(self) -> None:
        # after() doit toujours être réarmé : une exception dans le dessin
        # gèlerait l'interface, y compris la ligne d'état.
        try:
            try:
                while True:
                    self._traiter(self.file_ui.get_nowait())
            except queue.Empty:
                pass
            self.bulle.dessiner()
        except tk.TclError:
            return
        except Exception as exc:
            print(f"tic : {exc}", flush=True)
        try:
            self.racine.after(visuel.INTERVALLE_MS, self.tic)
        except tk.TclError:
            return

    def fermer(self, _event: object | None = None) -> None:
        self.session.demander_arret()
        try:
            self.racine.destroy()
        except tk.TclError:
            pass

    def boucler(self) -> None:
        try:
            self.racine.mainloop()
        except KeyboardInterrupt:
            self.fermer()


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parseur = argparse.ArgumentParser(
        description="Présence fenêtrée d'hyper-ambient, appuyer-pour-parler."
    )
    parseur.add_argument(
        "--url",
        default=moteur.URL_DEFAUT,
        help="URL WebSocket du transport (IPv4 explicite, pas localhost)",
    )
    parseur.add_argument(
        "--device",
        default=None,
        help="indice PortAudio, ou fragment du nom du micro",
    )
    parseur.add_argument(
        "--sortie",
        default=None,
        help="indice PortAudio, ou fragment du nom du haut-parleur",
    )
    return parseur.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = analyser_arguments(argv)
    Application(args).boucler()


if __name__ == "__main__":
    main()
