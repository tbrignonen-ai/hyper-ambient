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

import overlay as visuel
import sante as etat_sante
from onboarding import (
    ETAPES_WIZARD,
    ConfigurationPresence,
    charger_configuration,
    eclair_allume,
    enregistrer_configuration,
    libelle_eclair,
    raccourcis_lisibles,
    sequences_tk,
    statut_pour_etat,
    terminer_onboarding,
    ui_presence,
)

# Champ sombre plein : le bureau ne perce plus la fenêtre app.
# L'overlay flottant, lui, garde le chroma-key (COULEUR_TRANSPARENTE).
FOND = visuel.FOND_CHAMP
FOND_VITRE = "#102028"
MARGE_NAPPE = 28
BORD_VITRE = "#2a4a5c"
ENCRE = "#d8e4ec"
ENCRE_SOURDE = "#8aa0b0"
ENCRE_FONCEE = "#0c141c"
TAILLE_BULLE = 260
URL_DEFAUT = "ws://127.0.0.1:8001/hostagent"
moteur: Any | None = None


def _trace_c10(evenement: str, **champs: Any) -> None:
    """Trace minimale C10 : PTT, WS, premier audio. Horloge monotone."""
    extra = " ".join(f"{cle}={valeur}" for cle, valeur in champs.items())
    suffixe = f" {extra}" if extra else ""
    print(f"C10 t={time.monotonic():.3f} {evenement}{suffixe}", flush=True)


def consommer_reponse(
    ws,
    sortie,
    t_fin_parole: float,
    deposer: Callable[[dict[str, Any]], None],
    arreter: threading.Event,
    interrompre: threading.Event | None = None,
    sur_interruption: Callable[[], None] | None = None,
) -> bool:
    """Lit la socket jusqu'au marqueur vide, restitue, et relaye l'état.

    ``interrompre`` est le bouton Parler : s'il est enfoncé pendant la
    réponse, la voix se tait tout de suite (tampon de la carte jeté), la
    capture démarre par ``sur_interruption``, et la socket est vidée sans
    rien jouer jusqu'au marqueur. Renvoie True si la réponse a été coupée.

    Le serveur envoie, dans l'ordre : des paquets audio, puis un rapport,
    puis un marqueur de fin vide. Sortir dès qu'un message n'a pas de
    trames revenait à sortir SUR LE RAPPORT, en laissant le marqueur dans
    la socket — le tour suivant le lisait à la place de sa propre réponse,
    et restait muet. Seul ``frames == []`` termine le tour.
    """
    premier_son = None
    interrompu = False
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
        if interrompre is not None and interrompre.is_set() and not interrompu:
            interrompu = True
            try:
                sortie.abort()
            except Exception as exc:
                print(f"interruption : {exc}", flush=True)
            if sur_interruption is not None:
                sur_interruption()
            deposer({"type": "statut", "texte": "Interrompue — je t'écoute."})
        if interrompu:
            continue
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
        moteur._reposer(sortie)
        deposer({"type": "etat", "etat": "repos", "niveau": None})
    return interrompu


class Bulle:
    """La présence ronde : même dessin vivant que l'overlay, dans l'app."""

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

        self.toile.delete("all")
        visuel.dessiner_nappe(
            self.toile,
            largeur=self.taille,
            hauteur=self.taille,
            palette=palette,
            maintenant=maintenant,
            etat=self.etat,
        )
        visuel.dessiner_orbe(
            self.toile,
            cx=self.taille / 2,
            cy=self.taille / 2,
            taille=self.taille,
            etat=self.etat,
            palette=palette,
            angle=self.angle,
            souffle=souffle,
            maintenant=maintenant,
        )


class BadgeEclair:
    """Icône éclair dédiée : éteinte en local, allumée dès l'appel distant."""

    def __init__(self, toile: tk.Canvas, taille: int) -> None:
        self.toile = toile
        self.taille = taille
        self.etat = "repos"
        self.naissance = time.perf_counter()

    def appliquer_etat(self, etat: str) -> None:
        self.etat = etat

    def dessiner(self) -> None:
        maintenant = time.perf_counter() - self.naissance
        self.toile.delete("all")
        visuel.dessiner_eclair(
            self.toile,
            cx=self.taille / 2,
            cy=self.taille / 2,
            taille=self.taille * 0.78,
            allume=eclair_allume(self.etat),
            maintenant=maintenant,
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
        raccourci_label: str,
    ) -> None:
        super().__init__(name="session-vocale", daemon=True)
        self.file_ui = file_ui
        self.url = url
        self.device = device
        self.nom_sortie = sortie
        self.raccourci_label = raccourci_label
        self.arreter = threading.Event()
        self.tenu = threading.Event()
        self.canal_pret = threading.Event()
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
        global moteur
        try:
            from native.hostagent import talk as moteur_charge
        except ImportError as exc:
            self.deposer(
                {
                    "type": "erreur",
                    "texte": f"Dépendance audio absente : {exc}",
                }
            )
            return
        moteur = moteur_charge
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
                            self.canal_pret.clear()
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
                        self.canal_pret.set()
                        _trace_c10("WS_OPEN", url=self.url)
                        self.deposer(
                            {
                                "type": "statut",
                                "texte": (
                                    "Canal prêt. Maintenez Parler ou "
                                    f"{self.raccourci_label}."
                                ),
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
                    self.canal_pret.clear()
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
        # True quand la réponse précédente a été coupée : la capture tourne
        # déjà depuis l'appui, il ne faut ni l'attendre ni la relancer.
        deja_en_ecoute = False
        while not self.arreter.is_set():
            if not deja_en_ecoute:
                while not self.arreter.is_set() and not self.tenu.is_set():
                    self.tenu.wait(0.2)
                if self.arreter.is_set():
                    return
                capture.start()
            deja_en_ecoute = False
            self.deposer({"type": "statut", "texte": "Écoute… relâchez pour envoyer."})
            while not self.arreter.is_set() and self.tenu.is_set():
                time.sleep(0.03)
            trames = capture.stop()
            t_fin_parole = time.perf_counter()
            if self.arreter.is_set():
                return
            if not trames:
                _trace_c10("AUDIO_SEND", n_trames=0, n_samples=0)
                self.deposer(
                    {
                        "type": "statut",
                        "texte": "Aucune trame capturée (parole trop courte).",
                    }
                )
                self.deposer({"type": "etat", "etat": "repos", "niveau": None})
                continue
            n_samples = sum(int(trame.samples.size) for trame in trames)
            _trace_c10("AUDIO_SEND", n_trames=len(trames), n_samples=n_samples)
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
            deja_en_ecoute = consommer_reponse(
                ws, sortie, t_fin_parole, self.deposer, self.arreter,
                interrompre=self.tenu, sur_interruption=capture.start,
            ) is True
            print("tour : terminé", flush=True)


class Application:
    """Fenêtre normale : bulle, bouton maintenu, transcripts, ligne d'état."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.file_ui: queue.Queue = queue.Queue()
        self.configuration = charger_configuration(args.config)
        if args.onboarding:
            self.configuration = ConfigurationPresence(
                onboarding_termine=False,
                raccourci_ptt=self.configuration.raccourci_ptt,
            )
        self.chemin_configuration = args.config
        self.session = SessionVocale(
            self.file_ui,
            url=args.url,
            device=args.device,
            sortie=args.sortie,
            raccourci_label=raccourcis_lisibles()[self.configuration.raccourci_ptt],
        )
        self.enfonce = False
        self.dernier_delai_ms: float | None = None
        self.texte_statut = "Connexion…"
        self.session_lancee = False
        self.raccourci_en_cours = self.configuration.raccourci_ptt
        self.badge: BadgeEclair | None = None
        self.ligne_eclair: tk.Label | None = None
        self.bulle: Bulle | None = None
        self.orbe_accueil: Bulle | None = None
        self.toile_fond: tk.Canvas | None = None
        self.naissance_champ = time.perf_counter()
        self._tic_arme = False
        self.chemin_sante = Path(args.sante) if getattr(args, "sante", None) else None
        self.sondes_actives = bool(getattr(args, "sondes", False)) and self.chemin_sante is None
        self.bandeau_alerte: tk.Label | None = None
        self.cadre_sante: tk.Frame | None = None
        self._dernier_sante_ts = 0.0
        self._sondes_stop = threading.Event()
        self._sondes_fil: threading.Thread | None = None
        self._phrase_reprise = ""

        self.racine = tk.Tk()
        self.racine.title("hyper-ambient")
        self.racine.configure(bg=FOND)
        self.racine.geometry("520x800")
        self.racine.minsize(440, 700)
        # Fenêtre normale : pas d'overrideredirect, la croix doit fermer.
        # Pas de chroma-key : le geste HA est la nappe/orbe, pas un trou.
        self.racine.protocol("WM_DELETE_WINDOW", self.fermer)

        self.toile_fond = tk.Canvas(
            self.racine,
            bg=FOND,
            highlightthickness=0,
            bd=0,
        )
        self.toile_fond.place(x=0, y=0, relwidth=1, relheight=1)

        # Vitre insete : la nappe du champ reste lisible dans la marge.
        self.conteneur = tk.Frame(self.racine, bg=FOND)
        self.conteneur.place(
            x=MARGE_NAPPE,
            y=MARGE_NAPPE,
            relwidth=1,
            relheight=1,
            width=-2 * MARGE_NAPPE,
            height=-2 * MARGE_NAPPE,
        )

        if self.configuration.onboarding_termine:
            self._afficher_application()
        else:
            self._afficher_bienvenue()
        self._armer_tic()

    def _vider(self) -> None:
        self.orbe_accueil = None
        self.bulle = None
        self.badge = None
        self.ligne_eclair = None
        self.bandeau_alerte = None
        self.cadre_sante = None
        for enfant in self.conteneur.winfo_children():
            enfant.destroy()

    def _cadre_onboarding(
        self, indice: int, titre: str, description: str
    ) -> tuple[tk.Frame, tk.Frame]:
        self._vider()
        enveloppe = tk.Frame(self.conteneur, bg=FOND)
        enveloppe.pack(fill=tk.BOTH, expand=True)
        cadre = tk.Frame(
            enveloppe,
            bg=FOND_VITRE,
            highlightthickness=1,
            highlightbackground=BORD_VITRE,
        )
        cadre.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(cadre, bg=FOND_VITRE)
        inner.pack(fill=tk.BOTH, expand=True, padx=26, pady=22)
        pied = tk.Frame(inner, bg=FOND_VITRE)
        pied.pack(side=tk.BOTTOM, fill=tk.X)
        toile_orbe = tk.Canvas(
            inner,
            width=140,
            height=140,
            bg=FOND_VITRE,
            highlightthickness=0,
            bd=0,
        )
        toile_orbe.pack(pady=(0, 8))
        self.orbe_accueil = Bulle(toile_orbe, 140)
        self.orbe_accueil.appliquer_etat("ecoute", niveau=0.42)
        tk.Label(
            inner,
            text=ui_presence()["step"].format(
                indice=indice, total=len(ETAPES_WIZARD)
            ),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 16))
        tk.Label(
            inner,
            text=titre,
            bg=FOND_VITRE,
            fg=ENCRE,
            font=("Segoe UI", 24, "bold"),
            anchor="w",
            justify="left",
        ).pack(fill=tk.X)
        tk.Label(
            inner,
            text=description,
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X, pady=(12, 20))
        return inner, pied

    def _rendre_focus_visible(self, widget: tk.Misc) -> None:
        lueur = visuel.PALETTES["ecoute"]["lueur"]
        widget.configure(
            highlightthickness=3,
            highlightcolor=lueur,
            highlightbackground=FOND_VITRE,
        )

        def entrer(_event: object) -> None:
            widget.configure(highlightbackground=lueur)

        def sortir(_event: object) -> None:
            widget.configure(highlightbackground=FOND_VITRE)

        widget.bind("<FocusIn>", entrer, add="+")
        widget.bind("<FocusOut>", sortir, add="+")

    def _bouton_principal(
        self, parent: tk.Misc, texte: str, commande: Callable[[], None]
    ) -> tk.Button:
        bouton = tk.Button(
            parent,
            text=texte,
            command=commande,
            font=("Segoe UI", 12, "bold"),
            bg=visuel.PALETTES["ecoute"]["coeur"],
            fg=ENCRE_FONCEE,
            activebackground=visuel.PALETTES["ecoute"]["lueur"],
            activeforeground=ENCRE_FONCEE,
            padx=18,
            pady=12,
            takefocus=1,
        )
        bouton.pack(fill=tk.X, side=tk.BOTTOM)
        self._rendre_focus_visible(bouton)
        bouton.focus_set()
        return bouton

    def _bouton_secondaire(
        self, parent: tk.Misc, texte: str, commande: Callable[[], None]
    ) -> tk.Button:
        bouton = tk.Button(
            parent,
            text=texte,
            command=commande,
            font=("Segoe UI", 10),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            activebackground="#142028",
            activeforeground=ENCRE,
            relief=tk.FLAT,
            takefocus=1,
        )
        bouton.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 8))
        self._rendre_focus_visible(bouton)
        return bouton

    def _achever_onboarding(self, raccourci_ptt: str | None = None) -> None:
        self.configuration = terminer_onboarding(
            self.configuration, raccourci_ptt=raccourci_ptt
        )
        self.raccourci_en_cours = self.configuration.raccourci_ptt
        self.session.raccourci_label = raccourcis_lisibles()[
            self.configuration.raccourci_ptt
        ]
        try:
            enregistrer_configuration(self.configuration, self.chemin_configuration)
        except OSError as exc:
            print(f"configuration non enregistrée : {exc}", flush=True)
        self._afficher_application()

    def _afficher_bienvenue(self) -> None:
        u = ui_presence()
        cadre, pied = self._cadre_onboarding(1, u["welcome_title"], u["welcome_body"])
        tk.Label(
            cadre,
            text=u["no_recording"],
            bg=FOND_VITRE,
            fg=ENCRE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X)
        tk.Label(
            cadre,
            text=u["a11y"],
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X, pady=(16, 0))
        self._bouton_principal(pied, u["continue"], self._afficher_reglage_ptt)
        self._bouton_secondaire(pied, u["skip"], self._achever_onboarding)

    def _afficher_reglage_ptt(self) -> None:
        u = ui_presence()
        cadre, pied = self._cadre_onboarding(2, u["ptt_title"], u["ptt_body"])
        tk.Label(
            cadre,
            text=u["shortcut_in_app"],
            bg=FOND_VITRE,
            fg=ENCRE,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        choix = tk.StringVar(value=self.raccourci_en_cours)

        def retenir(*_args: object) -> None:
            self.raccourci_en_cours = choix.get()

        choix.trace_add("write", retenir)
        for valeur, libelle in raccourcis_lisibles().items():
            radio = tk.Radiobutton(
                cadre,
                text=libelle,
                variable=choix,
                value=valeur,
                bg=FOND_VITRE,
                fg=ENCRE,
                activebackground=FOND_VITRE,
                activeforeground=ENCRE,
                selectcolor="#142028",
                font=("Segoe UI", 11),
                anchor="w",
                takefocus=1,
            )
            radio.pack(fill=tk.X, pady=4)
            self._rendre_focus_visible(radio)
        self._monter_essai_ptt(cadre)
        self._bouton_principal(pied, u["continue"], self._afficher_masquage)
        self._bouton_secondaire(
            pied,
            u["skip"],
            lambda: self._achever_onboarding(self.raccourci_en_cours),
        )

    def _monter_essai_ptt(self, parent: tk.Misc) -> None:
        tenu = {"on": False}
        bouton = tk.Button(
            parent,
            text="Essayer : maintenez ici (souris ou Entrée)",
            font=("Segoe UI", 11, "bold"),
            bg=visuel.PALETTES["repos"]["anneau"],
            fg=ENCRE,
            activebackground=visuel.PALETTES["ecoute"]["coeur"],
            activeforeground=ENCRE_FONCEE,
            relief=tk.RAISED,
            bd=3,
            padx=12,
            pady=10,
            takefocus=1,
        )
        bouton.pack(fill=tk.X, pady=(18, 0))
        self._rendre_focus_visible(bouton)

        def presser(_event: object | None = None) -> str:
            tenu["on"] = True
            bouton.configure(
                relief=tk.SUNKEN,
                text=ui_presence()["hearing"],
                bg=visuel.PALETTES["ecoute"]["coeur"],
                fg=ENCRE_FONCEE,
            )
            return "break"

        def relacher(_event: object | None = None) -> str:
            if not tenu["on"]:
                return "break"
            tenu["on"] = False
            bouton.configure(
                relief=tk.RAISED,
                text="Essayer : maintenez ici (souris ou Entrée)",
                bg=visuel.PALETTES["repos"]["anneau"],
                fg=ENCRE,
            )
            return "break"

        bouton.bind("<ButtonPress-1>", presser)
        bouton.bind("<ButtonRelease-1>", relacher)
        bouton.bind("<KeyPress-Return>", presser)
        bouton.bind("<KeyRelease-Return>", relacher)
        bouton.bind("<KeyPress-space>", presser)
        bouton.bind("<KeyRelease-space>", relacher)

    def _afficher_masquage(self) -> None:
        cadre, pied = self._cadre_onboarding(3, "Masquer la configuration", TEXTE_MASQUAGE)
        tk.Label(
            cadre,
            text=(
                f"Raccourci retenu : {RACCOURCIS[self.raccourci_en_cours]}. "
                "Pendant un appel distant, l'éclair s'allume et le statut le dit en texte."
            ),
            bg=FOND_VITRE,
            fg=ENCRE,
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X)
        tk.Label(
            cadre,
            text=RAPPEL_A11Y,
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X, pady=(16, 0))

        def commencer_et_masquer() -> None:
            self._achever_onboarding(self.raccourci_en_cours)
            self.masquer_configuration()

        self._bouton_principal(
            pied,
            "Commencer",
            lambda: self._achever_onboarding(self.raccourci_en_cours),
        )
        self._bouton_secondaire(pied, "Commencer et masquer", commencer_et_masquer)

    def _afficher_application(self) -> None:
        self._vider()
        cadre = tk.Frame(self.conteneur, bg=FOND)
        cadre.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.cadre_sante = tk.Frame(cadre, bg=etat_sante.BANDEAU_BG)
        self.bandeau_alerte = tk.Label(
            self.cadre_sante,
            text="",
            bg=etat_sante.BANDEAU_BG,
            fg=etat_sante.BANDEAU_FG,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            justify="left",
            wraplength=440,
            padx=12,
            pady=10,
            takefocus=1,
        )
        self.bandeau_alerte.pack(fill=tk.X)
        self._rendre_focus_visible(self.bandeau_alerte)

        bandeau = tk.Frame(cadre, bg=FOND)
        bandeau.pack(fill=tk.X, pady=(4, 0))

        self.toile = tk.Canvas(
            bandeau,
            width=TAILLE_BULLE,
            height=TAILLE_BULLE,
            bg=FOND,
            highlightthickness=0,
            bd=0,
        )
        self.toile.pack(side=tk.LEFT, expand=True)
        self.bulle = Bulle(self.toile, TAILLE_BULLE)

        cote_eclair = tk.Frame(
            bandeau,
            bg=FOND_VITRE,
            highlightthickness=1,
            highlightbackground=BORD_VITRE,
        )
        cote_eclair.pack(side=tk.RIGHT, padx=(8, 4), pady=12)
        taille_eclair = 72
        self.toile_eclair = tk.Canvas(
            cote_eclair,
            width=taille_eclair,
            height=taille_eclair,
            bg=FOND_VITRE,
            highlightthickness=0,
            bd=0,
        )
        self.toile_eclair.pack()
        self.badge = BadgeEclair(self.toile_eclair, taille_eclair)
        self.ligne_eclair = tk.Label(
            cote_eclair,
            text=libelle_eclair("repos"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            wraplength=120,
            justify="center",
        )
        self.ligne_eclair.pack(pady=(4, 0))

        raccourci = RACCOURCIS[self.configuration.raccourci_ptt]
        # Les événements explicites conservent la sémantique maintenir/relâcher,
        # y compris lorsque le bouton est atteint avec Tab.
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
            takefocus=1,
            highlightthickness=2,
            highlightcolor=visuel.PALETTES["ecoute"]["lueur"],
        )
        self.bouton.pack(pady=12, fill=tk.X)
        self.bouton.bind("<ButtonPress-1>", self.enfoncer)
        self.bouton.bind("<ButtonRelease-1>", self.relacher)
        self.bouton.bind("<KeyPress-Return>", self.enfoncer)
        self.bouton.bind("<KeyRelease-Return>", self.relacher)
        self._rendre_focus_visible(self.bouton)

        self.bouton_masquer = tk.Button(
            cadre,
            text="Masquer la configuration",
            command=self.masquer_configuration,
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            activebackground="#142028",
            activeforeground=ENCRE,
            relief=tk.FLAT,
            takefocus=1,
        )
        self.bouton_masquer.pack(fill=tk.X, pady=(0, 8))
        self._rendre_focus_visible(self.bouton_masquer)

        vitre = tk.Frame(
            cadre,
            bg=FOND_VITRE,
            highlightthickness=1,
            highlightbackground=BORD_VITRE,
        )
        vitre.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        panneau = tk.Frame(vitre, bg=FOND_VITRE)
        panneau.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        tk.Label(
            panneau,
            text=f"Raccourci : {raccourci}  ·  {TEXTE_MASQUAGE}",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=440,
        ).pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            panneau,
            text="Compris",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))
        self.zone_compris = self._zone_texte(panneau)

        tk.Label(
            panneau,
            text="Réponse",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))
        self.zone_reponse = self._zone_texte(panneau)

        self.ligne_etat = tk.Label(
            panneau,
            text=self._composer_statut(),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=440,
        )
        self.ligne_etat.pack(fill=tk.X, pady=(12, 0), side=tk.BOTTOM)

        appui, relache = sequences_tk(self.configuration.raccourci_ptt)
        self.racine.bind_all(appui, self._espace_enfonce)
        self.racine.bind_all(relache, self._espace_relache)
        self.racine.bind_all("<Escape>", lambda _e: self.fermer())

        print("UI_PRETE", flush=True)
        if self.chemin_sante and self.chemin_sante.exists():
            try:
                self.appliquer_etat_sante(etat_sante.lire_snapshot(self.chemin_sante))
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                pass
        elif self.sondes_actives and not self._sondes_fil:
            self._sondes_fil = threading.Thread(
                target=self._boucle_sondes,
                name="sondes-sante",
                daemon=True,
            )
            self._sondes_fil.start()
        if not self.session_lancee:
            self.session_lancee = True
            self.session.start()

    def masquer_configuration(self) -> None:
        """Masque dans la barre des tâches, qui reste le geste de rappel fiable."""
        self.relacher()
        self.racine.iconify()

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
        if getattr(self, "ligne_etat", None) is None:
            return
        self.ligne_etat.configure(text=self._composer_statut())

    def _appliquer_eclair(self, etat: str) -> None:
        if self.badge is not None:
            self.badge.appliquer_etat(etat)
        if self.ligne_eclair is None:
            return
        allume = eclair_allume(etat)
        self.ligne_eclair.configure(
            text=libelle_eclair(etat),
            fg=visuel.PALETTES["escalade"]["lueur"] if allume else ENCRE_SOURDE,
            font=("Segoe UI", 10, "bold") if allume else ("Segoe UI", 10),
        )

    def enfoncer(self, _event: object | None = None) -> None:
        if self.enfonce:
            return
        if not self.session.canal_pret.is_set():
            _trace_c10("PTT_IGNORE")
            self._afficher_statut("Canal pas encore prêt.")
            return
        self.enfonce = True
        self.session.tenu.set()
        _trace_c10("PTT_ON")
        if self.bulle is not None:
            self.bulle.appliquer_etat("ecoute", niveau=None)
        self._appliquer_eclair("ecoute")
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
        _trace_c10("PTT_OFF")
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

    def appliquer_etat_sante(self, etat: dict[str, Any]) -> None:
        vue = etat_sante.bandeau_depuis_etat(etat)
        self._phrase_reprise = str(vue.get("texte_reprise") or "")
        if self.bandeau_alerte is None or self.cadre_sante is None:
            if vue["visible"]:
                self._afficher_statut(str(vue["texte"]))
            elif self._phrase_reprise:
                self._afficher_statut(self._phrase_reprise)
            return
        if vue["visible"]:
            self.bandeau_alerte.configure(
                text=str(vue["texte"]),
                bg=str(vue["bg"]),
                fg=str(vue["fg"]),
                takefocus=1,
            )
            self.cadre_sante.configure(bg=str(vue["bg"]))
            if not self.bandeau_alerte.winfo_manager():
                self.bandeau_alerte.pack(fill=tk.X)
            if not self.cadre_sante.winfo_manager():
                freres = [
                    enfant
                    for enfant in self.cadre_sante.master.pack_slaves()
                    if enfant is not self.cadre_sante
                ]
                options = {"fill": tk.X, "pady": (0, 8)}
                if freres:
                    options["before"] = freres[0]
                self.cadre_sante.pack(**options)
            try:
                self.bandeau_alerte.focus_set()
            except tk.TclError:
                pass
            self._afficher_statut(str(vue["texte"]))
        else:
            self.bandeau_alerte.pack_forget()
            self.cadre_sante.pack_forget()
            if self._phrase_reprise:
                self._afficher_statut(self._phrase_reprise)

    def _boucle_sondes(self) -> None:
        racine_depot = Path(__file__).resolve().parents[2]
        worker_dir = racine_depot / "workers" / "night_health_vault_note"
        if str(worker_dir) not in sys.path:
            sys.path.insert(0, str(worker_dir))
        try:
            from handlers import handle_health_check
        except ImportError as exc:
            print(f"sondes : {exc}", flush=True)
            return
        while not self._sondes_stop.is_set():
            try:
                etat = handle_health_check({})
                self.file_ui.put({"type": "sante", "etat": etat})
            except Exception as exc:
                print(f"sondes : {exc}", flush=True)
            self._sondes_stop.wait(2.0)

    def _rafraichir_sante_fichier(self) -> None:
        if self.chemin_sante is None:
            return
        maintenant = time.perf_counter()
        if maintenant - self._dernier_sante_ts < 1.0:
            return
        self._dernier_sante_ts = maintenant
        if not self.chemin_sante.exists():
            return
        try:
            self.appliquer_etat_sante(etat_sante.lire_snapshot(self.chemin_sante))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return

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
                if self.bulle is not None:
                    self.bulle.appliquer_etat(etat, niveau=valeur)
                self._appliquer_eclair(etat)
                distant = statut_pour_etat(etat)
                if distant:
                    self._afficher_statut(distant)
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
        elif kind == "sante":
            brut = message.get("etat")
            if isinstance(brut, dict):
                self.appliquer_etat_sante(brut)

    def _armer_tic(self) -> None:
        if self._tic_arme:
            return
        self._tic_arme = True
        self.racine.after(visuel.INTERVALLE_MS, self.tic)

    def _dessiner_champ(self) -> None:
        if self.toile_fond is None:
            return
        largeur = max(int(self.toile_fond.winfo_width()), 2)
        hauteur = max(int(self.toile_fond.winfo_height()), 2)
        etat = "repos"
        if self.bulle is not None:
            etat = self.bulle.etat
        elif self.orbe_accueil is not None:
            etat = self.orbe_accueil.etat
        self.toile_fond.delete("nappe")
        visuel.dessiner_nappe(
            self.toile_fond,
            largeur=largeur,
            hauteur=hauteur,
            palette=visuel.PALETTES.get(etat, visuel.PALETTES["repos"]),
            maintenant=time.perf_counter() - self.naissance_champ,
            etat=etat,
            ampleur=0.58,
            etendre=True,
        )

    def tic(self) -> None:
        # after() doit toujours être réarmé : une exception dans le dessin
        # gèlerait l'interface, y compris la ligne d'état.
        try:
            try:
                while True:
                    self._traiter(self.file_ui.get_nowait())
            except queue.Empty:
                pass
            self._rafraichir_sante_fichier()
            self._dessiner_champ()
            if self.orbe_accueil is not None:
                self.orbe_accueil.dessiner()
            if self.bulle is not None:
                self.bulle.dessiner()
            if self.badge is not None:
                self.badge.dessiner()
        except tk.TclError:
            return
        except Exception as exc:
            print(f"tic : {exc}", flush=True)
        try:
            self.racine.after(visuel.INTERVALLE_MS, self.tic)
        except tk.TclError:
            return

    def fermer(self, _event: object | None = None) -> None:
        self._sondes_stop.set()
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
        default=URL_DEFAUT,
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
    parseur.add_argument(
        "--config",
        type=Path,
        default=None,
        help="chemin de configuration (utile aux tests et installations portables)",
    )
    parseur.add_argument(
        "--onboarding",
        action="store_true",
        help="réafficher l'onboarding sans effacer le choix enregistré",
    )
    parseur.add_argument(
        "--sante",
        type=Path,
        default=None,
        help="fichier JSON d'état de santé (bandeau d'alerte, tests et mode dégradé)",
    )
    parseur.add_argument(
        "--sondes",
        action="store_true",
        help="sonder les ponts en direct (activé tout seul si --sante est absent)",
    )
    return parseur.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = analyser_arguments(argv)
    if args.sante is None:
        args.sondes = True
    Application(args).boucler()


if __name__ == "__main__":
    main()
