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
import os
import queue
import sys
import threading
import time
import ctypes
import tkinter as tk

try:
    from tkinter import ttk
except ImportError:  # pragma: no cover
    ttk = None
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
    appliquer_langue_presence,
    charger_configuration,
    eclair_allume,
    enregistrer_configuration,
    libelle_eclair,
    message_options,
    normaliser_configuration,
    raccourcis_lisibles,
    sequences_relache_extra,
    sequences_tk,
    statut_pour_etat,
    terminer_onboarding,
    ui_presence,
)
from src.i18n import t

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


def assurer_stdio(journal: Path | None = None) -> Path | None:
    """pythonw laisse stdout/stderr à None et ferme les fd C 1/2.

    C13 : WS ouvert, 0 AUDIO_RECV. ``python -u`` (flux valides) marche.
    On rattache Python *et* les descripteurs C avant d'importer sounddevice.
    """
    if sys.stdout is not None and sys.stderr is not None:
        try:
            sys.stdout.fileno()
            sys.stderr.fileno()
            return None
        except (OSError, AttributeError):
            pass
    if journal is None:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        racine = (
            Path(base) / "hyper-ambient" if base else Path.home() / ".hyper-ambient"
        )
        journal = racine / "presence.log"
    journal.parent.mkdir(parents=True, exist_ok=True)
    flux = open(journal, "a", encoding="utf-8", buffering=1)
    try:
        os.dup2(flux.fileno(), 1)
        os.dup2(flux.fileno(), 2)
    except OSError:
        pass
    sys.stdout = flux
    sys.stderr = flux
    return journal


def _socket_fermee(exc: BaseException) -> bool:
    """Vrai si la socket est morte : il faut remonter pour se reconnecter.

    Avaler cette erreur hors tour laissait Présence boucler sur une socket
    fermée après une relance du host-agent, sans jamais se reconnecter.
    """
    return type(exc).__name__.startswith("ConnectionClosed") or isinstance(
        exc, ConnectionError
    )


def journaliser(*args: object) -> None:
    """pythonw n'a pas de stdout : print() tuait le fil session (C13)."""
    flux = getattr(sys, "stdout", None)
    if flux is None:
        return
    try:
        print(*args, file=flux, flush=True)
    except OSError:
        return


def _trace_c10(evenement: str, **champs: Any) -> None:
    """Trace minimale C10 : PTT, WS, premier audio. Horloge monotone."""
    extra = " ".join(f"{cle}={valeur}" for cle, valeur in champs.items())
    suffixe = f" {extra}" if extra else ""
    journaliser(f"C10 t={time.monotonic():.3f} {evenement}{suffixe}")


def action_appui_parler(*, mains_libres: bool, ecoute_active: bool) -> str:
    """Hold PTT, ou toggle press-to-start / press-to-send."""
    if not mains_libres:
        return "hold"
    return "send" if ecoute_active else "start"


def relache_termine_lecoute(mains_libres: bool) -> bool:
    """False en mains libres : relâcher ne doit pas envoyer le tour."""
    return not mains_libres


def est_repetition_clavier(touche_enfoncee: bool, event: object | None) -> bool:
    """True seulement pour l'auto-repeat clavier, pas pour un clic souris."""
    if not touche_enfoncee:
        return False
    if event is None:
        return True
    keysym = str(getattr(event, "keysym", "") or "")
    return bool(keysym) and keysym not in {"??", "None"}


def libelle_bouton_parler(
    *,
    mains_libres: bool,
    ecoute_active: bool,
    touche_enfoncee: bool,
    textes: dict[str, str],
) -> str:
    """ON : Écoute… pendant l'appui, Appuie pour envoyer après relâche."""
    if mains_libres:
        if ecoute_active and touche_enfoncee:
            return textes["listening_toggle"]
        if ecoute_active:
            return textes["tap_to_send"]
        return textes["speak"]
    return textes["speaking"] if touche_enfoncee else textes["speak"]


def echap_coupe_la_voix(en_lecture: bool) -> bool:
    """Échap : Stop si Magpie parle, sinon quitter (comportement actuel)."""
    return bool(en_lecture)


DELAI_JEV_PRET_MS = 3000


def relayer_jev_pret(
    message: Any, deposer: Callable[[dict[str, Any]], None]
) -> bool:
    """Relaye ``{"type":"jev_pret"}`` vers l'UI. True si le message est consommé."""
    if isinstance(message, dict) and message.get("type") == "jev_pret":
        deposer({"type": "jev_pret"})
        return True
    return False


def relayer_conversation(
    message: Any, deposer: Callable[[dict[str, Any]], None]
) -> bool:
    """Relaye ``{"type":"conversation", ...}`` vers l'UI. True si consommé."""
    if not isinstance(message, dict) or message.get("type") != "conversation":
        return False
    ouverte = message.get("ouverte") is True
    try:
        restant_s = float(message.get("restant_s") or 0.0)
    except (TypeError, ValueError):
        restant_s = 0.0
    deposer({"type": "conversation", "ouverte": ouverte, "restant_s": restant_s})
    return True


def relayer_harnais(
    message: Any, deposer: Callable[[dict[str, Any]], None]
) -> bool:
    """Relaye ``{"type":"harnais_session", ...}`` : ouvrir la conversation du harnais."""
    if not isinstance(message, dict) or message.get("type") != "harnais_session":
        return False
    deposer(
        {
            "type": "harnais_session",
            "harnais": str(message.get("harnais") or ""),
            "session": str(message.get("session") or ""),
        }
    )
    return True


def relayer_cerveau(
    message: Any, deposer: Callable[[dict[str, Any]], None]
) -> bool:
    """Relaye ``{"type":"cerveau", ...}`` (distant actif) vers l'UI. True si consommé."""
    if not isinstance(message, dict) or message.get("type") != "cerveau":
        return False
    deposer(
        {
            "type": "cerveau",
            "state": str(message.get("state") or ""),
            "nom": str(message.get("nom") or ""),
            "mode": str(message.get("mode") or ""),
        }
    )
    return True


def libelle_indicateur_conversation(
    *,
    mains_libres: bool,
    ouverte: bool,
    restant_s: float,
    textes: dict[str, str],
) -> str:
    """État 1 vide ; 2 invitation ; 3 décompte. Rien si mains libres éteint."""
    if not mains_libres:
        return ""
    if ouverte:
        return textes["conversation_open"].format(n=max(0, int(restant_s)))
    return textes["conversation_invite"]


def consommer_reponse(
    ws,
    sortie,
    t_fin_parole: float,
    deposer: Callable[[dict[str, Any]], None],
    arreter: threading.Event,
    interrompre: threading.Event | None = None,
    sur_interruption: Callable[[], None] | None = None,
    couper: threading.Event | None = None,
) -> bool:
    """Lit la socket jusqu'au marqueur vide, restitue, et relaye l'état.

    ``couper`` est le bouton Stop : la voix se tait, statut Interrompue,
    pas d'écoute. ``interrompre`` est Parler pendant la réponse : barge-in
    (tampon jeté + ``sur_interruption``). Renvoie True seulement en barge-in.

    Le serveur envoie, dans l'ordre : des paquets audio, puis un rapport,
    puis un marqueur de fin vide. Sortir dès qu'un message n'a pas de
    trames revenait à sortir SUR LE RAPPORT, en laissant le marqueur dans
    la socket — le tour suivant le lisait à la place de sa propre réponse,
    et restait muet. Seul ``frames == []`` termine le tour.
    """
    premier_son = None
    interrompu = False
    barge_in = False

    def _trancher_interruption() -> bool:
        nonlocal interrompu, barge_in
        if interrompu:
            return True
        stop_demande = couper is not None and couper.is_set()
        barge_demande = interrompre is not None and interrompre.is_set()
        if not (stop_demande or barge_demande):
            return False
        interrompu = True
        barge_in = barge_demande and not stop_demande
        try:
            sortie.abort()
        except Exception as exc:
            journaliser(f"interruption : {exc}")
        if barge_in and sur_interruption is not None:
            sur_interruption()
        deposer(
            {
                "type": "statut",
                "texte": (
                    ui_presence()["interrupted_listening"]
                    if barge_in
                    else ui_presence()["interrupted"]
                ),
            }
        )
        return True

    while not arreter.is_set():
        # Petit timeout : barge-in vocal et Stop ne doivent pas attendre
        # le prochain paquet TTS. Fallback bloquant si recv n'accepte pas
        # timeout (tests, vieux client). close() débloque encore.
        try:
            try:
                brut = ws.recv(timeout=0.05)
            except TypeError:
                brut = ws.recv()
        except TimeoutError:
            _trancher_interruption()
            continue
        except Exception:
            return barge_in
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
        if relayer_jev_pret(message, deposer):
            continue
        if relayer_conversation(message, deposer):
            continue
        if relayer_cerveau(message, deposer):
            continue
        if relayer_harnais(message, deposer):
            continue
        recues = message.get("frames")
        if recues is None:
            continue
        if not recues:
            break
        if _trancher_interruption():
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
            journaliser(f"restitution : {exc}")

    if premier_son is None and not arreter.is_set() and not interrompu:
        deposer({"type": "statut", "texte": "Aucune trame de réponse — rien à restituer."})
    elif premier_son is not None:
        if not interrompu:
            time.sleep(0.25)
        moteur._reposer(sortie)
        deposer({"type": "etat", "etat": "repos", "niveau": None})
    return barge_in


def ligne_lecture(capture, *, barge: bool) -> str:
    """Ce que le micro a capté pendant que MOTHER parlait, et le seuil
    d'interruption vocale : de quoi régler le « stop » sans deviner (24/09)."""
    instantane = getattr(capture, "instantane", None)
    if not callable(instantane):
        return ""
    from native.hostagent.windows_audio import FACTEUR_SEUIL_LECTURE, PLANCHER_LECTURE_RMS

    inst = instantane()
    seuil = max(float(inst.get("seuil", 0.0)) * FACTEUR_SEUIL_LECTURE, PLANCHER_LECTURE_RMS)
    return (
        f"LECTURE : rms_max={float(inst.get('rms_max', 0.0)):.0f} "
        f"seuil_interruption={seuil:.0f} coupee={'oui' if barge else 'non'}"
    )


def ligne_pouls_ml(capture, *, n_segments: int, en_lecture: bool, couper: bool) -> str:
    """Pouls ML : tranche entendue / pas fermée / pas revenue."""
    inst: dict[str, Any] = {}
    getter = getattr(capture, "instantane", None)
    if callable(getter):
        try:
            inst = dict(getter() or {})
        except Exception:
            inst = {}
    suspendue = bool(inst.get("suspendue", getattr(capture, "_suspendu", False)))
    return (
        "ML : vivante, %d segment(s) envoye(s), lecture=%s, suspendue=%s, "
        "seuil=%.0f, rms=%.0f, pic=%.0f, accumulation=%s, couper=%s, "
        "trop_courts=%d (dernier %.0f ms)"
        % (
            n_segments,
            "oui" if en_lecture else "non",
            "oui" if suspendue else "non",
            float(inst.get("seuil") or 0.0),
            float(inst.get("rms") or 0.0),
            float(inst.get("rms_max") or 0.0),
            "oui" if inst.get("accumulation") else "non",
            "oui" if couper else "non",
            int(inst.get("rejets_courts") or 0),
            float(inst.get("dernier_rejet_ms") or 0.0),
        )
    )


class _OuEvenements:
    """True si l'un des événements est levé. ``is_set`` seulement (pas wait)."""

    def __init__(self, *evenements: threading.Event | None) -> None:
        self._evenements = evenements

    def is_set(self) -> bool:
        return any(evt is not None and evt.is_set() for evt in self._evenements)


def evenement_interruption_lecture(tenu: threading.Event, capture) -> object:
    """Parler (tenu) ou barge-in vocal, même chemin dans consommer_reponse."""
    vocal = getattr(capture, "barge_in", None)
    if vocal is None:
        return tenu
    return _OuEvenements(tenu, vocal)


def apres_barge_in(capture) -> None:
    """Voix coupée : conserver l'audio vocal, sinon reprendre propre."""
    vocal = getattr(capture, "barge_in", None)
    if vocal is not None and vocal.is_set():
        regime = getattr(capture, "regime_lecture", None)
        if callable(regime):
            regime(False)
        return
    reprendre = getattr(capture, "reprendre", None)
    if callable(reprendre):
        reprendre()


def _abort_sortie(sortie) -> None:
    if sortie is None:
        return
    try:
        sortie.abort()
    except Exception as exc:
        journaliser(f"interruption : {exc}")


class Bulle:
    """La présence ronde : même dessin vivant que l'overlay, dans l'app."""

    def __init__(self, toile: tk.Canvas, taille: int, contraste: bool = False) -> None:
        self.toile = toile
        self.taille = taille
        self.contraste = contraste
        self.etat = "repos"
        self.palette_affichee = visuel.palette_pour("repos", contraste)
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
        cible = visuel.palette_pour(self.etat, self.contraste)
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
            etat=self.etat,
        )


class SessionVocale(threading.Thread):
    """Réseau + micro + haut-parleur, hors du fil tkinter.

    ``tenu`` est l'écoute armée par l'interface (hold PTT, ou toggle
    mains libres jusqu'au second appui). On capture tant qu'il est levé.
    """

    def __init__(
        self,
        file_ui: queue.Queue,
        *,
        url: str,
        device: str | None,
        sortie: str | None,
        raccourci_label: str,
        mains_libres: bool = False,
    ) -> None:
        super().__init__(name="session-vocale", daemon=True)
        self.file_ui = file_ui
        self.url = url
        self.device = device
        self.nom_sortie = sortie
        self.raccourci_label = raccourci_label
        self.mains_libres = bool(mains_libres)
        self.arreter = threading.Event()
        self.tenu = threading.Event()
        self.couper = threading.Event()
        self.en_lecture = threading.Event()
        self.canal_pret = threading.Event()
        self._options_a_envoyer = threading.Event()
        # Bascule du cerveau distant, envoyée seule : renvoyer mains_libres
        # refermerait la conversation côté host-agent.
        self._ml_a_envoyer = False
        self._cerveau_a_envoyer: dict[str, Any] | None = None
        self._attendre_jev = False
        self.ws = None
        self.sortie = None
        self._capture_continue = None

    def demander_envoi_options(self) -> None:
        self._ml_a_envoyer = True
        self._options_a_envoyer.set()

    def demander_bascule_cerveau(self, choix: dict[str, Any]) -> None:
        self._cerveau_a_envoyer = dict(choix)
        self._options_a_envoyer.set()

    def _pousser_options(self, ws) -> None:
        choix, self._cerveau_a_envoyer = self._cerveau_a_envoyer, None
        envoyer_ml = self._ml_a_envoyer or choix is None
        self._ml_a_envoyer = False
        try:
            if choix is not None:
                ws.send(json.dumps({"type": "options", "cerveau": choix}))
                journaliser(f"OPTIONS cerveau={choix}")
            if envoyer_ml:
                ws.send(json.dumps(message_options(self.mains_libres)))
                journaliser(f"OPTIONS mains_libres={self.mains_libres}")
        except Exception as exc:
            journaliser(f"options : {exc}")
        self._options_a_envoyer.clear()
        if envoyer_ml:
            self._attendre_jev = bool(self.mains_libres)

    def _aspirer_jev_pret(self, ws, timeout: float = 0.2) -> dict[str, Any] | None:
        """Lit un jev_pret hors tour, sans bloquer l'attente PTT.

        Rend le message qu'il n'a pas su relayer (des trames d'annonce), pour
        que la boucle mains libres le joue au lieu de le perdre (24/09)."""
        try:
            brut = ws.recv(timeout=timeout)
        except TimeoutError:
            return
        except TypeError:
            self.tenu.wait(timeout)
            return
        except Exception as exc:
            journaliser(f"jev_pret : {exc}")
            if _socket_fermee(exc):
                raise
            self._attendre_jev = False
            return
        try:
            message = json.loads(brut)
        except (json.JSONDecodeError, TypeError):
            return
        if relayer_jev_pret(message, self.deposer):
            self._attendre_jev = False
            return
        if relayer_conversation(message, self.deposer):
            return
        if relayer_cerveau(message, self.deposer):
            return
        if relayer_harnais(message, self.deposer):
            return
        return message if isinstance(message, dict) else None

    def _jouer_annonce_ml(self, ws, capture, sortie, trames: list) -> None:
        """Annonce de mandat hors tour, en mains libres (séance du 24/09).

        Micro en régime lecture, comme pour une réponse : il ne s'enregistre
        pas lui-même, et la voix ou Stop coupent l'annonce. Le reste de
        l'annonce, jusqu'au marqueur vide, passe par ``consommer_reponse``.
        """
        journaliser(f"annonce hors tour (mains libres) : {len(trames)} trames")
        ligne_lecture(capture, barge=False)  # remet le pic à zéro
        if hasattr(capture, "regime_lecture"):
            capture.regime_lecture(True, on_barge_in=lambda: _abort_sortie(sortie))
        else:
            capture.suspendre()
        self.couper.clear()
        self.en_lecture.set()
        barge = False
        try:
            try:
                moteur._jouer(sortie, [x for bloc in trames for x in bloc])
            except Exception as exc:
                journaliser(f"restitution : {exc}")
            barge = (
                consommer_reponse(
                    ws, sortie, time.perf_counter(), self.deposer, self.arreter,
                    interrompre=evenement_interruption_lecture(self.tenu, capture),
                    couper=self.couper,
                    sur_interruption=lambda: apres_barge_in(capture),
                )
                is True
            )
        finally:
            mesure = ligne_lecture(capture, barge=barge)
            if mesure:
                journaliser(mesure)
            self.en_lecture.clear()
            self.couper.clear()
            if hasattr(capture, "regime_lecture"):
                capture.regime_lecture(False)
        if not barge and not self.arreter.is_set() and self.mains_libres:
            reprendre = getattr(capture, "reprendre", None)
            if callable(reprendre):
                reprendre()

    def _aspirer_hors_tour(
        self, ws, capture, sortie, timeout: float = 0.2
    ) -> bool:
        """Lit la socket hors tour en mode bouton, sans bloquer l'attente PTT.

        Relaie jev_pret et conversation comme ``_aspirer_jev_pret``, et joue
        une annonce de mandat (trames puis marqueur vide) jusqu'à son
        marqueur. Rend True si l'appui l'a coupée : la capture tourne déjà.
        """
        try:
            brut = ws.recv(timeout=timeout)
        except TimeoutError:
            return False
        except TypeError:
            self.tenu.wait(timeout)
            return False
        except Exception as exc:
            journaliser(f"hors tour : {exc}")
            if _socket_fermee(exc):
                raise
            self.tenu.wait(timeout)
            return False
        try:
            message = json.loads(brut)
        except (json.JSONDecodeError, TypeError):
            return False
        if not isinstance(message, dict):
            return False
        if relayer_jev_pret(message, self.deposer):
            self._attendre_jev = False
            return False
        if relayer_conversation(message, self.deposer):
            return False
        if relayer_cerveau(message, self.deposer):
            return False
        if relayer_harnais(message, self.deposer):
            return False
        recues = message.get("frames")
        if not recues:
            return False
        journaliser(f"annonce hors tour : {len(recues)} trames")
        a_jouer: list[float] = []
        for brute in recues:
            a_jouer.extend(brute)
        try:
            moteur._jouer(sortie, a_jouer)
        except Exception as exc:
            journaliser(f"restitution : {exc}")
        self.couper.clear()
        self.en_lecture.set()
        try:
            return consommer_reponse(
                ws, sortie, time.perf_counter(), self.deposer, self.arreter,
                interrompre=self.tenu, couper=self.couper,
                sur_interruption=capture.start,
            ) is True
        finally:
            self.en_lecture.clear()
            self.couper.clear()

    def deposer(self, message: dict[str, Any]) -> None:
        if not self.arreter.is_set():
            self.file_ui.put(message)

    def demander_arret(self) -> None:
        self.arreter.set()
        self.tenu.clear()
        self.couper.set()
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
        assurer_stdio()
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
            if sys.platform == "darwin":
                from native.hostagent.platform_audio import micro_accessible

                if not micro_accessible(device=indice):
                    self.deposer({"type": "erreur", "texte":
                                  "Accès micro non établi : vérifier le périphérique et la permission Microphone macOS."})
                    return
            fabrique = moteur._fabrique_entree(indice, sd)
            capture = moteur.PushToTalkCapture(stream_factory=fabrique)
            from native.hostagent.platform_audio import CaptureContinue

            self._capture_continue = CaptureContinue(stream_factory=fabrique)
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

        self.sortie = sortie
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
                        self._pousser_options(ws)
                        _trace_c10("WS_OPEN", url=self.url)
                        u_canal = ui_presence()
                        cle_pret = (
                            "channel_ready_hands_free"
                            if self.mains_libres
                            else "channel_ready"
                        )
                        pret = u_canal[cle_pret].format(
                            raccourci=self.raccourci_label
                        )
                        self.deposer({"type": "statut", "texte": pret})
                        journaliser("CANAL_PRET")
                        self._boucle_tours(ws, capture, sortie)
                except Exception as exc:
                    if self.arreter.is_set():
                        break
                    if moteur._est_erreur_audio(exc):
                        texte = moteur.decrire_erreur_peripherique(exc)
                    else:
                        texte = f"Impossible de joindre {self.url} : {exc}"
                    journaliser(texte)
                    self.deposer({"type": "erreur", "texte": texte})
                    self.arreter.wait(2.0)
                finally:
                    self.canal_pret.clear()
                    self.ws = None
        finally:
            self.sortie = None
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
            if self.mains_libres and self._capture_continue is not None:
                deja_en_ecoute = False
                # Un seul flux a la fois sur le micro. Mesure du 2026-09-20 :
                # un appui sur Parler laissait son flux ouvert, le mains
                # libres en ouvrait un second sur le meme peripherique, et
                # Windows servait du silence au second — rms=0 alors que le
                # micro fonctionnait. L'oreille paraissait morte.
                try:
                    capture.stop()
                except Exception:
                    pass
                self._boucle_tours_continus(ws, self._capture_continue, sortie)
                continue
            if not deja_en_ecoute:
                while not self.arreter.is_set() and not self.tenu.is_set():
                    if self.mains_libres and self._capture_continue is not None:
                        break
                    if self._options_a_envoyer.is_set():
                        self._pousser_options(ws)
                    # Hors tour, la socket est lue aussi en mode bouton :
                    # une annonce de mandat (« Codex a fini… ») arrive quand
                    # personne ne parle. Laissée en file, elle devenait la
                    # réponse du tour suivant, et tout se décalait d'un cran.
                    if self._aspirer_hors_tour(ws, capture, sortie):
                        deja_en_ecoute = True
                        break
                if self.arreter.is_set():
                    return
                if self.mains_libres and self._capture_continue is not None:
                    continue
                if not deja_en_ecoute:
                    capture.start()
            deja_en_ecoute = False
            u_tour = ui_presence()
            self.deposer(
                {
                    "type": "statut",
                    "texte": (
                        u_tour["listening_tap_send"]
                        if self.mains_libres
                        else u_tour["listening"]
                    ),
                }
            )
            while not self.arreter.is_set() and self.tenu.is_set():
                time.sleep(0.03)
            trames = capture.stop()
            t_fin_parole = time.perf_counter()
            if self.arreter.is_set():
                return
            if self.mains_libres:
                self.deposer({"type": "statut", "texte": u_tour["sending"]})
            if not trames:
                _trace_c10("AUDIO_SEND", n_trames=0, n_samples=0)
                self.deposer(
                    {
                        "type": "statut",
                        "texte": ui_presence()["no_frames"],
                    }
                )
                self.deposer({"type": "etat", "etat": "repos", "niveau": None})
                continue
            n_samples = sum(int(trame.samples.size) for trame in trames)
            _trace_c10("AUDIO_SEND", n_trames=len(trames), n_samples=n_samples)
            self.deposer(
                {
                    "type": "statut",
                    "texte": ui_presence()["frames_sent"].format(n=len(trames)),
                }
            )
            journaliser(f"envoi : {len(trames)} trames")
            ws.send(
                json.dumps(
                    {
                        "type": "invoke",
                        "primitive": "audio.capture",
                        "frames": [trame.samples.tolist() for trame in trames],
                        "mains_libres": self.mains_libres,
                    }
                )
            )
            self.couper.clear()
            self.en_lecture.set()
            try:
                deja_en_ecoute = consommer_reponse(
                    ws, sortie, t_fin_parole, self.deposer, self.arreter,
                    interrompre=self.tenu, couper=self.couper,
                    sur_interruption=capture.start,
                ) is True
            finally:
                self.en_lecture.clear()
                self.couper.clear()
            journaliser("tour : terminé")

    def _boucle_tours_continus(self, ws, capture, sortie) -> None:
        """Micro ouvert en continu : tours au silence, bouton = envoi immédiat."""
        capture.start()
        tenu_etait = self.tenu.is_set()
        u_tour = ui_presence()
        self.deposer({"type": "statut", "texte": u_tour["listening_tap_send"]})
        journaliser("ML : boucle continue demarree")
        # Trace de vie : sans elle, « le mode meurt » est indiscernable de
        # « la detection de voix ne declenche pas ». Mesure du 2026-09-20.
        _dernier_pouls = time.monotonic()
        _n_segments = 0
        try:
            while not self.arreter.is_set() and self.mains_libres:
                maintenant = time.monotonic()
                if maintenant - _dernier_pouls >= 5.0:
                    _dernier_pouls = maintenant
                    journaliser(
                        ligne_pouls_ml(
                            capture,
                            n_segments=_n_segments,
                            en_lecture=self.en_lecture.is_set(),
                            couper=self.couper.is_set(),
                        )
                    )
                if self._options_a_envoyer.is_set():
                    self._pousser_options(ws)
                reste = self._aspirer_jev_pret(
                    ws, timeout=0.2 if self._attendre_jev else 0.03
                )
                if reste is not None and reste.get("frames"):
                    self._jouer_annonce_ml(ws, capture, sortie, reste["frames"])
                    tenu_etait = self.tenu.is_set()
                    continue
                if not self.en_lecture.is_set() and self.couper.is_set():
                    # Stop pressé hors lecture : ne pas armer le tour suivant.
                    self.couper.clear()
                tenu_est = self.tenu.is_set()
                if tenu_etait and not tenu_est:
                    capture.forcer_fin()
                tenu_etait = tenu_est
                if capture.segment_pret():
                    trames = capture.prendre_segment()
                    _n_segments += 1
                    journaliser("ML : segment %d detecte (%d trames)" % (_n_segments, len(trames)))
                    self._expedier_tour_continu(ws, capture, sortie, trames)
                    tenu_etait = self.tenu.is_set()
                    continue
                time.sleep(0.03)
        finally:
            capture.stop()

    def _expedier_tour_continu(self, ws, capture, sortie, trames) -> None:
        t_fin_parole = time.perf_counter()
        self.deposer({"type": "statut", "texte": ui_presence()["sending"]})
        if not trames:
            _trace_c10("AUDIO_SEND", n_trames=0, n_samples=0)
            self.deposer({"type": "statut", "texte": ui_presence()["no_frames"]})
            self.deposer({"type": "etat", "etat": "repos", "niveau": None})
            return
        n_samples = sum(int(trame.samples.size) for trame in trames)
        _trace_c10("AUDIO_SEND", n_trames=len(trames), n_samples=n_samples)
        self.deposer(
            {
                "type": "statut",
                "texte": ui_presence()["frames_sent"].format(n=len(trames)),
            }
        )
        journaliser(f"envoi : {len(trames)} trames")
        ws.send(
            json.dumps(
                {
                    "type": "invoke",
                    "primitive": "audio.capture",
                    "frames": [trame.samples.tolist() for trame in trames],
                    "mains_libres": self.mains_libres,
                }
            )
        )
        self.couper.clear()
        ligne_lecture(capture, barge=False)  # remet le pic à zéro
        if hasattr(capture, "regime_lecture"):
            capture.regime_lecture(True, on_barge_in=lambda: _abort_sortie(sortie))
        else:
            capture.suspendre()
        self.en_lecture.set()
        barge = False
        stop_pendant = False
        try:
            barge = (
                consommer_reponse(
                    ws,
                    sortie,
                    t_fin_parole,
                    self.deposer,
                    self.arreter,
                    interrompre=evenement_interruption_lecture(self.tenu, capture),
                    couper=self.couper,
                    sur_interruption=lambda: apres_barge_in(capture),
                )
                is True
            )
            stop_pendant = self.couper.is_set()
        finally:
            mesure = ligne_lecture(capture, barge=barge)
            if mesure:
                journaliser(mesure)
            self.en_lecture.clear()
            stop_pendant = stop_pendant or self.couper.is_set()
            self.couper.clear()
            if hasattr(capture, "regime_lecture"):
                capture.regime_lecture(False)
        if not barge and not stop_pendant:
            time.sleep(0.25)
        if not self.arreter.is_set() and self.mains_libres:
            if not barge:
                reprendre = getattr(capture, "reprendre", None)
                if callable(reprendre):
                    reprendre()
        journaliser("tour : terminé")


class Application:
    """Fenêtre normale : bulle, bouton maintenu, transcripts, ligne d'état."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.file_ui: queue.Queue = queue.Queue()
        self.configuration = charger_configuration(args.config)
        if args.onboarding:
            self.configuration = ConfigurationPresence(
                onboarding_termine=False,
                raccourci_ptt=self.configuration.raccourci_ptt,
                langue=self.configuration.langue,
                contraste=self.configuration.contraste,
                mains_libres=self.configuration.mains_libres,
            )
        appliquer_langue_presence(self.configuration)
        self.chemin_configuration = args.config
        self.session = SessionVocale(
            self.file_ui,
            url=args.url,
            device=args.device,
            sortie=args.sortie,
            raccourci_label=raccourcis_lisibles()[self.configuration.raccourci_ptt],
            mains_libres=self.configuration.mains_libres,
        )
        self.enfonce = False
        self.ecoute_basculee = False
        self._touche_parler_enfoncee = False
        self.dernier_delai_ms: float | None = None
        self.texte_statut = ui_presence()["connecting"]
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
        self.bouton_mains_libres: tk.Button | None = None
        self.bouton_stop: tk.Button | None = None
        self.bouton_reglages: tk.Button | None = None
        self.fenetre_reglages = None
        self.cadre_sante: tk.Frame | None = None
        self.cadre_conversation: tk.Frame | None = None
        self.pastille_conversation: tk.Canvas | None = None
        self.ligne_conversation: tk.Label | None = None
        self._conversation_ouverte = False
        self._conversation_restant_s = 0.0
        self._dernier_sante_ts = 0.0
        self._sondes_stop = threading.Event()
        self._sondes_fil: threading.Thread | None = None
        self._phrase_reprise = ""
        self._jev_repli_id: Any = None

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
        # Fenêtre normale : pas d'overrideredirect, la croix doit fermer.
        # Pas de chroma-key : le geste HA est la nappe/orbe, pas un trou.
        self.racine.protocol("WM_DELETE_WINDOW", self.fermer)
        self.racine.after(50, self._appliquer_icone_win32)
        self.racine.after(400, self._appliquer_icone_win32)

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
        self.bouton_mains_libres = None
        self.bouton_stop = None
        self.bouton_reglages = None
        self.ligne_mains_libres = None
        self.cadre_conversation = None
        self.pastille_conversation = None
        self.ligne_conversation = None
        self.cadre_sante = None
        self.ecoute_basculee = False
        self._touche_parler_enfoncee = False
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
        self.orbe_accueil = Bulle(toile_orbe, 140, self.configuration.contraste)
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
            journaliser(f"configuration non enregistrée : {exc}")
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
        tk.Label(
            cadre,
            text=u["hands_free"],
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X, pady=(12, 0))
        self._monter_langue_et_contraste(cadre)
        self._bouton_principal(pied, u["continue"], self._afficher_mains_libres)
        self._bouton_secondaire(pied, u["skip"], self._achever_onboarding)

    def _afficher_mains_libres(self) -> None:
        u = ui_presence()
        cadre, pied = self._cadre_onboarding(
            2, u["hands_free_title"], u["hands_free"]
        )
        tk.Label(
            cadre,
            text=u["a11y"],
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill=tk.X)
        self._bouton_principal(
            pied, u["hands_free_enable"], lambda: self._choisir_mains_libres(True)
        )
        self._bouton_secondaire(
            pied, u["hands_free_later"], lambda: self._choisir_mains_libres(False)
        )

    def _choisir_mains_libres(self, actif: bool) -> None:
        self._appliquer_options(mains_libres=actif)
        self._afficher_reglage_ptt()

    def _afficher_reglage_ptt(self) -> None:
        u = ui_presence()
        cadre, pied = self._cadre_onboarding(3, u["ptt_title"], u["ptt_body"])
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
            text=ui_presence()["try_hold"],
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
                text=ui_presence()["try_hold"],
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
        u = ui_presence()
        cadre, pied = self._cadre_onboarding(4, u["hide_title"], u["hide_body"])
        tk.Label(
            cadre,
            text=u["shortcut_kept"].format(
                raccourci=raccourcis_lisibles()[self.raccourci_en_cours]
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
            text=u["a11y"],
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
            u["start"],
            lambda: self._achever_onboarding(self.raccourci_en_cours),
        )
        self._bouton_secondaire(pied, u["start_and_hide"], commencer_et_masquer)

    def _monter_langue_et_contraste(
        self, parent: tk.Misc, *, avec_langue: bool = True
    ) -> None:
        u = ui_presence()
        if avec_langue:
            tk.Label(
                parent,
                text=u["language"],
                bg=FOND_VITRE,
                fg=ENCRE,
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill=tk.X, pady=(16, 4))
            choix = tk.StringVar(value=self.configuration.langue)

            def retenir_langue(*_args: object) -> None:
                self._appliquer_options(langue=choix.get())

            choix.trace_add("write", retenir_langue)
            for code, cle in (("fr", "reglages.langue.fr"), ("en", "reglages.langue.en")):
                radio = tk.Radiobutton(
                    parent,
                    text=t(cle),
                    variable=choix,
                    value=code,
                    bg=FOND_VITRE,
                    fg=ENCRE,
                    activebackground=FOND_VITRE,
                    activeforeground=ENCRE,
                    selectcolor="#142028",
                    font=("Segoe UI", 11),
                    anchor="w",
                    takefocus=1,
                )
                radio.pack(fill=tk.X, pady=2)
                self._rendre_focus_visible(radio)
        contraste = tk.IntVar(value=1 if self.configuration.contraste else 0)

        def retenir_contraste(*_args: object) -> None:
            self._appliquer_options(contraste=bool(contraste.get()))

        case = tk.Checkbutton(
            parent,
            text=u["contrast"],
            variable=contraste,
            command=retenir_contraste,
            bg=FOND_VITRE,
            fg=ENCRE,
            activebackground=FOND_VITRE,
            activeforeground=ENCRE,
            selectcolor="#142028",
            font=("Segoe UI", 11),
            anchor="w",
            takefocus=1,
        )
        case.pack(fill=tk.X, pady=(8, 0))
        self._rendre_focus_visible(case)

    def _appliquer_options(
        self,
        *,
        langue: str | None = None,
        contraste: bool | None = None,
        mains_libres: bool | None = None,
    ) -> None:
        self.configuration = ConfigurationPresence(
            onboarding_termine=self.configuration.onboarding_termine,
            raccourci_ptt=self.configuration.raccourci_ptt,
            langue=langue or self.configuration.langue,
            contraste=self.configuration.contraste if contraste is None else contraste,
            mains_libres=(
                self.configuration.mains_libres
                if mains_libres is None
                else bool(mains_libres)
            ),
        )
        if mains_libres is False:
            self._conversation_ouverte = False
            self._conversation_restant_s = 0.0
        os.environ["HA_LANG"] = self.configuration.langue
        appliquer_langue_presence(self.configuration)
        self.session.raccourci_label = raccourcis_lisibles()[
            self.configuration.raccourci_ptt
        ]
        self.session.mains_libres = self.configuration.mains_libres
        if mains_libres is not None:
            self.session.demander_envoi_options()
            journaliser(
                f"mains_libres={'ON' if self.configuration.mains_libres else 'OFF'} "
                "sync configuration=session"
            )
        if self.orbe_accueil is not None:
            self.orbe_accueil.contraste = self.configuration.contraste
        if self.bulle is not None:
            self.bulle.contraste = self.configuration.contraste
        try:
            enregistrer_configuration(self.configuration, self.chemin_configuration)
        except OSError as exc:
            journaliser(f"configuration non enregistrée : {exc}")
        self._rafraichir_bouton_mains_libres()
        self._rafraichir_ligne_mains_libres()
        self._rafraichir_bouton_parler()
        self._rafraichir_indicateur_conversation()

    def _rafraichir_bouton_mains_libres(self) -> None:
        bouton = self.bouton_mains_libres
        if bouton is None:
            return
        u = ui_presence()
        actif = self.configuration.mains_libres
        bouton.configure(
            text=u["hands_free_on"] if actif else u["hands_free_off"],
            bg=visuel.PALETTES["ecoute"]["coeur"] if actif else FOND_VITRE,
            fg=ENCRE_FONCEE if actif else ENCRE_SOURDE,
            activebackground=visuel.PALETTES["ecoute"]["lueur"] if actif else "#142028",
            activeforeground=ENCRE_FONCEE if actif else ENCRE,
        )

    def _rafraichir_ligne_mains_libres(self) -> None:
        ligne = getattr(self, "ligne_mains_libres", None)
        if ligne is None:
            return
        u = ui_presence()
        raccourci = raccourcis_lisibles()[self.configuration.raccourci_ptt]
        ligne.configure(text=u["hands_free_hint"].format(raccourci=raccourci))

    def _rafraichir_indicateur_conversation(self) -> None:
        cadre = getattr(self, "cadre_conversation", None)
        ligne = getattr(self, "ligne_conversation", None)
        pastille = getattr(self, "pastille_conversation", None)
        if cadre is None or ligne is None:
            return
        mains = self._mains_libres_actif()
        ouverte = bool(getattr(self, "_conversation_ouverte", False))
        restant = float(getattr(self, "_conversation_restant_s", 0.0) or 0.0)
        texte = libelle_indicateur_conversation(
            mains_libres=mains,
            ouverte=ouverte,
            restant_s=restant,
            textes=ui_presence(),
        )
        ligne.configure(text=texte)
        if not mains:
            cadre.pack_forget()
            return
        if not cadre.winfo_manager():
            apres = getattr(self, "ligne_mains_libres", None)
            options: dict[str, Any] = {"fill": tk.X, "pady": (0, 8)}
            if apres is not None and apres.winfo_manager():
                options["after"] = apres
            cadre.pack(**options)
        etat = "ecoute" if ouverte else "repos"
        palette = visuel.palette_pour(etat, self.configuration.contraste)
        ligne.configure(fg=palette["lueur"] if ouverte else ENCRE_SOURDE)
        if pastille is None:
            return
        pastille.delete("all")
        pastille.configure(bg=FOND)
        pastille.create_oval(
            1,
            1,
            13,
            13,
            fill=palette["coeur"],
            outline=palette["lueur"],
        )

    def _rafraichir_bouton_parler(self) -> None:
        bouton = getattr(self, "bouton", None)
        if bouton is None:
            return
        u = ui_presence()
        actif = self._mains_libres_actif()
        texte = libelle_bouton_parler(
            mains_libres=actif,
            ecoute_active=self.ecoute_basculee,
            touche_enfoncee=self._touche_parler_enfoncee,
            textes=u,
        )
        if actif and self.ecoute_basculee:
            bouton.configure(
                relief=tk.SUNKEN if self._touche_parler_enfoncee else tk.RAISED,
                text=texte,
                bg=visuel.PALETTES["ecoute"]["coeur"],
                fg="#0c141c",
            )
            return
        if self.enfonce:
            bouton.configure(
                relief=tk.SUNKEN,
                text=texte,
                bg=visuel.PALETTES["ecoute"]["coeur"],
                fg="#0c141c",
            )
            return
        bouton.configure(
            relief=tk.RAISED,
            text=texte,
            bg=visuel.PALETTES["repos"]["anneau"],
            fg=ENCRE,
        )

    def _mains_libres_actif(self) -> bool:
        actif = bool(self.configuration.mains_libres)
        session = getattr(self, "session", None)
        if session is not None and session.mains_libres != actif:
            session.mains_libres = actif
            session.demander_envoi_options()
            journaliser(f"mains_libres sync configuration={actif}")
        return actif

    def _basculer_mains_libres(self) -> None:
        if self.ecoute_basculee:
            self._envoyer_ecoute_toggle()
        nouveau = not self.configuration.mains_libres
        self._appliquer_options(mains_libres=nouveau)
        if nouveau and self.enfonce and not self.ecoute_basculee:
            self._demarrer_ecoute_toggle()
        u = ui_presence()
        raccourci = raccourcis_lisibles()[self.configuration.raccourci_ptt]
        if nouveau:
            self._afficher_statut(u["hands_free_connecting"])
            self._armer_repli_jev_pret()
        else:
            self._annuler_repli_jev_pret()
            self._afficher_statut(u["hands_free_hint"].format(raccourci=raccourci))
        self._focus_parler()

    def _armer_repli_jev_pret(self) -> None:
        self._annuler_repli_jev_pret()
        try:
            self._jev_repli_id = self.racine.after(
                DELAI_JEV_PRET_MS, self._repli_jev_pret
            )
        except tk.TclError:
            self._jev_repli_id = None

    def _annuler_repli_jev_pret(self) -> None:
        ident = getattr(self, "_jev_repli_id", None)
        if ident is None:
            return
        try:
            self.racine.after_cancel(ident)
        except tk.TclError:
            pass
        self._jev_repli_id = None

    def _repli_jev_pret(self) -> None:
        self._jev_repli_id = None
        self._afficher_jev_pret_si_en_connexion()

    def _afficher_jev_pret_si_en_connexion(self) -> None:
        if not self.configuration.mains_libres:
            return
        try:
            if self.texte_statut != ui_presence()["hands_free_connecting"]:
                return
            self._afficher_statut(ui_presence()["hands_free_connected"])
        except tk.TclError:
            return

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
        self.bulle = Bulle(self.toile, TAILLE_BULLE, self.configuration.contraste)

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
        # Indicateur et bascule du cerveau distant (24/09) : on sait toujours
        # qui converse, et on en change sans ouvrir les Réglages.
        self._monter_bascule_cerveau(cote_eclair)
        self._monter_choix_harnais(cote_eclair)

        raccourci = raccourcis_lisibles()[self.configuration.raccourci_ptt]
        u = ui_presence()
        rang_voix = tk.Frame(cadre, bg=FOND)
        rang_voix.pack(pady=12, fill=tk.X)
        # Hold PTT par défaut ; mains libres = toggle sans maintenir.
        self.bouton = tk.Button(
            rang_voix,
            text=u["speak"],
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
        self.bouton.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.bouton.bind("<ButtonPress-1>", self.enfoncer)
        self.bouton.bind("<ButtonRelease-1>", self.relacher)
        self.bouton.bind("<KeyPress-Return>", self.enfoncer)
        self.bouton.bind("<KeyRelease-Return>", self.relacher)
        self.bouton.bind("<KeyPress-space>", self.enfoncer)
        self.bouton.bind("<KeyRelease-space>", self.relacher)
        self._rendre_focus_visible(self.bouton)
        self.bouton.focus_set()
        self._rafraichir_bouton_parler()

        self.bouton_stop = tk.Button(
            rang_voix,
            text=u["stop"],
            command=self.couper_voix,
            font=("Segoe UI", 16, "bold"),
            bg="#3a1c1c",
            fg=ENCRE,
            activebackground="#5a2828",
            activeforeground=ENCRE,
            relief=tk.RAISED,
            bd=3,
            padx=18,
            pady=16,
            takefocus=1,
            highlightthickness=2,
            highlightcolor=visuel.PALETTES["ecoute"]["lueur"],
        )
        self.bouton_stop.pack(side=tk.RIGHT, padx=(8, 0), fill=tk.Y)
        self._rendre_focus_visible(self.bouton_stop)

        self.bouton_mains_libres = tk.Button(
            cadre,
            text=u["hands_free_off"],
            command=self._basculer_mains_libres,
            font=("Segoe UI", 11, "bold"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            activebackground="#142028",
            activeforeground=ENCRE,
            relief=tk.FLAT,
            takefocus=1,
        )
        self.bouton_mains_libres.pack(fill=tk.X, pady=(0, 8))
        self._rendre_focus_visible(self.bouton_mains_libres)
        self._rafraichir_bouton_mains_libres()
        raccourci_hint = raccourcis_lisibles()[self.configuration.raccourci_ptt]
        self.ligne_mains_libres = tk.Label(
            cadre,
            text=u["hands_free_hint"].format(raccourci=raccourci_hint),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=440,
        )
        self.ligne_mains_libres.pack(fill=tk.X, pady=(0, 8))

        self.cadre_conversation = tk.Frame(cadre, bg=FOND)
        self.pastille_conversation = tk.Canvas(
            self.cadre_conversation,
            width=14,
            height=14,
            bg=FOND,
            highlightthickness=0,
            bd=0,
        )
        self.pastille_conversation.pack(side=tk.LEFT, padx=(0, 8))
        self.ligne_conversation = tk.Label(
            self.cadre_conversation,
            text="",
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.ligne_conversation.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._rafraichir_indicateur_conversation()

        self.bouton_reglages = tk.Button(
            cadre,
            text=u["settings"],
            command=self.ouvrir_reglages,
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            activebackground="#142028",
            activeforeground=ENCRE,
            relief=tk.FLAT,
            takefocus=1,
        )
        self.bouton_reglages.pack(fill=tk.X, pady=(0, 8))
        self._rendre_focus_visible(self.bouton_reglages)

        self.bouton_masquer = tk.Button(
            cadre,
            text=u["hide_config"],
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

        options = tk.Frame(cadre, bg=FOND)
        options.pack(fill=tk.X, pady=(0, 4))
        self._monter_langue_et_contraste(options, avec_langue=False)

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
            text=f"{raccourci}  ·  {u['hide_body']}",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=440,
        ).pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            panneau,
            text=u["understood"],
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))
        self.zone_compris = self._zone_texte(panneau)

        tk.Label(
            panneau,
            text=u["reply"],
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
        for extra in sequences_relache_extra(self.configuration.raccourci_ptt):
            self.racine.bind_all(extra, self._espace_relache)
        self.racine.bind_all("<Escape>", self._echap)
        self.racine.bind_all("<Control-h>", lambda _e: self.masquer_configuration() or "break")
        self.racine.bind_all("<Control-H>", lambda _e: self.masquer_configuration() or "break")
        self.racine.bind_all("<F6>", self._focus_parler)
        self.racine.bind_all("<Control-slash>", lambda _e: self._afficher_aide_clavier())

        journaliser("UI_PRETE")
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


    def _focus_parler(self, _event: object | None = None) -> str:
        if self.bouton is not None:
            try:
                self.bouton.focus_set()
            except tk.TclError:
                pass
        return "break"

    def _afficher_aide_clavier(self) -> None:
        """Rappel des raccourcis clavier (a11y)."""
        raccourci = raccourcis_lisibles()[self.configuration.raccourci_ptt]
        self._afficher_statut(
            "Clavier : Tab parcours · Entrée active · "
            + raccourci
            + " parler · Ctrl+H masquer · F6 focus Parler · Échap Stop si parole, sinon quitter"
        )

    def ouvrir_reglages(self, chemin: Path | None = None) -> object:
        """Ouvre la fenêtre Réglages sans bloquer la fenêtre principale."""
        try:
            from reglages_ui import FenetreReglages, chemin_env_local
        except ImportError:
            from native.presence.reglages_ui import FenetreReglages, chemin_env_local

        existante = getattr(self, "fenetre_reglages", None)
        if existante is not None:
            try:
                if existante.fenetre.winfo_exists():
                    existante.fenetre.lift()
                    existante.fenetre.focus_set()
                    return existante
            except tk.TclError:
                pass
        cible = Path(chemin) if chemin is not None else chemin_env_local()
        self.fenetre_reglages = FenetreReglages(
            self.racine,
            cible,
            contraste=bool(self.configuration.contraste),
            langue=self.configuration.langue,
            sur_langue=lambda code: self._appliquer_options(langue=code),
        )
        return self.fenetre_reglages

    def masquer_configuration(self) -> None:
        """Masque dans la barre des tâches, qui reste le geste de rappel fiable."""
        if self.ecoute_basculee:
            self._envoyer_ecoute_toggle()
        else:
            self.relacher()
        self.racine.iconify()

    def _zone_texte(self, parent: tk.Misc) -> tk.Text:
        zone = tk.Text(
            parent,
            height=3,
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
        return (
            f"{self.texte_statut}  ·  "
            f"{ui_presence()['first_sound'].format(ms=self.dernier_delai_ms)}"
        )

    def _monter_bascule_cerveau(self, parent: tk.Misc) -> None:
        from native.presence import cerveau_distant as cd
        from native.presence.reglages_ui import chemin_env_local

        self._chemin_env = chemin_env_local()
        try:
            self._choix_cerveau = cd.choix_bascule(self._chemin_env)
        except Exception as exc:
            journaliser(f"bascule cerveau : {exc}")
            self._choix_cerveau = []
        self.var_cerveau = tk.StringVar(self.racine, value="…")
        if ttk is None or not self._choix_cerveau:
            self.combo_cerveau = None
            return
        self.combo_cerveau = ttk.Combobox(
            parent,
            textvariable=self.var_cerveau,
            values=[libelle for libelle, _ in self._choix_cerveau],
            state="readonly",
            width=18,
            takefocus=1,
            font=("Segoe UI", 9),
        )
        self.combo_cerveau.pack(pady=(4, 2), padx=4)
        self.combo_cerveau.bind("<<ComboboxSelected>>", lambda _e: self._basculer_cerveau())

    def _monter_choix_harnais(self, parent: tk.Misc) -> None:
        """« Harnais au premier plan » : la console du harnais s'ouvre devant,
        ou réduite. La conversation y est affichée dans les deux cas (24/09)."""
        from native.presence.harnais_ouvert import OuvreurHarnais

        self._ouvreur_harnais = OuvreurHarnais(str(Path(__file__).resolve().parents[2]))
        self.var_harnais_devant = tk.BooleanVar(
            self.racine, value=self.configuration.harnais_premier_plan
        )
        fond = parent.cget("bg")
        tk.Checkbutton(
            parent,
            text=ui_presence()["harness_front"],
            variable=self.var_harnais_devant,
            command=self._basculer_harnais_devant,
            bg=fond,
            activebackground=fond,
            fg="#c8c8d0",
            activeforeground="#ffffff",
            selectcolor=fond,
            font=("Segoe UI", 9),
            takefocus=1,
        ).pack(pady=(0, 2))

    def _basculer_harnais_devant(self) -> None:
        from dataclasses import replace

        self.configuration = replace(
            self.configuration, harnais_premier_plan=bool(self.var_harnais_devant.get())
        )
        try:
            enregistrer_configuration(self.configuration, self.chemin_configuration)
        except OSError as exc:
            journaliser(f"configuration non enregistrée : {exc}")

    def _ouvrir_harnais(self, message: dict[str, Any]) -> None:
        ouvreur = getattr(self, "_ouvreur_harnais", None)
        if ouvreur is None:
            return
        harnais, session = message.get("harnais", ""), message.get("session", "")
        devant = self.configuration.harnais_premier_plan

        def _ouvrir() -> None:
            # Hors du fil de l'UI : trouver la fenêtre prend jusqu'à 1 s.
            try:
                ouvert = ouvreur.ouvrir(harnais, session, premier_plan=devant)
            except Exception as exc:
                journaliser(f"harnais non ouvert : {exc}")
                return
            journaliser(f"HARNAIS {harnais} session={session} ouvert={ouvert}")

        threading.Thread(target=_ouvrir, name="harnais", daemon=True).start()

    def _basculer_cerveau(self) -> None:
        from native.presence import cerveau_distant as cd

        libelle = self.var_cerveau.get()
        choix = dict(self._choix_cerveau).get(libelle)
        if choix is None or getattr(self, "session", None) is None:
            return
        self.session.demander_bascule_cerveau(choix)
        self.var_cerveau.set(f"{libelle}…")
        # Le choix survit au redémarrage : écrit hors du fil de l'UI.
        threading.Thread(
            target=cd.enregistrer_choix,
            args=(self._chemin_env, choix["mode"], choix.get("model", ""), choix.get("effort", "low")),
            daemon=True,
        ).start()

    def _afficher_cerveau(self, message: dict[str, Any]) -> None:
        if getattr(self, "combo_cerveau", None) is None:
            return
        nom = str(message.get("nom") or "")
        etat = str(message.get("state") or "")
        if message.get("mode") == "api" and nom:
            nom = f"{nom} (clé d'API)"
        if etat == "switching":
            nom = f"{nom}…"
        elif etat == "error":
            nom = f"{nom} — indisponible"
        self.var_cerveau.set(nom)

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
            fg=visuel.PALETTES[etat if etat in visuel.PALETTES else "escalade"]["lueur"] if allume else ENCRE_SOURDE,
            font=("Segoe UI", 10, "bold") if allume else ("Segoe UI", 10),
        )

    def enfoncer(self, _event: object | None = None) -> None:
        if est_repetition_clavier(self._touche_parler_enfoncee, _event):
            return
        if not self.session.canal_pret.is_set():
            _trace_c10("PTT_IGNORE")
            self._afficher_statut(ui_presence()["channel_not_ready"])
            return
        self._touche_parler_enfoncee = True
        action = action_appui_parler(
            mains_libres=self._mains_libres_actif(),
            ecoute_active=self.ecoute_basculee,
        )
        if action == "send":
            self._envoyer_ecoute_toggle()
            return
        if action == "start":
            self._demarrer_ecoute_toggle()
            return
        if self.enfonce:
            return
        self.enfonce = True
        self.session.tenu.set()
        _trace_c10("PTT_ON")
        if self.bulle is not None:
            self.bulle.appliquer_etat("ecoute", niveau=None)
        self._appliquer_eclair("ecoute")
        self._rafraichir_bouton_parler()
        journaliser("bouton : enfoncé")

    def relacher(self, _event: object | None = None) -> None:
        self._touche_parler_enfoncee = False
        if not relache_termine_lecoute(self._mains_libres_actif()):
            if self.ecoute_basculee:
                self._rafraichir_bouton_parler()
                self._afficher_statut(ui_presence()["listening_tap_send"])
            return
        if not self.enfonce:
            return
        self.enfonce = False
        self.session.tenu.clear()
        _trace_c10("PTT_OFF")
        self._rafraichir_bouton_parler()
        journaliser("bouton : relâché")

    def _demarrer_ecoute_toggle(self) -> None:
        self.ecoute_basculee = True
        self.enfonce = True
        self.session.mains_libres = True
        self.session.tenu.set()
        _trace_c10("PTT_ON")
        if self.bulle is not None:
            self.bulle.appliquer_etat("ecoute", niveau=None)
        self._appliquer_eclair("ecoute")
        u = ui_presence()
        self._rafraichir_bouton_parler()
        self._afficher_statut(u["listening_toggle"])
        journaliser("mains_libres=ON start")

    def _envoyer_ecoute_toggle(self) -> None:
        self.ecoute_basculee = False
        self.enfonce = False
        self.session.tenu.clear()
        _trace_c10("PTT_OFF")
        u = ui_presence()
        self._rafraichir_bouton_parler()
        self._afficher_statut(u["sending"])
        journaliser("mains_libres=ON send")

    def _voix_en_cours(self) -> bool:
        if self.session.en_lecture.is_set():
            return True
        bulle = getattr(self, "bulle", None)
        return bulle is not None and getattr(bulle, "etat", None) == "parole"

    def couper_voix(self, _event: object | None = None) -> None:
        """Stop : leve le drapeau, et rien d'autre.

        Un seul fil touche le flux audio, celui de la session. Avorter le flux
        ici, depuis le fil Tk, revenait a appeler ``abort()`` pendant que le fil
        de session etait bloque dans ``sortie.write()`` ; PortAudio se coincait
        et le rappel d'entree ``_on_audio`` cessait de se declencher. Mesure du
        2026-09-20 : apres un Stop, plus aucun segment n'etait detecte pendant
        trente secondes, alors que la capture se declarait non suspendue et que
        la boucle mains libres restait vivante.

        ``consommer_reponse`` scrute ``couper`` entre deux paquets audio et
        avorte depuis le bon fil ; la coupure reste immediate a l'oreille.
        """
        self.session.couper.set()
        self._afficher_statut(ui_presence()["interrupted"])
        journaliser("stop : coupure voix demandee")

    def _echap(self, _event: object | None = None) -> str | None:
        if echap_coupe_la_voix(self._voix_en_cours()):
            self.couper_voix()
            return "break"
        self.fermer()
        return None


    def _focus_autorise_ptt(self, event: tk.Event | None = None) -> bool:
        """Espace = PTT sauf champ texte. En mains libres, le raccourci reste actif hors Speak."""
        try:
            w = self.racine.focus_get()
        except tk.TclError:
            w = None
        if w is None:
            return True
        if getattr(self, "bouton", None) is not None and w is self.bouton:
            return True
        if isinstance(w, (tk.Entry, tk.Text, tk.Spinbox)):
            return False
        if self._mains_libres_actif():
            return True
        if isinstance(w, (tk.Radiobutton, tk.Checkbutton)):
            return False
        if isinstance(w, tk.Button) and w is not getattr(self, "bouton", None):
            return False
        return True

    def _espace_enfonce(self, event: tk.Event) -> str | None:
        # Repeat clavier : KeyPress se repete tant que la touche reste enfoncee.
        if event.keysym != "space":
            return None
        if not self._focus_autorise_ptt(event):
            return None
        self.enfoncer(event)
        return "break"

    def _espace_relache(self, event: tk.Event) -> str | None:
        if event.keysym != "space":
            return None
        if self._touche_parler_enfoncee or self.enfonce or self.ecoute_basculee:
            self.relacher(event)
            return "break"
        if not self._focus_autorise_ptt(event):
            return None
        self.relacher(event)
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
            journaliser(f"sondes : {exc}")
            return
        while not self._sondes_stop.is_set():
            try:
                etat = handle_health_check({})
                self.file_ui.put({"type": "sante", "etat": etat})
            except Exception as exc:
                journaliser(f"sondes : {exc}")
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
            self._afficher_statut(ui_presence()["replying"])
        elif kind == "statut":
            self._afficher_statut(str(message.get("texte") or ""))
        elif kind == "jev_pret":
            self._annuler_repli_jev_pret()
            self._afficher_jev_pret_si_en_connexion()
        elif kind == "cerveau":
            self._afficher_cerveau(message)
        elif kind == "harnais_session":
            self._ouvrir_harnais(message)
        elif kind == "conversation":
            self._conversation_ouverte = message.get("ouverte") is True
            try:
                self._conversation_restant_s = float(message.get("restant_s") or 0.0)
            except (TypeError, ValueError):
                self._conversation_restant_s = 0.0
            self._rafraichir_indicateur_conversation()
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
            palette=visuel.palette_pour(etat, self.configuration.contraste),
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
            journaliser(f"tic : {exc}")
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
        self._annuler_repli_jev_pret()
        self._sondes_stop.set()
        self.session.demander_arret()
        existante = getattr(self, "fenetre_reglages", None)
        if existante is not None:
            try:
                existante.fermer()
            except tk.TclError:
                pass
            self.fenetre_reglages = None
        # PhotoImage + iconphoto(-default) : lâcher sur le fil Tk avant
        # destroy, sinon l'image survit à l'interpréteur et le prochain
        # Tk() du processus (suite de tests, relance interne) plante.
        self._icone_photo = None
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
        "--journal",
        type=Path,
        default=None,
        help="journal propre à cette instance (notamment avec pythonw)",
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
    assurer_stdio(args.journal)
    if args.sante is None:
        args.sondes = True
    threading.Thread(target=_demarrer_ponts, name="ponts", daemon=True).start()
    Application(args).boucler()


def _demarrer_ponts() -> None:
    """Codex et Claude Code configurés : leurs ponts partent avec Presence."""
    try:
        import ponts

        lances = ponts.demarrer_ponts(Path(__file__).resolve().parents[2])
        if lances:
            print(f"PONTS : demarres {', '.join(lances)}", flush=True)
    except Exception as exc:  # un pont absent ne doit jamais fermer Presence
        print(f"PONTS : echec {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
