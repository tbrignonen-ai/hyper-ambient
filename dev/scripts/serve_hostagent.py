#!/usr/bin/env python3
"""Point d'entrée conteneur : transport host-agent + chaîne EARS / BRAIN / MOUTH.

    python3 dev/scripts/serve_hostagent.py
    python native/hostagent/talk.py
"""
from __future__ import annotations

import contextlib

import asyncio
import ipaddress
import math
import os
import re
import sys
import time
from datetime import datetime, date, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.hostagent.audio import (
    FRAME_SAMPLES,
    SAMPLE_RATE,
    AudioFrame,
    RechantillonneurContinu,
)
from src.hostagent.transport import create_transport_app
from src.hostagent.warmup import prechauffer
from src.presence.etat import Presence
from src.mouth.secours import LIMITE_ENONCE_S, est_silence, phrase_de_secours
from src.ears.silence import jeter_tour_bruit
from src.mouth.reveil import phrase_de_reveil, reveil_court_suffit
from src.mouth.output_gain import appliquer_gain_doux
from src.brain.contexte import (
    MemoireConversation,
    TamponAmbiant,
    phrase_garde,
    question_d_outil,
)
from src.brain.tool_loop import run_tool_loop
from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry
from src.brain.tools_calculator import register_calculator
from src.brain.tools_codex import register_ask_codex
from src.brain.tools_cli import register_ask_claude
from src.brain.tools_muse import register_ask_muse
from src.brain.tools_web import register_web_search
from src.brain.mandat import (
    DELAI_RAPPEL_S,
    NOMS_HARNAIS,
    OUTIL_PAR_HARNAIS,
    RegistreMandats,
    phrase_arrivee,
    phrase_rappel,
)
from src.ears.jev_reflexe import FenetreConversation, nom_du_produit_prononce
from src.gate.permission import Gate

# Douze messages, soit six echanges. Assez pour conserver le fil d'une courte
# conversation vocale, sans laisser le contexte du modele local croitre sans
# borne d'un tour a l'autre.
MEMOIRE_MESSAGES = 12

HOST = "0.0.0.0"
PORT = 8001
SECRET_DEVELOPPEMENT = "partage-installation"
VOIX_PIPER = "/workspace/models/piper/fr_FR-tom-medium.onnx"

# Ce qu'on dit AVANT d'aller chercher dehors. Codex met 19 a 36 secondes a
# repondre : sans annonce, c'est une demi-minute de silence, qui s'entend comme
# une panne et non comme une deliberation. Ces phrases sont ecrites, pas
# generees — les faire produire par le modele couterait exactement la latence
# qu'elles existent pour couvrir. Meme raison que les amorces du routeur.
#
# Elles ne reprennent pas « un instant » : l'amorce du routeur vient de le dire
# une seconde plus tot, et l'entendre deux fois de suite s'entend comme un
# bégaiement. Celle de Codex annonce l'ordre de grandeur plutot que de le taire
# — vingt secondes prevenues se vivent autrement que vingt secondes subies.
ANNONCES_OUTILS = {
    "ask_codex": "Je demande à Codex, ça prend une vingtaine de secondes.",
    # Mesuré : 23,8 s pour le pont seul, 40,9 s dans un tour complet. Annoncer
    # « une vingtaine » serait déjà un petit mensonge à la trente-huitième.
    "ask_muse": "Je demande son avis à Muse, ça prend une trentaine de secondes.",
    # Mesuré : ~10 s à chaud (9,9 s puis 9,5 s), mais plus de 40 s au tout
    # premier appel — démarrage à froid de la CLI, le même phénomène que Codex
    # relevé le 11 (35,8 s à froid contre 19 s à chaud). Le délai du pont, lui,
    # couvre le cas froid ; l'annonce ne promet aucune durée, parce que la
    # norme est courte et qu'annoncer « une minute » ferait paraître long ce
    # qui ne l'est pas.
    "ask_claude": "Je demande son analyse à Claude.",
    "web_search": "Je cherche ça sur le web.",
    "calculer": "Je calcule ça.",
}
ANNONCE_OUTIL_PAR_DEFAUT = "Je consulte un outil."

# Le delai de l'outil depasse celui du pont (40 s) a dessein : c'est la phrase
# prononcable du pont (« delai depasse ») qui doit sortir, pas une coupure cote
# client qui, elle, n'a rien a dire.
DELAI_OUTIL_S = 65.0

# Claude raisonne a travers plusieurs fichiers : c'est sa raison d'etre ici, et
# c'est ce qui le rend lent. Son pont attend 90 s ; le client doit attendre plus
# LONGTEMPS que lui, sinon c'est le client qui coupe et la phrase prononcable du
# pont (« delai depasse ») ne sort jamais. Mesure : 41,8 s de coupure seche sur
# une question d'architecture, avec l'ancien couple 40/65.
DELAI_OUTIL_CLAUDE_S = 110.0


def annonce_outil(nom: str) -> str:
    """La phrase prononcée avant l'appel de `nom`.

    Un nom d'outil ne se prononce pas : « ask_codex » lu à voix haute est un
    bruit, pas une information. La table rend une phrase pour les outils connus,
    et une formule neutre pour les autres — jamais l'identifiant brut.
    FR par défaut ; ``HA_LANG=en`` bascule les phrases.
    """
    from src.i18n import t

    phrase = t(f"tools.{nom}")
    if phrase == f"tools.{nom}":
        return t("tools.default")
    return phrase


# La carte de dégustation fige voix / oreille / cerveau. Ce chargeur propage
# les jetons d'outils ; il ne doit pas déplacer MOUTH_*, EARS_*, BRAIN_*, MODEL,
# ni le reste du dotenv (HF_TOKEN, ALIAS, …).
_PREFIXES_MODELE = ("MOUTH_", "EARS_", "BRAIN_")
_CLES_MODELE = frozenset({"MODEL"})
_CLES_OUTILS = frozenset(
    {
        "CODEX_BRIDGE_TOKEN",
        "CODEX_BRIDGE_URL",
        "CLI_BRIDGE_TOKEN",
        "CLI_BRIDGE_URL",
        "MUSE_BRIDGE_URL",
        "SEARXNG_URL",
        "TAVILY_API_KEY",
        "BRAVE_API_KEY",
        "EXA_API_KEY",
        "JINA_API_KEY",
        "SERPER_API_KEY",
        "TYPESAFE_API_KEY",
    }
)
# EN 0.1 : UI / prompt / nombres. Pas un secret, pas une clé modèle.
# Presence pose HA_LANG sur Windows ; le host-agent (conteneur) doit le
# relire depuis .env.local, sinon le cerveau et Magpie restent en FR.
_CLES_LANGUE = frozenset({"HA_LANG", "HYPER_AMBIENT_LANG"})
# Carte figée 19 sept : cerveau / oreille / voix. Aucun secret. Écrase
# l'ancienne carte (router / Qwen3 / Supertonic) au boot, sauf CARTE_FIGEE=0
# ou une variable *_FORCE déjà utile.
_CLES_CARTE = frozenset(
    {
        "BRAIN_SERVICE",
        "BRAIN_MODEL",
        "BRAIN_MODEL_LOCAL",
        "MODEL",
        "EARS_BACKEND",
        "EARS_MODEL",
        "EARS_LANGUAGE",
        "EARS_DEVICE",
        "EARS_COMPUTE_TYPE",
        "EARS_HOTWORDS",
        "MOUTH_BACKEND",
        "MOUTH_VOICE_NAME",
        "MOUTH_LANGUAGE",
        "MOUTH_DEVICE",
        "MOUTH_OUTPUT_GAIN_DB",
    }
)
_CARTE_FIGEE = _ROOT / "dev" / "scripts" / "carte_figee.env"


_LANGUES_ASSISTANTE = frozenset({"fr", "en"})


def _avertir_repli_configuration(cle: str, valeur: object, defaut: object) -> None:
    """Journalise un repli de configuration sans empêcher le boot."""
    print(
        f"ATTENTION : {cle} invalide ({valeur!r}) — repli sur {defaut!r}",
        file=sys.stderr,
        flush=True,
    )


def _code_langue(valeur: object, *, cle: str = "HA_LANG") -> str:
    """Normalise la langue ; toute valeur absente ou invalide revient au français."""
    code = str(valeur or "").replace("_", "-").strip().lower()
    code = code.split("-", 1)[0]
    if not code:
        return "fr"
    if code not in _LANGUES_ASSISTANTE:
        _avertir_repli_configuration(cle, valeur, "fr")
        return "fr"
    return code


def synchroniser_langue_assistante(
    langue: object,
    *,
    environ: dict[str, str] | None = None,
    accent: object | None = None,
) -> dict[str, object]:
    """Aligne cerveau, oreille et bouche sans effacer un accent explicite.

    ``MOUTH_LANGUAGE_FORCE`` est le contrat de surcharge volontaire : absent,
    la bouche suit la langue de l'assistante ; présent (ou ``accent`` fourni),
    la bouche garde cette phonétique tandis que BRAIN et EARS changent. Cette
    opération ne charge aucun modèle : Faster-Whisper/Qwen lisent ``language``
    à chaque transcription, et Magpie l'envoie à chaque synthèse.
    """
    if environ is None:
        environ = os.environ
    code = _code_langue(langue)
    accent_explicite = accent if _valeur_utile(accent) else environ.get(
        "MOUTH_LANGUAGE_FORCE", ""
    )
    bouche = (
        _code_langue(accent_explicite, cle="MOUTH_LANGUAGE_FORCE")
        if _valeur_utile(accent_explicite)
        else code
    )
    environ["HA_LANG"] = code
    environ["HYPER_AMBIENT_LANG"] = code
    environ["EARS_LANGUAGE"] = code
    environ["MOUTH_LANGUAGE"] = bouche
    if _valeur_utile(accent):
        environ["MOUTH_LANGUAGE_FORCE"] = bouche
    return {"language": code, "ears": code, "mouth": bouche, "accent": bouche != code}


def _est_cle_modele(cle: str) -> bool:
    return cle in _CLES_MODELE or cle.startswith(_PREFIXES_MODELE)


def _valeur_utile(valeur: object) -> bool:
    if valeur is None:
        return False
    return bool(str(valeur).replace("\r", "").strip())


def _texte_configuration(cle: str, defaut: str) -> str:
    """Lit une chaîne d'environnement en traitant absence et blancs comme le défaut."""
    valeur = os.getenv(cle)
    if not _valeur_utile(valeur):
        return defaut
    return str(valeur).replace("\r", "").strip()


def _nombre_configuration(cle: str, defaut: float) -> float:
    """Lit un nombre d'environnement sans laisser une faute bloquer le démarrage."""
    valeur = os.getenv(cle)
    if not _valeur_utile(valeur):
        return defaut
    try:
        nombre = float(str(valeur).replace("\r", "").strip())
    except (TypeError, ValueError):
        _avertir_repli_configuration(cle, valeur, defaut)
        return defaut
    if not math.isfinite(nombre):
        _avertir_repli_configuration(cle, valeur, defaut)
        return defaut
    return nombre


def parser_env_local(chemin: Path) -> dict[str, str]:
    """Lit un dotenv Windows-safe : splitlines enlève LF/CRLF, on jette le `\\r` restant."""
    if not chemin.is_file():
        return {}
    paires: dict[str, str] = {}
    for ligne in chemin.read_bytes().splitlines():
        ligne = ligne.replace(b"\r", b"")
        if not ligne or ligne.lstrip().startswith(b"#"):
            continue
        if b"=" not in ligne:
            continue
        cle_b, val_b = ligne.split(b"=", 1)
        cle = cle_b.decode("utf-8", "replace").strip().lstrip("\ufeff")
        val = val_b.decode("utf-8", "replace").strip().strip('"').strip("'")
        if cle:
            paires[cle] = val
    return paires


def charger_env_local(
    chemin: Path | None = None,
    environ: dict[str, str] | None = None,
) -> list[str]:
    """Propage `.env.local` dans l'env du process.

    Cause racine du 19 sept : `serve_hostagent` ne lisait que `os.getenv`, et le
    boot du jour n'est pas passé par `relancer_routeur.sh`. `docker start` ne
    recharge pas `env_file`. Les jetons sont dans le fichier monté, absents du
    process. On les injecte ici, sans coller de `\\r`, sans toucher aux clés
    modèle, sans écraser une valeur déjà utile.
    """
    if environ is None:
        environ = os.environ
    if chemin is None:
        chemin = _ROOT / ".env.local"
    injectees: list[str] = []
    for cle, val in parser_env_local(Path(chemin)).items():
        if (cle not in _CLES_OUTILS and cle not in _CLES_LANGUE) or _est_cle_modele(cle):
            continue
        if _valeur_utile(environ.get(cle, "")):
            continue
        environ[cle] = val
        injectees.append(cle)
    return injectees


def _carte_desactivee(environ: dict[str, str]) -> bool:
    val = str(environ.get("CARTE_FIGEE", "1")).replace("\r", "").strip().lower()
    return val in {"0", "off", "false", "non"}


def charger_carte_figee(
    chemin: Path | None = None,
    environ: dict[str, str] | None = None,
) -> list[str]:
    """Propage la carte figée (modèles seulement) dans l'env du process.

    Distinct de ``charger_env_local`` : la whitelist C1 ne touche pas
    MOUTH_*/EARS_*/BRAIN_*/MODEL, donc un reboot retombait sur Pocket/Estelle.
    Ici la carte **écrase** l'ancienne, sans secret, sans jeton d'outil.
    """
    if environ is None:
        environ = os.environ
    if _carte_desactivee(environ):
        return []
    if chemin is None:
        chemin = _CARTE_FIGEE
    injectees: list[str] = []
    for cle, val in parser_env_local(Path(chemin)).items():
        if cle not in _CLES_CARTE or not _valeur_utile(val):
            continue
        force = environ.get(f"{cle}_FORCE", "")
        environ[cle] = (
            str(force).replace("\r", "").strip() if _valeur_utile(force) else val
        )
        injectees.append(cle)
    return injectees


def _appliquer_env_boot(environ: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """Jetons, carte, puis langue cohérente. C1 ne déplace pas les modèles."""
    outils = charger_env_local(environ=environ)
    carte = charger_carte_figee(environ=environ)
    cible_env = environ if environ is not None else os.environ
    langue = cible_env.get("HA_LANG")
    if not _valeur_utile(langue):
        langue = cible_env.get("HYPER_AMBIENT_LANG", "fr")
    synchroniser_langue_assistante(langue, environ=cible_env)
    return outils, carte


@contextlib.contextmanager
def _poser_environ(environ: dict[str, str]):
    """Pose `environ` dans os.environ le temps d'un rapport, puis restaure."""
    snapshot = dict(os.environ)
    os.environ.update({k: str(v) for k, v in environ.items()})
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)


def rapport_branchements(
    environ: dict[str, str] | None = None,
    env_local: Path | None = None,
    carte: Path | None = None,
) -> dict:
    """Sans poids GPU : carte, langue, hotwords, C11, C12, C4, JeV."""
    from src.i18n import langue, system_prompt, t

    if environ is None:
        outils, cles_carte = _appliquer_env_boot()
        ctx = contextlib.nullcontext()
    else:
        outils = charger_env_local(chemin=env_local, environ=environ)
        cles_carte = charger_carte_figee(chemin=carte, environ=environ)
        ctx = _poser_environ(environ)

    with ctx:
        registre = construire_registre(client=object())
        try:
            actifs = sorted(verifier_registre(registre))
        except RuntimeError:
            actifs = sorted(
                schema["function"]["name"] for schema in registre.schemas()
            )
        model = os.getenv("MODEL", "")
        return {
            "env_injectees": outils,
            "carte": cles_carte,
            "brain_service": os.getenv("BRAIN_SERVICE", ""),
            "model_basename": Path(model).name if model else "",
            "ears_backend": os.getenv("EARS_BACKEND", ""),
            "ears_model": os.getenv("EARS_MODEL", ""),
            "ears_hotwords": os.getenv("EARS_HOTWORDS", ""),
            "mouth_backend": os.getenv("MOUTH_BACKEND", ""),
            "mouth_voice": os.getenv("MOUTH_VOICE_NAME", ""),
            "mouth_device": os.getenv("MOUTH_DEVICE", ""),
            "lang": langue(),
            "annonce_calculer": t("tools.calculer"),
            "identite": "Hyper Ambient" in system_prompt(),
            "outils": actifs,
            "jev": True,
        }


def formatter_rapport(rapport: dict) -> str:
    """Texte de dry-run. Clés seulement, aucune valeur de secret."""
    return "\n".join(
        [
            f"CARTE : {', '.join(sorted(rapport.get('carte') or []))}",
            f"BRAIN : {rapport.get('brain_service', '')} {rapport.get('model_basename', '')}".strip(),
            (
                f"EARS  : {rapport.get('ears_backend', '')} / {rapport.get('ears_model', '')}"
                f" hotwords={rapport.get('ears_hotwords', '')}"
            ),
            (
                f"MOUTH : {rapport.get('mouth_backend', '')} "
                f"{rapport.get('mouth_voice', '')} {rapport.get('mouth_device', '')}"
            ),
            f"LANG  : {rapport.get('lang', 'fr')}",
            f"C11   : {'Hyper Ambient' if rapport.get('identite') else 'ABSENT'}",
            f"OUTILS: {', '.join(rapport.get('outils') or [])}",
            "JEV   : on",
            f"ANNONCE calculer: {rapport.get('annonce_calculer', '')}",
        ]
    )


def dry_run(
    environ: dict[str, str] | None = None,
    env_local: Path | None = None,
    carte: Path | None = None,
) -> int:
    print(
        formatter_rapport(
            rapport_branchements(
                environ=environ, env_local=env_local, carte=carte
            )
        ),
        flush=True,
    )
    return 0


def jev_ignore_tour(evaluation) -> bool:
    """True seulement si JeV a tranché : la phrase n'est pas adressée à l'assistante.

    ``None`` (pas de clé, timeout, erreur) = repli bouton : on n'ignore pas.
    Un harnais nommé n'a aucun effet ici : aucun modèle n'envoie une tâche.
    """
    if evaluation is None:
        return False
    signals = getattr(evaluation, "signals", None)
    if signals is None:
        return False
    return not bool(signals.addressed_to_mother)


def jev_doit_ignorer(evaluation, *, mains_libres: bool) -> bool:
    """JeV ne filtre que si Presence a armé mains libres pour la session."""
    if not mains_libres:
        return False
    return jev_ignore_tour(evaluation)


def construire_registre(client=None, registre_mandats=None) -> ToolRegistry:
    """Les outils que hyper-ambient peut déclencher à la voix.

    Le calculateur est toujours disponible : il est local et ne dépend ni d'un
    jeton ni d'un client HTTP. Les autres outils restent conditionnels à leur
    configuration, afin de ne pas exposer au modèle un pont inutilisable.
    """
    registre = ToolRegistry()
    register_calculator(registre)
    jeton = os.getenv("CODEX_BRIDGE_TOKEN", "").strip()
    if jeton and client is not None:
        register_ask_codex(
            registre,
            token=jeton,
            client=client,
            timeout_s=DELAI_OUTIL_S,
            registre_mandats=registre_mandats,
        )
    # Muse : second avis, sur un pont deja debout dans WSL. L'URL est lue ici et
    # non a l'import, pour qu'ajouter un agent ne demande ni reconstruction
    # d'image ni recreation de conteneur — `docker start` reste la seule
    # commande de reprise.
    url_muse = os.getenv("MUSE_BRIDGE_URL", "").strip()
    if url_muse and client is not None:
        register_ask_muse(registre, url=url_muse, client=client)
    # Claude : analyse et revue, sur le pont CLI. `ask_hermes` existe dans le
    # meme module et n'est **pas** enregistre : le chemin vers Hermes est ecrit,
    # il n'est pas emprunte aujourd'hui. Un outil declare au modele finit
    # toujours par etre appele.
    jeton_cli = os.getenv("CLI_BRIDGE_TOKEN", "").strip()
    if jeton_cli and client is not None:
        register_ask_claude(
            registre,
            token=jeton_cli,
            client=client,
            timeout_s=DELAI_OUTIL_CLAUDE_S,
            registre_mandats=registre_mandats,
        )
    # Web : l'instance SearXNG locale ne demande aucune cle. Si elle devient
    # injoignable ou renvoie zero resultat (CAPTCHA), le handler essaie ddgs,
    # Tavily, Brave, Exa, Jina et Serper dans cet ordre. Au moins un backend
    # configure doit exister pour declarer l'outil au modele.
    url_searxng = os.getenv("SEARXNG_URL", "").strip()
    cle_tavily = os.getenv("TAVILY_API_KEY", "").strip()
    cles_web = (
        cle_tavily,
        os.getenv("BRAVE_API_KEY", "").strip(),
        os.getenv("EXA_API_KEY", "").strip(),
        os.getenv("JINA_API_KEY", "").strip(),
        os.getenv("SERPER_API_KEY", "").strip(),
    )
    if client is not None and (url_searxng or any(cles_web)):
        register_web_search(
            registre,
            searxng_url=url_searxng or None,
            api_key=cle_tavily,
            client=client,
        )
    return registre


def outils_attendus_depuis_env() -> set[str]:
    """Noms qui doivent etre exposes pour la configuration courante."""
    attendus: set[str] = {"calculer"}
    if os.getenv("CODEX_BRIDGE_TOKEN", "").strip():
        attendus.add("ask_codex")
    if os.getenv("CLI_BRIDGE_TOKEN", "").strip():
        attendus.add("ask_claude")
    if os.getenv("MUSE_BRIDGE_URL", "").strip():
        attendus.add("ask_muse")
    if any(
        os.getenv(key, "").strip()
        for key in (
            "SEARXNG_URL", "TAVILY_API_KEY", "BRAVE_API_KEY", "EXA_API_KEY",
            "JINA_API_KEY", "SERPER_API_KEY",
        )
    ):
        attendus.add("web_search")
    return attendus


def verifier_registre(registre: ToolRegistry) -> set[str]:
    """Echoue tot si config et schemas divergent, avant une demo vocale."""
    actifs = {schema["function"]["name"] for schema in registre.schemas()}
    attendus = outils_attendus_depuis_env()
    if actifs != attendus:
        raise RuntimeError(
            "registre outils incoherent: "
            f"attendus={sorted(attendus)} actifs={sorted(actifs)}"
        )
    if "ask_hermes" in actifs:
        raise RuntimeError("ask_hermes ne doit pas etre expose")
    return actifs


def construire_porte() -> Gate:
    """La porte qui autorise les outils. `ask_codex` est en lecture seule, donc
    `auto` l'autorise sans rien demander ; `GATE_MODE=ask` resserre sans toucher
    au code."""
    return Gate(mode=os.getenv("GATE_MODE", "auto"))


NOM_HARNAIS_PAR_OUTIL = {v: k for k, v in OUTIL_PAR_HARNAIS.items()}


def dossier_conversations(environ=None) -> Path:
    """Répertoire des transcriptions, via un chemin monté en conteneur.

    `/workspace/data` est le volume `./data` du compose : c'est le même
    mécanisme que les autres écritures du host-agent. Sur l'hôte Windows,
    hors conteneur, on retombe sur `%LOCALAPPDATA%\\hyper-ambient\\conversations`.
    """
    environ = os.environ if environ is None else environ
    override = str(environ.get("HA_CONVERSATIONS_DIR") or "").strip()
    if override:
        return Path(override)
    data_conteneur = Path("/workspace/data")
    if data_conteneur.is_dir():
        return data_conteneur / "conversations"
    local = environ.get("LOCALAPPDATA") or environ.get("APPDATA")
    if local:
        return Path(local) / "hyper-ambient" / "conversations"
    return Path.home() / ".hyper-ambient" / "conversations"


def _dernier_dimanche(annee: int, mois: int):
    jour = date(annee, mois, 31)
    return date.fromordinal(jour.toordinal() - ((jour.weekday() + 1) % 7))


class _Paris(tzinfo):
    """Repli Europe/Paris si tzdata n'est pas installé dans le conteneur."""

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=1)
        jour = dt.date() if hasattr(dt, "date") else dt
        mars = _dernier_dimanche(jour.year, 3)
        octo = _dernier_dimanche(jour.year, 10)
        if mars <= jour < octo:
            return timedelta(hours=2)
        return timedelta(hours=1)

    def tzname(self, dt):
        return "CEST" if self.utcoffset(dt) == timedelta(hours=2) else "CET"

    def dst(self, dt):
        return (
            timedelta(hours=1)
            if self.utcoffset(dt) == timedelta(hours=2)
            else timedelta(0)
        )


def _fuseau_paris():
    """Europe/Paris, même sans la base tzdata du conteneur."""
    try:
        return ZoneInfo("Europe/Paris")
    except Exception:
        return _Paris()


FUSEAU_CONVERSATION = _fuseau_paris()


def maintenant_local(quand=None):
    """Heure de la machine (Europe/Paris), jamais l'UTC du conteneur."""
    if quand is None:
        return datetime.now(FUSEAU_CONVERSATION)
    if getattr(quand, "tzinfo", None) is None:
        return quand
    return quand.astimezone(FUSEAU_CONVERSATION)


def nouveau_fichier_conversation(quand=None, dossier=None) -> Path:
    """Un fichier Markdown horodaté par conversation, créé tout de suite."""
    quand = maintenant_local(quand)
    racine = dossier_conversations() if dossier is None else Path(dossier)
    racine.mkdir(parents=True, exist_ok=True)
    chemin = racine / f"{quand.strftime('%Y-%m-%d_%H-%M')}.md"
    if not chemin.exists():
        chemin.write_text(
            f"# Conversation {quand.strftime('%Y-%m-%d %H:%M')}\n\n",
            encoding="utf-8",
        )
    return chemin


def ecrire_ligne_conversation(chemin, locuteur: str, texte: str, *, heure=None) -> None:
    """Ajoute une ligne et flush : une coupure ne doit pas perdre le tour."""
    if chemin is None:
        return
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    heure = maintenant_local() if heure is None else maintenant_local(heure)
    ligne = f"{heure.strftime('%H:%M:%S')}  {locuteur}  {texte}\n"
    with open(chemin, "a", encoding="utf-8") as flux:
        flux.write(ligne)
        flux.flush()
        os.fsync(flux.fileno())


async def monter_cerveau(*, mandats=None, client=None, brain=None):
    """Cerveau, registre, porte, mandats — le montage commun voix / écrit.

    Sans EARS, sans MOUTH, sans websocket. Les deux chemins appellent cette
    fonction : un second montage divergent serait une dette immédiate.
    """
    from src.brain.factory import build_brain_with_fallback
    import httpx

    if mandats is None:
        mandats = RegistreMandats()
    if client is None:
        client = httpx.AsyncClient()
    if brain is None:
        brain = await build_brain_with_fallback()
    registre = construire_registre(client=client, registre_mandats=mandats)
    porte = construire_porte()
    verifier_registre(registre)
    return {
        "brain": brain,
        "registre": registre,
        "porte": porte,
        "mandats": mandats,
        "client": client,
    }


def recoller_prononce(morceaux) -> str:
    """Joint des phrases déjà closes.

    Un `Un instant.` suivi de `Je vais…` se prononce collé. L'espace se
    remet à la couture, pas à la fin de chaque libellé — un flux de
    jetons (`Hel` + `lo`) ne doit pas devenir `Hel lo`.
    """
    texte = ""
    for piece in morceaux:
        if not piece:
            continue
        if texte and texte[-1] in ".!?" and not piece[:1].isspace():
            texte += " "
        texte += piece
    return texte.strip()


def flux_cerveau(brain, prompt, registre, porte, historique):
    """Le flux d'un tour : boucle d'outils si le registre est garni.

    Pas de `tool_choice` forcé : le distant appelle l'outil de lui-même.
    Un mandat déposé clôt le tour sans reformulation.

    Une seule annonce d'attente sur ce chemin : l'accusé du mandat. Il
    nomme le harnais et promet l'arrivée — l'amorce du routeur et la
    phrase du modèle disent la même chose. On les jette ici, au dépôt.
    """
    if registre is not None and len(registre):
        def est_handler_mandat(nom: str) -> bool:
            spec = registre.get(nom)
            return bool(
                spec is not None
                and hasattr(spec.handler, "registre_mandats")
            )

        async def flux_avec_mandat():
            # Ne retenir que si un harnais est nommé : sinon on casserait
            # le flux mot à mot des tours ordinaires.
            retenir = bool(
                re.search(r"\b" + NOMS_HARNAIS + r"\b", prompt or "", re.IGNORECASE)
            )
            tampon = []
            async for chunk in run_tool_loop(
                brain,
                prompt,
                registre,
                porte,
                history=historique,
                max_tool_calls=2,
            ):
                if chunk.get("channel") == "tool":
                    nom = chunk.get("tool", "")
                    if chunk.get("phase") == "call" and est_handler_mandat(nom):
                        tampon.clear()
                        yield chunk
                        continue
                    for piece in tampon:
                        yield piece
                    tampon.clear()
                    yield chunk
                    if (
                        chunk.get("phase") == "result"
                        and est_handler_mandat(nom)
                    ):
                        contenu = (chunk.get("content") or "").strip()
                        if contenu:
                            yield {
                                "delta": contenu,
                                "stop_reason": "mandat_depose",
                                "ttft_ms": None,
                            }
                        return
                    continue
                if retenir:
                    tampon.append(chunk)
                else:
                    yield chunk
            for piece in tampon:
                yield piece

        return flux_avec_mandat()
    return brain.query_streaming(prompt, history=historique)


def construire_ears():
    """Construit EARS depuis l'environnement, sans charger les poids.

    ``faster-whisper`` reste un repli explicite. L'option 2 choisit Qwen3-ASR
    via ``EARS_BACKEND=qwen3`` ; les imports restent paresseux afin qu'un
    backend absent n'empêche pas l'autre de démarrer.
    """
    backend = _texte_configuration("EARS_BACKEND", "faster-whisper").lower()
    if backend not in {"qwen3", "qwen3-asr", "faster-whisper", "faster_whisper", "whisper"}:
        _avertir_repli_configuration("EARS_BACKEND", backend, "faster-whisper")
        backend = "faster-whisper"
    default_model = (
        "0.6B" if backend in {"qwen3", "qwen3-asr"} else "large-v3-turbo"
    )
    model_size = _texte_configuration("EARS_MODEL", default_model)
    language = _code_langue(_texte_configuration("EARS_LANGUAGE", "fr"), cle="EARS_LANGUAGE")
    device = _texte_configuration("EARS_DEVICE", "cuda")
    compute_type = os.getenv("EARS_COMPUTE_TYPE")

    if backend in {"qwen3", "qwen3-asr"}:
        from src.ears.qwen3_asr import Qwen3ASR

        classe = Qwen3ASR
    elif backend in {"faster-whisper", "faster_whisper", "whisper"}:
        from src.ears.faster_whisper_asr import FasterWhisperASR

        classe = FasterWhisperASR
    kwargs = {"model_size": model_size, "language": language, "device": device}
    if compute_type:
        kwargs["compute_type"] = compute_type
    hotwords = os.getenv("EARS_HOTWORDS", "").strip()
    if hotwords and backend in {"faster-whisper", "faster_whisper", "whisper"}:
        kwargs["hotwords"] = hotwords
    return backend, classe(**kwargs)


def lire_secret() -> str:
    """Secret d'installation, ou valeur de développement si la variable manque."""
    secret = os.environ.get("HA_HOSTAGENT_SECRET") or os.environ.get("MOTHER_HOSTAGENT_SECRET")
    if secret:
        return secret
    print(
        "ATTENTION : HA_HOSTAGENT_SECRET est absent. "
        "Secret de développement utilisé (« partage-installation »). "
        "Ne pas exposer ce service hors de la machine.",
        file=sys.stderr,
        flush=True,
    )
    return SECRET_DEVELOPPEMENT


def _vers_float32(echantillons) -> np.ndarray:
    """Convertit int16 → float32 ∈ [-1, 1] ; laisse le float32 intact."""
    arr = np.asarray(echantillons).reshape(-1)
    if arr.dtype == np.int16:
        return arr.astype(np.float32) / np.float32(32768.0)
    return np.ascontiguousarray(arr, dtype=np.float32)


def _rechantillonner(pcm: np.ndarray, orig_sr: int) -> np.ndarray:
    """Ramène à 16 kHz un énoncé **complet** : phrase d'attente, phrase de secours.

    Réservé aux appels qui tiennent tout l'audio en main. Le flux de MOUTH, lui,
    arrive par blocs de 80 ms et doit passer par `RechantillonneurContinu` :
    convertir chaque bloc isolément pose un transitoire à chaque couture — voir
    `dev/tests/test_resample_continu.py`.
    """
    if orig_sr == SAMPLE_RATE or pcm.size == 0:
        return pcm
    import librosa

    return librosa.resample(pcm, orig_sr=orig_sr, target_sr=SAMPLE_RATE)


def _trames_depuis_pcm(pcm: np.ndarray, leftover: list) -> list[AudioFrame]:
    """Découpe en trames de FRAME_SAMPLES. Le reliquat reste pour le morceau suivant."""
    convertis = np.concatenate([leftover[0], pcm]) if leftover[0].size else pcm
    n_complet = (convertis.size // FRAME_SAMPLES) * FRAME_SAMPLES
    trames = []
    for debut in range(0, n_complet, FRAME_SAMPLES):
        chunk = np.array(
            convertis[debut : debut + FRAME_SAMPLES],
            dtype=np.float32,
            copy=True,
        )
        trames.append(AudioFrame(samples=chunk))
    leftover[0] = np.array(convertis[n_complet:], dtype=np.float32, copy=True)
    return trames


def _vider_reliquat(leftover: list) -> list[AudioFrame]:
    """Émet la dernière trame, paddée de silence : on ne jette pas la queue."""
    reste = leftover[0]
    leftover[0] = np.zeros(0, dtype=np.float32)
    if reste.size == 0:
        return []
    pad = np.zeros(FRAME_SAMPLES, dtype=np.float32)
    pad[: reste.size] = reste
    return [AudioFrame(samples=pad)]


def _json_trames(trames: list[AudioFrame]) -> dict:
    """Même encodage qu'à l'aller : listes de flottants, une par trame."""
    return {
        "type": "invoke",
        "primitive": "audio.render",
        "frames": [trame.samples.tolist() for trame in trames],
    }


def composer_rapport(amorces: list[str], reponse: list[str]) -> tuple[str, str]:
    """Sépare ce qui a couvert l'attente de ce qui a répondu.

    L'amorce (« Un instant. ») est prononcée hors flux et n'est pas une réponse :
    la recoller au texte du modèle faisait lire « Un instant. Je suis juste là »
    comme une seule phrase, dans le rapport comme dans le log.
    """
    return recoller_prononce(reponse), " ".join(a.strip() for a in amorces if a.strip())


class HostPipeline:
    """Modèles chargés une fois ; chaque tour de parole réutilise la même instance."""

    def __init__(self) -> None:
        self.asr = None
        # Memoire de conversation. Sans elle, « oui, vas-y » ne veut rien
        # dire : chaque tour partait seul, et hyper-ambient a repondu qu'elle
        # n'avait pas le resultat d'une question a laquelle elle venait de
        # repondre. On garde les derniers echanges, pas toute la session :
        # le contexte du modele local est petit et la latence croit avec.
        self._historique: list[dict] = []
        self._memoire = MemoireConversation()
        self._tampon_ambiant = TamponAmbiant()
        # Resultats d'outils du dernier tour qui en a execute. `_historique`
        # ne retient que le texte parle : sans ce buffer, « contre-analyse
        # Claude du resultat Codex » n'a plus le texte Codex au tour suivant.
        self._dernier_outils: list[dict] = []
        # Les messages issus d'un tour avec outil restent disponibles pendant
        # une seule reprise.  Les conserver dans la mémoire conversationnelle
        # ordinaire faisait réapparaître une météo plusieurs tours plus tard,
        # même après l'expiration de `_dernier_outils`.
        self._historique_outils_ephemeres: list[dict] = []
        self.brain = None
        self.tts = None
        # Le registre est vide tant que `load` ne l'a pas garni : un tour joue
        # sans lui doit rester le tour d'avant, pas un tour degrade.
        self.registre: ToolRegistry | None = None
        self.porte: Gate | None = None
        self._client_outils = None
        self._jev = None
        self._mains_libres = False
        self._fenetre = FenetreConversation()
        self._websocket = None
        self._tache_maintien_jev = None
        self._tache_indicateur_conversation = None
        self._conversation_ouverte_emise = False
        self._lock = asyncio.Lock()
        self.output_gain_db = _nombre_configuration("MOUTH_OUTPUT_GAIN_DB", 0.0)
        self._mandats = RegistreMandats()
        self._dernier_parole_a = time.monotonic()
        self._tache_mandats = None
        self._badge_prets = -1
        self._tache_rechargement_mouth = None
        self._tache_surveillance_langue = None
        self._signature_langue = None
        self._journal_conversation = None

    def _noter_conversation(self, locuteur: str, texte: str) -> None:
        if not texte:
            return
        ecrire_ligne_conversation(self._journal_conversation, locuteur, texte)

    def on_options(self, message) -> dict | None:
        """Presence : mains-libres et langue vivante sur hello/options.

        Le protocole accepte ``language`` (ou les deux noms historiques) et
        ``accent``. Le statut retourné est envoyé au client par le transport :
        l'UI peut annoncer un éventuel rechargement au lieu de prétendre que la
        nouvelle voix est déjà prête.
        """
        if not isinstance(message, dict):
            return None
        statut = None
        langue = message.get("language", message.get("HA_LANG", message.get("HYPER_AMBIENT_LANG")))
        if langue is not None:
            accent = message.get("accent")
            # Le client qui expose déjà le réglage sous son nom historique est
            # aussi explicite qu'un champ ``accent`` dédié.
            if not _valeur_utile(accent) and "MOUTH_LANGUAGE" in message:
                accent = message["MOUTH_LANGUAGE"]
            try:
                reglage = synchroniser_langue_assistante(
                    langue, accent=accent
                )
            except ValueError as exc:
                return {"type": "language_status", "state": "error", "error": str(exc)}
            mode = self._appliquer_langue_aux_modeles(reglage)
            statut = {"type": "language_status", **reglage, "state": mode}
            print(
                "LANG  : "
                f"{reglage['language']} (ASR={reglage['ears']}, TTS={reglage['mouth']}; "
                f"{'appliquée à chaud' if mode == 'ready' else mode})",
                flush=True,
            )

        if "mains_libres" in message:
            self._mains_libres = message.get("mains_libres") is True
            if not self._mains_libres:
                # Couper le mode referme la conversation : la prochaine
                # activation repart d'une page blanche.
                self._fenetre.fermer()
                self._fermer_conversation()
            print(
                f"JEV   : mains_libres={'on' if self._mains_libres else 'off'}",
                flush=True,
            )
            if self._mains_libres:
                self._demarrer_maintien_jev()
                self._demarrer_indicateur_conversation()
            else:
                self._arreter_maintien_jev()
                self._arreter_indicateur_conversation()
        return statut

    def _appliquer_langue_aux_modeles(self, reglage: dict[str, object]) -> str:
        """Change les paramètres lus à chaque requête et rend son état honnête."""
        if self.asr is not None and hasattr(self.asr, "language"):
            self.asr.language = reglage["ears"]
        if self.tts is None:
            return "ready"
        # Magpie ne lie pas la langue aux poids : _render la transmet au serveur
        # pour chaque phrase. Whisper et Qwen ont la même propriété par appel.
        if type(self.tts).__name__ == "MagpieTTS":
            self.tts.language = reglage["mouth"]
            return "ready"
        if type(self.tts).__name__ == "PocketTTS":
            self._demarrer_rechargement_pocket(str(reglage["mouth"]))
            return "reloading"
        # Piper et Supertonic ont une voix liée à leurs poids, sans carte de
        # modèle par langue. Dire « prêt » ou « rechargement » serait mensonger.
        return "unsupported"

    def _demarrer_rechargement_pocket(self, langue: str) -> None:
        """Recharge Pocket à côté de la voix active puis échange à la frontière d'un tour."""
        tache = self._tache_rechargement_mouth
        if tache is not None and not tache.done():
            return

        async def recharger() -> None:
            from src.mouth.pocket_tts import PocketTTS

            ancienne = self.tts
            candidate = PocketTTS(
                language=langue,
                voice=os.getenv("MOUTH_VOICE_NAME", getattr(ancienne, "voice", "estelle")),
                device=os.getenv("MOUTH_DEVICE", getattr(ancienne, "device", "cpu")),
                profile=os.getenv("MOUTH_PROFILE", "aurora"),
                demi_tons=_nombre_configuration("MOUTH_DEMI_TONS", 0.0),
            )
            if not await candidate.load_model():
                print("LANG  : rechargement Pocket échoué — ancienne voix conservée", flush=True)
                return
            async with self._lock:
                self.tts = candidate
            print("LANG  : rechargement Pocket terminé", flush=True)

        self._tache_rechargement_mouth = asyncio.create_task(recharger())

    def _demarrer_surveillance_langue(self) -> None:
        """Compatibilité avec le bouton existant qui écrit seulement .env.local.

        Le message WS est instantané. Cette veille courte couvre l'ancienne UI
        pendant sa migration : elle ne relance jamais le serveur et ne lit que
        les trois réglages non secrets concernés.
        """
        tache = self._tache_surveillance_langue
        if tache is not None and not tache.done():
            return
        self._tache_surveillance_langue = asyncio.create_task(
            self._surveiller_langue()
        )

    async def _surveiller_langue(self) -> None:
        chemin = _ROOT / ".env.local"
        try:
            while True:
                paires = parser_env_local(chemin)
                signature = tuple(
                    (cle, paires.get(cle, ""))
                    for cle in ("HA_LANG", "HYPER_AMBIENT_LANG", "MOUTH_ACCENT")
                )
                if signature != self._signature_langue:
                    # Un tour possède les instances ASR/TTS pendant toute sa
                    # durée. La bascule attend donc la frontière du tour, au
                    # lieu de changer la phonétique au milieu d'une phrase.
                    if self._lock.locked():
                        await asyncio.sleep(0.25)
                        continue
                    self._signature_langue = signature
                    langue = paires.get("HA_LANG") or paires.get("HYPER_AMBIENT_LANG")
                    if _valeur_utile(langue):
                        # Une clé explicitement vidée remet la bouche en mode
                        # cohérent ; sans elle, une surcharge FORCE reste voulue.
                        if "MOUTH_ACCENT" in paires and not _valeur_utile(
                            paires["MOUTH_ACCENT"]
                        ):
                            os.environ.pop("MOUTH_LANGUAGE_FORCE", None)
                        reglage = synchroniser_langue_assistante(
                            langue,
                            accent=paires.get("MOUTH_ACCENT"),
                        )
                        mode = self._appliquer_langue_aux_modeles(reglage)
                        print(
                            f"LANG  : .env.local → {reglage['language']} "
                            f"({mode})",
                            flush=True,
                        )
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            raise

    def _demarrer_maintien_jev(self) -> None:
        tache = self._tache_maintien_jev
        if tache is not None and not tache.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._tache_maintien_jev = asyncio.create_task(self._boucle_prechauffage_jev())

    def _arreter_maintien_jev(self) -> None:
        tache = self._tache_maintien_jev
        self._tache_maintien_jev = None
        if tache is None or tache.done():
            return
        tache.cancel()
        print("JEV   : maintien arrete", flush=True)

    async def _boucle_prechauffage_jev(self) -> None:
        jev = getattr(self, "_jev", None)
        if jev is None:
            return
        debut = time.monotonic()
        try:
            ok = await jev.prechauffer()
            if ok:
                print(
                    f"JEV   : prechauffage ok en {int((time.monotonic() - debut) * 1000)} ms",
                    flush=True,
                )
            await self._signaler_jev_pret()
            await jev.maintenir()
        except asyncio.CancelledError:
            raise

    async def _signaler_jev_pret(self) -> None:
        websocket = self._websocket
        if websocket is None:
            return
        try:
            await websocket.send_json({"type": "jev_pret"})
        except Exception:
            return

    def _restant_conversation_s(self) -> float:
        if not self._fenetre.engagee():
            return 0.0
        jusqu_a = getattr(self._fenetre, "_jusqu_a", None)
        if jusqu_a is None:
            return 0.0
        return max(0.0, float(jusqu_a) - time.monotonic())

    def _payload_conversation(self) -> dict:
        ouverte = bool(self._mains_libres and self._fenetre.engagee())
        return {
            "type": "conversation",
            "ouverte": ouverte,
            "restant_s": self._restant_conversation_s() if ouverte else 0.0,
        }

    async def _signaler_conversation(self) -> None:
        websocket = self._websocket
        if websocket is None:
            return
        payload = self._payload_conversation()
        try:
            await websocket.send_json(payload)
        except Exception:
            return
        self._conversation_ouverte_emise = bool(payload["ouverte"])

    def _demarrer_indicateur_conversation(self) -> None:
        tache = self._tache_indicateur_conversation
        if tache is not None and not tache.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._tache_indicateur_conversation = asyncio.create_task(
            self._boucle_indicateur_conversation()
        )

    def _arreter_indicateur_conversation(self) -> None:
        tache = self._tache_indicateur_conversation
        self._tache_indicateur_conversation = None
        if tache is not None and not tache.done():
            tache.cancel()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._signaler_conversation())

    async def _boucle_indicateur_conversation(self) -> None:
        await self._signaler_conversation()
        try:
            while self._mains_libres:
                await asyncio.sleep(1.0)
                ouverte = self._fenetre.engagee()
                if self._conversation_ouverte_emise and not ouverte:
                    garde = self._fermer_conversation()
                    if garde:
                        print(f"JEV   : {garde}", flush=True)
                        self._noter_conversation("hyper-ambient", garde)
                if ouverte or self._conversation_ouverte_emise:
                    await self._signaler_conversation()
        except asyncio.CancelledError:
            raise

    def _fermer_conversation(self) -> str:
        """Purge la mémoire vive. Les mandats en cours restent."""
        self._memoire.purger()
        self._tampon_ambiant.oublier()
        self._historique = []
        self._dernier_outils = []
        self._historique_outils_ephemeres = []
        return phrase_garde([m.harnais for m in self._mandats.en_cours()])

    async def _ouvrir_conversation(self) -> None:
        self._fenetre.engager()
        await self._signaler_conversation()

    def peer_address_of(self, websocket) -> str:
        """Mémorise le socket pour le retour audio, et tranche la localité.

        Docker Desktop présente l'hôte derrière une passerelle, pas en
        loopback, alors que le client parle bien à localhost:8001. On
        ramène ce cas à 127.0.0.1 ; le secret, lui, reste exigé.
        """
        self._websocket = websocket
        host = websocket.client.host if websocket.client is not None else "127.0.0.1"
        try:
            if ipaddress.ip_address(host).is_loopback:
                return host
        except ValueError:
            pass
        return "127.0.0.1"

    def on_frames(self, frames):
        """Rend le tour de parole au transport, qui l'attend.

        Il était détaché par `create_task`, et la voix partait donc d'une tâche
        extérieure au point d'entrée ASGI. Depuis la montée de version du socle
        web, uvicorn ferme le transport dès que l'application rend la main : le
        premier envoi du tour tombait sur un socket déjà fermé, l'exception était
        avalée par le garde-fou, et le tour mourait sans un son. Rendre la
        coroutine laisse le transport l'attendre — tout ce qui part sur le socket
        part désormais de la tâche qui le détient.
        """
        return self._tour(frames, self._websocket)

    async def load(self) -> None:
        """Charge EARS, BRAIN et MOUTH une seule fois, avant d'accepter un client."""
        injectees, cles_carte = _appliquer_env_boot()
        if injectees:
            print(
                "ENV   : "
                + ", ".join(sorted(injectees))
                + " depuis .env.local",
                flush=True,
            )
        if cles_carte:
            print(
                "CARTE : "
                + ", ".join(sorted(cles_carte))
                + " depuis carte_figee.env",
                flush=True,
            )
        from src.i18n import langue

        print(
            f"LANG  : {langue()} (prompt/nombres ; carte ASR/TTS="
            f"{os.getenv('EARS_LANGUAGE', 'fr')}/{os.getenv('MOUTH_LANGUAGE', 'fr')})",
            flush=True,
        )
        voix = _texte_configuration("MOUTH_VOICE", VOIX_PIPER)

        gain_lineaire = 10.0 ** (self.output_gain_db / 20.0)
        print(
            f"MOUTH : post-gain sortie {self.output_gain_db:+.1f} dB "
            f"(x{gain_lineaire:.2f}), limiteur doux tanh",
            flush=True,
        )

        backend_ears, self.asr = construire_ears()
        hotwords = getattr(self.asr, "hotwords", None)
        extra_hw = f" hotwords={hotwords}" if hotwords else ""
        print(
            f"EARS  : chargement {backend_ears} / {self.asr.model_size} "
            f"sur {self.asr.device}{extra_hw}…",
            flush=True,
        )
        if not await self.asr.load_model():
            print("EARS  : modèle indisponible", flush=True)
            raise SystemExit(1)

        pieces = await monter_cerveau(mandats=self._mandats)
        self.brain = pieces["brain"]
        self._client_outils = pieces["client"]
        self.registre = pieces["registre"]
        self.porte = pieces["porte"]
        self._mandats = pieces["mandats"]
        health = await self.brain.health()
        print(
            f"BRAIN : {self.brain.name} @ {self.brain.api_endpoint} — {health['detail']}",
            flush=True,
        )

        actifs = {schema["function"]["name"] for schema in self.registre.schemas()}
        if actifs:
            noms = ", ".join(sorted(actifs))
            print(f"OUTILS: {noms} — porte en mode {self.porte.mode}", flush=True)
        else:
            print(
                "OUTILS: aucun backend configure — tour de parole sans outil",
                flush=True,
            )
        self._assurer_veille_mandats()
        self._journal_conversation = nouveau_fichier_conversation()
        print(f"CONVO : {self._journal_conversation}", flush=True)

        from src.ears.jev_reflexe import JevReflexe

        self._jev = JevReflexe()
        print("JEV   : réflexe en entrée (repli silencieux sans clé)", flush=True)

        # MOUTH : Pocket TTS par défaut. Piper reste joignable par MOUTH_BACKEND=piper,
        # parce qu'il ne coûte aucune VRAM — c'est le repli si le GPU est saturé.
        backend = _texte_configuration("MOUTH_BACKEND", "pocket").lower()
        if backend not in {"pocket", "supertonic", "magpie", "piper"}:
            _avertir_repli_configuration("MOUTH_BACKEND", backend, "piper")
            backend = "piper"
        if backend == "pocket":
            from src.mouth.pocket_tts import PocketTTS

            langue = _texte_configuration("MOUTH_LANGUAGE", "french_24l")
            nom_voix = _texte_configuration("MOUTH_VOICE_NAME", "estelle")
            profil = _texte_configuration("MOUTH_PROFILE", "aurora")
            # pocket-tts n'a ni reglage de vitesse ni reglage de hauteur.
            # MOUTH_DEMI_TONS descend la voix par reechantillonnage, ce qui
            # ralentit la diction dans le meme rapport : -3 donne une tierce
            # mineure plus bas et 19 % plus lent. Device cpu : 0 VRAM, le
            # GPU reste a EARS / llama-server.
            demi_tons = _nombre_configuration("MOUTH_DEMI_TONS", 0.0)
            device = _texte_configuration("MOUTH_DEVICE", "cpu")
            print(
                f"MOUTH : chargement pocket-tts {langue} / {nom_voix} "
                f"profil={profil} device={device} demi_tons={demi_tons:+g}…",
                flush=True,
            )
            self.tts = PocketTTS(
                language=langue,
                voice=nom_voix,
                device=device,
                profile=profil,
                demi_tons=demi_tons,
            )
        elif backend == "supertonic":
            from src.mouth.supertonic_tts import SupertonicTTS

            # Voix feminine lente demandee le 15 sept : F5, la plus grave des
            # styles feminins, ralentie. CPU, 0 VRAM.
            style = _texte_configuration("MOUTH_STYLE", "F5")
            vitesse = _nombre_configuration("MOUTH_SPEED", 0.88)
            profil = _texte_configuration("MOUTH_PROFILE", "aurora")
            print(
                f"MOUTH : chargement supertonic-3 {style} vitesse={vitesse} profil={profil}…",
                flush=True,
            )
            self.tts = SupertonicTTS(style=style, speed=vitesse, profile=profil)
        elif backend == "magpie":
            from src.mouth.magpie_tts import MagpieTTS

            # Voix retenue à la dégustation : Magpie Sofia, CPU, 0 VRAM.
            # Le modèle reste chargé (nemo-speech serve), pas un binaire
            # relancé à chaque phrase. llama-server (:8080) n'est pas touché.
            nom_voix = _texte_configuration("MOUTH_VOICE_NAME", "Sofia")
            langue = _code_langue(_texte_configuration("MOUTH_LANGUAGE", "fr"), cle="MOUTH_LANGUAGE")
            device = _texte_configuration("MOUTH_DEVICE", "cpu")
            print(
                f"MOUTH : chargement magpie {nom_voix}…",
                flush=True,
            )
            self.tts = MagpieTTS(voice=nom_voix, language=langue, device=device)
        else:
            from src.mouth.piper_tts import PiperTTS

            # Les voix francaises de Piper sont natives — elles n'ont jamais
            # entendu d'anglais — mais claires : 235 Hz mesures sur siwis, quand
            # hyper-ambient demande grave. MOUTH_DEMI_TONS les descend ; -6
            # ramene siwis a 155 Hz, la hauteur de la voix Pocket qu'il aimait.
            demi_tons = _nombre_configuration("MOUTH_DEMI_TONS", 0.0)
            profil = _texte_configuration("MOUTH_PROFILE", "aurora")
            print(
                f"MOUTH : chargement piper {voix} profil={profil} "
                f"demi_tons={demi_tons:+g}…",
                flush=True,
            )
            self.tts = PiperTTS(
                model_path=voix, profile=profil, demi_tons=demi_tons
            )

        if not await self.tts.load_model():
            print(
                "MOUTH : voix indisponible — lancer dev/scripts/fetch_models.sh core",
                flush=True,
            )
            raise SystemExit(1)
        self._demarrer_surveillance_langue()

    async def close(self) -> None:
        tache_langue = self._tache_surveillance_langue
        self._tache_surveillance_langue = None
        if tache_langue is not None and not tache_langue.done():
            tache_langue.cancel()
        tache_mouth = self._tache_rechargement_mouth
        self._tache_rechargement_mouth = None
        if tache_mouth is not None and not tache_mouth.done():
            tache_mouth.cancel()
        tache = self._tache_mandats
        self._tache_mandats = None
        if tache is not None and not tache.done():
            tache.cancel()
        if self.brain is not None:
            await self.brain.close()
        if self._client_outils is not None:
            await self._client_outils.aclose()
            self._client_outils = None

    def _historique_pour_modele(self) -> list[dict]:
        """Parole retenue + derniers resultats d'outils, hors amorces TTS.

        Le buffer ne compte pas dans MEMOIRE_MESSAGES : un resultat Codex de
        1200 caracteres ne doit pas evincer les six echanges parles.
        """
        historique = list(self._historique)
        for outil in self._dernier_outils:
            nom = outil.get("name") or "outil"
            contenu = (outil.get("content") or "").strip()
            if not contenu:
                continue
            historique.append(
                {"role": "user", "content": f"[résultat outil {nom}] {contenu}"}
            )
        return historique

    def _purger_historique_outils_ephemere(self) -> None:
        """Retire les échanges fondés sur un outil après leur unique reprise."""
        if not self._historique_outils_ephemeres:
            return
        identifiants = {id(message) for message in self._historique_outils_ephemeres}
        self._historique = [
            message for message in self._historique if id(message) not in identifiants
        ]
        self._historique_outils_ephemeres = []

    def _registre_pour_tour(self, prompt: str):
        """Registre expose au modele pour CE tour.

        Les harnais restent visibles à chaque tour : le modèle choisit de les
        appeler comme il choisit le web. Leurs handlers déposent un mandat et
        rendent la main immédiatement, sans appel bloquant dans le tour.
        """
        return self.registre

    def _flux_brain(self, prompt: str):
        """Le flux du tour : sous boucle d'outils si le registre est garni.

        Le registre vide rend **exactement** l'appel d'avant, sans `tools` dans
        la charge utile. Un registre garni passe par la boucle : le routeur
        retire les schemas sur un REFLEXE. Deux outils par tour, un seul par
        aller-retour modele (MAX_TOOL_CALLS_PER_ITERATION=1). Brancher Codex
        ne doit rien changer a « Bonjour. ».
        """
        historique = self._historique_pour_modele()
        # Le resultat est utile au seul tour qui suit son appel. On fabrique
        # d'abord sa copie dans `historique`, puis on vide le buffer avant la
        # requete : il ne sera plus reinjecte au tour suivant, sauf si ce tour
        # produit lui-meme un nouveau resultat d'outil.
        self._dernier_outils = []
        # `historique` est la copie remise à ce tour de suivi.  Une fois cette
        # copie prise, les réponses et résultats qui venaient de l'outil ne
        # doivent plus atteindre le modèle au tour suivant.
        self._purger_historique_outils_ephemere()
        registre = self._registre_pour_tour(prompt)
        return flux_cerveau(
            self.brain, prompt, registre, self.porte, historique,
        )

    def _assurer_veille_mandats(self) -> None:
        tache = self._tache_mandats
        if tache is not None and not tache.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._tache_mandats = asyncio.create_task(self._boucle_mandats())

    async def _boucle_mandats(self) -> None:
        try:
            while True:
                await asyncio.sleep(0.5)
                websocket = self._websocket
                if websocket is None:
                    continue
                # Sans mandat, la boucle ne touche a RIEN : ni socket, ni
                # verrou de parole. Mesure du 2026-09-20 : prendre le verrou
                # toutes les demi-secondes faisait osciller l'etat de
                # l'interface en continu, la fenetre clignotait sans arret
                # alors qu'aucun mandat n'existait.
                if not self._mandats.prets() and not self._mandats.en_cours():
                    continue
                await self._signaler_badge_mandat(websocket)
                if self._lock.locked():
                    continue
                leftover = [np.zeros(0, dtype=np.float32)]
                await self.annoncer_mandats_prets(websocket, leftover)
        except asyncio.CancelledError:
            raise

    async def _signaler_badge_mandat(self, websocket) -> None:
        """Badge passif seulement : jamais d'elevation de fenetre."""
        n = len(self._mandats.prets())
        if n == self._badge_prets:
            return
        self._badge_prets = n
        if websocket is None:
            return
        from src.i18n import t

        try:
            await websocket.send_json(
                {
                    "type": "mandat_badge",
                    "prets": n,
                    "libelle": t("mandat.badge", n=n),
                }
            )
        except Exception:
            return

    async def annoncer_mandats_prets(self, websocket, leftover=None) -> None:
        """Annonce d'arrivee ou rappel, seulement si la parole est libre.

        Jamais pendant une lecture audio, jamais au milieu d'un tour.
        Le mandat pret attend. Pas d'elevation de fenetre.
        """
        if self._lock.locked():
            return
        async with self._lock:
            await self._annoncer_mandats_prets_verrouille(websocket, leftover)

    async def _annoncer_mandats_prets_verrouille(self, websocket, leftover) -> None:
        if leftover is None:
            leftover = [np.zeros(0, dtype=np.float32)]
        if self.tts is None:
            return
        await self._signaler_badge_mandat(websocket)
        maintenant = time.monotonic()
        for mandat in list(self._mandats.prets()):
            phrase = phrase_arrivee(mandat)
            self._noter_conversation(f"← {mandat.harnais}", phrase)
            print(
                f"MANDAT: arrivee {mandat.harnais} id={mandat.identifiant} — {phrase!r}",
                flush=True,
            )
            try:
                n_trames, duree_s = await self._dire_maintenant(
                    websocket, phrase, leftover
                )
            except Exception as exc:
                print(
                    f"MANDAT: annonce echec id={mandat.identifiant} "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                continue
            if not n_trames:
                print(
                    f"MANDAT: annonce audio_vide id={mandat.identifiant} — non confirmee",
                    flush=True,
                )
                continue
            print(
                f"MANDAT: annonce emission id={mandat.identifiant} "
                f"trames={n_trames} duree_s={duree_s:.3f}",
                flush=True,
            )
            # L'annonce arrive apres la fin du tour de parole precedent. Elle
            # est donc elle-meme un tour complet : sans ce marqueur, ses audio
            # reste sur la socket et est lu comme le debut du tour suivant.
            await self._envoyer(websocket, [])
            print(
                f"MANDAT: annonce fin_envoyee id={mandat.identifiant}", flush=True
            )
            self._mandats.marquer_annonce(mandat.identifiant)
            await self._signaler_badge_mandat(websocket)
        silence_s = maintenant - self._dernier_parole_a
        for mandat in list(self._mandats.en_cours()):
            if mandat.rappel_fait:
                continue
            if maintenant - mandat.depose_a < DELAI_RAPPEL_S:
                continue
            if silence_s < DELAI_RAPPEL_S:
                continue
            phrase = phrase_rappel(mandat.harnais)
            print(f"MANDAT: rappel {mandat.harnais}", flush=True)
            await self._dire_maintenant(websocket, phrase, leftover)
            # Meme contrat de transport que l'annonce d'arrivee : aucun audio
            # hors d'un tour termine explicitement.
            await self._envoyer(websocket, [])
            mandat.rappel_fait = True

    async def _envoyer(self, websocket, trames: list[AudioFrame]) -> None:
        """Envoie des paquets d'une seconde, ou un marqueur vide de fin de tour."""
        if trames:
            self._dernier_parole_a = time.monotonic()
        if websocket is None:
            return
        if not trames:
            await websocket.send_json(_json_trames([]))
            return
        trames = [
            AudioFrame(
                samples=appliquer_gain_doux(trame.samples, self.output_gain_db)
            )
            for trame in trames
        ]
        paquet = SAMPLE_RATE // FRAME_SAMPLES
        for debut in range(0, len(trames), paquet):
            await websocket.send_json(_json_trames(trames[debut : debut + paquet]))

    async def _envoyer_rapport(
        self,
        websocket,
        *,
        transcript: str,
        reply: str,
        timings_ms: dict,
        amorces: str = "",
    ) -> None:
        """Émet le rapport après l'audio : transcript, réponse, durées d'étages.

        `amorces` est additif : les clients existants lisent `transcript` et
        `reply` et ignorent le reste. Toujours une chaîne, jamais `None`.
        """
        if websocket is None:
            return
        await websocket.send_json(
            {
                "type": "report",
                "transcript": transcript,
                "reply": reply,
                "amorces": amorces,
                "timings_ms": timings_ms,
            }
        )

    async def _dire_maintenant(self, websocket, phrase: str, leftover: list) -> tuple[int, float]:
        """Synthetise et envoie une phrase sans passer par le flux de tokens.

        Sert aux phrases d'attente du routeur : leur seule raison d'etre est
        d'occuper le silence pendant que le modele distant reflechit, donc
        elles ne doivent subir aucun tampon.
        """
        out = await self.tts.synthesize(phrase)
        pcm = _rechantillonner(
            _vers_float32(out.get("audio", [])),
            int(out.get("sample_rate") or self.tts.sample_rate),
        )
        trames = _trames_depuis_pcm(pcm, leftover) + _vider_reliquat(leftover)
        if trames:
            await self._envoyer(websocket, trames)
        return len(trames), float(pcm.size) / SAMPLE_RATE

    async def _dire_secours(
        self,
        websocket,
        leftover: list,
        *,
        phrase: str,
        transcript: str,
        t_tour: float,
        ears_ms: float,
        brain_ms: float,
    ) -> None:
        """Prononce la phrase de secours, puis le rapport, puis le marqueur vide.

        Même ordre que le tour réussi : l'audio part avant le rapport.
        La recette lit `reply` : sans la phrase ici, elle afficherait
        une réponse vide et on ne saurait pas quel étage a lâché.
        """
        t_mouth = time.monotonic()
        out = await self.tts.synthesize(phrase)
        pcm = _rechantillonner(
            _vers_float32(out.get("audio", [])),
            int(out.get("sample_rate") or self.tts.sample_rate),
        )
        trames = _trames_depuis_pcm(pcm, leftover) + _vider_reliquat(leftover)
        t_derniere = time.monotonic()
        mouth_ms = (t_derniere - t_mouth) * 1000.0
        if trames:
            await self._envoyer(websocket, trames)
            t_derniere = time.monotonic()
        await self._envoyer_rapport(
            websocket,
            transcript=transcript,
            reply=phrase,
            timings_ms={
                "ears": ears_ms,
                "brain": brain_ms,
                "mouth": mouth_ms,
                "total": (t_derniere - t_tour) * 1000.0,
            },
        )
        await self._envoyer(websocket, [])

    async def _tour(self, frames, websocket) -> None:
        async with self._lock:
            await self._enchainer(frames, websocket)
        leftover = [np.zeros(0, dtype=np.float32)]
        await self.annoncer_mandats_prets(websocket, leftover)

    async def _enchainer(self, frames, websocket) -> None:
        leftover = [np.zeros(0, dtype=np.float32)]
        # Horloge monotone, jamais l'heure murale. BRAIN streame pendant
        # que MOUTH synthétise déjà les premiers tokens : les deux
        # étages se CHEVAUCHENT. ears / brain / mouth ne sont donc pas
        # des tranches disjointes qu'on additionnerait pour reconstituer
        # total. total est le mur d'horloge du tour (réception de la fin
        # du tour → dernière trame envoyée) ; il reste ≥ à la somme
        # parce qu'il englobe l'envoi, pas parce que les étages
        # s'enchaînent sans recouvrement.
        t_tour = time.monotonic()
        # La presence visuelle suit le tour de l'exterieur : elle ne participe a
        # aucune decision, elle raconte. Son emission ne peut pas retarder l'audio,
        # `emettre` rendant la main sans attendre le client (voir src/presence).
        presence = Presence(websocket)
        try:
            if not frames:
                print(
                    f"C10 t={time.monotonic():.3f} AUDIO_RECV n_trames=0 duree_s=0",
                    flush=True,
                )
                await self._envoyer(websocket, [])
                return

            audio = np.concatenate([trame.samples for trame in frames])
            duree_audio_s = float(audio.size) / SAMPLE_RATE
            print(
                f"C10 t={time.monotonic():.3f} AUDIO_RECV "
                f"n_trames={len(frames)} duree_s={duree_audio_s:.3f}",
                flush=True,
            )

            # Silence mesuré sur le signal, jamais déduit du transcript :
            # Whisper hallucine sur du vide (« Sous-titrage ST' 501 » observé
            # sur ce serveur), donc un transcript non vide ne prouve rien.
            if est_silence(audio):
                print(
                    f"EARS  : {duree_audio_s:.1f} s sous le seuil d'énergie — "
                    "silence, transcription sautée",
                    flush=True,
                )
                phrase = phrase_de_secours(
                    transcript="",
                    reply="",
                    brain_injoignable=False,
                    duree_audio_s=0.0,
                    # Ecoute continue : le micro est ouvert en permanence, donc
                    # un segment sans parole n'est pas une demande restee sans
                    # reponse. Annoncer le silence ferait parler en boucle.
                    mains_libres=self._mains_libres,
                )
                if phrase:
                    await self._dire_secours(
                        websocket,
                        leftover,
                        phrase=phrase,
                        transcript="",
                        t_tour=t_tour,
                        ears_ms=0.0,
                        brain_ms=0.0,
                    )
                else:
                    await self._envoyer(websocket, [])
                return

            # Au-delà de la limite on sait déjà que la transcription
            # sera mauvaise : on l'économise, et on dit la longueur.
            if duree_audio_s > LIMITE_ENONCE_S:
                print(
                    f"EARS  : {duree_audio_s:.1f} s — au-delà de "
                    f"{LIMITE_ENONCE_S:.0f} s, transcription sautée",
                    flush=True,
                )
                phrase = phrase_de_secours(
                    transcript="",
                    reply="",
                    brain_injoignable=False,
                    duree_audio_s=duree_audio_s,
                )
                if phrase:
                    await self._dire_secours(
                        websocket,
                        leftover,
                        phrase=phrase,
                        transcript="",
                        t_tour=t_tour,
                        ears_ms=0.0,
                        brain_ms=0.0,
                    )
                else:
                    await self._envoyer(websocket, [])
                return

            presence.emettre("ecoute")
            await presence.vider()
            # Un seul « reflexion » par tour : la boucle voit passer des centaines
            # de tokens, et la deduplication de Presence ne suffirait pas puisque
            # « escalade » peut s'intercaler entre deux.
            presence_reflexion = [True]
            t_ears = time.monotonic()
            result = await self.asr.transcribe(audio)
            ears_ms = (time.monotonic() - t_ears) * 1000.0
            prompt = (result.get("text") or "").strip()
            print(
                f"C10 t={time.monotonic():.3f} TRANSCRIPT {prompt!r} "
                f"ears_ms={ears_ms:.0f}",
                flush=True,
            )
            print(
                f"EARS  : \"{prompt}\" — {result.get('latency_ms', 0):.0f} ms",
                flush=True,
            )
            if jeter_tour_bruit(
                prompt,
                result.get("segments"),
                mains_libres=self._mains_libres,
            ):
                print(
                    f'EARS  : segment rejeté (bruit) "{prompt}"',
                    flush=True,
                )
                await self._envoyer(websocket, [])
                return
            if not prompt:
                print("EARS  : rien transcrit", flush=True)
                phrase = phrase_de_secours(
                    transcript=prompt,
                    reply="",
                    brain_injoignable=False,
                    duree_audio_s=duree_audio_s,
                )
                if phrase:
                    await self._dire_secours(
                        websocket,
                        leftover,
                        phrase=phrase,
                        transcript=prompt,
                        t_tour=t_tour,
                        ears_ms=ears_ms,
                        brain_ms=0.0,
                    )
                else:
                    await self._envoyer(websocket, [])
                return

            jev = getattr(self, "_jev", None)
            if jev is not None and self._mains_libres and self._fenetre.engagee():
                # Conversation en cours : elle a ete adressee il y a peu, donc
                # ce qui suit lui est destine. « bonjour » seul score 0.31 chez
                # JeV, sous une phrase de television — aucun seuil ne le
                # rattrape, seule une memoire courte le peut.
                print("JEV   : conversation en cours — evaluation sautee", flush=True)
                await self._ouvrir_conversation()
                jev = None
            if jev is not None and self._mains_libres and nom_du_produit_prononce(prompt):
                # Elle est nommee : l'intention est certaine et verifiee en
                # local. Mesure du 2026-09-20 : JeV note « Hyper Ambient »
                # seul a 0.39, sous tout seuil utilisable. On evite l'appel
                # distant, son cout et ses ~250 ms.
                print("JEV   : nommee — evaluation distante inutile", flush=True)
                await self._ouvrir_conversation()
                jev = None
            if jev is not None and self._mains_libres:
                evaluation = await jev.evaluate(prompt)
                if jev_doit_ignorer(evaluation, mains_libres=True):
                    print(
                        "JEV   : pas adressée à l'assistante — tour ignoré",
                        flush=True,
                    )
                    self._tampon_ambiant.deposer(prompt, time.monotonic())
                    presence.emettre("repos")
                    await presence.vider()
                    await self._envoyer(websocket, [])
                    return
                # JeV a tranche « adressee » : la conversation commence.
                await self._ouvrir_conversation()
                harness = getattr(
                    getattr(evaluation, "signals", None), "named_harness", None
                )
                if harness:
                    print(
                        "JEV   : harnais nommé (observation, aucun envoi)",
                        flush=True,
                    )
                from src.i18n import langue as langue_session

                if reveil_court_suffit(prompt, langue=langue_session()):
                    print(
                        "JEV   : interpellation sans demande — reveil court",
                        flush=True,
                    )
                    phrase = phrase_de_reveil(langue=langue_session())
                    self._noter_conversation("Toi", prompt)
                    self._noter_conversation("hyper-ambient", phrase)
                    presence.emettre("parole")
                    await presence.vider()
                    await self._dire_secours(
                        websocket,
                        leftover,
                        phrase=phrase,
                        transcript=prompt,
                        t_tour=t_tour,
                        ears_ms=ears_ms,
                        brain_ms=0.0,
                    )
                    presence.emettre("repos")
                    await presence.vider()
                    return

            self._noter_conversation("Toi", prompt)
            if self._memoire.doit_fermer(
                mains_libres=self._mains_libres, maintenant=time.monotonic()
            ):
                garde = self._fermer_conversation()
                if garde:
                    print(f"JEV   : {garde}", flush=True)
                    self._noter_conversation("hyper-ambient", garde)
            ambiant = self._tampon_ambiant.fournir(prompt, time.monotonic())
            prompt_modele = f"{ambiant}\n{prompt}" if ambiant else prompt

            ttft_ms = None
            amorces: list[str] = []
            reponse: list[str] = []
            brain_error = None
            brain_ms = 0.0
            mouth_ms = 0.0
            t_derniere_trame = None
            outils_ce_tour: list[dict] = []

            # Départ commun : le flux BRAIN alimente MOUTH en recouvrement.
            t_brain_mouth = time.monotonic()

            async def deltas():
                nonlocal ttft_ms, brain_error, brain_ms
                # Vrai entre le retour d'un outil et le mot suivant : la phrase
                # du modèle a été interrompue par l'appel, il faut la recoudre.
                recoudre = False
                async for chunk in self._flux_brain(prompt_modele):
                    if presence_reflexion[0]:
                        presence_reflexion[0] = False
                        presence.emettre("reflexion")
                    if chunk.get("ttft_ms") is not None:
                        ttft_ms = chunk["ttft_ms"]
                    # `.get`, pas `[...]` : les chunks de la boucle d'outils ne
                    # portent ni `stop_reason` ni `ttft_ms`. L'indexation directe
                    # levait KeyError au premier appel d'outil, le garde-fou de
                    # `_enchainer` l'avalait, et le tour mourait sans un mot.
                    if chunk.get("stop_reason") == "error":
                        brain_error = chunk.get("error", "unknown")
                    # Un chunk d'outil ne porte pas de texte : il porte une
                    # attente. C'est la seule chose qui doive s'entendre ici —
                    # le nom de l'outil, ses arguments et son resultat restent
                    # hors de la voix.
                    if chunk.get("channel") == "tool":
                        if chunk.get("phase") == "call":
                            nom_outil = chunk.get("tool") or "outil"
                            harnais = NOM_HARNAIS_PAR_OUTIL.get(nom_outil, nom_outil)
                            self._noter_conversation(
                                f"→ {harnais}", question_d_outil(chunk)
                            )
                            # Codex et Claude ont un handler de mandat : il
                            # répond tout de suite par son accusé. Annoncer ici
                            # une attente de vingt secondes serait faux et
                            # répéterait la phrase qui suit.
                            spec = (
                                self.registre.get(chunk.get("tool", ""))
                                if self.registre is not None
                                else None
                            )
                            if spec is not None and hasattr(
                                spec.handler, "registre_mandats"
                            ):
                                continue
                            phrase = annonce_outil(chunk.get("tool", ""))
                            # Comptee comme une amorce : c'est une phrase
                            # d'attente, pas une reponse. Recollee au texte, le
                            # rapport lirait « Je demande a Codex, un instant.
                            # Il y a neuf fichiers » comme une seule phrase.
                            amorces.append(phrase)
                            print(
                                f"OUTIL : {chunk.get('tool')} — \"{phrase}\"",
                                flush=True,
                            )
                            await self._dire_maintenant(websocket, phrase, leftover)
                            # L'appel sort de la machine : c'est une escalade,
                            # au sens ou la fenetre l'affiche deja.
                            presence.emettre("escalade")
                            await presence.vider()
                        else:
                            # Résultat rendu, ou refus de la porte : le
                            # prochain mot du modèle reprend là où l'appel
                            # l'avait coupé.
                            recoudre = True
                            contenu = (chunk.get("content") or "").strip()
                            if contenu:
                                if len(contenu) > MAX_TOOL_CONTENT_CHARS:
                                    keep = MAX_TOOL_CONTENT_CHARS - 4
                                    contenu = contenu[:keep].rstrip() + " […]"
                                outils_ce_tour.append(
                                    {
                                        "name": chunk.get("tool") or "outil",
                                        "content": contenu,
                                    }
                                )
                        continue
                    if not chunk.get("delta"):
                        continue
                    # Le routeur marque « flush » les phrases d'attente
                    # (« Un instant. ») qu'il emet AVANT d'interroger le
                    # modele distant. Les faire passer par le flux normal les
                    # ferait attendre 24 caracteres et une ponctuation : la
                    # phrase qui existe pour couvrir l'attente arriverait
                    # apres l'attente. On les prononce donc tout de suite,
                    # hors du flux.
                    if chunk.get("flush"):
                        # Comptees a part, jamais avec la reponse : recollees,
                        # elles faisaient lire « Un instant. Je suis juste la »
                        # comme une seule phrase dans le rapport. Elles ne vont
                        # PAS non plus en memoire : « Un instant. » n'est pas une
                        # reponse, et la relire au tour suivant apprendrait au
                        # modele a temporiser au lieu de repondre.
                        amorces.append(chunk["delta"])
                        print(
                            f"BRAIN : {chunk.get('channel', 'flush')} — "
                            f"\"{chunk['delta']}\"",
                            flush=True,
                        )
                        await self._dire_maintenant(
                            websocket, chunk["delta"], leftover
                        )
                        # La phrase d'attente n'existe que sur escalade : c'est le
                        # seul signal fiable qu'on a que la question est partie au
                        # loin, et il arrive avant la reponse distante.
                        presence.emettre("escalade")
                        await presence.vider()
                        continue
                    texte = chunk["delta"]
                    # La couture entre deux tours de boucle. Mesuré deux fois
                    # sur deux sur la chaîne réelle : « Je lui demande.Le
                    # fichier router.py… ». MOUTH découpe sur la ponctuation,
                    # et un point collé au mot suivant ne fait pas frontière :
                    # les deux phrases partaient d'un seul souffle.
                    if recoudre:
                        recoudre = False
                        if (
                            reponse
                            and not reponse[-1][-1:].isspace()
                            and not texte[:1].isspace()
                        ):
                            texte = " " + texte
                    reponse.append(texte)
                    yield texte
                brain_ms = (time.monotonic() - t_brain_mouth) * 1000.0

            t_gen = time.perf_counter()
            n_chunks = 0
            # Un rechantillonneur pour tout le flux de ce tour. MOUTH sort par
            # blocs de 80 ms ; les convertir un par un remettait les bords du
            # filtre a zero douze fois par seconde, ce qui s'entendait comme un
            # hachurage. Celui-ci porte la queue du filtre d'un bloc au suivant.
            flux_16k = RechantillonneurContinu(
                int(getattr(self.tts, "sample_rate", SAMPLE_RATE)), SAMPLE_RATE
            )
            async for out in self.tts.synthesize_stream(deltas()):
                pcm = flux_16k.pousser(_vers_float32(out.get("audio", [])))
                trames = _trames_depuis_pcm(pcm, leftover)
                if not trames:
                    continue
                n_chunks += 1
                if n_chunks == 1:
                    # Première trame synthétisée — et déjà partie, avant
                    # tout rapport : NFR-01 se joue sur mic_to_audible.
                    mouth_ms = (time.monotonic() - t_brain_mouth) * 1000.0
                    print(
                        f"MOUTH : premier audio après {(time.perf_counter() - t_gen) * 1000:.0f} ms",
                        flush=True,
                    )
                await self._envoyer(websocket, trames)
                t_derniere_trame = time.monotonic()
                # Apres l'envoi, jamais avant : la voix passe d'abord.
                presence.emettre("parole")
                await presence.vider()

            # La queue retenue dans le filtre appartient a la phrase : sans ce
            # vidage, les dernieres millisecondes du dernier mot restent dedans.
            reste_16k = flux_16k.vider()
            if reste_16k.size:
                queue = _trames_depuis_pcm(reste_16k, leftover) + _vider_reliquat(leftover)
            else:
                queue = _vider_reliquat(leftover)
            if queue:
                if n_chunks == 0:
                    mouth_ms = (time.monotonic() - t_brain_mouth) * 1000.0
                await self._envoyer(websocket, queue)
                t_derniere_trame = time.monotonic()

            # `text` ne porte plus que la reponse : les amorces partent a part,
            # dans un champ dedie du rapport.
            text, texte_amorces = composer_rapport(amorces, reponse)

            # La memoire ne retient que la reponse utile : les phrases
            # d'attente sont du remplissage de latence, pas du contenu.
            if text:
                message_utilisateur = {"role": "user", "content": prompt}
                message_assistant = {"role": "assistant", "content": text}
                self._historique.extend([message_utilisateur, message_assistant])
                self._memoire.retenir(
                    prompt, text, timestamp=time.monotonic()
                )
                if outils_ce_tour:
                    self._historique_outils_ephemeres.extend(
                        [message_utilisateur, message_assistant]
                    )
                del self._historique[:-MEMOIRE_MESSAGES]
            if outils_ce_tour:
                self._dernier_outils = outils_ce_tour

            if not text:
                print(f"BRAIN : rien produit — {brain_error}", flush=True)
                phrase = phrase_de_secours(
                    transcript=prompt,
                    reply=text,
                    brain_injoignable=brain_error is not None,
                    duree_audio_s=duree_audio_s,
                )
                if phrase:
                    await self._dire_secours(
                        websocket,
                        leftover,
                        phrase=phrase,
                        transcript=prompt,
                        t_tour=t_tour,
                        ears_ms=ears_ms,
                        brain_ms=brain_ms,
                    )
                    return
            else:
                suffixe = "..." if len(text) > 120 else ""
                print(f"BRAIN : \"{text[:120]}{suffixe}\"", flush=True)
                if ttft_ms is not None:
                    print(f"BRAIN : TTFT {ttft_ms:.0f} ms", flush=True)
                self._noter_conversation("hyper-ambient", text)

            # Le rapport suit la première trame (ici : toutes les trames
            # utiles). On a transcript, reply, et total une fois la
            # dernière trame partie. Le marqueur vide vient après.
            if t_derniere_trame is not None:
                total_ms = (t_derniere_trame - t_tour) * 1000.0
                await self._envoyer_rapport(
                    websocket,
                    transcript=prompt,
                    reply=text,
                    amorces=texte_amorces,
                    timings_ms={
                        "ears": ears_ms,
                        "brain": brain_ms,
                        "mouth": mouth_ms,
                        "total": total_ms,
                    },
                )

            presence.emettre("repos")
            await presence.vider()
            await self._envoyer(websocket, [])
        except Exception as exc:
            # Le type et la trace, pas seulement `{exc}` : une exception dont le
            # message est vide s'imprimait « tour interrompu : » et ne disait
            # rien du tout. Un tour qui meurt en silence est deja assez penible
            # a l'oreille pour ne pas l'etre aussi dans le journal.
            import traceback

            print(
                f"tour interrompu : {type(exc).__name__}: {exc}", flush=True
            )
            print(traceback.format_exc(), flush=True)
            try:
                await self._envoyer(websocket, [])
            except Exception:
                return


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--dry-run" in argv:
        raise SystemExit(dry_run())
    injectees, cles_carte = _appliquer_env_boot()
    if injectees:
        print(
            "ENV   : "
            + ", ".join(sorted(injectees))
            + " depuis .env.local",
            flush=True,
        )
    if cles_carte:
        print(
            "CARTE : "
            + ", ".join(sorted(cles_carte))
            + " depuis carte_figee.env",
            flush=True,
        )
    secret = lire_secret()
    pipeline = HostPipeline()
    app = create_transport_app(
        secret=secret,
        on_frames=pipeline.on_frames,
        peer_address_of=pipeline.peer_address_of,
        on_options=pipeline.on_options,
    )
    # FastAPI 0.141 a retire add_event_handler : les evenements startup/shutdown
    # passent desormais par un gestionnaire de contexte lifespan. On charge les
    # modeles une seule fois, a l'ouverture, et jamais par tour de parole.
    @contextlib.asynccontextmanager
    async def lifespan(_app):
        await pipeline.load()
        journal: list = []
        rapport = await prechauffer(
            ears=pipeline.asr,
            mouth=pipeline.tts,
            brain=pipeline.brain,
            rechantillonner=_rechantillonner,
            journal=journal,
        )
        for entree in journal:
            print(entree, flush=True)
        for etage, duree in rapport.durees_ms.items():
            print(f"{etage} : préchauffé en {duree:.0f} ms", flush=True)
        print(f"écoute sur {HOST}:{PORT} /hostagent", flush=True)
        try:
            yield
        finally:
            await pipeline.close()

    app.router.lifespan_context = lifespan

    import uvicorn

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        ws_max_size=16 * 1024 * 1024,
        # websockets 17 a supprime l'API historique qu'utilise l'implementation
        # « websockets » d'uvicorn : la poignee de main s'ouvrait puis restait
        # muette jusqu'au timeout du client. L'implementation sans-io est celle
        # prevue pour cette version.
        # Choisissable, parce que c'est ici que la voix se perd. Mesure du
        # 13 septembre, client et serveur tous deux dans le conteneur, sans NAT
        # entre eux : EARS transcrit, MOUTH rend son premier audio à 692 ms, et
        # le premier envoi meurt en `ClientDisconnected` — uvicorn voit la
        # connexion perdue quand le client, lui, attend toujours. Pouvoir
        # changer d'implémentation sans toucher au code est le seul moyen de
        # trancher entre « notre code » et « cette pile-là ».
        ws=os.getenv("HOSTAGENT_WS_IMPL", "websockets-sansio"),
    )


if __name__ == "__main__":
    main()
