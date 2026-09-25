"""Mémoire glissante des tours parlés, indépendante du routeur."""
from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Awaitable, Callable


MARQUE_RESUME = "compactage_resume"
MAX_RESUME = 480
MAX_SOURCE_CHARS = 6000


def _fait_personnel(message: dict) -> str:
    if message.get("role") != "user":
        return ""
    contenu = (message.get("content") or "").strip()
    if not contenu or len(contenu) > 240:
        return ""
    norme = "".join(c for c in unicodedata.normalize("NFKD", contenu.lower()) if not unicodedata.combining(c))
    nom = re.search(r"\b(?:je m[' ]appelle|mon nom est|my name is|me llamo)\b", norme)
    horaire = re.search(r"\b\d{1,2}\s*(?:h\b|heures?\b|am\b|pm\b|:\d{2}\b)", norme)
    personnel = re.search(r"\b(?:ma|mon|mes|my|mi)\b", norme)
    return contenu[:180] if nom or (personnel and horaire) else ""


def est_nouvelle_conversation(texte: str) -> bool:
    norme = "".join(c for c in unicodedata.normalize("NFKD", texte.lower()) if not unicodedata.combining(c))
    norme = re.sub(r"[^a-z ]", " ", norme)
    norme = " ".join(norme.split())
    return bool(re.fullmatch(
        r"(?:(?:ouvre|commence|demarre|lance|start|begin|inicia|empieza) (?:une |a |una )?)?"
        r"(?:nouvelle conversation|new conversation|nueva conversacion)", norme
    ))


def resume_message(texte: str) -> dict:
    return {"role": "system", "content": f"Mémoire de la conversation : {texte}", MARQUE_RESUME: True}


@dataclass(frozen=True)
class BudgetModele:
    fenetre: int
    cible_latence: int

    @property
    def plafond(self) -> int:
        return max(128, min(int(self.fenetre * 0.6), self.cible_latence))


def budget_pour_modele(modele, *, canal: str = "deep") -> BudgetModele:
    """La carte se surcharge par environnement, sans figer les fournisseurs futurs."""
    nom = str(getattr(modele, "model", getattr(modele, "name", ""))).lower()
    local = canal == "reflex" or "llama" in str(getattr(modele, "name", "")).lower()
    def entier(cle, repli):
        try:
            return max(128, int(os.getenv(cle, str(repli))))
        except ValueError:
            return repli
    if local:
        return BudgetModele(int(getattr(modele, "n_ctx", 4096)), entier("COMPACTAGE_LATENCE_REFLEXE_JETONS", 256))
    if "minimax" in nom:
        fenetre = 204800
    elif "gpt" in nom or "claude" in nom or "sonnet" in nom:
        fenetre = 200000
    else:
        fenetre = 32768
    return BudgetModele(entier("COMPACTAGE_FENETRE_DISTANTE", fenetre), entier("COMPACTAGE_LATENCE_DISTANTE_JETONS", 3000))


async def lire_fenetre_locale(modele) -> int:
    """llama.cpp expose n_ctx via /slots (ou /props selon sa version)."""
    endpoint = str(getattr(modele, "api_endpoint", ""))
    base = endpoint.split("/v1/")[0]
    if not base.startswith("http"):
        return 4096
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            for route in ("/props", "/slots"):
                result = (await client.get(base + route)).json()
                if isinstance(result, list) and result:
                    result = result[0]
                n_ctx = result.get("n_ctx") or result.get("endpoint_props", {}).get("n_ctx")
                if n_ctx:
                    modele.n_ctx = int(n_ctx)
                    return modele.n_ctx
    except Exception:
        pass
    return 4096


async def resumer_local(ancien: str, echanges: list[dict]) -> str:
    """Appel du modèle local déjà chargé ; aucun coût VRAM supplémentaire."""
    import httpx
    host = os.getenv("COMPACTAGE_RESUMEUR_URL") or os.getenv("LLAMA_SERVER_HOST", "http://localhost:8080")
    lignes = "\n".join(f"{m['role']}: {m.get('content', '')}" for m in echanges)
    instruction = (
        f"Mémoire factuelle en français, {MAX_RESUME} caractères maximum, sans introduction. "
        "Conserve exactement les faits donnés par l'utilisateur (nom, heures), "
        "les décisions explicites, questions ouvertes et tâches confiées aux harnais. "
        "Intègre la mémoire précédente. N'infère jamais un accord ou une décision "
        "à partir d'une proposition de l'assistant. Oublie les répétitions.\n"
        f"Mémoire précédente : {ancien}\nÉchanges :\n{lignes}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        result = await client.post(host.rstrip("/") + "/v1/chat/completions", json={
            "model": os.getenv("COMPACTAGE_RESUMEUR_MODELE", os.getenv("BRAIN_MODEL_LOCAL", "local")),
            "messages": [{"role": "user", "content": instruction}],
            "temperature": 0, "max_tokens": 220, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        })
        result.raise_for_status()
        texte = result.json()["choices"][0]["message"]["content"].strip()
        if not texte:
            raise ValueError("résumé vide")
        return texte


class Compacteur:
    def __init__(self, budget: BudgetModele, *, summarizer: Callable[[str, list[dict]], Awaitable[str]] = resumer_local,
                 garder_tours: int = 3):
        self.budget = budget
        self.summarizer = summarizer
        self.garder_tours = garder_tours
        self.historique: list[dict] = []
        self.resume = ""
        self.faits: list[str] = []
        self._tache: asyncio.Task | None = None
        self._generation = 0

    def retenir(self, utilisateur: str, assistant: str) -> None:
        self.historique.extend([{"role": "user", "content": utilisateur},
                               {"role": "assistant", "content": assistant}])

    def messages(self) -> list[dict]:
        return ([resume_message(self.resume)] if self.resume else []) + list(self.historique)

    def planifier(self) -> None:
        from src.brain.contexte import estimer_jetons
        if self._tache is not None and not self._tache.done():
            return
        if len(self.historique) <= self.garder_tours * 2:
            return
        if estimer_jetons(self.messages()) <= self.budget.plafond:
            return
        # L'échec laisse tous les tours intacts. Le tour suivant réessaiera.
        candidats = self.historique[: -self.garder_tours * 2]
        taille = 0
        nombre = 0
        for message in candidats:
            longueur = len(message.get("content") or "")
            if taille + longueur > MAX_SOURCE_CHARS:
                break
            taille += longueur
            nombre += 1
        # Les tours parlés sont des paires ; ne couper ni question ni réponse.
        nombre -= nombre % 2
        prefixe = candidats[:nombre]
        anciens = [m for m in prefixe if not (m.get("content") or "").startswith("[résultat outil")]
        if not anciens:
            return
        generation = self._generation
        async def faire():
            try:
                texte = (await self.summarizer(self.resume, anciens)).strip()
                if texte and generation == self._generation:
                    for message in anciens:
                        fait = _fait_personnel(message)
                        if fait and fait not in self.faits:
                            self.faits.append(fait)
                    faits = " ".join(self.faits)
                    # Les faits utilisateur restent en tête même si le 3B les
                    # omet dans un résumé glissant ultérieur.
                    if len(faits) > 240:
                        faits = faits[:240]
                    prefixe_faits = faits + "\n" if faits and faits not in texte else ""
                    self.resume = (prefixe_faits + texte)[:MAX_RESUME]
                    # Par identité : une purge d'outils a pu décaler la liste
                    # pendant le résumé ; retirer par position ôterait des
                    # tours récents jamais résumés.
                    resumes = {id(m) for m in prefixe}
                    self.historique[:] = [m for m in self.historique if id(m) not in resumes]
            except Exception:
                # Garder l'intégralité des tours et retenter au prochain tour.
                pass
        self._tache = asyncio.create_task(faire())

    async def attendre(self) -> None:
        if self._tache is not None:
            await self._tache

    def vider(self) -> None:
        self._generation += 1
        if self._tache is not None and not self._tache.done():
            self._tache.cancel()
        self._tache = None
        self.historique.clear()
        self.resume = ""
        self.faits.clear()
