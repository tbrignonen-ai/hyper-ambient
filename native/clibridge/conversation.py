"""Mode abonnement : une session Claude Code gardée ouverte pour converser.

Mesure du 24/09 : `claude -p` relancé à chaque tour coûte ~4,7 s quel que
soit le modèle — c'est le démarrage du CLI. Une session en flux JSON gardée
ouverte répond en 0,7 à 1 s, autant qu'une clé d'API. Le pont garde donc une
session vivante par modèle, plus une réserve déjà démarrée : un redémarrage
ne tombe jamais au milieu de la conversation.

C'est le binaire `claude` non modifié, connecté par l'utilisateur à son propre
abonnement — l'usage que la documentation Claude Code autorise. La réflexion
est réduite au minimum (`--effort low`, aucun jeton de réflexion), les réglages
et la mémoire de l'utilisateur ne sont pas chargés, et le seul outil est la
recherche web, pour que le mode abonnement garde l'accès au web.
"""
from __future__ import annotations

import json

from native import sans_console
import os
import shutil
import subprocess
import tempfile
import threading
from typing import Callable, Iterator, Optional

# L'alias suit toujours le dernier modèle de la famille. Le CLI n'a pas de
# commande qui liste les modèles : la liste est celle de sa documentation.
MODELES_CLAUDE = [
    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5 — équilibré (conseillé)"},
    {"id": "haiku", "label": "Claude Haiku — le plus rapide"},
    {"id": "opus", "label": "Claude Opus — le plus capable, plus lent"},
    {"id": "fable", "label": "Claude Fable"},
]

MODELE_PAR_DEFAUT = "claude-sonnet-5"

_ENTETE_CONTEXTE = "Pour mémoire, ce qui s'est dit depuis ta dernière réponse :"
_LIBELLES = {"user": "Utilisateur", "assistant": "Toi"}


def _texte(message: dict) -> str:
    return (message.get("content") or "").strip()


def message_pour_session(
    messages: list[dict], derniere_reponse: Optional[str]
) -> tuple[str, bool]:
    """Ce qu'il faut écrire à la session, et s'il faut une session neuve.

    La session a sa propre mémoire. On lui envoie la nouvelle réplique, plus
    ce qu'elle n'a pas vu depuis sa dernière réponse (annonce d'un harnais,
    réplique du réflexe local). Si sa dernière réponse n'apparaît plus dans
    l'historique, la conversation a changé : session neuve, tout le contexte.
    """
    dialogue = [m for m in messages if m.get("role") in _LIBELLES]
    resumes = [m.get("content", "").strip() for m in messages if m.get("compactage_resume")]
    if not dialogue:
        return "", derniere_reponse is not None
    courant = _texte(dialogue[-1])
    precedent = dialogue[:-1]

    neuve = True
    depuis = 0
    if derniere_reponse is not None:
        for i in range(len(precedent) - 1, -1, -1):
            if precedent[i].get("role") == "assistant" and _texte(precedent[i]) == derniere_reponse.strip():
                neuve = False
                depuis = i + 1
                break
    elif not precedent:
        neuve = True

    a_rappeler = [m for m in precedent[depuis:] if _texte(m)]
    if not a_rappeler and not (neuve and resumes):
        return courant, neuve
    lignes = (resumes[-1:] if neuve else []) + [f"- {_LIBELLES[m['role']]} : {_texte(m)}" for m in a_rappeler]
    return "\n".join([_ENTETE_CONTEXTE, *lignes, "", courant]), neuve


def commande_session(exe: str, *, modele: str, systeme: str, effort: str = "low") -> list[str]:
    return [
        exe,
        "-p",
        "--model", modele,
        "--effort", effort or "low",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--no-session-persistence",
        # Ni réglages, ni mémoire, ni serveurs MCP de l'utilisateur : la voix
        # n'hérite pas de son environnement de développement.
        "--setting-sources", "",
        "--strict-mcp-config",
        "--tools", "WebSearch",
        "--allowedTools", "WebSearch",
        "--system-prompt", systeme,
    ]


def _systeme(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return _texte(m)
    return ""


class SessionClaude:
    """Une session vivante pour un modèle, plus une réserve prête à servir."""

    def __init__(
        self,
        *,
        modele: str = MODELE_PAR_DEFAUT,
        effort: str = "low",
        exe: Optional[str] = None,
        lancer: Callable[..., object] = subprocess.Popen,
        reserve: bool = True,
    ) -> None:
        self.modele = modele
        self.effort = effort or "low"
        self.exe = exe or shutil.which("claude") or "claude"
        self._lancer = lancer
        self._avec_reserve = reserve
        self._verrou = threading.Lock()
        self._proc = None
        self._systeme: Optional[str] = None
        self._reserve = None
        self._systeme_reserve: Optional[str] = None
        self.derniere_reponse: Optional[str] = None
        # Dossier vide : aucun CLAUDE.md de projet n'est découvert.
        self._dossier = tempfile.mkdtemp(prefix="ha-conversation-")

    def _demarrer(self, systeme: str):
        env = dict(os.environ, MAX_THINKING_TOKENS="0")
        return self._lancer(
            commande_session(self.exe, modele=self.modele, systeme=systeme, effort=self.effort),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self._dossier,
            env=env,
            text=True,
            encoding="utf-8",
            **sans_console.options(),
        )

    def prechauffer(self, systeme: str) -> None:
        """Démarre la réserve maintenant : le premier tour ne paiera pas le démarrage."""
        if not self._avec_reserve:
            return
        if self._reserve is not None and self._systeme_reserve == systeme:
            return
        self._arreter(self._reserve)
        self._reserve = self._demarrer(systeme)
        self._systeme_reserve = systeme

    def _session_neuve(self, systeme: str):
        self._arreter(self._proc)
        if self._reserve is not None and self._systeme_reserve == systeme:
            proc, self._reserve = self._reserve, None
        else:
            proc = self._demarrer(systeme)
        self._proc, self._systeme = proc, systeme
        self.derniere_reponse = None
        if self._avec_reserve:
            self._reserve = self._demarrer(systeme)
            self._systeme_reserve = systeme
        return proc

    @staticmethod
    def _arreter(proc) -> None:
        if proc is None:
            return
        try:
            proc.stdin.close()
            proc.terminate()
        except Exception:
            pass

    def repondre(self, messages: list[dict]) -> Iterator[str]:
        """Rend les morceaux de texte de la réponse, au fil de l'eau."""
        with self._verrou:
            systeme = _systeme(messages)
            texte, neuve = message_pour_session(messages, self.derniere_reponse)
            if neuve:
                # Session neuve : tout le contexte repart, pas seulement le neuf.
                texte, _ = message_pour_session(messages, None)
            proc = self._proc
            if (
                neuve
                or proc is None
                or proc.poll() is not None
                or systeme != self._systeme
            ):
                proc = self._session_neuve(systeme)
            proc.stdin.write(
                json.dumps(
                    {"type": "user", "message": {"role": "user", "content": texte}},
                    ensure_ascii=False,
                )
                + "\n"
            )
            proc.stdin.flush()
            reponse = []
            for ligne in proc.stdout:
                try:
                    evenement = json.loads(ligne)
                except ValueError:
                    continue
                if evenement.get("type") == "stream_event":
                    delta = (evenement.get("event") or {}).get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        reponse.append(delta["text"])
                        yield delta["text"]
                elif evenement.get("type") == "result":
                    break
            self.derniere_reponse = "".join(reponse).strip() or None
