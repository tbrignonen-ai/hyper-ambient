"""Accueil guidé par le modèle : fenêtre Tk fine.

Toute la logique (sondes, verdicts, persistance) vit dans ``onboarding_llm``.
Ce module ne fait que dessiner, lancer les sondes hors du fil Tk et poser
leurs résultats dans une file relue par ``after``. Tk n'est pas sûr entre fils.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    import onboarding
    import onboarding_llm as llm
except ImportError:  # pragma: no cover - natif/presence non présent sur sys.path
    from native.presence import onboarding
    from native.presence import onboarding_llm as llm

# Couleurs recopiées de app.py (import circulaire impossible) ; un futur thème les centralisera.
FOND = "#0c141c"
FOND_VITRE = "#102028"
BORD_VITRE = "#2a4a5c"
ENCRE = "#d8e4ec"
ENCRE_SOURDE = "#8aa0b0"
ACTIVE_BOUTON = "#142028"
VERT = "#3ccf7a"
GRIS = "#6b7d88"
ROUGE = "#e5484d"
COULEUR_POINT = {llm.VERT: VERT, llm.ROUGE: ROUGE}

POLICE = ("Segoe UI", 11)
POLICE_GRAS = ("Segoe UI", 11, "bold")
POLICE_TITRE = ("Segoe UI", 15, "bold")
POLICE_PETITE = ("Segoe UI", 10)

DUREE_TOUR_MS = 45_000
INTERVALLE_FILE_MS = 100
TAILLE_BADGE = 40

# Textes français de l'interface.
TEXTE_TITRE = "Accueil guidé (modèles)"
TEXTE_ETAPE = "Étape {index} sur {total} : {nom}"
NOMS_ETAPES = {"declarer": "Déclarer", "guider": "Guider", "armer": "Armer", "essayer": "Essayer"}
TEXTE_DECLARER = (
    "Le nom, l'adresse et la clé vont dans .env.local, jamais dans presence.json."
)
LIBELLE_NOM = "Nom du modèle"
LIBELLE_ADRESSE = "Adresse de l'API"
LIBELLE_CLE = "Clé d'accès"
BOUTON_VERIFIER = "Vérifier"
BOUTON_PASSER = "Passer"
BOUTON_CONTINUER = "Continuer"
BOUTON_TERMINER = "Terminer"
BOUTON_ACTIVER = "Activer"
BOUTON_MAINTENIR = "Maintenir pour parler"
NON_VERIFIE = "Non vérifié"
TEXTE_VERIFICATION_EN_COURS = "Vérification en cours…"
TEXTE_VERIFICATION_IMPOSSIBLE = "Vérification impossible ({nom}) — non vérifié"
TEXTE_GUIDER_NOTE = "Proposé par le cerveau local. Rien ne s'arme tout seul : vous cochez."
TEXTE_ARMER_NOTE = (
    "Chaque bouton lance une vraie sonde. Vert seulement si le pont, "
    "le jeton et le PONG sont prouvés."
)
TEXTE_SONDE_EN_COURS = "Sonde en cours…"
TEXTE_SONDE_IMPOSSIBLE = "Sonde impossible"
TEXTE_INDICATEURS = "pont : {pont} · token : {jeton} · PONG : {pong}"
TEXTE_ESSAYER_NOTE = "Seuls les harnais verts sont essayés. Maintenez le bouton, parlez, relâchez."
TEXTE_ESSAI_PRET = "Maintenez le bouton, puis parlez."
TEXTE_ESSAI_EN_COURS = "Tour en cours : parlez, puis relâchez."
TEXTE_BADGE_REPOS = "repos"
TEXTE_SANS_VOIX = "Voix indisponible ici : réponse affichée seulement."
CAUSE_CANAL_FERME = "canal vocal pas prêt"
TEXTE_SAUVEGARDE_IMPOSSIBLE = "Sauvegarde impossible : ce choix ne sera pas gardé."
PHRASES_ESSAI = {
    "codex": "Dites : « Codex, réponds PONG »",
    "claude": "Dites : « Claude, réponds PONG »",
    "distant": "Dites : « Explique-moi en détail pourquoi le ciel est bleu »",
}


def _oui_non(valeur: bool | None) -> str:
    if valeur is None:
        return "?"
    return "oui" if valeur else "non"


def _indicateurs(etat: llm.EtatHarnais) -> str:
    return TEXTE_INDICATEURS.format(
        pont=_oui_non(etat.pont), jeton=_oui_non(etat.jeton), pong=_oui_non(etat.pong)
    )


def _executer_en_fil(fonction: Callable[[], None]) -> None:
    """Hors fil Tk par défaut : une sonde réseau ne fige jamais la fenêtre."""
    threading.Thread(target=fonction, name="onboarding-llm", daemon=True).start()


def _titre(parent: tk.Misc, texte: str) -> tk.Label:
    etiquette = tk.Label(parent, text=texte, bg=FOND, fg=ENCRE, font=POLICE_TITRE, anchor="w")
    etiquette.pack(fill=tk.X, pady=(0, 6))
    return etiquette


def _note(parent: tk.Misc, texte: str = "") -> tk.Label:
    etiquette = tk.Label(
        parent, text=texte, bg=FOND, fg=ENCRE_SOURDE, font=POLICE_PETITE,
        anchor="w", justify="left", wraplength=440,
    )
    etiquette.pack(fill=tk.X, pady=(0, 6))
    return etiquette


def _etiquette(parent: tk.Misc, texte: str = "", police: tuple = POLICE) -> tk.Label:
    return tk.Label(
        parent, text=texte, bg=FOND, fg=ENCRE, font=police,
        anchor="w", justify="left", wraplength=440,
    )


def _bouton(parent: tk.Misc, texte: str, commande: Callable[[], None] | None = None) -> tk.Button:
    return tk.Button(
        parent,
        text=texte,
        command=commande,
        bg=FOND_VITRE,
        fg=ENCRE,
        activebackground=ACTIVE_BOUTON,
        activeforeground=ENCRE,
        relief=tk.FLAT,
        font=POLICE,
        takefocus=1,
        highlightthickness=2,
        highlightbackground=FOND,
        highlightcolor=ENCRE_SOURDE,
    )


def _entree(parent: tk.Misc, **options: Any) -> tk.Entry:
    return tk.Entry(
        parent,
        bg=FOND_VITRE,
        fg=ENCRE,
        insertbackground=ENCRE,
        relief=tk.FLAT,
        font=POLICE,
        takefocus=1,
        highlightthickness=2,
        highlightbackground=BORD_VITRE,
        highlightcolor=ENCRE_SOURDE,
        **options,
    )


class FenetreOnboardingLLM(tk.Toplevel):
    """Accueil guidé : quatre écrans, et une seule vérité, celle des sondes réelles."""

    def __init__(
        self,
        *,
        racine: tk.Misc,
        chemin_configuration: Path | None = None,
        chemin_env_local: Path,
        requeteur: Callable[[llm.Requete], llm.Reponse] = llm.requete_http,
        lire_jetons: Callable[[], Mapping[str, str]] | None = None,
        enfoncer: Callable[..., None] | None = None,
        relacher: Callable[..., None] | None = None,
        dire: Callable[[str], None] | None = None,
        canal_pret: Callable[[], bool] | None = None,
        proposer: Callable[[], Mapping[str, str]] | None = None,
        executer: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        super().__init__(racine)
        self.title(TEXTE_TITRE)
        self.configure(bg=FOND)
        self.geometry("520x680")
        self.minsize(440, 560)
        self.protocol("WM_DELETE_WINDOW", self._fermer)
        self.bind("<Escape>", lambda _event: self._fermer())
        self.bind("<Destroy>", self._sur_destruction, add="+")

        self.chemin_configuration = (
            Path(chemin_configuration)
            if chemin_configuration is not None
            else onboarding.chemin_configuration()
        )
        self.chemin_env_local = Path(chemin_env_local)
        self.requeteur = requeteur
        self._lire_jetons = lire_jetons or self._lire_jetons_par_defaut
        self._fn_enfoncer = enfoncer
        self._fn_relacher = relacher
        self._dire = dire
        self._canal_pret = canal_pret
        self._proposer = proposer
        self._executer = executer or _executer_en_fil

        self.etat: llm.EtatOnboardingLLM = llm.charger_onboarding_llm(self.chemin_configuration)
        # Un armement persisté n'est jamais une preuve : tout repart de GRIS.
        self.etats_harnais: dict[str, llm.EtatHarnais] = llm.etats_initiaux(self.etat)
        self._file: queue.Queue = queue.Queue()
        self._sonde_en_cours: str | None = None
        self._verification_en_cours = False
        self._essai_cle: str | None = None
        self._evenements: list[dict[str, Any]] = []
        self._vu_resultat = False
        self._bouton_tenu: str | None = None
        self._timer_essai: Any = None
        self._boucle_id: Any = None
        self._propositions_demandees = False
        self._dits: set[str] = set()
        self._textes_essai: dict[str, str] = {}
        self._etape_affichee: str | None = None

        self.label_etape = tk.Label(self, text="", bg=FOND, fg=ENCRE_SOURDE, font=POLICE_PETITE, anchor="w")
        self.label_etape.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(12, 0))
        self.label_statut = tk.Label(
            self, text="", bg=FOND, fg=ROUGE, font=POLICE_PETITE, anchor="w", wraplength=440
        )
        self.label_statut.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(0, 8))
        self._corps = tk.Frame(self, bg=FOND)
        self._corps.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        self.label_verification: tk.Label | None = None
        self.entree_nom: tk.Entry | None = None
        self.entree_url: tk.Entry | None = None
        self.entree_cle: tk.Entry | None = None
        self._variables_guide: dict[str, tk.BooleanVar] = {}
        self._cases_guide: dict[str, tk.Checkbutton] = {}
        self.points: dict[str, tk.Canvas] = {}
        self.labels_harnais: dict[str, tk.Label] = {}
        self.labels_indicateurs: dict[str, tk.Label] = {}
        self.boutons_activer: dict[str, tk.Button] = {}
        self.badges: dict[str, tk.Canvas] = {}
        self.labels_badge: dict[str, tk.Label] = {}
        self.labels_phrase: dict[str, tk.Label] = {}
        self.boutons_essai: dict[str, tk.Button] = {}
        self.label_essai: dict[str, tk.Label] = {}
        self._zones_essai: dict[str, tk.Frame] = {}
        self._premier: dict[str, tk.Misc] = {}

        self._ecrans: dict[str, tk.Frame] = {
            "declarer": self._construire_declarer(),
            "guider": self._construire_guider(),
            "armer": self._construire_armer(),
            "essayer": self._construire_essayer(),
        }
        self._rafraichir_essayer()
        self._boucle_id = self.after(INTERVALLE_FILE_MS, self._boucle)
        self.afficher_etape(self.etat.etape)

    # --- Persistance et chargement -----------------------------------------

    def _lire_jetons_par_defaut(self) -> dict[str, str]:
        from src.onboarding.reglages import lire_reglages

        return lire_reglages(self.chemin_env_local)

    def _sauver(self) -> None:
        try:
            llm.enregistrer_onboarding_llm(self.etat, self.chemin_configuration)
        except OSError:
            self.label_statut.configure(text=TEXTE_SAUVEGARDE_IMPOSSIBLE)
            return
        self.label_statut.configure(text="")

    # --- Construction des écrans -------------------------------------------

    def _cadre(self) -> tk.Frame:
        return tk.Frame(self._corps, bg=FOND)

    def _pied(self, cadre: tk.Frame, boutons: list[tuple[str, Callable[[], None]]]) -> tk.Frame:
        pied = tk.Frame(cadre, bg=FOND)
        pied.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))
        for texte, commande in reversed(boutons):
            _bouton(pied, texte, commande).pack(side=tk.RIGHT, padx=(8, 0))
        return pied

    def _construire_declarer(self) -> tk.Frame:
        cadre = self._cadre()
        self._pied(cadre, [
            (BOUTON_PASSER, lambda: self._avancer("declarer")),
            (BOUTON_CONTINUER, lambda: self._avancer("declarer")),
        ])
        _titre(cadre, "Déclarer le modèle distant")
        _note(cadre, TEXTE_DECLARER)
        for libelle, attribut, options in (
            (LIBELLE_NOM, "entree_nom", {}),
            (LIBELLE_ADRESSE, "entree_url", {}),
            (LIBELLE_CLE, "entree_cle", {"show": "•"}),
        ):
            _etiquette(cadre, libelle, POLICE_GRAS).pack(fill=tk.X, pady=(6, 2))
            entree = _entree(cadre, **options)
            entree.pack(fill=tk.X, ipady=4)
            setattr(self, attribut, entree)
        self._premier["declarer"] = self.entree_nom

        ligne = tk.Frame(cadre, bg=FOND)
        ligne.pack(fill=tk.X, pady=(12, 4))
        self._bouton_verifier = _bouton(ligne, BOUTON_VERIFIER, self.verifier)
        self._bouton_verifier.pack(side=tk.LEFT)
        self.label_verification = _etiquette(cadre, NON_VERIFIE)
        self.label_verification.pack(fill=tk.X, pady=(4, 0))
        return cadre

    def _construire_guider(self) -> tk.Frame:
        cadre = self._cadre()
        self._pied(cadre, [
            (BOUTON_PASSER, lambda: self._avancer("guider")),
            (BOUTON_CONTINUER, lambda: self._avancer("guider")),
        ])
        _titre(cadre, "Guider")
        _note(cadre, TEXTE_GUIDER_NOTE)
        textes = {item.cle: item.texte for item in llm.proposer_checklist(None)}
        for cle in llm.HARNAIS:
            variable = tk.BooleanVar(master=self, value=cle in self.etat.guide_coche)
            self._variables_guide[cle] = variable
            case = tk.Checkbutton(
                cadre,
                text=textes[cle],
                variable=variable,
                command=lambda c=cle: self._cocher(c),
                bg=FOND,
                fg=ENCRE,
                activebackground=FOND,
                activeforeground=ENCRE,
                selectcolor=FOND_VITRE,
                anchor="w",
                justify="left",
                wraplength=440,
                font=POLICE,
                takefocus=1,
            )
            case.pack(fill=tk.X, pady=6)
            self._cases_guide[cle] = case
        self._premier["guider"] = self._cases_guide[llm.HARNAIS[0]]
        return cadre

    def _construire_armer(self) -> tk.Frame:
        cadre = self._cadre()
        self._pied(cadre, [
            (BOUTON_PASSER, lambda: self._avancer("armer")),
            (BOUTON_CONTINUER, lambda: self._avancer("armer")),
        ])
        _titre(cadre, "Armer")
        _note(cadre, TEXTE_ARMER_NOTE)
        for cle in llm.HARNAIS:
            rangee = tk.Frame(cadre, bg=FOND)
            rangee.pack(fill=tk.X, pady=6)
            haut = tk.Frame(rangee, bg=FOND)
            haut.pack(fill=tk.X)
            point = tk.Canvas(haut, width=14, height=14, bg=FOND, highlightthickness=0, bd=0)
            point.pack(side=tk.LEFT, padx=(0, 8))
            self.points[cle] = point
            _etiquette(haut, llm.NOMS_HARNAIS[cle], POLICE_GRAS).pack(side=tk.LEFT)
            bouton = _bouton(haut, BOUTON_ACTIVER, lambda c=cle: self.activer(c))
            bouton.pack(side=tk.RIGHT)
            self.boutons_activer[cle] = bouton
            self.labels_harnais[cle] = _etiquette(rangee)
            self.labels_harnais[cle].pack(fill=tk.X)
            self.labels_indicateurs[cle] = _note(rangee)
        self._premier["armer"] = self.boutons_activer[llm.HARNAIS[0]]
        return cadre

    def _construire_essayer(self) -> tk.Frame:
        cadre = self._cadre()
        self._pied(cadre, [(BOUTON_TERMINER, self._terminer_etape)])
        _titre(cadre, "Essayer")
        _note(cadre, TEXTE_ESSAYER_NOTE)
        for cle in llm.HARNAIS:
            rangee = tk.Frame(cadre, bg=FOND)
            rangee.pack(fill=tk.X, pady=6)
            haut = tk.Frame(rangee, bg=FOND)
            haut.pack(fill=tk.X)
            _etiquette(haut, llm.NOMS_HARNAIS[cle], POLICE_GRAS).pack(side=tk.LEFT)
            badge = tk.Canvas(haut, width=TAILLE_BADGE, height=TAILLE_BADGE, bg=FOND, highlightthickness=0, bd=0)
            badge.pack(side=tk.RIGHT)
            self.badges[cle] = badge
            self.labels_badge[cle] = tk.Label(
                haut, text=TEXTE_BADGE_REPOS, bg=FOND, fg=ENCRE_SOURDE, font=POLICE_PETITE
            )
            self.labels_badge[cle].pack(side=tk.RIGHT, padx=6)
            self._dessiner_badge(cle, "repos")

            self.label_essai[cle] = _etiquette(rangee, "")
            self.label_essai[cle].pack(fill=tk.X, pady=(4, 0))
            zone = tk.Frame(rangee, bg=FOND)
            self._zones_essai[cle] = zone
            self.labels_phrase[cle] = _etiquette(zone, PHRASES_ESSAI[cle])
            self.labels_phrase[cle].pack(fill=tk.X)
            bouton = _bouton(zone, BOUTON_MAINTENIR)
            bouton.pack(anchor="w", pady=4)
            bouton.bind("<ButtonPress-1>", lambda _event, c=cle: self._appuyer_essai(c))
            bouton.bind("<ButtonRelease-1>", lambda _event, c=cle: self._relacher_essai(c))
            self.boutons_essai[cle] = bouton
        self._premier["essayer"] = self.boutons_essai[llm.HARNAIS[0]]
        return cadre

    # --- Affichage ----------------------------------------------------------

    def afficher_etape(self, nom: str) -> None:
        if nom not in llm.ETAPES_LLM:
            raise ValueError(f"étape inconnue : {nom}")
        for cadre in self._ecrans.values():
            cadre.pack_forget()
        self._ecrans[nom].pack(fill=tk.BOTH, expand=True)
        self._etape_affichee = nom
        self.label_etape.configure(
            text=TEXTE_ETAPE.format(index=llm.ETAPES_LLM.index(nom) + 1, total=len(llm.ETAPES_LLM), nom=NOMS_ETAPES[nom])
        )
        if self.etat.etape != nom:
            self.etat = replace(self.etat, etape=nom)
            self._sauver()
        if nom == "guider":
            self._rafraichir_guider()
        elif nom == "armer":
            self._rafraichir_armer()
        elif nom == "essayer":
            self._rafraichir_essayer()
        premier = self._premier.get(nom)
        if premier is not None:
            try:
                premier.focus_set()
            except tk.TclError:
                pass

    def _avancer(self, nom: str) -> None:
        self.etat = llm.passer_etape(self.etat, nom)
        self._sauver()
        self.afficher_etape(self.etat.etape)

    def _rafraichir_guider(self) -> None:
        for cle, variable in self._variables_guide.items():
            variable.set(cle in self.etat.guide_coche)
        if self._proposer is not None and not self._propositions_demandees:
            self._propositions_demandees = True
            proposer = self._proposer
            self._lancer(lambda: llm.proposer_checklist(proposer), "propositions")

    def _cocher(self, cle: str) -> None:
        self.etat = llm.cocher(self.etat, cle, bool(self._variables_guide[cle].get()))
        self._sauver()

    def _rafraichir_armer(self) -> None:
        for cle in llm.HARNAIS:
            etat = self.etats_harnais[cle]
            self.points[cle].delete("all")
            self.points[cle].create_oval(2, 2, 12, 12, fill=COULEUR_POINT.get(etat.couleur, GRIS), outline="")
            self.labels_harnais[cle].configure(text=llm.libelle_etat(etat))
            self.labels_indicateurs[cle].configure(text=_indicateurs(etat))
            self.boutons_activer[cle].configure(
                state=tk.DISABLED if self._sonde_en_cours is not None else tk.NORMAL
            )

    def _rafraichir_essayer(self) -> None:
        for cle in llm.HARNAIS:
            zone = self._zones_essai[cle]
            zone.pack_forget()
            if self.etats_harnais[cle].couleur == llm.VERT:
                zone.pack(fill=tk.X, before=self.label_essai[cle])
                self.label_essai[cle].configure(text=self._textes_essai.get(cle, TEXTE_ESSAI_PRET))
            else:
                self._afficher_repli(cle)

    def _afficher_repli(self, cle: str) -> None:
        repli = llm.repli_non_arme(cle, self.etats_harnais[cle])
        if cle in self._dits:
            self.label_essai[cle].configure(text=self._textes_essai.get(cle, repli.texte_affiche))
        elif self._etape_affichee == "essayer":
            # Une seule fois par fenêtre : pas de répétition vocale à chaque rafraîchissement.
            self._dits.add(cle)
            self._montrer_essai(cle, repli.texte_affiche, repli.a_dire)
        else:
            self.label_essai[cle].configure(text=repli.texte_affiche)

    def _dessiner_badge(self, cle: str, etat: str) -> None:
        allume = onboarding.eclair_allume(etat)
        fill, contour = onboarding.couleurs_eclair(allume, etat=etat)
        toile = self.badges[cle]
        toile.delete("all")
        centre = TAILLE_BADGE / 2
        toile.create_polygon(
            *onboarding.sommets_eclair(centre, centre, TAILLE_BADGE),
            fill=fill,
            outline=contour,
        )
        self.labels_badge[cle].configure(
            text=onboarding.libelle_eclair(etat) if allume else TEXTE_BADGE_REPOS
        )

    # --- Déclarer -----------------------------------------------------------

    def verifier(self) -> None:
        if self._verification_en_cours or self.entree_nom is None:
            return
        decl = llm.DeclarationDistant(
            nom=self.entree_nom.get(), url=self.entree_url.get(), cle=self.entree_cle.get()
        )
        self._verification_en_cours = True
        self.label_verification.configure(text=TEXTE_VERIFICATION_EN_COURS)

        def travail() -> llm.ResultatVerification:
            llm.enregistrer_declaration(decl, self.chemin_env_local)
            return llm.verifier_distant(decl, self.requeteur)

        self._lancer(travail, "verification")

    def _appliquer_verification(self, valeur: Any) -> None:
        self._verification_en_cours = False
        if isinstance(valeur, BaseException):
            message = TEXTE_VERIFICATION_IMPOSSIBLE.format(nom=type(valeur).__name__)
            verifie = False
        else:
            message = valeur.message
            verifie = valeur.verifie
        self.label_verification.configure(text=message)
        self.etat = replace(self.etat, distant_verifie=verifie)
        self._sauver()

    # --- Armer --------------------------------------------------------------

    def activer(self, cle: str) -> None:
        """Lance une sonde réelle pour un seul harnais, à la demande de l'utilisateur."""
        if cle not in llm.HARNAIS:
            raise ValueError(f"harnais inconnu : {cle}")
        if self._sonde_en_cours is not None:
            return
        self._sonde_en_cours = cle
        self.labels_harnais[cle].configure(text=TEXTE_SONDE_EN_COURS)
        self._rafraichir_armer()
        etat = self.etat

        def travail() -> llm.EtatHarnais:
            jetons = self._lire_jetons()
            _, harnais = llm.armer_avec_etat(etat, cle, jetons, self.requeteur)
            return harnais

        self._lancer(travail, "harnais", cle)

    def _appliquer_harnais(self, cle: str, valeur: Any) -> None:
        self._sonde_en_cours = None
        if isinstance(valeur, BaseException):
            harnais = llm.EtatHarnais(llm.GRIS, TEXTE_SONDE_IMPOSSIBLE.lower())
        else:
            harnais = valeur
        self.etats_harnais[cle] = harnais
        # Seul le drapeau d'armement change : une coche faite pendant la sonde reste.
        self.etat = replace(self.etat, armes={**self.etat.armes, cle: harnais.couleur == llm.VERT})
        self._sauver()
        self._rafraichir_armer()
        self._rafraichir_essayer()

    # --- Essayer ------------------------------------------------------------

    def _appuyer_essai(self, cle: str) -> None:
        if self._canal_pret is not None and self._essai_cle is None and not self._canal_pret():
            # Sans canal vocal, aucun tour ne partira : on le dit tout de suite.
            texte = llm.repli_texte(CAUSE_CANAL_FERME)
            self._montrer_essai(cle, texte, texte)
            return
        if self._debuter_essai(cle):
            self._bouton_tenu = cle
            if self._fn_enfoncer is not None:
                self._fn_enfoncer()

    def _relacher_essai(self, cle: str) -> None:
        if self._bouton_tenu != cle:
            return
        self._bouton_tenu = None
        if self._fn_relacher is not None:
            self._fn_relacher()

    def _debuter_essai(self, cle: str) -> bool:
        if self._essai_cle is not None or cle not in llm.HARNAIS:
            return False
        if self.etats_harnais[cle].couleur != llm.VERT:
            return False
        self._essai_cle = cle
        self._evenements = []
        self._vu_resultat = False
        self._timer_essai = self.after(DUREE_TOUR_MS, self._expirer_essai)
        self.label_essai[cle].configure(text=TEXTE_ESSAI_EN_COURS)
        return True

    def recevoir(self, message: Mapping[str, Any]) -> None:
        """Reçoit chaque message de la file Presence ; ne retient que le tour en cours."""
        cle = self._essai_cle
        if cle is None:
            return
        type_ = message.get("type")
        self._evenements.append(dict(message))
        if type_ == "etat":
            etat = str(message.get("etat") or "repos")
            self._dessiner_badge(cle, etat)
            if etat == "repos" and self._vu_resultat:
                self._terminer_essai()
        elif type_ in ("rapport", "erreur"):
            # Un « statut » (Envoi…, Écoute…) arrive aussi en début de tour : il
            # ne clôt rien. Sans rapport, c'est le délai qui tranche.
            self._vu_resultat = True

    def _expirer_essai(self) -> None:
        self._timer_essai = None
        self._terminer_essai()

    def _terminer_essai(self) -> None:
        cle = self._essai_cle
        if cle is None:
            return
        self._annuler_essai()
        self._essai_cle = None
        resultat = llm.evaluer_tour(cle, self._evenements)
        self._montrer_essai(cle, resultat.texte_affiche, resultat.a_dire)
        self._dessiner_badge(cle, resultat.eclair or "repos")
        self.etat = replace(self.etat, essais={**self.etat.essais, cle: resultat.reussi})
        self._sauver()

    def _montrer_essai(self, cle: str, texte: str, a_dire: str | None) -> None:
        suffixe = ""
        if a_dire:
            if self._dire is None:
                suffixe = TEXTE_SANS_VOIX
            else:
                try:
                    self._dire(a_dire)
                except Exception:  # la voix ne doit jamais effacer le texte
                    suffixe = TEXTE_SANS_VOIX
        affiche = f"{texte}\n{suffixe}" if suffixe else texte
        self._textes_essai[cle] = affiche
        self.label_essai[cle].configure(text=affiche)

    def _terminer_etape(self) -> None:
        self.etat = llm.passer_etape(self.etat, "essayer")
        self._sauver()
        self._fermer()

    # --- File des sondes (hors fil Tk) -------------------------------------

    def _lancer(self, travail: Callable[[], Any], nature: str, cle: str | None = None) -> None:
        def tache() -> None:
            try:
                valeur: Any = travail()
            except Exception as exc:  # une sonde ne doit jamais tuer la fenêtre
                valeur = exc
            self._file.put((nature, cle, valeur))

        self._executer(tache)

    def traiter_resultats(self) -> None:
        """Vide la file une fois et applique les résultats sur le fil Tk."""
        while True:
            try:
                nature, cle, valeur = self._file.get_nowait()
            except queue.Empty:
                return
            if nature == "verification":
                self._appliquer_verification(valeur)
            elif nature == "harnais" and cle is not None:
                self._appliquer_harnais(cle, valeur)
            elif nature == "propositions" and not isinstance(valeur, BaseException):
                for item in valeur:
                    case = self._cases_guide.get(item.cle)
                    if case is not None:
                        case.configure(text=item.texte)

    def _boucle(self) -> None:
        self._boucle_id = None
        self.traiter_resultats()
        try:
            self._boucle_id = self.after(INTERVALLE_FILE_MS, self._boucle)
        except tk.TclError:
            self._boucle_id = None

    # --- Fermeture ----------------------------------------------------------

    def _annuler_essai(self) -> None:
        if self._timer_essai is not None:
            try:
                self.after_cancel(self._timer_essai)
            except tk.TclError:
                pass
            self._timer_essai = None

    def _sur_destruction(self, event: tk.Event) -> None:
        if str(event.widget) != str(self):
            return
        if self._boucle_id is not None:
            try:
                self.after_cancel(self._boucle_id)
            except tk.TclError:
                pass
            self._boucle_id = None
        self._annuler_essai()
        if self._bouton_tenu is not None and self._fn_relacher is not None:
            self._bouton_tenu = None
            self._fn_relacher()

    def _fermer(self) -> None:
        try:
            self.destroy()
        except tk.TclError:
            pass
