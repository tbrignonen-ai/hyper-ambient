"""Politique de contexte vocal : spine, projections, tampon, purge.

La parole seule entre dans la fenêtre. Les dumps techniques restent sur
disque. Deux canaux, un noyau commun de trois tours.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

# Seuil déjà mesuré dans router.py (un énoncé autonome se juge seul).
LONGUEUR_ANAPHORIQUE = 25
# 160, pas 80 : le classifieur tronque déjà à 160 dans router.py.
TRONCATURE_CLASSIFIEUR = 160

SPINE_TOURS = 3
REFLEXE_TOURS = 3
JETONS_REFLEXE = 512
# 15 tours : le plafond mesuré MEMOIRE_MESSAGES=12 protégeait le modèle
# local partagé. Le réflexe a maintenant sa propre borne de 3 tours.
MEMOIRE_TOURS_PROFOND = 15
JETONS_PROFOND = 3000

# 30 s : déjà la durée de FenetreConversation (mesure JeV du 20/09).
DUREE_SILENCE_MAINS_LIBRES_S = 30.0
DUREE_SILENCE_BOUTON_S = 60.0
TAMPON_AMBIANT_S = 5.0
LONGUEUR_ANAPHORE_AMBIANT = 15


def estimer_jetons(messages: Iterable[dict]) -> int:
    """Heuristique caractères / 4 : assez stable pour un plafond dur."""
    total = 0
    for message in messages:
        total += max(1, len((message.get("content") or "")) // 4)
    return total


@dataclass
class TourParle:
    user_norm: str
    assistant_spoken: str
    origine: str = "profond"
    mandate_ref: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class TamponAmbiant:
    """Dernière phrase non adressée, quelques secondes seulement."""

    texte: str = ""
    depose_a: Optional[float] = None

    def deposer(self, texte: str, maintenant: float) -> None:
        self.texte = (texte or "").strip()
        self.depose_a = maintenant if self.texte else None

    def oublier(self) -> None:
        self.texte = ""
        self.depose_a = None

    def fournir(self, enonce: str, maintenant: float) -> Optional[str]:
        if not self.texte or self.depose_a is None:
            return None
        if maintenant - self.depose_a >= TAMPON_AMBIANT_S:
            self.oublier()
            return None
        if len((enonce or "").strip()) > LONGUEUR_ANAPHORE_AMBIANT:
            self.oublier()
            return None
        marque = f"[ambiant] {self.texte}"
        self.oublier()
        return marque


@dataclass
class MemoireConversation:
    """Tours parlés vifs. Le disque garde le reste."""

    _tours: list[TourParle] = field(default_factory=list)
    dernier_tour_a: Optional[float] = None

    def retenir(
        self,
        user_norm: str,
        assistant_spoken: str,
        origine: str = "profond",
        mandate_ref: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        # Forme prononcée seulement : jamais un dump d'outil.
        if (user_norm or "").startswith("[résultat outil"):
            return
        if (assistant_spoken or "").startswith("[résultat outil"):
            return
        self._tours.append(
            TourParle(
                user_norm=(user_norm or "").strip(),
                assistant_spoken=(assistant_spoken or "").strip(),
                origine=origine,
                mandate_ref=mandate_ref,
                timestamp=0.0 if timestamp is None else timestamp,
            )
        )
        del self._tours[:-MEMOIRE_TOURS_PROFOND]
        if timestamp is not None:
            self.dernier_tour_a = timestamp

    def spine(self) -> list[dict]:
        return [
            {
                "user_norm": tour.user_norm,
                "assistant_spoken": tour.assistant_spoken,
                "origine": tour.origine,
                "mandate_ref": tour.mandate_ref,
            }
            for tour in self._tours[-SPINE_TOURS:]
        ]

    def messages(self) -> list[dict]:
        messages: list[dict] = []
        for tour in self._tours:
            if tour.user_norm:
                messages.append({"role": "user", "content": tour.user_norm})
            if tour.assistant_spoken:
                messages.append({"role": "assistant", "content": tour.assistant_spoken})
        return messages

    def purger(self) -> None:
        self._tours.clear()
        self.dernier_tour_a = None

    def silence_s(self, maintenant: float) -> float:
        if self.dernier_tour_a is None:
            return 0.0
        return max(0.0, maintenant - self.dernier_tour_a)

    def doit_fermer(self, *, mains_libres: bool, maintenant: float) -> bool:
        if self.dernier_tour_a is None or not self._tours:
            return False
        borne = (
            DUREE_SILENCE_MAINS_LIBRES_S if mains_libres else DUREE_SILENCE_BOUTON_S
        )
        return self.silence_s(maintenant) >= borne


def _messages_depuis_tours(tours: list[TourParle]) -> list[dict]:
    messages: list[dict] = []
    for tour in tours:
        if tour.user_norm:
            messages.append({"role": "user", "content": tour.user_norm})
        if tour.assistant_spoken:
            messages.append({"role": "assistant", "content": tour.assistant_spoken})
    return messages


def projeter(memoire: MemoireConversation, canal: str) -> list[dict]:
    tours = REFLEXE_TOURS if canal == "reflex" else MEMOIRE_TOURS_PROFOND
    jetons = JETONS_REFLEXE if canal == "reflex" else JETONS_PROFOND
    retenus = list(memoire._tours[-tours:])
    messages = _messages_depuis_tours(retenus)
    while estimer_jetons(messages) > jetons and len(retenus) > 1:
        retenus = retenus[1:]
        messages = _messages_depuis_tours(retenus)
    return messages


def _dernier_tour(contexte) -> tuple[str, str]:
    if contexte is None:
        return "", ""
    if isinstance(contexte, MemoireConversation):
        if not contexte._tours:
            return "", ""
        dernier = contexte._tours[-1]
        return dernier.user_norm, dernier.assistant_spoken
    messages = list(contexte or [])
    user_norm = ""
    spoken = ""
    for message in reversed(messages):
        role = (message or {}).get("role")
        contenu = ((message or {}).get("content") or "").strip()
        if not contenu:
            continue
        if role == "assistant" and not spoken:
            spoken = contenu
        elif role == "user" and not user_norm:
            user_norm = contenu
        if spoken and user_norm:
            break
    return user_norm, spoken


def fenetre_classifieur(prompt: str, contexte=None) -> str:
    """Énoncé seul si > 25 caractères ; sinon + tour précédent tronqué."""
    texte = (prompt or "").strip()
    if not (0 < len(texte) < LONGUEUR_ANAPHORIQUE):
        return texte
    user_norm, spoken = _dernier_tour(contexte)
    if not user_norm and not spoken:
        return texte
    champs = []
    if user_norm:
        champs.append(user_norm[:TRONCATURE_CLASSIFIEUR])
    if spoken:
        champs.append(spoken[:TRONCATURE_CLASSIFIEUR])
    return "Tour precedent : " + " / ".join(champs) + chr(10) + texte


def projeter_messages(messages: list[dict], canal: str) -> list[dict]:
    """Projection sur une liste {role, content} déjà construite.

    Les messages d'un tour d'outil en cours (assistant.tool_calls, role tool)
    restent dans l'ordre : les retrancher casserait le protocole.
    """
    extras = []
    spoken = []
    protocole = []
    for message in messages or []:
        contenu = message.get("content") or ""
        if contenu.startswith("[résultat outil"):
            extras.append(message)
        elif message.get("role") == "tool" or message.get("tool_calls"):
            protocole.append(message)
        elif message.get("role") in {"user", "assistant"}:
            spoken.append(message)
        else:
            protocole.append(message)
    tours = REFLEXE_TOURS if canal == "reflex" else MEMOIRE_TOURS_PROFOND
    jetons = JETONS_REFLEXE if canal == "reflex" else JETONS_PROFOND
    borne = spoken[-(tours * 2) :]
    while estimer_jetons(borne + extras + protocole) > jetons and len(borne) > 2:
        borne = borne[2:]
    return borne + extras + protocole


def projeter_kw(kw: dict, canal: str) -> dict:
    """Réduit history et messages au plafond du canal, sans jeter le tour courant."""
    propre = dict(kw)
    propre["history"] = projeter_messages(list(propre.get("history") or []), canal)
    messages = propre.get("messages")
    if not messages:
        return propre
    systeme = [m for m in messages if m.get("role") == "system"][:1]
    reste = [m for m in messages if m.get("role") != "system"]
    courant: list[dict] = []
    if reste and reste[-1].get("role") == "user":
        courant = [reste[-1]]
        reste = reste[:-1]
    propre["messages"] = systeme + projeter_messages(reste, canal) + courant
    return propre


def phrase_garde(harnais: list[str]) -> str:
    if not harnais:
        return ""
    if len(harnais) == 1:
        return f"Je garde un œil sur {harnais[0]}."
    noms = ", ".join(harnais[:-1]) + f" et {harnais[-1]}"
    return f"Je garde un œil sur {noms}."


def canal_porteur(vues: Iterable[Optional[str]], defaut: str = "reflex") -> str:
    """Premier morceau qui porte le canal, pas le dernier."""
    for canal in vues:
        if canal in {"deep", "filler", "holding", "tool"}:
            return "deep"
        if canal == "reflex":
            return "reflex"
    return defaut


def question_d_outil(chunk: dict, prompt_repli: str = "") -> str:
    """La question du modèle, pas le prompt brut."""
    arguments = chunk.get("arguments") if isinstance(chunk, dict) else None
    if isinstance(arguments, dict):
        for cle in ("question", "query", "instruction"):
            valeur = arguments.get(cle)
            if isinstance(valeur, str) and valeur.strip():
                return valeur.strip()
    return (prompt_repli or "").strip()
