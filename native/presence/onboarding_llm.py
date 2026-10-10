"""Accueil guidé par le modèle (V1) : logique pure, sondes injectées.

Aucune dépendance graphique ni HTTP tierce : tout passe par ``urllib`` et par
un ``requeteur`` injectable. Règle d'or : jamais « connecté » sans preuve.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

try:
    from onboarding import lire_json_presence
except ImportError:  # pragma: no cover - natif/presence non présent sur sys.path
    from native.presence.onboarding import lire_json_presence

ETAPES_LLM = ("declarer", "guider", "armer", "essayer")

VERT = "vert"
GRIS = "gris"
ROUGE = "rouge"

CAUSE_PONT_FERME = "pont fermé"
CAUSE_TOKEN_REFUSE = "token refusé"
CAUSE_TOKEN_ABSENT = "token absent"
CAUSE_PAS_DE_PONG = "pas de PONG"
CAUSE_NON_VERIFIE = "non vérifié"

HARNAIS = ("codex", "claude", "distant")
NOMS_HARNAIS = {"codex": "Codex", "claude": "Claude Code", "distant": "Modèle distant"}
# Route attendue dans les événements de la file Presence, par harnais.
ROUTE_ATTENDUE = {"codex": "harnais", "claude": "harnais", "distant": "escalade"}

# Ponts locaux : port, nom du jeton dans .env.local, agent éventuel.
PONTS = {
    "codex": ("http://127.0.0.1:8765/ask", "CODEX_BRIDGE_TOKEN", {}),
    "claude": ("http://127.0.0.1:8766/ask", "CLI_BRIDGE_TOKEN", {"agent": "claude"}),
}

TEXTES_GUIDE = {
    "codex": "Codex — les fichiers : lire et modifier le code du projet.",
    "claude": "Claude — la relecture : relire un changement avant de le garder.",
    "distant": "Distant — le raisonnement : les questions longues ou difficiles.",
}

CLE_PERSISTANCE = "onboarding_llm"


# --- Requête HTTP ----------------------------------------------------------------

@dataclass(frozen=True)
class Requete:
    methode: str
    url: str
    entetes: dict = field(default_factory=dict)
    corps: dict | None = None
    delai_s: float = 5.0


@dataclass(frozen=True)
class Reponse:
    statut: int | None
    corps: str
    latence_ms: float
    erreur: str | None = None


def _ms(debut: float) -> float:
    return (time.perf_counter() - debut) * 1000.0


def _raison(raison: object) -> str:
    if isinstance(raison, (socket.timeout, TimeoutError)):
        return "délai dépassé"
    if isinstance(raison, ConnectionRefusedError):
        return "connexion refusée"
    if isinstance(raison, socket.gaierror):
        return "adresse introuvable"
    return str(raison) or type(raison).__name__


def _lire(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:  # corps absent ou déjà consommé
        return ""


def requete_http(requete: Requete) -> Reponse:
    """Exécute une requête réelle. Ne lève jamais : l'échec devient une Reponse."""
    entetes = dict(requete.entetes)
    donnees = None
    if requete.corps is not None:
        donnees = json.dumps(requete.corps, ensure_ascii=False).encode("utf-8")
        entetes.setdefault("Content-Type", "application/json")
    debut = time.perf_counter()
    try:
        envoi = urllib.request.Request(
            requete.url, data=donnees, headers=entetes, method=requete.methode
        )
        with urllib.request.urlopen(envoi, timeout=requete.delai_s) as rep:
            corps = rep.read().decode("utf-8", errors="replace")
            return Reponse(statut=rep.status, corps=corps, latence_ms=_ms(debut))
    except urllib.error.HTTPError as exc:  # avant URLError : c'en est une sous-classe
        return Reponse(statut=exc.code, corps=_lire(exc), latence_ms=_ms(debut))
    except urllib.error.URLError as exc:
        return Reponse(None, "", _ms(debut), _raison(exc.reason))
    except Exception as exc:  # adresse invalide, OSError, etc.
        return Reponse(None, "", _ms(debut), _raison(exc))


# --- Déclarer ----------------------------------------------------------------------

@dataclass(frozen=True)
class DeclarationDistant:
    nom: str
    url: str
    cle: str


@dataclass(frozen=True)
class ResultatVerification:
    verifie: bool
    statut: int | None
    latence_ms: float | None
    message: str


def url_sante(url: str) -> str:
    """Adresse de santé : la racine de l'API suivie de /models.

    Même convention que ``health()`` dans src/brain/openai_compat.py : on retire
    le suffixe /chat/completions puis on interroge /models.
    """
    base = (url or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")].rstrip("/")
    return f"{base}/models" if base else ""


def _sans_cle(texte: str, cle: str) -> str:
    # La clé ne doit jamais atteindre l'écran, même recopiée dans une erreur.
    return texte.replace(cle, "•••") if cle else texte


def verifier_distant(
    decl: DeclarationDistant, requeteur: Callable[[Requete], Reponse] = requete_http
) -> ResultatVerification:
    url = url_sante(decl.url)
    if not url:
        return ResultatVerification(False, None, None, "Adresse manquante — non vérifié")
    entetes = {"Authorization": f"Bearer {decl.cle}"} if decl.cle else {}
    rep = requeteur(Requete(methode="GET", url=url, entetes=entetes))
    if rep.statut is None:
        raison = _sans_cle(rep.erreur or "erreur", decl.cle)
        return ResultatVerification(False, None, rep.latence_ms, f"Injoignable ({raison}) — non vérifié")
    verifie = 200 <= rep.statut < 300
    suffixe = "vérifié" if verifie else "non vérifié"
    message = f"HTTP {rep.statut} en {round(rep.latence_ms)} ms — {suffixe}"
    return ResultatVerification(verifie, rep.statut, rep.latence_ms, message)


def enregistrer_declaration(decl: DeclarationDistant, chemin_env_local: Path) -> None:
    """Pose les secrets et l'adresse dans .env.local, jamais dans presence.json."""
    from src.onboarding.reglages import poser_reglages

    valeurs = {
        "BRAIN_MODEL": decl.nom.strip(),
        "BRAIN_API_ENDPOINT": decl.url.strip(),
        "BRAIN_API_KEY": decl.cle.strip(),
    }
    poser_reglages(Path(chemin_env_local), {k: v for k, v in valeurs.items() if v})


# --- État des harnais ---------------------------------------------------------------

@dataclass(frozen=True)
class EtatHarnais:
    couleur: str
    cause: str = ""
    pont: bool | None = None
    jeton: bool | None = None
    pong: bool | None = None

    def __post_init__(self) -> None:
        if self.couleur == VERT and not (self.pont is True and self.jeton is True and self.pong is True):
            raise ValueError("un harnais vert exige pont, jeton et PONG prouvés")


def etat_depuis_indicateurs(*, pont: bool | None, jeton: bool | None, pong: bool | None) -> EtatHarnais:
    if pont is True and jeton is True and pong is True:
        return EtatHarnais(VERT, "", pont, jeton, pong)
    if pont is False:
        return EtatHarnais(ROUGE, CAUSE_PONT_FERME, pont, jeton, pong)
    if jeton is False:
        return EtatHarnais(ROUGE, CAUSE_TOKEN_REFUSE, pont, jeton, pong)
    if pong is False:
        return EtatHarnais(ROUGE, CAUSE_PAS_DE_PONG, pont, jeton, pong)
    return EtatHarnais(GRIS, CAUSE_NON_VERIFIE, pont, jeton, pong)


def libelle_etat(etat: EtatHarnais) -> str:
    if etat.couleur == VERT:
        return "Connecté — PONG reçu"
    texte = etat.cause or CAUSE_NON_VERIFIE
    return texte[:1].upper() + texte[1:]


def _interpreter(rep: Reponse, pong_si_2xx: bool | None) -> EtatHarnais:
    if rep.statut is None:
        return etat_depuis_indicateurs(pont=False, jeton=None, pong=None)
    if rep.statut in (401, 403):
        return etat_depuis_indicateurs(pont=True, jeton=False, pong=None)
    if 200 <= rep.statut < 300:
        return etat_depuis_indicateurs(pont=True, jeton=True, pong=pong_si_2xx)
    return etat_depuis_indicateurs(pont=True, jeton=True, pong=False)


def sonder_harnais(
    cle: str,
    jetons: Mapping[str, str],
    requeteur: Callable[[Requete], Reponse] = requete_http,
) -> EtatHarnais:
    """Sonde un seul harnais. Vert seulement si pont, jeton et PONG sont prouvés."""
    if cle not in HARNAIS:
        raise ValueError(f"harnais inconnu : {cle}")
    if cle == "distant":
        url = url_sante(jetons.get("BRAIN_API_ENDPOINT") or "")
        if not url:
            return EtatHarnais(GRIS, CAUSE_NON_VERIFIE)
        jeton = (jetons.get("BRAIN_API_KEY") or "").strip()
        entetes = {"Authorization": f"Bearer {jeton}"} if jeton else {}
        rep = requeteur(Requete(methode="GET", url=url, entetes=entetes))
        # Pour le distant, la réponse de santé 2xx tient lieu de PONG.
        return _interpreter(rep, pong_si_2xx=True)

    url, nom_jeton, extra = PONTS[cle]
    jeton = (jetons.get(nom_jeton) or "").strip()
    if not jeton:
        return EtatHarnais(ROUGE, CAUSE_TOKEN_ABSENT, pont=None, jeton=False, pong=None)
    corps = {"question": "PONG", **extra}
    rep = requeteur(Requete(methode="POST", url=url, entetes={"Authorization": f"Bearer {jeton}"}, corps=corps))
    return _interpreter(rep, pong_si_2xx="PONG" in rep.corps.upper())


def etats_initiaux(etat: EtatOnboardingLLM) -> dict[str, EtatHarnais]:
    # Un armement persisté n'est jamais une preuve : tout repart de GRIS.
    return {cle: EtatHarnais(GRIS, CAUSE_NON_VERIFIE) for cle in HARNAIS}


# --- Étape Essayer : résultat d'un tour réel ------------------------------------

@dataclass(frozen=True)
class ResultatEssai:
    harnais: str
    reussi: bool
    texte_affiche: str
    a_dire: str | None
    eclair: str | None
    repli: bool


def repli_texte(cause: str) -> str:
    texte = (cause or "").strip() or "pas de réponse"
    return f"{texte[:1].upper()}{texte[1:]}, je reste en local."


def _pont_ou_connexion(texte: str) -> bool:
    bas = texte.lower()
    return "pont" in bas or "connexion" in bas


def evaluer_tour(cle: str, evenements: Iterable[Mapping[str, Any]]) -> ResultatEssai:
    """Juge un tour push-to-talk réel à partir des événements de la file Presence."""
    route = ROUTE_ATTENDUE.get(cle, "harnais")
    routes_vues: set[str] = set()
    reponse = ""
    premier_son = False
    alerte = ""
    for ev in evenements:
        type_ = ev.get("type")
        if type_ == "etat":
            routes_vues.add(str(ev.get("etat")))
        elif type_ == "rapport":
            reponse = str(ev.get("reply") or "").strip()
        elif type_ == "premier_son":
            premier_son = True
        elif type_ in ("statut", "erreur"):
            alerte += " " + str(ev.get("texte") or "")

    # Si le pipeline a déjà parlé, Presence ne redit pas la phrase (pas de doublon).
    if reponse and route in routes_vues:
        return ResultatEssai(cle, True, reponse, None if premier_son else reponse, route, False)
    if reponse:
        nom = NOMS_HARNAIS.get(cle, cle)
        texte = f"Pas de réponse de {nom}, je reste en local. Réponse locale : {reponse}"
        return ResultatEssai(cle, False, texte, None if premier_son else texte, None, True)
    texte = repli_texte("Pont fermé" if _pont_ou_connexion(alerte) else "Pas de réponse")
    return ResultatEssai(cle, False, texte, texte, None, True)


def repli_non_arme(cle: str, etat_harnais: EtatHarnais) -> ResultatEssai:
    """Harnais non vert : aucun tour n'est tenté, on dit seulement pourquoi."""
    texte = repli_texte(etat_harnais.cause or CAUSE_NON_VERIFIE)
    return ResultatEssai(cle, False, texte, texte, None, True)


# --- État persistant de l'onboarding LLM ----------------------------------------

@dataclass(frozen=True)
class EtatOnboardingLLM:
    etape: str = "declarer"
    distant_verifie: bool = False
    guide_coche: tuple[str, ...] = ()
    armes: dict[str, bool] = field(default_factory=dict)
    essais: dict[str, bool] = field(default_factory=dict)
    termine: bool = False


def passer_etape(etat: EtatOnboardingLLM, etape: str) -> EtatOnboardingLLM:
    index = ETAPES_LLM.index(etape)
    if index + 1 >= len(ETAPES_LLM):
        return replace(etat, etape="essayer", termine=True)
    return replace(etat, etape=ETAPES_LLM[index + 1])


@dataclass(frozen=True)
class ItemGuide:
    cle: str
    texte: str
    coche: bool = False


def proposer_checklist(
    proposer: Callable[[], Mapping[str, str]] | None = None,
) -> tuple[ItemGuide, ...]:
    """Textes de la checklist ; ceux du cerveau local remplacent les défauts s'il répond."""
    propositions: Mapping[str, str] = {}
    if proposer is not None:
        try:
            propositions = proposer() or {}
        except Exception:  # cerveau local absent : les textes par défaut suffisent
            propositions = {}
    if not isinstance(propositions, Mapping):
        propositions = {}
    items = []
    for cle in HARNAIS:
        texte = propositions.get(cle)
        if not (isinstance(texte, str) and texte.strip()):
            texte = TEXTES_GUIDE[cle]
        items.append(ItemGuide(cle=cle, texte=texte.strip(), coche=False))
    return tuple(items)


def cocher(etat: EtatOnboardingLLM, cle: str, valeur: bool) -> EtatOnboardingLLM:
    # Cocher la checklist ne prouve rien : armes reste intact.
    coches = set(etat.guide_coche)
    if valeur:
        coches.add(cle)
    else:
        coches.discard(cle)
    return replace(etat, guide_coche=tuple(c for c in HARNAIS if c in coches))


def armer_avec_etat(
    etat: EtatOnboardingLLM,
    cle: str,
    jetons: Mapping[str, str],
    requeteur: Callable[[Requete], Reponse] = requete_http,
) -> tuple[EtatOnboardingLLM, EtatHarnais]:
    harnais = sonder_harnais(cle, jetons, requeteur)
    armes = dict(etat.armes)
    armes[cle] = harnais.couleur == VERT
    return replace(etat, armes=armes), harnais


def armer(
    etat: EtatOnboardingLLM,
    cle: str,
    jetons: Mapping[str, str],
    requeteur: Callable[[Requete], Reponse] = requete_http,
) -> EtatOnboardingLLM:
    return armer_avec_etat(etat, cle, jetons, requeteur)[0]


# --- Persistance (clé séparée dans presence.json) -----------------------------------

def _liste_connue(brut: Any) -> tuple[str, ...]:
    if not isinstance(brut, list):
        return ()
    presents = {c for c in brut if isinstance(c, str)}
    return tuple(c for c in HARNAIS if c in presents)


def _booleens_connus(brut: Any) -> dict[str, bool]:
    if not isinstance(brut, dict):
        return {}
    return {k: v for k, v in brut.items() if k in HARNAIS and isinstance(v, bool)}


def charger_onboarding_llm(chemin: Path) -> EtatOnboardingLLM:
    brut = lire_json_presence(Path(chemin)).get(CLE_PERSISTANCE)
    if not isinstance(brut, dict):
        return EtatOnboardingLLM()
    etape = brut.get("etape")
    return EtatOnboardingLLM(
        etape=etape if etape in ETAPES_LLM else "declarer",
        distant_verifie=brut.get("distant_verifie") is True,
        guide_coche=_liste_connue(brut.get("guide_coche")),
        armes=_booleens_connus(brut.get("armes")),
        essais=_booleens_connus(brut.get("essais")),
        termine=brut.get("termine") is True,
    )


def enregistrer_onboarding_llm(etat: EtatOnboardingLLM, chemin: Path) -> Path:
    cible = Path(chemin)
    cible.parent.mkdir(parents=True, exist_ok=True)
    # Lecture puis écriture de tout le fichier : les autres clés restent en place.
    contenu = lire_json_presence(cible)
    contenu[CLE_PERSISTANCE] = {
        "etape": etat.etape,
        "distant_verifie": etat.distant_verifie,
        "guide_coche": list(etat.guide_coche),
        "armes": dict(etat.armes),
        "essais": dict(etat.essais),
        "termine": etat.termine,
    }
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(cible)
    return cible
