"""Fenêtre Réglages de Presence : configurer les services depuis l'application.

Pas un assistant de premier lancement. Les sondes ne s'exécutent jamais
sur le fil Tk : fil séparé, résultat rendu par ``after()``. Une clé déjà
posée n'apparaît que par ses quatre derniers caractères, jamais en clair,
et n'est pas réécrite si le champ n'est pas retouché.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import queue
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:  # pragma: no cover — image docker sans Tk
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]

from src.i18n import t
from src.onboarding import sondes as module_sondes
from src.onboarding.reglages import lire_reglages, poser_reglages, reglage_present
from src.onboarding.sondes import (
    ETAT_MUET,
    Sonde,
    outil_cli_pret,
    sonder_brain_distant,
    sonder_claude,
    sonder_codex,
    sonder_jev,
    sonder_tout,
)

logger = logging.getLogger(__name__)

CLES_SECRETES = frozenset(
    {
        "BRAIN_API_KEY",
        "CODEX_BRIDGE_TOKEN",
        "CLI_BRIDGE_TOKEN",
        "TYPESAFE_API_KEY",
    }
)

BLOCS: tuple[dict[str, Any], ...] = (
    {
        "id": "modele_local",
        "cles": (),
        "titre": "reglages.modele_local_titre",
        "aide": "reglages.modele_local_aide",
        "donnees": "reglages.donnees.modele_local",
        "sortie": False,
        "info": True,
    },
    {
        "id": "cles",
        "cles": (),
        "titre": "reglages.cles_titre",
        "aide": "reglages.cles_aide",
        "donnees": "reglages.donnees.cles",
        "sortie": False,
        "info": True,
    },
    {
        "id": "voix",
        "cles": ("MOUTH_VOICE_NAME", "MOUTH_LANGUAGE"),
        "titre": "reglages.voix_titre",
        "aide": "reglages.voix_aide",
        "donnees": "reglages.donnees.voix",
        "sortie": False,
        "info": True,
        "menu": True,
        "repliable": True,
    },
    {
        "id": "langue",
        "cles": (),
        "titre": "reglages.langue_titre",
        "aide": "reglages.langue_aide",
        "donnees": "reglages.donnees.langue",
        "sortie": False,
        "info": True,
        "menu_langue": True,
    },
    {
        "id": "outil_codex",
        "cles": (),
        "titre": "reglages.outil_codex_titre",
        "aide": "reglages.outil_codex_aide",
        "donnees": "reglages.donnees.outil_codex",
        "sortie": False,
    },
    {
        "id": "outil_claude",
        "cles": (),
        "titre": "reglages.outil_claude_titre",
        "aide": "reglages.outil_claude_aide",
        "donnees": "reglages.donnees.outil_claude",
        "sortie": False,
    },
    {
        "id": "codex",
        "cles": ("CODEX_BRIDGE_URL", "CODEX_BRIDGE_TOKEN"),
        "titre": "reglages.codex_titre",
        "aide": "reglages.codex_aide",
        "donnees": "reglages.donnees.codex",
        "sortie": False,
    },
    {
        "id": "claude",
        "cles": ("CLI_BRIDGE_URL", "CLI_BRIDGE_TOKEN"),
        "titre": "reglages.claude_titre",
        "aide": "reglages.claude_aide",
        "donnees": "reglages.donnees.claude",
        "sortie": False,
    },
    {
        # 24/09 : l'utilisateur choisit qui converse à distance — sa clé d'API
        # ou son abonnement Claude / ChatGPT — et le modèle, dans une liste
        # lue en direct auprès du pont.
        "id": "cerveau_distant",
        "cles": (),
        "titre": "reglages.cerveau_titre",
        "aide": "reglages.cerveau_aide",
        "donnees": "reglages.donnees.cerveau_distant",
        "sortie": True,
        "info": True,
        "menu_cerveau": True,
    },
    {
        "id": "brain_distant",
        "cles": ("BRAIN_MODEL", "BRAIN_API_ENDPOINT", "BRAIN_API_KEY"),
        "titre": "reglages.brain_titre",
        "aide": "reglages.brain_aide",
        "donnees": "reglages.donnees.brain_distant",
        "sortie": True,
    },
    {
        "id": "jev",
        "cles": ("TYPESAFE_MODEL", "TYPESAFE_API_KEY"),
        "titre": "reglages.jev_titre",
        "aide": "reglages.jev_aide",
        "donnees": "reglages.donnees.jev",
        "sortie": True,
    },
    {
        "id": "recherche",
        "cles": (),
        "titre": "reglages.recherche_titre",
        "aide": "reglages.recherche_aide",
        "donnees": "reglages.donnees.recherche",
        "sortie": True,
        "info": True,
    },
)

CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "id": "machine",
        "titre": "reglages.categorie.machine",
        "blocs": ("modele_local", "cles", "voix", "langue"),
    },
    {
        "id": "outils",
        "titre": "reglages.categorie.outils",
        "blocs": ("outil_codex", "outil_claude", "codex", "claude"),
    },
    {
        "id": "distants",
        "titre": "reglages.categorie.distants",
        "blocs": ("cerveau_distant", "brain_distant", "jev", "recherche"),
    },
)

_SONDES_DEFAUT: dict[str, Callable[..., Any]] = {
    "brain_distant": sonder_brain_distant,
    "codex": sonder_codex,
    "claude": sonder_claude,
    "jev": sonder_jev,
    "tout": sonder_tout,
    "outil_codex": lambda nom="codex", *_a, **_k: outil_cli_pret("codex"),
    "outil_claude": lambda nom="claude", *_a, **_k: outil_cli_pret("claude"),
}

FOND = "#0c1820"
FOND_VITRE = "#102028"
BORD = "#2a4a5c"
ENCRE = "#d8e4ec"
ENCRE_SOURDE = "#8aa0b0"
PASTILLE_OK = "#3dba7a"
PASTILLE_KO = "#d04a4a"
PASTILLE_NEUTRE = "#4a6474"
# Troisième état : le service est joignable, mais aucune réponse vérifiable
# n'est revenue. Ni vert (rien n'est prouvé), ni rouge (il n'est pas tombé).
PASTILLE_MUET = "#d9a441"
MARQUEUR_LOCAL = "#4a8a72"
MARQUEUR_SORTIE = "#b89654"
# Champ de saisie : rectangle lisible, distinct du panneau (#102028).
FOND_CHAMP = "#1c3a4a"
BORD_CHAMP = "#6a9aac"
BORD_FOCUS = "#7ec8dc"
ENCRE_INVITE = "#7a96a4"
FOND_CHAMP_CONTRASTE = "#2a5060"
BORD_CHAMP_CONTRASTE = "#a8e0f0"
BORD_FOCUS_CONTRASTE = "#e8f8fc"
ENCRE_INVITE_CONTRASTE = "#b8d0dc"

_CLES_INVITE_IGNOREES = frozenset(
    {
        "Tab",
        "ISO_Left_Tab",
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Caps_Lock",
        "Num_Lock",
        "Left",
        "Right",
        "Up",
        "Down",
        "Home",
        "End",
        "Escape",
        "Return",
        "KP_Enter",
        "Win_L",
        "Win_R",
        "App",
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F7",
        "F8",
        "F9",
        "F10",
        "F11",
        "F12",
    }
)


def couleurs_champ(contraste: bool = False) -> dict[str, str]:
    """Palette du rectangle de saisie. Contraste élevé : bord et focus plus clairs."""
    if contraste:
        return {
            "fond": FOND_CHAMP_CONTRASTE,
            "bord": BORD_CHAMP_CONTRASTE,
            "focus": BORD_FOCUS_CONTRASTE,
            "invite": ENCRE_INVITE_CONTRASTE,
            "encre": ENCRE,
        }
    return {
        "fond": FOND_CHAMP,
        "bord": BORD_CHAMP,
        "focus": BORD_FOCUS,
        "invite": ENCRE_INVITE,
        "encre": ENCRE,
    }


def sortie_du_bloc(bloc: dict[str, Any]) -> bool:
    return bool(bloc.get("sortie"))


def aide_verifier() -> str:
    """Ce que « Vérifier » coûte vraiment, dit à l'écran.

    L'ancien libellé promettait cinq secondes pour tout : c'était vrai tant
    que les sondes ne posaient aucune question. Un harnais met bien plus, et
    une promesse fausse à l'écran vaut un plantage devant un jury. Le chiffre
    vient de la constante des sondes, pas d'un texte recopié.
    """
    cle = "reglages.verifier_aide_delais"
    texte = t(cle)
    if texte != cle:
        return texte
    return (
        "Vérifier appelle réellement le service : cinq secondes pour un "
        "service distant, jusqu'à "
        f"{int(module_sondes.DELAI_HARNAIS_S)} secondes pour un harnais, qui "
        "doit vraiment répondre à une question."
    )


def legende_etats() -> str:
    """Trois couleurs, trois sens. Sans légende, l'orange se devine."""
    cle = "reglages.legende_etats"
    texte = t(cle)
    if texte != cle:
        return texte
    return (
        "Vert : le service a répondu à la question de test. "
        "Orange : joignable, mais aucune réponse vérifiable. "
        "Rouge : injoignable, ou rien n'est encore configuré."
    )


def libelle_donnees(bloc: dict[str, Any]) -> str:
    return t(str(bloc["donnees"]))


def chemin_env_local(racine: Path | None = None) -> Path:
    base = Path(racine) if racine is not None else Path(__file__).resolve().parents[2]
    return base / ".env.local"


def chemin_carte_figee(racine: Path | None = None) -> Path:
    base = Path(racine) if racine is not None else Path(__file__).resolve().parents[2]
    return base / "dev" / "scripts" / "carte_figee.env"


def voix_courante(chemin: Path, carte: Path | None = None) -> str:
    """Voix choisie dans `.env.local`, sinon celle de la carte figée."""
    champs, _secrets = precharger(Path(chemin))
    nom = (champs.get("MOUTH_VOICE_NAME") or "").strip()
    if nom:
        return nom
    fichier = Path(carte) if carte is not None else chemin_carte_figee()
    return (lire_reglages(fichier).get("MOUTH_VOICE_NAME") or "").strip()


def renvoi_outil_depuis(champs: dict[str, str] | None) -> bool:
    """Absent du fichier = active. Seuls 0 / off / false / non desactivent."""
    brut = ((champs or {}).get("VOIX_RENVOI_OUTIL") or "1").strip().lower()
    return brut not in {"0", "off", "false", "non"}


def accent_courant(chemin: Path, carte: Path | None = None) -> str:
    """Phonétique choisie dans `.env.local`, sinon celle de la carte figée."""
    champs, _secrets = precharger(Path(chemin))
    nom = (champs.get("MOUTH_LANGUAGE") or "").strip()
    if nom:
        return nom
    return accent_naturel(carte)


def accent_naturel(carte: Path | None = None) -> str:
    """Valeur carte : aucun accent supplémentaire. Ne pas la changer."""
    fichier = Path(carte) if carte is not None else chemin_carte_figee()
    try:
        valeur = (lire_reglages(fichier).get("MOUTH_LANGUAGE") or "").strip()
    except OSError:
        valeur = ""
    return valeur or "fr"


def prefixe_langue(code: str) -> str:
    brut = (code or "").strip().replace("_", "-")
    if not brut:
        return ""
    return brut.split("-", 1)[0].lower()


def libelle_accent(code: str) -> str:
    """Libellé humain d'une langue Magpie. Pas un code d'ingénieur."""
    pref = prefixe_langue(code)
    if not pref:
        return t("reglages.accent_aucun")
    cle = f"reglages.accent.{pref}"
    texte = t(cle)
    if texte == cle:
        return t("reglages.accent.autre", code=code)
    return texte


def options_accent(
    langues: tuple[str, ...] | list[str],
    naturel: str = "fr",
) -> list[tuple[str, str]]:
    """Premier choix : aucun accent (carte). Ensuite la liste Magpie."""
    defaut = (naturel or "fr").strip() or "fr"
    options: list[tuple[str, str]] = [(t("reglages.accent_aucun"), defaut)]
    vus = {defaut}
    for brut in langues or ():
        code = str(brut).strip() if brut is not None else ""
        if not code or code in vus:
            continue
        vus.add(code)
        options.append((libelle_accent(code), code))
    return options


def url_tavily(texte: str | None = None) -> str:
    """Première adresse https du libellé Recherche web. Pas une clé secrète."""
    brut = texte if texte is not None else t("reglages.recherche_tavily")
    for mot in brut.replace("(", " ").replace(")", " ").split():
        if mot.startswith("https://"):
            return mot.rstrip(".,;:")
    return ""


def options_langue() -> list[tuple[str, str]]:
    return [
        (t("reglages.langue.fr"), "fr"),
        (t("reglages.langue.en"), "en"),
    ]


def libelle_pour_langue(code: str, options: list[tuple[str, str]]) -> str:
    cible = (code or "fr").strip().lower()
    if cible.startswith("en"):
        cible = "en"
    else:
        cible = "fr"
    for libelle, valeur in options:
        if valeur == cible:
            return libelle
    return options[0][0] if options else t("reglages.langue.fr")


def libelle_pour_accent(code: str, options: list[tuple[str, str]]) -> str:
    if not options:
        return t("reglages.accent_aucun")
    cible = (code or "").strip()
    for libelle, valeur in options:
        if valeur == cible:
            return libelle
    if not cible or cible == options[0][1]:
        return options[0][0]
    pref = prefixe_langue(cible)
    for libelle, valeur in options[1:]:
        if prefixe_langue(valeur) == pref:
            return libelle
    return options[0][0]


def _jouer_wav(donnees: bytes) -> None:
    import os
    import tempfile

    if not donnees:
        return
    fd, chemin = tempfile.mkstemp(suffix=".wav")
    try:
        os.write(fd, donnees)
        os.close(fd)
        fd = -1
        try:
            import winsound

            winsound.PlaySound(chemin, winsound.SND_FILENAME)
        except (ImportError, RuntimeError, OSError):
            pass
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(chemin)
        except OSError:
            pass


class ChampMenu:
    """Adapter `.get()` pour un menu, comme un champ de saisie.

    Si ``codes_par_libelle`` est posé, le menu affiche des libellés humains
    et ``get()`` rend le code enregistré (voix Magpie, langue de phonétique).
    """

    def __init__(
        self,
        variable: Any,
        codes_par_libelle: dict[str, str] | None = None,
    ) -> None:
        self._variable = variable
        self._codes = dict(codes_par_libelle or {})

    def poser_codes(self, codes_par_libelle: dict[str, str]) -> None:
        self._codes = dict(codes_par_libelle)

    def get(self) -> str:
        brut = (self._variable.get() or "").strip()
        if self._codes:
            return (self._codes.get(brut) or brut).strip()
        return brut


class ChampCase:
    """Adapter `.get()` pour une case : rend « 1 » ou « 0 »."""

    def __init__(self, variable: Any) -> None:
        self._variable = variable

    def get(self) -> str:
        try:
            return "1" if int(self._variable.get()) else "0"
        except (TypeError, ValueError):
            return "1"


def quatre_derniers(valeur: str | None) -> str:
    texte = (valeur or "").strip()
    if not texte:
        return ""
    return texte[-4:]


def precharger(chemin: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Rend ``(champs publics, secrets en mémoire)``.

    Les secrets ne vont pas dans ``champs`` : l'écran ne les affiche jamais
    en clair. Seul le suffixe de quatre caractères part vers le libellé.
    """
    brut = lire_reglages(Path(chemin))
    champs: dict[str, str] = {}
    secrets: dict[str, str] = {}
    for cle, valeur in brut.items():
        if cle in CLES_SECRETES:
            if str(valeur).strip():
                secrets[cle] = valeur
        else:
            champs[cle] = valeur
    return champs, secrets


def secret_effectif(saisie: str, existant: str) -> str:
    """Valeur à sonder : saisie neuve, sinon la clé déjà posée."""
    texte = (saisie or "").strip()
    deja = (existant or "").strip()
    if not texte or (deja and texte == quatre_derniers(deja)):
        return deja
    return texte


def valeurs_a_poser(
    saisie: dict[str, str], existants: dict[str, str]
) -> dict[str, str]:
    """Omet une clé secrète que l'utilisateur n'a pas retouchée."""
    posees: dict[str, str] = {}
    for cle, valeur in saisie.items():
        if cle in CLES_SECRETES:
            texte = (valeur or "").strip()
            deja = (existants.get(cle) or "").strip()
            if not texte:
                continue
            if deja and texte == quatre_derniers(deja):
                continue
            posees[cle] = texte
        else:
            posees[cle] = "" if valeur is None else str(valeur)
    return posees


def enregistrer_saisie(
    chemin: Path,
    saisie: dict[str, str],
    existants: dict[str, str],
    *,
    poser: Callable[[Path, dict[str, str]], None] | None = None,
) -> dict[str, str]:
    posees = valeurs_a_poser(saisie, existants)
    if posees:
        (poser or poser_reglages)(Path(chemin), posees)
    return posees


def lancer_hors_fil(
    travail: Callable[[], Any],
    rendre: Callable[[Any], None],
    *,
    planifier: Callable[[Callable[[], None]], None],
    fil_cls: type[threading.Thread] = threading.Thread,
) -> threading.Thread:
    """Exécute ``travail`` hors du fil courant ; ``rendre`` passe par ``planifier``.

    ``planifier`` est ``widget.after(0, fn)`` côté Tk, une file en test.
    """

    def corps() -> None:
        try:
            resultat = travail()
        except Exception as exc:
            resultat = exc
        planifier(lambda valeur=resultat: rendre(valeur))

    fil = fil_cls(target=corps, name="reglages-sonde", daemon=True)
    fil.start()
    return fil


def _importer_ouvrir_feedback() -> Callable[..., bool]:
    try:
        from onboarding import ouvrir_feedback
    except ImportError:
        from native.presence.onboarding import ouvrir_feedback
    return ouvrir_feedback


def ouvrir_fenetre_reglages(
    parent: Any, chemin: Path | None = None, **kwargs: Any
) -> "FenetreReglages":
    return FenetreReglages(parent, chemin or chemin_env_local(), **kwargs)


if tk is not None:

    class ChampSaisie(tk.Entry):
        """Zone de saisie visiblement éditable : bordure, focus, invite grise."""

        def __init__(
            self,
            parent: Any,
            *,
            invite: str = "",
            secret: bool = False,
            contraste: bool = False,
        ) -> None:
            self._couleurs = couleurs_champ(contraste)
            self._invite = invite
            self._secret = secret
            self._invite_visible = False
            super().__init__(
                parent,
                takefocus=1,
                bg=self._couleurs["fond"],
                fg=self._couleurs["encre"],
                insertbackground=self._couleurs["encre"],
                relief=tk.SOLID,
                bd=2,
                font=("Segoe UI", 11),
                highlightthickness=2,
                highlightbackground=self._couleurs["bord"],
                highlightcolor=self._couleurs["focus"],
                disabledbackground=self._couleurs["fond"],
                readonlybackground=self._couleurs["fond"],
            )
            self.bind("<FocusIn>", self._sur_focus, add="+")
            self.bind("<FocusOut>", self._sur_blur, add="+")
            self.bind("<KeyPress>", self._frappe, add="+")
            self.bind("<<Paste>>", self._coller, add="+")
            if self._invite:
                self.afficher_invite()

        @property
        def invite_visible(self) -> bool:
            return self._invite_visible

        @property
        def secret(self) -> bool:
            return self._secret

        def texte_affiche(self) -> str:
            return super().get()

        def get(self) -> str:  # type: ignore[override]
            if self._invite_visible:
                return ""
            return super().get()

        def insert(self, index: Any, string: str) -> None:  # type: ignore[override]
            if self._invite_visible:
                self._retirer_invite()
                super().insert(0, string)
                return
            super().insert(index, string)

        def delete(self, first: Any, last: Any | None = None) -> None:  # type: ignore[override]
            if self._invite_visible:
                self._retirer_invite()
                return
            super().delete(first, last)

        def poser_valeur(self, valeur: str) -> None:
            self._retirer_invite()
            super().delete(0, tk.END)
            if valeur:
                super().insert(0, valeur)

        def afficher_invite(self) -> None:
            if not self._invite:
                self._invite_visible = False
                self._appliquer_saisie()
                return
            self._invite_visible = True
            super().delete(0, tk.END)
            super().insert(0, self._invite)
            self.configure(
                fg=self._couleurs["invite"],
                show="",
                insertbackground=self._couleurs["encre"],
            )

        def _retirer_invite(self) -> None:
            if not self._invite_visible:
                return
            super().delete(0, tk.END)
            self._invite_visible = False
            self._appliquer_saisie()

        def _appliquer_saisie(self) -> None:
            self.configure(
                fg=self._couleurs["encre"],
                show="*" if self._secret else "",
                insertbackground=self._couleurs["encre"],
            )

        def _sur_focus(self, _event: object | None = None) -> None:
            self.configure(
                highlightbackground=self._couleurs["focus"],
                highlightcolor=self._couleurs["focus"],
            )

        def _sur_blur(self, _event: object | None = None) -> None:
            self.configure(
                highlightbackground=self._couleurs["bord"],
                highlightcolor=self._couleurs["focus"],
            )
            if not self._invite_visible and not super().get():
                self.afficher_invite()

        def _frappe(self, event: Any) -> str | None:
            if not self._invite_visible:
                return None
            touche = str(getattr(event, "keysym", "") or "")
            if touche in _CLES_INVITE_IGNOREES:
                return None
            if touche in ("BackSpace", "Delete"):
                return "break"
            etat = int(getattr(event, "state", 0) or 0)
            if etat & 0x4:
                return None
            char = str(getattr(event, "char", "") or "")
            if char and char.isprintable():
                self._retirer_invite()
                return None
            if len(touche) == 1:
                self._retirer_invite()
            return None

        def _coller(self, _event: object | None = None) -> None:
            if self._invite_visible:
                self._retirer_invite()

else:  # pragma: no cover — image docker sans Tk
    ChampSaisie = None  # type: ignore[assignment,misc]


class FenetreReglages:
    """Toplevel non-modale : la fenêtre principale reste utilisable."""

    def __init__(
        self,
        parent: Any,
        chemin: Path,
        *,
        sondes: dict[str, Callable[..., Any]] | None = None,
        client: Any = None,
        contraste: bool = False,
        ouvrir_retour: Callable[..., Any] | None = None,
        lister_voix: Callable[..., Any] | None = None,
        jouer_extrait: Callable[..., Any] | None = None,
        langue: str = "fr",
        sur_langue: Callable[[str], Any] | None = None,
        ouvrir_lien: Callable[[str], Any] | None = None,
    ) -> None:
        if tk is None:
            raise RuntimeError("tkinter indisponible")
        self.chemin = Path(chemin)
        self.client = client
        self.sondes = dict(sondes or {})
        self.contraste = bool(contraste)
        self._ouvrir_retour = ouvrir_retour or _importer_ouvrir_feedback()
        self._lister_voix = lister_voix
        self._jouer_extrait = jouer_extrait
        self._langue = "en" if str(langue).lower().startswith("en") else "fr"
        self._sur_langue = sur_langue
        self._ouvrir_lien = ouvrir_lien
        self.champs: dict[str, Any] = {}
        self.boutons_verifier: dict[str, tk.Button] = {}
        self.details: dict[str, tk.Label] = {}
        self.pastilles: dict[str, dict[str, Any]] = {}
        self.marqueurs_confidentialite: dict[str, bool] = {}
        self._toiles: dict[str, tk.Canvas] = {}
        self._suffixes: dict[str, tk.Label] = {}
        self._en_cours: set[str] = set()
        self._file: queue.Queue = queue.Queue()
        self._apres: Any = None
        self.var_voix: Any = None
        self.combo_voix: Any = None
        self.ligne_voix_repli: Any = None
        self.var_renvoi: Any = None
        self.case_renvoi: Any = None
        self.var_accent: Any = None
        self.combo_accent: Any = None
        self.corps_voix: Any = None
        self.bouton_ecouter: Any = None
        self._champ_accent: ChampMenu | None = None
        self.var_langue: Any = None
        self.combo_langue: Any = None
        self.ligne_langue_delai: Any = None
        self.ligne_langue_etat: Any = None
        self.lien_tavily: Any = None
        self._champ_langue: ChampMenu | None = None
        champs, secrets = precharger(self.chemin)
        self._secrets = secrets

        self.fenetre = tk.Toplevel(parent)
        self.fenetre.title(t("reglages.titre"))
        self.fenetre.configure(bg=FOND)
        self.fenetre.geometry("520x760")
        self.fenetre.minsize(440, 480)
        # Pas de grab : la fenêtre principale doit rester cliquable.
        self.fenetre.protocol("WM_DELETE_WINDOW", self.fermer)
        self.fenetre.bind("<Escape>", self._echap)
        self.fenetre.bind("<KeyPress-Escape>", self._echap)
        self.fenetre.bind_all("<Escape>", self._echap, add="+")

        self.barre_menus = tk.Menu(self.fenetre)
        self.fenetre.configure(menu=self.barre_menus)
        self.menu_aide = tk.Menu(self.barre_menus, tearoff=0)
        self.barre_menus.add_cascade(label=t("reglages.menu"), menu=self.menu_aide)
        self.menu_aide.add_command(
            label=t("ui.feedback"), command=self._lancer_feedback
        )

        tk.Label(
            self.fenetre,
            text=t("reglages.a11y"),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            wraplength=480,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 2))
        tk.Label(
            self.fenetre,
            text=t("reglages.confidentialite"),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            wraplength=480,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(0, 4))

        pied = tk.Frame(self.fenetre, bg=FOND)
        pied.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=12)
        self.ligne_legende = tk.Label(
            pied,
            text=legende_etats(),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=480,
            justify="left",
            anchor="w",
        )
        self.ligne_legende.pack(fill=tk.X, pady=(0, 4))
        self.ligne_aide_verifier = tk.Label(
            pied,
            text=aide_verifier() + " " + t("reglages.echec_manuel"),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=480,
            justify="left",
            anchor="w",
        )
        self.ligne_aide_verifier.pack(fill=tk.X, pady=(0, 8))
        rang_actions = tk.Frame(pied, bg=FOND)
        rang_actions.pack(fill=tk.X)
        self.bouton_tout = tk.Button(
            rang_actions,
            text=t("reglages.tout_verifier"),
            command=self.tout_verifier,
            takefocus=1,
            bg=FOND_VITRE,
            fg=ENCRE,
            activebackground="#142028",
            activeforeground=ENCRE,
            relief=tk.RAISED,
        )
        self.bouton_tout.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        self.bouton_enregistrer = tk.Button(
            rang_actions,
            text=t("reglages.enregistrer"),
            command=self.enregistrer,
            takefocus=1,
            bg=FOND_VITRE,
            fg=ENCRE,
            activebackground="#142028",
            activeforeground=ENCRE,
            relief=tk.RAISED,
        )
        self.bouton_enregistrer.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.ligne_statut = tk.Label(
            self.fenetre,
            text="",
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.ligne_statut.pack(side=tk.BOTTOM, fill=tk.X, padx=16)

        cadre_scroll = tk.Frame(self.fenetre, bg=FOND)
        cadre_scroll.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        toile = tk.Canvas(cadre_scroll, bg=FOND, highlightthickness=0, bd=0)
        barre = tk.Scrollbar(cadre_scroll, orient=tk.VERTICAL, command=toile.yview)
        toile.configure(yscrollcommand=barre.set)
        barre.pack(side=tk.RIGHT, fill=tk.Y)
        toile.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(toile, bg=FOND)
        fenetre_id = toile.create_window((0, 0), window=inner, anchor="nw")

        def _ajuster(_event: object | None = None) -> None:
            toile.configure(scrollregion=toile.bbox("all"))
            toile.itemconfigure(fenetre_id, width=toile.winfo_width())

        inner.bind("<Configure>", _ajuster)
        toile.bind("<Configure>", _ajuster)

        par_id = {str(bloc["id"]): bloc for bloc in BLOCS}
        for categorie in CATEGORIES:
            self._monter_categorie(inner, categorie)
            if categorie["id"] == "outils":
                self._monter_detecter(inner)
            for bloc_id in categorie["blocs"]:
                self._monter_bloc(inner, par_id[bloc_id], champs)

        for bloc in BLOCS:
            service = str(bloc["id"])
            self.marqueurs_confidentialite[service] = sortie_du_bloc(bloc)
            if not bloc.get("info"):
                self.pastilles[service] = {"ok": None, "detail": "", "etat": ""}
        # Ce que chaque champ affichait à l'ouverture : « Enregistrer » ne
        # pose que ce qui a changé, sinon une installation neuve repart avec
        # des clés vides qui écrasent les valeurs du conteneur.
        self._charges = {
            cle: champ.get() for cle, champ in self.champs.items()
        }
        self._apres = self.fenetre.after(40, self._pomper_file)
        self.fenetre.focus_set()

    def _monter_bloc(
        self, parent: tk.Misc, bloc: dict[str, Any], champs: dict[str, str]
    ) -> None:
        service = str(bloc["id"])
        cadre = tk.Frame(
            parent,
            bg=FOND_VITRE,
            highlightthickness=1,
            highlightbackground=BORD,
        )
        cadre.pack(fill=tk.X, padx=8, pady=8)
        interieur = tk.Frame(cadre, bg=FOND_VITRE)
        interieur.pack(fill=tk.X, padx=12, pady=10)
        entete = tk.Frame(interieur, bg=FOND_VITRE)
        entete.pack(fill=tk.X)
        tk.Label(
            entete,
            text=t(bloc["titre"]),
            bg=FOND_VITRE,
            fg=ENCRE,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._monter_marqueur(interieur, bloc)
        if bloc.get("repliable"):
            corps = tk.Frame(interieur, bg=FOND_VITRE)
            self.corps_voix = corps
            self._monter_corps_bloc(corps, bloc, champs)
            if t(bloc["titre"]):
                entete.bind("<Button-1>", lambda _e: self._basculer_voix(), add="+")
                for enfant in entete.winfo_children():
                    enfant.bind(
                        "<Button-1>", lambda _e: self._basculer_voix(), add="+"
                    )
            return
        self._monter_corps_bloc(interieur, bloc, champs)

    def _monter_corps_bloc(
        self, parent: tk.Misc, bloc: dict[str, Any], champs: dict[str, str]
    ) -> None:
        service = str(bloc["id"])
        tk.Label(
            parent,
            text=t(bloc["aide"]),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 8))
        if bloc.get("menu"):
            self._monter_menu_voix(parent, champs)
            if bloc.get("info"):
                return
        if bloc.get("menu_langue"):
            self._monter_menu_langue(parent)
            if bloc.get("info"):
                return
        if bloc.get("menu_cerveau"):
            self._monter_menu_cerveau(parent)
            if bloc.get("info"):
                return
        if service == "recherche":
            self._monter_reco_tavily(parent)
        interieur = parent
        for cle in bloc["cles"]:
            tk.Label(
                interieur,
                text=t(f"reglages.champ.{cle}"),
                bg=FOND_VITRE,
                fg=ENCRE_SOURDE,
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill=tk.X)
            cle_exemple = f"reglages.champ.{cle}_exemple"
            exemple = t(cle_exemple)
            if exemple != cle_exemple:
                tk.Label(
                    interieur,
                    text=exemple,
                    bg=FOND_VITRE,
                    fg=ENCRE_SOURDE,
                    font=("Segoe UI", 8),
                    wraplength=440,
                    justify="left",
                    anchor="w",
                ).pack(fill=tk.X, pady=(0, 2))
            secret = cle in CLES_SECRETES
            champ = ChampSaisie(
                interieur,
                invite=t(f"reglages.invite.{cle}"),
                secret=secret,
                contraste=self.contraste,
            )
            champ.pack(fill=tk.X, pady=(2, 10), ipady=8)
            if not secret:
                valeur = champs.get(cle, "")
                if str(valeur).strip():
                    champ.poser_valeur(valeur)
            self.champs[cle] = champ
            if secret:
                suffixe = quatre_derniers(self._secrets.get(cle, ""))
                texte = (
                    t("reglages.posee", suffixe=suffixe)
                    if suffixe and reglage_present(self.chemin, cle)
                    else ""
                )
                ligne = tk.Label(
                    interieur,
                    text=texte,
                    bg=FOND_VITRE,
                    fg=ENCRE_SOURDE,
                    font=("Segoe UI", 8),
                    anchor="w",
                )
                ligne.pack(fill=tk.X, pady=(0, 6))
                self._suffixes[cle] = ligne

        if bloc.get("info"):
            return

        rang = tk.Frame(interieur, bg=FOND_VITRE)
        rang.pack(fill=tk.X, pady=(4, 0))
        bouton = tk.Button(
            rang,
            text=t("reglages.verifier"),
            command=lambda s=service: self.verifier(s),
            takefocus=1,
            bg=FOND,
            fg=ENCRE,
            activebackground="#142028",
            activeforeground=ENCRE,
        )
        bouton.pack(side=tk.LEFT)
        self.boutons_verifier[service] = bouton
        toile = tk.Canvas(
            rang,
            width=14,
            height=14,
            bg=FOND_VITRE,
            highlightthickness=0,
            bd=0,
        )
        toile.pack(side=tk.LEFT, padx=8)
        self._toiles[service] = toile
        self._dessiner_pastille(service, None)
        detail = tk.Label(
            rang,
            text="",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=280,
            justify="left",
        )
        detail.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.details[service] = detail

    def _monter_categorie(
        self, parent: tk.Misc, categorie: dict[str, Any]
    ) -> None:
        tk.Label(
            parent,
            text=t(categorie["titre"]),
            bg=FOND,
            fg=ENCRE,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, padx=8, pady=(16, 2))

    def _monter_marqueur(self, parent: tk.Misc, bloc: dict[str, Any]) -> None:
        rang = tk.Frame(parent, bg=FOND_VITRE)
        rang.pack(fill=tk.X, pady=(2, 0))
        toile = tk.Canvas(
            rang,
            width=12,
            height=12,
            bg=FOND_VITRE,
            highlightthickness=0,
            bd=0,
        )
        toile.pack(side=tk.LEFT, padx=(0, 6), pady=2)
        couleur = MARQUEUR_SORTIE if sortie_du_bloc(bloc) else MARQUEUR_LOCAL
        toile.create_oval(2, 2, 10, 10, fill=couleur, outline=couleur)
        tk.Label(
            rang,
            text=libelle_donnees(bloc),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=420,
            justify="left",
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _monter_menu_voix(self, parent: tk.Misc, champs: dict[str, str] | None = None) -> None:
        from src.onboarding.sondes import LANGUES_TTS_REPLI, VOIX_TTS_REPLI

        courante = voix_courante(self.chemin)
        voix = list(VOIX_TTS_REPLI)
        if courante and courante not in voix:
            voix.append(courante)
        if courante:
            selection = courante
        elif "Sofia" in voix:
            selection = "Sofia"
        elif voix:
            selection = voix[0]
        else:
            selection = ""
        self.var_voix = tk.StringVar(self.fenetre, value=selection)

        naturel = accent_naturel()
        options = options_accent(LANGUES_TTS_REPLI, naturel=naturel)
        codes = {libelle: code for libelle, code in options}
        libelles = [libelle for libelle, _code in options]
        courant_accent = accent_courant(self.chemin)
        self.var_accent = tk.StringVar(
            self.fenetre,
            value=libelle_pour_accent(courant_accent, options),
        )

        palette = couleurs_champ(self.contraste)
        if ttk is not None:
            try:
                style = ttk.Style(self.fenetre)
                try:
                    style.theme_use("clam")
                except tk.TclError:
                    pass
                style.configure(
                    "Voix.TCombobox",
                    fieldbackground=palette["fond"],
                    background=palette["fond"],
                    foreground=palette["encre"],
                    arrowcolor=palette["encre"],
                )
            except tk.TclError:
                pass

        rang = tk.Frame(parent, bg=FOND_VITRE)
        rang.pack(fill=tk.X, pady=(2, 4))
        col_voix = tk.Frame(rang, bg=FOND_VITRE)
        col_voix.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        tk.Label(
            col_voix,
            text=" ",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X)
        self.combo_voix = self._combo_voix(col_voix, self.var_voix, voix)

        col_accent = tk.Frame(rang, bg=FOND_VITRE)
        col_accent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        tk.Label(
            col_accent,
            text=t("reglages.accent_titre"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X)
        self.combo_accent = self._combo_voix(col_accent, self.var_accent, libelles)

        col_btn = tk.Frame(rang, bg=FOND_VITRE)
        col_btn.pack(side=tk.LEFT)
        tk.Label(
            col_btn,
            text=" ",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X)
        self.bouton_ecouter = tk.Button(
            col_btn,
            text=t("reglages.voix_ecouter"),
            command=self._ecouter_voix,
            takefocus=1,
            bg=FOND,
            fg=ENCRE,
            activebackground="#142028",
            activeforeground=ENCRE,
        )
        self.bouton_ecouter.pack(ipady=2)

        self.champs["MOUTH_VOICE_NAME"] = ChampMenu(self.var_voix)
        self._champ_accent = ChampMenu(self.var_accent, codes)
        self.champs["MOUTH_LANGUAGE"] = self._champ_accent

        tk.Label(
            parent,
            text=t("reglages.accent_compromis"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        self.ligne_voix_repli = tk.Label(
            parent,
            text=t("reglages.voix_repli"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=440,
            justify="left",
            anchor="w",
        )
        self.ligne_voix_repli.pack(fill=tk.X, pady=(0, 4))
        self.var_renvoi = tk.IntVar(
            self.fenetre,
            value=1 if renvoi_outil_depuis(champs) else 0,
        )
        self.case_renvoi = tk.Checkbutton(
            parent,
            text=t("reglages.renvoi_outil"),
            variable=self.var_renvoi,
            bg=FOND_VITRE,
            fg=ENCRE,
            activebackground=FOND_VITRE,
            activeforeground=ENCRE,
            selectcolor="#142028",
            font=("Segoe UI", 11),
            anchor="w",
            takefocus=1,
        )
        self.case_renvoi.pack(fill=tk.X, pady=(4, 0))
        self.champs["VOIX_RENVOI_OUTIL"] = ChampCase(self.var_renvoi)
        self._rafraichir_voix()

    def _monter_menu_langue(self, parent: tk.Misc) -> None:
        options = options_langue()
        codes = {libelle: code for libelle, code in options}
        libelles = [libelle for libelle, _code in options]
        self.var_langue = tk.StringVar(
            self.fenetre,
            value=libelle_pour_langue(self._langue, options),
        )
        self.combo_langue = self._combo_voix(parent, self.var_langue, libelles)
        self._champ_langue = ChampMenu(self.var_langue, codes)
        try:
            self.combo_langue.bind(
                "<<ComboboxSelected>>", lambda _e: self._appliquer_langue()
            )
        except tk.TclError:
            pass
        self.ligne_langue_delai = tk.Label(
            parent,
            text=t("reglages.langue_delai"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=440,
            justify="left",
            anchor="w",
        )
        self.ligne_langue_delai.pack(fill=tk.X, pady=(0, 2))
        self.ligne_langue_etat = tk.Label(
            parent,
            text="",
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=440,
            justify="left",
            anchor="w",
        )
        self.ligne_langue_etat.pack(fill=tk.X, pady=(0, 4))

    def _appliquer_langue(self) -> None:
        if self._champ_langue is None or self.ligne_langue_etat is None:
            return
        code = self._champ_langue.get()
        if code not in ("fr", "en") or code == self._langue:
            return
        self.ligne_langue_etat.configure(text=t("reglages.langue_en_cours"))

        def travail() -> str:
            return code

        def rendre(resultat: Any) -> None:
            if not self._vivante():
                return
            if not isinstance(resultat, Exception) and self._sur_langue is not None:
                self._sur_langue(str(resultat))
                self._langue = str(resultat)
            if self.ligne_langue_etat is not None:
                self.ligne_langue_etat.configure(text="")

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def _monter_menu_cerveau(self, parent: tk.Misc) -> None:
        """Mode du cerveau distant et modèle, la liste lue en direct au pont."""
        from native.presence import cerveau_distant as cd

        mode, modele, effort = cd.choix_courant(self.chemin)
        self._cerveau_effort = effort
        libelles = {code: t(f"reglages.cerveau_mode.{code}") for code, _l in cd.MODES}
        libelles_modes = list(libelles.values())
        self._codes_modes = {libelle: code for code, libelle in libelles.items()}
        self.var_cerveau_mode = tk.StringVar(
            self.fenetre, value=libelles.get(mode, libelles_modes[0])
        )
        tk.Label(parent, text=t("reglages.cerveau_mode"), bg=FOND_VITRE,
                 fg=ENCRE_SOURDE, font=("Segoe UI", 9), anchor="w").pack(fill=tk.X)
        self.combo_cerveau_mode = self._combo_voix(parent, self.var_cerveau_mode, libelles_modes)
        tk.Label(parent, text=t("reglages.cerveau_modele"), bg=FOND_VITRE,
                 fg=ENCRE_SOURDE, font=("Segoe UI", 9), anchor="w").pack(fill=tk.X, pady=(6, 0))
        self.var_cerveau_modele = tk.StringVar(self.fenetre, value=modele)
        self._codes_modeles: dict[str, str] = {modele: modele} if modele else {}
        self.combo_cerveau_modele = self._combo_voix(
            parent, self.var_cerveau_modele, [modele] if modele else []
        )
        self.ligne_cerveau_etat = tk.Label(
            parent, text="", bg=FOND_VITRE, fg=ENCRE_SOURDE, font=("Segoe UI", 8),
            wraplength=440, justify="left", anchor="w",
        )
        self.ligne_cerveau_etat.pack(fill=tk.X, pady=(2, 2))
        tk.Button(
            parent, text=t("reglages.cerveau_appliquer"), command=self._appliquer_cerveau,
            font=("Segoe UI", 9), takefocus=1,
        ).pack(anchor="w", pady=(2, 4))
        try:
            self.combo_cerveau_mode.bind(
                "<<ComboboxSelected>>", lambda _e: self._rafraichir_modeles_cerveau()
            )
        except tk.TclError:
            pass
        self._rafraichir_modeles_cerveau(garder=modele)

    def _mode_cerveau(self) -> str:
        return self._codes_modes.get(self.var_cerveau_mode.get(), "api")

    def _rafraichir_modeles_cerveau(self, garder: str | None = None) -> None:
        from native.presence import cerveau_distant as cd

        mode = self._mode_cerveau()
        valeurs = self._valeurs_effectives()
        if mode == "api":
            self.combo_cerveau_modele.configure(values=[], state="disabled")
            self.var_cerveau_modele.set("")
            self.ligne_cerveau_etat.configure(text=t("reglages.cerveau_api"))
            return
        self.ligne_cerveau_etat.configure(text=t("reglages.cerveau_liste"))

        def travail() -> Any:
            return cd.lister_modeles(mode, valeurs)

        def rendre(resultat: Any) -> None:
            if not self._vivante() or isinstance(resultat, Exception):
                return
            self._codes_modeles = {m.get("label") or m["id"]: m["id"] for m in resultat}
            libelles = list(self._codes_modeles)
            self.combo_cerveau_modele.configure(values=libelles, state="readonly")
            voulu = garder or cd.MODELE_PAR_DEFAUT.get(mode, "")
            choisi = next(
                (lib for lib, ident in self._codes_modeles.items() if ident == voulu),
                libelles[0] if libelles else "",
            )
            self.var_cerveau_modele.set(choisi)
            self.ligne_cerveau_etat.configure(text="")

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def _appliquer_cerveau(self) -> None:
        """Enregistre le choix puis relance le host-agent, qui le lit au démarrage."""
        from native.presence import cerveau_distant as cd

        mode = self._mode_cerveau()
        libelle = self.var_cerveau_modele.get()
        modele = self._codes_modeles.get(libelle, libelle)
        effort = getattr(self, "_cerveau_effort", cd.EFFORT_PAR_DEFAUT)
        self.ligne_cerveau_etat.configure(text=t("reglages.cerveau_en_cours"))

        def travail() -> Any:
            cd.enregistrer_choix(self.chemin, mode, modele, effort)
            return cd.relancer_host_agent()

        def rendre(resultat: Any) -> None:
            if not self._vivante():
                return
            ok = resultat is True
            self.ligne_cerveau_etat.configure(
                text=t("reglages.cerveau_applique" if ok else "reglages.cerveau_echec")
            )

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def _monter_reco_tavily(self, parent: tk.Misc) -> None:
        tk.Label(
            parent,
            text=t("reglages.recherche_tavily"),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        adresse = url_tavily()
        self.lien_tavily = tk.Button(
            parent,
            text=adresse,
            command=self._ouvrir_tavily,
            takefocus=1,
            bg=FOND_VITRE,
            fg="#7ec8dc",
            activebackground=FOND_VITRE,
            activeforeground=ENCRE,
            relief=tk.FLAT,
            font=("Segoe UI", 9, "underline"),
            cursor="hand2",
            anchor="w",
        )
        self.lien_tavily.pack(fill=tk.X, pady=(0, 4))

    def _ouvrir_tavily(self) -> None:
        adresse = url_tavily()
        if not adresse:
            return
        action = self._ouvrir_lien or webbrowser.open
        action(adresse)

    def _combo_voix(self, parent: tk.Misc, variable: Any, valeurs: list[str]) -> Any:
        if ttk is not None:
            combo = ttk.Combobox(
                parent,
                textvariable=variable,
                values=valeurs,
                state="readonly",
                takefocus=1,
                font=("Segoe UI", 11),
            )
            try:
                combo.configure(style="Voix.TCombobox")
            except tk.TclError:
                pass
        else:  # pragma: no cover
            combo = tk.OptionMenu(parent, variable, *valeurs)
        combo.pack(fill=tk.X, ipady=4)
        return combo

    def _basculer_voix(self) -> None:
        corps = self.corps_voix
        if corps is None:
            return
        try:
            visible = bool(corps.winfo_ismapped())
        except tk.TclError:
            return
        if visible:
            corps.pack_forget()
        else:
            corps.pack(fill=tk.X)

    def _rafraichir_voix(self) -> None:
        def travail() -> Any:
            fn = self._lister_voix
            if fn is None:
                from src.onboarding.sondes import lister_voix_tts

                fn = lister_voix_tts
            resultat = fn()
            if inspect.isawaitable(resultat):
                resultat = asyncio.run(resultat)
            return resultat

        def rendre(resultat: Any) -> None:
            if not self._vivante():
                return
            if isinstance(resultat, Exception):
                from src.onboarding.sondes import LANGUES_TTS_REPLI, VOIX_TTS_REPLI, VoixTts

                resultat = VoixTts(VOIX_TTS_REPLI, False, LANGUES_TTS_REPLI)
            self._appliquer_voix(resultat)

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def _appliquer_voix(self, resultat: Any) -> None:
        from src.onboarding.sondes import LANGUES_TTS_REPLI, VOIX_TTS_REPLI, VoixTts

        if not isinstance(resultat, VoixTts):
            resultat = VoixTts(VOIX_TTS_REPLI, False, LANGUES_TTS_REPLI)
        voix = list(resultat.voix) or list(VOIX_TTS_REPLI)
        courante = ""
        if self.var_voix is not None:
            courante = (self.var_voix.get() or "").strip()
        if courante and courante not in voix:
            voix.append(courante)
        if self.combo_voix is not None:
            try:
                self.combo_voix.configure(values=voix)
            except tk.TclError:
                pass
        langues = list(resultat.langues or ())
        if not langues and not resultat.depuis_serveur:
            langues = list(LANGUES_TTS_REPLI)
        naturel = accent_naturel()
        options = options_accent(langues, naturel=naturel)
        libelles = [libelle for libelle, _code in options]
        codes = {libelle: code for libelle, code in options}
        if self._champ_accent is not None:
            actuel = self._champ_accent.get()
            self._champ_accent.poser_codes(codes)
        else:
            actuel = accent_courant(self.chemin)
        if self.combo_accent is not None:
            try:
                self.combo_accent.configure(values=libelles)
            except tk.TclError:
                pass
        if self.var_accent is not None:
            self.var_accent.set(libelle_pour_accent(actuel, options))
        if self.ligne_voix_repli is not None:
            self.ligne_voix_repli.configure(
                text="" if resultat.depuis_serveur else t("reglages.voix_repli")
            )

    def _ecouter_voix(self) -> None:
        voix = ""
        if "MOUTH_VOICE_NAME" in self.champs:
            voix = self.champs["MOUTH_VOICE_NAME"].get()
        langue = accent_naturel()
        if "MOUTH_LANGUAGE" in self.champs:
            langue = self.champs["MOUTH_LANGUAGE"].get() or langue
        texte = t("reglages.voix_extrait")

        def travail() -> Any:
            fn = self._jouer_extrait
            if fn is not None:
                return fn(voix, langue, texte)
            from src.onboarding.sondes import synthetiser_extrait_tts

            wav = asyncio.run(synthetiser_extrait_tts(voix, langue, texte))
            if wav:
                _jouer_wav(wav)
            return wav

        def rendre(resultat: Any) -> None:
            if not self._vivante():
                return
            if isinstance(resultat, Exception) or not resultat:
                self.ligne_statut.configure(text=t("reglages.voix_ecouter_echec"))

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def _monter_detecter(self, parent: tk.Misc) -> None:
        cadre = tk.Frame(
            parent,
            bg=FOND_VITRE,
            highlightthickness=1,
            highlightbackground=BORD,
        )
        cadre.pack(fill=tk.X, padx=8, pady=8)
        interieur = tk.Frame(cadre, bg=FOND_VITRE)
        interieur.pack(fill=tk.X, padx=12, pady=8)
        self.bouton_detecter = tk.Button(
            interieur,
            text=t("reglages.detecter_abonnements"),
            command=self.detecter_abonnements,
            takefocus=1,
            bg=FOND,
            fg=ENCRE,
            activebackground="#142028",
            activeforeground=ENCRE,
        )
        self.bouton_detecter.pack(side=tk.LEFT)

    def _dessiner_pastille(
        self, service: str, ok: bool | None, etat: str = ""
    ) -> None:
        toile = self._toiles[service]
        toile.delete("all")
        couleur = PASTILLE_NEUTRE
        if ok is True:
            couleur = PASTILLE_OK
        elif ok is False:
            couleur = PASTILLE_MUET if etat == ETAT_MUET else PASTILLE_KO
        toile.create_oval(2, 2, 12, 12, fill=couleur, outline=couleur)

    def _fn_sonde(self, service: str) -> Callable[..., Any]:
        return self.sondes.get(service) or _SONDES_DEFAUT[service]

    def _valeurs_effectives(self) -> dict[str, str]:
        valeurs: dict[str, str] = {}
        for cle, champ in self.champs.items():
            brut = champ.get()
            if cle in CLES_SECRETES:
                valeurs[cle] = secret_effectif(brut, self._secrets.get(cle, ""))
            else:
                valeurs[cle] = brut
        return valeurs

    def _planifier(self, fn: Callable[[], None]) -> None:
        """Le fil de travail ne touche jamais Tk : il dépose, le tic rend."""
        self._file.put(fn)

    def _pomper_file(self) -> None:
        try:
            while True:
                fn = self._file.get_nowait()
                fn()
        except queue.Empty:
            pass
        except tk.TclError:
            return
        if self._vivante():
            try:
                self._apres = self.fenetre.after(40, self._pomper_file)
            except tk.TclError:
                return

    def _appartient(self, widget: object | None) -> bool:
        if widget is None:
            return False
        if widget is self.fenetre:
            return True
        try:
            nom = str(widget)
            racine = str(self.fenetre)
        except tk.TclError:
            return False
        return nom == racine or nom.startswith(racine + ".")

    def _echap(self, event: object | None = None) -> str | None:
        if not self._vivante():
            return None
        widget = getattr(event, "widget", None) if event is not None else None
        if widget is None:
            try:
                widget = self.fenetre.focus_get()
            except tk.TclError:
                widget = None
        if self._appartient(widget):
            self.fermer()
            return "break"
        return None

    def _vivante(self) -> bool:
        try:
            return bool(self.fenetre.winfo_exists())
        except tk.TclError:
            return False

    async def _coro_un(self, service: str, vals: dict[str, str]) -> Sonde:
        fn = self._fn_sonde(service)
        client = self.client
        if service in ("outil_codex", "outil_claude"):
            nom = "codex" if service == "outil_codex" else "claude"
            resultat = fn(nom)
            if inspect.isawaitable(resultat):
                resultat = await resultat
            return self._sonde_du_bloc(service, resultat)
        if service == "brain_distant":
            return await fn(
                vals.get("BRAIN_API_ENDPOINT", ""),
                vals.get("BRAIN_API_KEY", ""),
                vals.get("BRAIN_MODEL", ""),
                client,
            )
        if service == "codex":
            return await fn(
                vals.get("CODEX_BRIDGE_URL", ""),
                vals.get("CODEX_BRIDGE_TOKEN", ""),
                client,
            )
        if service == "claude":
            return await fn(
                vals.get("CLI_BRIDGE_URL", ""),
                vals.get("CLI_BRIDGE_TOKEN", ""),
                client,
            )
        if service == "jev":
            return await fn(
                vals.get("TYPESAFE_API_KEY", ""),
                client,
                modele=vals.get("TYPESAFE_MODEL", "") or None,
            )
        raise ValueError(service)

    def _sonde_du_bloc(self, service: str, resultat: Any) -> Sonde:
        if not isinstance(resultat, Sonde):
            return Sonde(service, False, t("reglages.echec_sonde"), None)
        if resultat.service == service:
            return resultat
        return Sonde(
            service,
            resultat.ok,
            resultat.detail,
            resultat.latence_ms,
            getattr(resultat, "etat", "") or "",
        )

    async def _coro_tout(self, vals: dict[str, str]) -> list[Sonde]:
        http = await self._fn_sonde("tout")(vals, self.client)
        extra: list[Sonde] = []
        for service, nom in (("outil_codex", "codex"), ("outil_claude", "claude")):
            resultat = self._fn_sonde(service)(nom)
            if inspect.isawaitable(resultat):
                resultat = await resultat
            extra.append(self._sonde_du_bloc(service, resultat))
        return extra + list(http)

    async def _coro_abonnements(self) -> list[Sonde]:
        extra: list[Sonde] = []
        for service, nom in (("outil_codex", "codex"), ("outil_claude", "claude")):
            resultat = self._fn_sonde(service)(nom)
            if inspect.isawaitable(resultat):
                resultat = await resultat
            extra.append(self._sonde_du_bloc(service, resultat))
        return extra

    def verifier(self, service: str) -> None:
        if service in self._en_cours:
            return
        self._en_cours.add(service)
        bouton = self.boutons_verifier[service]
        bouton.configure(state="disabled", text=t("reglages.je_verifie"))
        vals = self._valeurs_effectives()

        def travail() -> Any:
            return asyncio.run(self._coro_un(service, vals))

        def rendre(resultat: Any) -> None:
            self._en_cours.discard(service)
            if not self._vivante():
                return
            bouton.configure(state="normal", text=t("reglages.verifier"))
            if isinstance(resultat, Exception):
                logger.info("reglages sonde %s: exception", service)
                self._appliquer_sonde(
                    Sonde(service, False, t("reglages.echec_sonde"), None)
                )
                return
            logger.info(
                "reglages sonde %s: ok=%s etat=%s",
                service,
                getattr(resultat, "ok", None),
                getattr(resultat, "etat", None),
            )
            self._appliquer_sonde(resultat)

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def detecter_abonnements(self) -> None:
        if "abonnements" in self._en_cours or "tout" in self._en_cours:
            return
        self._en_cours.add("abonnements")
        self.bouton_detecter.configure(
            state="disabled", text=t("reglages.je_verifie")
        )
        for cle in ("outil_codex", "outil_claude"):
            if cle in self.boutons_verifier:
                self.boutons_verifier[cle].configure(state="disabled")

        def travail() -> Any:
            return asyncio.run(self._coro_abonnements())

        def rendre(resultat: Any) -> None:
            self._en_cours.discard("abonnements")
            if not self._vivante():
                return
            self.bouton_detecter.configure(
                state="normal", text=t("reglages.detecter_abonnements")
            )
            for cle in ("outil_codex", "outil_claude"):
                if cle in self.boutons_verifier:
                    self.boutons_verifier[cle].configure(
                        state="normal", text=t("reglages.verifier")
                    )
            if isinstance(resultat, Exception):
                logger.info("reglages detecter abonnements: exception")
                return
            for sonde in resultat:
                self._appliquer_sonde(sonde)

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def tout_verifier(self) -> None:
        if "tout" in self._en_cours or "abonnements" in self._en_cours:
            return
        self._en_cours.add("tout")
        self.bouton_tout.configure(state="disabled", text=t("reglages.je_verifie"))
        self.bouton_detecter.configure(state="disabled")
        for bouton in self.boutons_verifier.values():
            bouton.configure(state="disabled")
        vals = self._valeurs_effectives()

        def travail() -> Any:
            return asyncio.run(self._coro_tout(vals))

        def rendre(resultat: Any) -> None:
            self._en_cours.discard("tout")
            if not self._vivante():
                return
            self.bouton_tout.configure(
                state="normal", text=t("reglages.tout_verifier")
            )
            self.bouton_detecter.configure(
                state="normal", text=t("reglages.detecter_abonnements")
            )
            for bouton in self.boutons_verifier.values():
                bouton.configure(state="normal", text=t("reglages.verifier"))
            if isinstance(resultat, Exception):
                logger.info("reglages sonde tout: exception")
                return
            for sonde in resultat:
                self._appliquer_sonde(sonde)

        lancer_hors_fil(travail, rendre, planifier=self._planifier)

    def _appliquer_sonde(self, sonde: Sonde) -> None:
        if sonde.service not in self.details:
            return
        etat = str(getattr(sonde, "etat", "") or "")
        self.pastilles[sonde.service] = {
            "ok": sonde.ok,
            "detail": sonde.detail,
            "etat": etat,
        }
        self.details[sonde.service].configure(text=sonde.detail)
        self._dessiner_pastille(sonde.service, sonde.ok, etat)
        if sonde.ok is False:
            self.ligne_statut.configure(text=t("reglages.echec_manuel"))

    def _saisie_retouchee(self) -> dict[str, str]:
        """Ce que l'utilisateur a changé, et rien d'autre.

        Écrire aussi les champs intacts poserait `BRAIN_MODEL=` sur une
        installation neuve : une clé vide dans `.env.local` écrase la valeur
        que le conteneur ou la carte figée avait posée. Une clé secrète passe
        toujours par `valeurs_a_poser`, qui sait la comparer à l'existante.
        """
        saisie: dict[str, str] = {}
        for cle, champ in self.champs.items():
            brut = champ.get()
            if cle in CLES_SECRETES:
                saisie[cle] = brut
            elif brut != self._charges.get(cle, ""):
                saisie[cle] = brut
        return saisie

    def enregistrer(self) -> None:
        saisie = self._saisie_retouchee()
        enregistrer_saisie(self.chemin, saisie, self._secrets)
        _, self._secrets = precharger(self.chemin)
        for cle, ligne in self._suffixes.items():
            suffixe = quatre_derniers(self._secrets.get(cle, ""))
            ligne.configure(
                text=t("reglages.posee", suffixe=suffixe) if suffixe else ""
            )
        for cle in CLES_SECRETES:
            if cle in self.champs:
                champ = self.champs[cle]
                champ.delete(0, tk.END)
                if hasattr(champ, "afficher_invite"):
                    champ.afficher_invite()
        self._charges = {cle: champ.get() for cle, champ in self.champs.items()}
        self.ligne_statut.configure(text=t("reglages.enregistre"))

    def _lancer_feedback(self) -> None:
        self._ouvrir_retour()

    def _relacher_variables(self) -> None:
        """Détache les StringVar sur le fil Tk tant que l'interpréteur vit.

        Sans ça, ``Variable.__del__`` part du fil ``reglages-sonde`` après
        destruction : Tcl panique (Windows 0x80000003) au lieu de lever
        une TclError rattrapable.
        """
        self.combo_voix = None
        self.combo_accent = None
        self.combo_langue = None
        self.champs.clear()
        self._champ_accent = None
        self._champ_langue = None
        self.case_renvoi = None
        for nom in ("var_voix", "var_accent", "var_langue", "var_renvoi"):
            setattr(self, nom, None)

    def fermer(self, _event: object | None = None) -> None:
        # Le tic de la file est porté par la fenêtre : sans annulation, il se
        # déclenche après la destruction et Tcl remonte
        # « invalid command name …_pomper_file » à chaque fermeture.
        if self._apres is not None:
            try:
                self.fenetre.after_cancel(self._apres)
            except tk.TclError:
                pass
            self._apres = None
        self._relacher_variables()
        try:
            self.fenetre.destroy()
        except tk.TclError:
            pass
