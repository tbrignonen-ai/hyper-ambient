#!/usr/bin/env python3
"""Point d'entrée conteneur : transport host-agent + chaîne EARS / BRAIN / MOUTH.

    python3 dev/scripts/serve_hostagent.py
    python native/hostagent/talk.py
"""
from __future__ import annotations

import contextlib

import asyncio
import ipaddress
import os
import sys
import time
from pathlib import Path

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
from src.mouth.output_gain import appliquer_gain_doux
from src.brain.tool_loop import run_tool_loop
from src.brain.tools import ToolRegistry
from src.brain.tools_calculator import register_calculator
from src.brain.tools_codex import register_ask_codex
from src.brain.tools_cli import register_ask_claude
from src.brain.tools_muse import register_ask_muse
from src.brain.tools_web import register_web_search
from src.gate.permission import Gate

# Six messages, soit trois echanges. Assez pour qu'un « oui, vas-y » ait un
# antecedent ; assez court pour que le contexte du modele local ne gonfle pas
# la latence a chaque tour.
MEMOIRE_MESSAGES = 6

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
    }
)
_CARTE_FIGEE = _ROOT / "dev" / "scripts" / "carte_figee.env"


def _est_cle_modele(cle: str) -> bool:
    return cle in _CLES_MODELE or cle.startswith(_PREFIXES_MODELE)


def _valeur_utile(valeur: object) -> bool:
    if valeur is None:
        return False
    return bool(str(valeur).replace("\r", "").strip())


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
        if cle not in _CLES_OUTILS or _est_cle_modele(cle):
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
    """Jetons d'outils puis carte figée. Ordre figé : C1 ne déplace pas les modèles."""
    outils = charger_env_local(environ=environ)
    carte = charger_carte_figee(environ=environ)
    return outils, carte


def jev_ignore_tour(evaluation) -> bool:
    """True seulement si JeV a tranché : la phrase n'est pas adressée à MOTHER.

    ``None`` (pas de clé, timeout, erreur) = repli bouton : on n'ignore pas.
    Un harnais nommé n'a aucun effet ici : aucun modèle n'envoie une tâche.
    """
    if evaluation is None:
        return False
    signals = getattr(evaluation, "signals", None)
    if signals is None:
        return False
    return not bool(signals.addressed_to_mother)


def construire_registre(client=None) -> ToolRegistry:
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
            registre, token=jeton, client=client, timeout_s=DELAI_OUTIL_S
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
            registre, token=jeton_cli, client=client, timeout_s=DELAI_OUTIL_CLAUDE_S
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


def construire_ears():
    """Construit EARS depuis l'environnement, sans charger les poids.

    ``faster-whisper`` reste un repli explicite. L'option 2 choisit Qwen3-ASR
    via ``EARS_BACKEND=qwen3`` ; les imports restent paresseux afin qu'un
    backend absent n'empêche pas l'autre de démarrer.
    """
    backend = os.getenv("EARS_BACKEND", "faster-whisper").strip().lower()
    default_model = (
        "0.6B" if backend in {"qwen3", "qwen3-asr"} else "large-v3-turbo"
    )
    model_size = os.getenv("EARS_MODEL", default_model)
    language = os.getenv("EARS_LANGUAGE", "fr")
    device = os.getenv("EARS_DEVICE", "cuda")
    compute_type = os.getenv("EARS_COMPUTE_TYPE")

    if backend in {"qwen3", "qwen3-asr"}:
        from src.ears.qwen3_asr import Qwen3ASR

        classe = Qwen3ASR
    elif backend in {"faster-whisper", "faster_whisper", "whisper"}:
        from src.ears.faster_whisper_asr import FasterWhisperASR

        classe = FasterWhisperASR
    else:
        raise ValueError(
            f"EARS_BACKEND inconnu: {backend!r} (attendu: qwen3 ou faster-whisper)"
        )

    kwargs = {"model_size": model_size, "language": language, "device": device}
    if compute_type:
        kwargs["compute_type"] = compute_type
    hotwords = os.getenv("EARS_HOTWORDS", "").strip()
    if hotwords and backend in {"faster-whisper", "faster_whisper", "whisper"}:
        kwargs["hotwords"] = hotwords
    return backend, classe(**kwargs)


def lire_secret() -> str:
    """Secret d'installation, ou valeur de développement si la variable manque."""
    secret = os.environ.get("MOTHER_HOSTAGENT_SECRET")
    if secret:
        return secret
    print(
        "ATTENTION : MOTHER_HOSTAGENT_SECRET est absent. "
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
    return "".join(reponse).strip(), " ".join(a.strip() for a in amorces if a.strip())


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
        self.brain = None
        self.tts = None
        # Le registre est vide tant que `load` ne l'a pas garni : un tour joue
        # sans lui doit rester le tour d'avant, pas un tour degrade.
        self.registre: ToolRegistry | None = None
        self.porte: Gate | None = None
        self._client_outils = None
        self._jev = None
        self._websocket = None
        self._lock = asyncio.Lock()
        self.output_gain_db = float(os.getenv("MOUTH_OUTPUT_GAIN_DB", "0"))

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
        from src.brain.factory import build_brain_with_fallback
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
        voix = os.getenv("MOUTH_VOICE", VOIX_PIPER)

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

        self.brain = await build_brain_with_fallback()
        health = await self.brain.health()
        print(
            f"BRAIN : {self.brain.name} @ {self.brain.api_endpoint} — {health['detail']}",
            flush=True,
        )

        # Les outils. Le client HTTP vit aussi longtemps que le pipeline : le
        # rouvrir par appel ajouterait une poignee de main TCP au milieu d'un
        # tour de parole, sur un chemin qui compte deja en dizaines de secondes.
        import httpx

        self._client_outils = httpx.AsyncClient()
        self.registre = construire_registre(client=self._client_outils)
        self.porte = construire_porte()
        actifs = verifier_registre(self.registre)
        if actifs:
            noms = ", ".join(sorted(actifs))
            print(f"OUTILS: {noms} — porte en mode {self.porte.mode}", flush=True)
        else:
            print(
                "OUTILS: aucun backend configure — tour de parole sans outil",
                flush=True,
            )

        from src.ears.jev_reflexe import JevReflexe

        self._jev = JevReflexe()
        print("JEV   : réflexe en entrée (repli silencieux sans clé)", flush=True)

        # MOUTH : Pocket TTS par défaut. Piper reste joignable par MOUTH_BACKEND=piper,
        # parce qu'il ne coûte aucune VRAM — c'est le repli si le GPU est saturé.
        backend = os.getenv("MOUTH_BACKEND", "pocket").lower()
        if backend == "pocket":
            from src.mouth.pocket_tts import PocketTTS

            langue = os.getenv("MOUTH_LANGUAGE", "french_24l")
            nom_voix = os.getenv("MOUTH_VOICE_NAME", "estelle")
            profil = os.getenv("MOUTH_PROFILE", "aurora")
            # pocket-tts n'a ni reglage de vitesse ni reglage de hauteur.
            # MOUTH_DEMI_TONS descend la voix par reechantillonnage, ce qui
            # ralentit la diction dans le meme rapport : -3 donne une tierce
            # mineure plus bas et 19 % plus lent. Device cpu : 0 VRAM, le
            # GPU reste a EARS / llama-server.
            demi_tons = float(os.getenv("MOUTH_DEMI_TONS", "0"))
            device = os.getenv("MOUTH_DEVICE", "cpu")
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
            style = os.getenv("MOUTH_STYLE", "F5")
            vitesse = float(os.getenv("MOUTH_SPEED", "0.88"))
            profil = os.getenv("MOUTH_PROFILE", "aurora")
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
            nom_voix = os.getenv("MOUTH_VOICE_NAME", "Sofia")
            langue = os.getenv("MOUTH_LANGUAGE", "fr")
            device = os.getenv("MOUTH_DEVICE", "cpu")
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
            demi_tons = float(os.getenv("MOUTH_DEMI_TONS", "0"))
            profil = os.getenv("MOUTH_PROFILE", "aurora")
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

    async def close(self) -> None:
        if self.brain is not None:
            await self.brain.close()
        if self._client_outils is not None:
            await self._client_outils.aclose()
            self._client_outils = None

    def _flux_brain(self, prompt: str):
        """Le flux du tour : sous boucle d'outils si le registre est garni.

        Le registre vide rend **exactement** l'appel d'avant, sans `tools` dans
        la charge utile. Un registre garni passe par la boucle : le routeur
        retire les schemas sur un REFLEXE, et la boucle n'execute qu'un outil
        par tour. Brancher Codex ne doit rien changer a « Bonjour. ».
        """
        historique = list(self._historique)
        if self.registre is not None and len(self.registre):
            return run_tool_loop(
                self.brain,
                prompt,
                self.registre,
                self.porte,
                history=historique,
                max_tool_calls=1,
            )
        return self.brain.query_streaming(prompt, history=historique)

    async def _envoyer(self, websocket, trames: list[AudioFrame]) -> None:
        """Envoie des paquets d'une seconde, ou un marqueur vide de fin de tour."""
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

    async def _dire_maintenant(self, websocket, phrase: str, leftover: list) -> None:
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
            if jev is not None:
                evaluation = await jev.evaluate(prompt)
                if jev_ignore_tour(evaluation):
                    print(
                        "JEV   : pas adressée à MOTHER — tour ignoré",
                        flush=True,
                    )
                    presence.emettre("repos")
                    await presence.vider()
                    await self._envoyer(websocket, [])
                    return
                harness = getattr(
                    getattr(evaluation, "signals", None), "named_harness", None
                )
                if harness:
                    print(
                        "JEV   : harnais nommé (observation, aucun envoi)",
                        flush=True,
                    )

            ttft_ms = None
            amorces: list[str] = []
            reponse: list[str] = []
            brain_error = None
            brain_ms = 0.0
            mouth_ms = 0.0
            t_derniere_trame = None

            # Départ commun : le flux BRAIN alimente MOUTH en recouvrement.
            t_brain_mouth = time.monotonic()

            async def deltas():
                nonlocal ttft_ms, brain_error, brain_ms
                # Vrai entre le retour d'un outil et le mot suivant : la phrase
                # du modèle a été interrompue par l'appel, il faut la recoudre.
                recoudre = False
                async for chunk in self._flux_brain(prompt):
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
                self._historique.append({"role": "user", "content": prompt})
                self._historique.append({"role": "assistant", "content": text})
                del self._historique[:-MEMOIRE_MESSAGES]

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


def main() -> None:
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
