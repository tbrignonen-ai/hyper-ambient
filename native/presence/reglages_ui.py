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
from pathlib import Path
from typing import Any, Callable

try:
    import tkinter as tk
except ModuleNotFoundError:  # pragma: no cover — image docker sans Tk
    tk = None  # type: ignore[assignment]

from src.i18n import t
from src.onboarding.reglages import lire_reglages, poser_reglages, reglage_present
from src.onboarding.sondes import (
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
        "blocs": ("modele_local", "cles"),
    },
    {
        "id": "outils",
        "titre": "reglages.categorie.outils",
        "blocs": ("outil_codex", "outil_claude", "codex", "claude"),
    },
    {
        "id": "distants",
        "titre": "reglages.categorie.distants",
        "blocs": ("brain_distant", "jev", "recherche"),
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
MARQUEUR_LOCAL = "#4a8a72"
MARQUEUR_SORTIE = "#b89654"


def sortie_du_bloc(bloc: dict[str, Any]) -> bool:
    return bool(bloc.get("sortie"))


def libelle_donnees(bloc: dict[str, Any]) -> str:
    return t(str(bloc["donnees"]))


def chemin_env_local(racine: Path | None = None) -> Path:
    base = Path(racine) if racine is not None else Path(__file__).resolve().parents[2]
    return base / ".env.local"


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


def ouvrir_fenetre_reglages(
    parent: Any, chemin: Path | None = None, **kwargs: Any
) -> "FenetreReglages":
    return FenetreReglages(parent, chemin or chemin_env_local(), **kwargs)


class FenetreReglages:
    """Toplevel non-modale : la fenêtre principale reste utilisable."""

    def __init__(
        self,
        parent: Any,
        chemin: Path,
        *,
        sondes: dict[str, Callable[..., Any]] | None = None,
        client: Any = None,
    ) -> None:
        if tk is None:
            raise RuntimeError("tkinter indisponible")
        self.chemin = Path(chemin)
        self.client = client
        self.sondes = dict(sondes or {})
        self.champs: dict[str, tk.Entry] = {}
        self.boutons_verifier: dict[str, tk.Button] = {}
        self.details: dict[str, tk.Label] = {}
        self.pastilles: dict[str, dict[str, Any]] = {}
        self.marqueurs_confidentialite: dict[str, bool] = {}
        self._toiles: dict[str, tk.Canvas] = {}
        self._suffixes: dict[str, tk.Label] = {}
        self._en_cours: set[str] = set()
        self._file: queue.Queue = queue.Queue()
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
        tk.Label(
            pied,
            text=t("reglages.verifier_aide") + " " + t("reglages.echec_manuel"),
            bg=FOND,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 8),
            wraplength=480,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
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
                self.pastilles[service] = {"ok": None, "detail": ""}
        self.fenetre.after(40, self._pomper_file)
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
        tk.Label(
            interieur,
            text=t(bloc["aide"]),
            bg=FOND_VITRE,
            fg=ENCRE_SOURDE,
            font=("Segoe UI", 9),
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 8))
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
            champ = tk.Entry(
                interieur,
                show="*" if secret else "",
                takefocus=1,
                bg="#142028",
                fg=ENCRE,
                insertbackground=ENCRE,
                relief=tk.FLAT,
            )
            champ.pack(fill=tk.X, pady=(0, 4))
            if not secret and cle in champs:
                champ.insert(0, champs[cle])
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

    def _dessiner_pastille(self, service: str, ok: bool | None) -> None:
        toile = self._toiles[service]
        toile.delete("all")
        couleur = PASTILLE_NEUTRE
        if ok is True:
            couleur = PASTILLE_OK
        elif ok is False:
            couleur = PASTILLE_KO
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
                self.fenetre.after(40, self._pomper_file)
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
        return Sonde(service, resultat.ok, resultat.detail, resultat.latence_ms)

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
                "reglages sonde %s: ok=%s", service, getattr(resultat, "ok", None)
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
        self.pastilles[sonde.service] = {"ok": sonde.ok, "detail": sonde.detail}
        self.details[sonde.service].configure(text=sonde.detail)
        self._dessiner_pastille(sonde.service, sonde.ok)
        if sonde.ok is False:
            self.ligne_statut.configure(text=t("reglages.echec_manuel"))

    def enregistrer(self) -> None:
        saisie = {cle: champ.get() for cle, champ in self.champs.items()}
        enregistrer_saisie(self.chemin, saisie, self._secrets)
        _, self._secrets = precharger(self.chemin)
        for cle, ligne in self._suffixes.items():
            suffixe = quatre_derniers(self._secrets.get(cle, ""))
            ligne.configure(
                text=t("reglages.posee", suffixe=suffixe) if suffixe else ""
            )
        for cle in CLES_SECRETES:
            if cle in self.champs:
                self.champs[cle].delete(0, tk.END)
        self.ligne_statut.configure(text=t("reglages.enregistre"))

    def fermer(self, _event: object | None = None) -> None:
        try:
            self.fenetre.destroy()
        except tk.TclError:
            pass
