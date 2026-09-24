"""Mode abonnement ChatGPT : une session `codex app-server` gardée ouverte.

Mesure du 24/09 : `codex exec` relancé à chaque tour coûte ~4,7 s ; un
app-server gardé ouvert répond en ~1,4 s, garde la mémoire du fil, et
`model/list` donne la liste des modèles en direct pour les Réglages.

C'est le binaire `codex` non modifié, connecté par l'utilisateur à son
abonnement ChatGPT. La réflexion est au plus bas que le modèle accepte
(`low`), le bac à sable est en lecture seule et aucune approbation n'est
demandée : la voix converse, elle ne travaille pas dans le dépôt.
"""
from __future__ import annotations

import json

from native import sans_console
import queue
import shutil
import subprocess
import tempfile
import threading
from typing import Callable, Iterator, Optional

from native.clibridge.conversation import message_pour_session

MODELE_PAR_DEFAUT = "gpt-6-luna"
DELAI_S = 90.0

# La voix converse, les harnais agissent. Sans ces coupures, GPT-6-Luna
# lançait des commandes (shell, computer_use) au lieu de répondre : 25 s
# sans un mot, séance du 24/09. La recherche web reste permise.
OUTILS_COUPES = (
    "shell_tool", "unified_exec", "computer_use", "browser_use", "browser_use_external",
    "in_app_browser", "apps", "plugins", "multi_agent", "image_generation", "view_image",
    "in_app_local_automation", "goals", "sleep_tool", "skill_search", "tool_suggest",
    "code_mode_host", "worktrees",
)


def _systeme(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return (m.get("content") or "").strip()
    return ""


class SessionCodex:
    def __init__(
        self,
        *,
        modele: str = MODELE_PAR_DEFAUT,
        effort: str = "low",
        exe: Optional[str] = None,
        lancer: Callable[..., object] = subprocess.Popen,
        prechauffage: bool = True,
    ) -> None:
        self.modele = modele
        self.effort = effort or "low"
        self.exe = exe or shutil.which("codex") or "codex"
        self._lancer = lancer
        self._prechauffage = prechauffage
        self._verrou = threading.RLock()
        self._proc = None
        self._file: "queue.Queue[dict]" = queue.Queue()
        self._reponses: dict[int, "queue.Queue[dict]"] = {}
        self._compteur = 0
        self._fil: Optional[str] = None
        self._systeme: Optional[str] = None
        self.derniere_reponse: Optional[str] = None
        # Dossier vide : aucun AGENTS.md de projet n'est découvert.
        self._dossier = tempfile.mkdtemp(prefix="ha-conversation-codex-")

    # -- transport JSON-RPC ------------------------------------------------

    def _lire(self, proc) -> None:
        for ligne in proc.stdout:
            if not ligne.strip():
                continue
            try:
                message = json.loads(ligne)
            except ValueError:
                continue
            ident = message.get("id")
            if ident is not None and "method" not in message and ident in self._reponses:
                self._reponses[ident].put(message)
            elif "method" in message:
                self._file.put(message)

    def _ecrire(self, objet: dict) -> None:
        self._proc.stdin.write(json.dumps(objet, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _requete(self, methode: str, params: dict) -> dict:
        self._compteur += 1
        ident = self._compteur
        boite: "queue.Queue[dict]" = queue.Queue()
        self._reponses[ident] = boite
        self._ecrire({"id": ident, "method": methode, "params": params})
        try:
            message = boite.get(timeout=DELAI_S)
        finally:
            self._reponses.pop(ident, None)
        if "error" in message:
            raise RuntimeError(f"{methode}: {message['error']}")
        return message.get("result") or {}

    def _demarrer(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = self._lancer(
            [self.exe, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self._dossier,
            text=True,
            encoding="utf-8",
            **sans_console.options(),
        )
        self._fil = None
        threading.Thread(target=self._lire, args=(self._proc,), daemon=True).start()
        self._requete("initialize", {"clientInfo": {"name": "hyper-ambient", "version": "0.1"}})
        self._ecrire({"method": "initialized"})

    def _nouveau_fil(self, systeme: str) -> str:
        resultat = self._requete(
            "thread/start",
            {
                "model": self.modele,
                "cwd": self._dossier,
                "sandbox": "read-only",
                "approvalPolicy": "never",
                "ephemeral": True,
                "developerInstructions": systeme,
                "config": {
                    "model_reasoning_effort": self.effort,
                    **{f"features.{outil}": False for outil in OUTILS_COUPES},
                },
            },
        )
        self._fil, self._systeme = resultat["thread"]["id"], systeme
        self.derniere_reponse = None
        return self._fil

    def _tour(self, fil: str, texte: str) -> Iterator[str]:
        resultat = self._requete(
            "turn/start",
            {"threadId": fil, "input": [{"type": "text", "text": texte}], "effort": self.effort},
        )
        # Un tour abandonné par le client (délai dépassé) finit quand même côté
        # app-server : ses deltas restent en file. Seul ce tour-ci compte (24/09).
        tour = ((resultat.get("turn") or {}).get("id")) or None
        while True:
            message = self._file.get(timeout=DELAI_S)
            params = message.get("params") or {}
            if params.get("threadId") not in (None, fil):
                continue
            if message.get("method") == "item/agentMessage/delta" and params.get("delta"):
                if tour and params.get("turnId") not in (None, tour):
                    continue
                yield params["delta"]
            elif message.get("method") == "turn/completed":
                fini = (params.get("turn") or {}).get("id")
                if tour and fini not in (None, tour):
                    continue
                return

    # -- interface commune aux sessions -----------------------------------

    def prechauffer(self, systeme: str) -> None:
        """Ouvre l'app-server et fait un échange muet : la connexion est chaude."""
        with self._verrou:
            self._demarrer()
            if self._prechauffage:
                fil = self._nouveau_fil(systeme)
                for _ in self._tour(fil, "Réponds seulement : prête."):
                    pass
                self._fil = None

    def modeles(self) -> list[dict]:
        with self._verrou:
            self._demarrer()
            donnees = self._requete("model/list", {}).get("data") or []
        return [
            {"id": m["id"], "label": m.get("displayName") or m["id"]}
            for m in donnees
            if m.get("id") and not m.get("hidden")
        ]

    def repondre(self, messages: list[dict]) -> Iterator[str]:
        with self._verrou:
            self._demarrer()
            systeme = _systeme(messages)
            texte, neuve = message_pour_session(messages, self.derniere_reponse)
            if neuve:
                texte, _ = message_pour_session(messages, None)
            fil = self._fil
            if neuve or fil is None or systeme != self._systeme:
                fil = self._nouveau_fil(systeme)
            reponse = []
            for morceau in self._tour(fil, texte):
                reponse.append(morceau)
                yield morceau
            self.derniere_reponse = "".join(reponse).strip() or None
