"""Le catalogue des sessions Claude Code et Codex de l'utilisateur (24/09).

Lecture seule, là où les harnais rangent leurs sessions :

- Claude Code : ``~/.claude/projects/<dossier>/<id>.jsonl`` ; titre donné par
  ``/rename`` (``custom-title``), dossier de travail (``cwd``) sur les messages.
- Codex : ``~/.codex/sessions/AAAA/MM/JJ/rollout-…-<id>.jsonl`` ; dossier dans
  ``session_meta``, nom du fil dans ``~/.codex/session_index.jsonl``.

Pour chaque session : identifiant, titre, premier message utile (l'aperçu),
dossier et date. ``chercher`` choisit la plus récente, ou celle dont le titre
puis l'aperçu contiennent le plus de mots de la requête.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

MAX_SESSIONS = 300
_CONSIGNE_VOCALE = re.compile(r"^Reponds en francais\b.*?Question\s*:\s*", re.S)
_MOTS = re.compile(r"[a-z0-9]+")
_VIDES = frozenset(
    "le la les l de des du d un une et ou a au aux en dans sur pour par avec qui que "
    "quoi dont parle parlait parlent parler propos sujet concernant contenant titre "
    "session sessions claude codex code cloud the of and or in on about".split()
)


def racine_claude() -> Path:
    return Path.home() / ".claude" / "projects"


def racine_codex() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in sans_accents if not unicodedata.combining(c)).lower()


def _texte(contenu) -> str:
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return " ".join(
            str(p.get("text") or "") for p in contenu if isinstance(p, dict)
        )
    return ""


def _apercu(texte: str) -> Optional[str]:
    """Le premier message utile : pas de bruit technique, sans la consigne du pont."""
    texte = (texte or "").strip()
    if not texte or texte.startswith("<") or texte.startswith("Caveat"):
        return None
    texte = _CONSIGNE_VOCALE.sub("", texte, count=1)
    # Il est lu à voix haute : ni titres markdown, ni retours à la ligne.
    texte = " ".join(texte.replace("#", " ").split())
    return texte or None


def _recents(fichiers: Iterable[Path]) -> list[Path]:
    avec_date = []
    for f in fichiers:
        try:
            avec_date.append((f.stat().st_mtime, f))
        except OSError:
            continue
    avec_date.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in avec_date[:MAX_SESSIONS]]


def _session_claude(fichier: Path) -> Optional[dict]:
    titre, apercu, cwd = "", None, None
    try:
        with open(fichier, encoding="utf-8", errors="replace") as flux:
            for ligne in flux:
                # Filtre textuel avant json.loads : 60 Mo se lisent en 0,2 s.
                titre_ici = '"custom-title"' in ligne
                if not titre_ici and (apercu is not None or '"user"' not in ligne):
                    continue
                try:
                    d = json.loads(ligne)
                except ValueError:
                    continue
                if d.get("type") == "custom-title":
                    titre = str(d.get("customTitle") or titre)
                elif d.get("type") == "user" and apercu is None and not d.get("isMeta"):
                    apercu = _apercu(_texte((d.get("message") or {}).get("content")))
                    cwd = d.get("cwd") or cwd
    except OSError:
        return None
    return {
        "harnais": "Claude",
        "id": fichier.stem,
        "titre": titre,
        "apercu": apercu or "",
        "cwd": cwd,
        "date": fichier.stat().st_mtime,
    }


def sessions_claude(racine: Optional[Path] = None) -> list[dict]:
    racine = Path(racine or racine_claude())
    sessions = (_session_claude(f) for f in _recents(racine.glob("*/*.jsonl")))
    return [s for s in sessions if s]


def _noms_codex(racine: Path) -> dict[str, str]:
    noms: dict[str, str] = {}
    try:
        with open(racine / "session_index.jsonl", encoding="utf-8", errors="replace") as flux:
            for ligne in flux:
                try:
                    d = json.loads(ligne)
                except ValueError:
                    continue
                if d.get("id") and d.get("thread_name"):
                    noms[str(d["id"])] = str(d["thread_name"])
    except OSError:
        pass
    return noms


def _session_codex(fichier: Path, noms: dict[str, str]) -> Optional[dict]:
    ident, cwd, apercu = None, None, None
    try:
        with open(fichier, encoding="utf-8", errors="replace") as flux:
            for ligne in flux:
                if ident is None and '"session_meta"' in ligne:
                    try:
                        meta = json.loads(ligne).get("payload") or {}
                    except ValueError:
                        continue
                    ident, cwd = meta.get("id"), meta.get("cwd")
                elif '"UserMessage"' in ligne:
                    try:
                        item = (json.loads(ligne).get("payload") or {}).get("item") or {}
                    except ValueError:
                        continue
                    apercu = _apercu(_texte(item.get("content")))
                    if apercu:
                        break
    except OSError:
        return None
    if not ident:
        return None
    return {
        "harnais": "Codex",
        "id": str(ident),
        "titre": noms.get(str(ident), ""),
        "apercu": apercu or "",
        "cwd": cwd,
        "date": fichier.stat().st_mtime,
    }


def sessions_codex(racine: Optional[Path] = None) -> list[dict]:
    racine = Path(racine or racine_codex())
    noms = _noms_codex(racine)
    fichiers = _recents((racine / "sessions").glob("*/*/*/rollout-*.jsonl"))
    sessions = (_session_codex(f, noms) for f in fichiers)
    return [s for s in sessions if s]


def mots_requete(requete: str) -> list[str]:
    return [m for m in _MOTS.findall(_normaliser(requete)) if m not in _VIDES]


def _score(session: dict, mots: list[str]) -> int:
    titre = _MOTS.findall(_normaliser(session.get("titre", "")))
    apercu = _MOTS.findall(_normaliser(session.get("apercu", "")))
    score = 0
    for mot in mots:
        if any(m.startswith(mot) for m in titre):
            score += 2
        elif any(m.startswith(mot) for m in apercu):
            score += 1
    return score


def chercher(sessions: list[dict], requete: str) -> Optional[dict]:
    """La plus récente sans requête ; sinon le meilleur score, puis la plus récente."""
    if not sessions:
        return None
    mots = mots_requete(requete)
    if not mots:
        return dict(max(sessions, key=lambda s: s["date"]), score=0)
    notees = [(_score(s, mots), s["date"], s) for s in sessions]
    score, _, meilleure = max(notees, key=lambda x: (x[0], x[1]))
    if score <= 0:
        return None
    return dict(meilleure, score=score)


def cwd_de_session(harnais: str, ident: str, racine: Optional[Path] = None) -> Optional[str]:
    """Le dossier de travail d'une session : Claude ne la reprend que depuis là."""
    if not ident or "/" in ident or "\\" in ident:
        return None
    if harnais == "Claude":
        for fichier in Path(racine or racine_claude()).glob(f"*/{ident}.jsonl"):
            session = _session_claude(fichier)
            return session["cwd"] if session else None
    elif harnais == "Codex":
        base = Path(racine or racine_codex()) / "sessions"
        for fichier in base.glob(f"*/*/*/rollout-*{ident}.jsonl"):
            session = _session_codex(fichier, {})
            return session["cwd"] if session else None
    return None
