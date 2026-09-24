"""Cerveau distant « abonnement » : la conversation passe par le Claude Code
de l'utilisateur, via le pont hôte (`native/clibridge`).

Même interface qu'un distant d'API : le routeur ne voit pas la différence.
Le pont garde une session vivante (0,5 à 1 s au premier mot, mesuré le 24/09)
au lieu de relancer le CLI à chaque tour (~4,7 s).

Le CLI ne fait pas d'appel de fonction à notre façon. Il garde sa propre
recherche web ; pour les harnais (``ask_claude``, ``ask_codex``), le modèle
écrit une ligne ``<<ask_claude: demande>>`` que ce module retire de la voix
et rend comme un appel d'outil ordinaire (séance du 24/09). Les demandes
explicites (« demande à Claude… ») partent, elles, sans attendre le modèle.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from src.brain.tools import ToolCall

logger = logging.getLogger(__name__)

_ROLES = {"system", "user", "assistant"}


_OUVRE, _FERME = "<<", ">>"
_APPEL = re.compile(r"\s*(ask_\w+)\s*:\s*(.+)", re.S)
MAX_DESCRIPTION = 220


def _harnais(outils) -> List[Dict[str, str]]:
    """Les outils de harnais parmi les schémas déclarés (les autres restent
    au modèle lui-même : il a sa recherche web, il sait calculer)."""
    trouves = []
    for schema in outils or []:
        fonction = (schema or {}).get("function") or {}
        nom = fonction.get("name") or ""
        if nom.startswith("ask_"):
            trouves.append({
                "name": nom,
                "description": " ".join(str(fonction.get("description") or "").split())[:MAX_DESCRIPTION],
            })
    return trouves


def consignes_outils(outils) -> str:
    """Le canal vers les harnais, pour un modèle sans appel de fonction.

    L'envoi reste décidé par l'utilisateur : le modèle reconnaît sa demande,
    quelle qu'en soit la tournure, il n'en prend jamais l'initiative.
    """
    harnais = _harnais(outils)
    if not harnais:
        return ""
    lignes = "\n".join(f"- {h['name']} : {h['description']}" for h in harnais)
    exemple = "\n".join(
        f"<<{h['name']}: As-tu accès au web ? Fais un essai et dis-moi le résultat.>>"
        for h in harnais[:2]
    )
    return (
        "\n\nCANAL VERS LES HARNAIS. Ce canal existe et tu peux t'en servir : "
        "hyper-ambient lit les lignes ci-dessous dans ta réponse et les transmet "
        "au harnais, dans la session déjà ouverte avec lui, puis annonce sa réponse "
        "quand elle arrive.\n"
        f"{lignes}\n"
        "Quand la personne te demande de faire faire, vérifier, tester, lire ou dire "
        "quelque chose par l'un d'eux — quelle que soit la tournure (« demande à… », "
        "« teste par Claude », « vois avec Codex », « dans la session de… ») — ta "
        "réponse commence par une ligne par harnais concerné, sans rien avant :\n"
        "<<nom_de_l_outil: sa demande, fidèlement, complétée seulement de ce qu'il "
        "faut pour qu'elle se comprenne seule>>\n"
        "Exemple. La personne : « Demande à Codex et à Claude s'ils ont accès au "
        "web. » Ta réponse :\n"
        f"{exemple}\n"
        "Ne dis jamais que tu n'as pas de moyen de les joindre, et n'invente jamais "
        "leur réponse. N'envoie rien à un harnais que la personne n'a pas demandé ; "
        "pour tout le reste, réponds normalement, sans ces lignes."
    )


class ExtracteurOutils:
    """Retire les lignes ``<<ask_x: demande>>`` d'un flux de texte, morceau par
    morceau, et les note comme appels d'outil. Le reste passe tel quel."""

    def __init__(self, noms) -> None:
        self.noms = set(noms)
        self.appels: List[ToolCall] = []
        self._tampon = ""

    def _noter(self, corps: str) -> None:
        m = _APPEL.match(corps)
        if not m or m.group(1) not in self.noms:
            return
        question = " ".join(m.group(2).split())
        if question:
            self.appels.append(ToolCall(
                id=f"abonnement-{len(self.appels) + 1}", name=m.group(1),
                arguments={"question": question},
                raw_arguments=json.dumps({"question": question}, ensure_ascii=False),
            ))

    def pousser(self, texte: str) -> str:
        self._tampon += texte or ""
        sortie = []
        while True:
            debut = self._tampon.find(_OUVRE)
            if debut < 0:
                # Un « < » final peut ouvrir un marqueur au morceau suivant.
                garde = 1 if self._tampon.endswith("<") else 0
                sortie.append(self._tampon[: len(self._tampon) - garde])
                self._tampon = self._tampon[len(self._tampon) - garde:]
                break
            sortie.append(self._tampon[:debut])
            fin = self._tampon.find(_FERME, debut + len(_OUVRE))
            if fin < 0:
                self._tampon = self._tampon[debut:]
                break
            self._noter(self._tampon[debut + len(_OUVRE): fin])
            self._tampon = self._tampon[fin + len(_FERME):]
        return "".join(sortie)

    def finir(self) -> str:
        reste, self._tampon = self._tampon, ""
        if reste.startswith(_OUVRE):
            # Marqueur jamais refermé : on le prend quand même, sans le dire.
            self._noter(reste[len(_OUVRE):])
            return ""
        return reste


def _base(url: str) -> str:
    url = (url or "").rstrip("/")
    for suffixe in ("/ask", "/chat"):
        if url.endswith(suffixe):
            return url[: -len(suffixe)]
    return url


class SubscriptionBrain:
    # Pas d'appel de fonction natif : une demande explicite à un harnais part
    # sans attendre le modèle (voir serve_hostagent.flux_cerveau) ; les autres
    # passent par le protocole ``<<ask_x: …>>`` de ExtracteurOutils.
    supporte_outils = False

    def __init__(self, *, bridge_url: str, token: str, model: str = "claude-sonnet-5",
                 effort: str = "low", harnais: str = "claude",
                 timeout_s: float = 90.0) -> None:
        self.base = _base(bridge_url)
        self.token = token
        self.model = model or "claude-sonnet-5"
        # Réflexion au plus bas par défaut : la voix ne paie pas le raisonnement.
        self.effort = effort or "low"
        self.timeout_s = timeout_s
        self.client = None
        self.name = f"abonnement-{harnais}/{self.model}"
        # Les harnais déclarés au dernier tour qui en avait : les consignes
        # restent identiques d'un tour à l'autre, sinon le pont rouvre un fil.
        self._outils_connus: List[Dict[str, Any]] = []

    @property
    def api_endpoint(self) -> str:
        return f"{self.base}/chat"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def initialize(self):
        import httpx

        self.client = httpx.AsyncClient(timeout=self.timeout_s)
        # La session du pont démarre maintenant : la première phrase de
        # l'utilisateur ne paiera pas les ~5 s de démarrage du CLI.
        try:
            from src.mouth.normalize import VOICE_SYSTEM_PROMPT

            await self.client.post(
                f"{self.base}/prechauffer",
                headers=self._headers(),
                json={"model": self.model, "effort": self.effort, "system": VOICE_SYSTEM_PROMPT},
                timeout=5.0,
            )
        except Exception as exc:
            logger.warning(f"abonnement : préchauffage impossible ({type(exc).__name__})")

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def health(self) -> Dict[str, Any]:
        try:
            r = await self.client.get(f"{self.base}/models", headers=self._headers())
            ok = r.status_code == 200
            return {"ok": ok, "detail": f"{self.name} HTTP {r.status_code}"}
        except Exception as exc:
            return {"ok": False, "detail": f"{self.name} {type(exc).__name__}"}

    @staticmethod
    def _messages(prompt, system, history, messages) -> List[Dict[str, str]]:
        if messages:
            source = list(messages)
        else:
            source = list(history or []) + [{"role": "user", "content": prompt}]
        propres = [
            {"role": m["role"], "content": (m.get("content") or "").strip()}
            for m in source
            if m.get("role") in _ROLES and (m.get("content") or "").strip()
            and not m.get("tool_calls")
        ]
        propres = [m for m in propres if m["role"] != "system"]
        if system is None:
            system = next(
                (m.get("content") for m in source if m.get("role") == "system"), None
            )
        if system is None:
            from src.mouth.normalize import VOICE_SYSTEM_PROMPT as system
        return [{"role": "system", "content": system}] + propres

    async def query_streaming(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        messages: Optional[List[Dict[str, Any]]] = None,
        tools: Any = None,
        tool_choice: Any = None,
        **_kw,
    ) -> AsyncIterator[Dict[str, Any]]:
        if _harnais(tools):
            self._outils_connus = list(tools)
        noms = {h["name"] for h in _harnais(tools)}
        extracteur = ExtracteurOutils(noms) if noms else None
        envoyes = self._messages(prompt, system, history, messages)
        consignes = consignes_outils(self._outils_connus)
        if consignes:
            envoyes[0] = {"role": "system", "content": envoyes[0]["content"] + consignes}
        corps = {
            "messages": envoyes,
            "model": self.model,
            "effort": self.effort,
        }
        t0 = time.monotonic()
        premier = True
        async with self.client.stream(
            "POST", f"{self.base}/chat", headers=self._headers(), json=corps
        ) as reponse:
            if reponse.status_code != 200:
                yield {"delta": "", "stop_reason": "error", "ttft_ms": None,
                       "error": f"pont HTTP {reponse.status_code}"}
                return
            async for ligne in reponse.aiter_lines():
                if not ligne.strip():
                    continue
                evenement = json.loads(ligne)
                if evenement.get("error"):
                    yield {"delta": "", "stop_reason": "error", "ttft_ms": None,
                           "error": evenement["error"]}
                    return
                if evenement.get("delta"):
                    texte = evenement["delta"]
                    if extracteur is not None:
                        texte = extracteur.pousser(texte)
                    if not texte:
                        continue
                    yield {
                        "delta": texte,
                        "stop_reason": None,
                        "ttft_ms": (time.monotonic() - t0) * 1000.0 if premier else None,
                    }
                    premier = False
        if extracteur is not None:
            reste = extracteur.finir()
            if reste:
                yield {"delta": reste, "stop_reason": None, "ttft_ms": None}
            if extracteur.appels:
                yield {"delta": "", "stop_reason": "tool_calls", "ttft_ms": None,
                       "tool_calls": extracteur.appels}
                return
        yield {"delta": "", "stop_reason": "stop", "ttft_ms": None}

    async def query(self, prompt: str, **kw) -> Dict[str, Any]:
        t0 = time.monotonic()
        texte = ""
        async for chunk in self.query_streaming(prompt, **kw):
            texte += chunk.get("delta") or ""
        return {"response": texte, "stop_reason": "stop", "tokens_used": 0,
                "latency_ms": (time.monotonic() - t0) * 1000.0}
