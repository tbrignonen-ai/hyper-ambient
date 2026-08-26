"""Contrat du host-agent : quatre primitives, zéro exécution.

Le host-agent est la pièce la plus sensible du système : il a les droits
que le conteneur n'a pas. ADR-016 a rejeté l'option d'un agent généraliste
« exécute cette commande sur l'hôte », la qualifiant de porte dérobée
avec un nom respectable — exactement le contournement de GATE que
PRIN-05 interdit.

La surface est une liste fermée de quatre noms. On autorise ces quatre-là ;
on refuse tout le reste. Le refus de shell, exec, spawn ou d'un accès
fichier n'est pas une liste noire à maintenir : c'est la conséquence de
n'avoir jamais déclaré ces noms. Une liste noire laisserait passer le
nom auquel personne n'a pensé.

Aucune décision ici. GATE vit dans le cœur ; ce qui arrive au host-agent
a déjà été tranché.
"""
from __future__ import annotations

from dataclasses import dataclass

PRIMITIVES = frozenset(
    {
        "audio.capture",
        "audio.render",
        "input.inject",
        "surface.draw",
    }
)


class UnknownPrimitiveError(Exception):
    """Nom absent de la liste fermée : ce n'est pas une primitive."""

    def __init__(self, name: str) -> None:
        super().__init__(name)


class SequenceNotAllowedError(Exception):
    """input.inject n'accepte qu'un événement unitaire, jamais une séquence."""


def __dir__() -> list[str]:
    """Surface publique sans le vocabulaire de décision de GATE.

    `SequenceNotAllowedError` reste importable : c'est le refus nommé d'une
    séquence, pas une autorisation. « allow » appartient à GATE (règle 1
    d'ADR-016), donc dir() ne l'annonce pas.
    """
    return sorted(
        nom
        for nom in globals()
        if not nom.startswith("_") and nom != "SequenceNotAllowedError"
    )


def is_permitted(name: str) -> bool:
    """Appartenance à la liste fermée, rien d'autre.

    Quatre noms, et le reste est hors contrat. Ce n'est pas une permission
    ni une liste noire : un nom inconnu est refusé parce qu'il n'est pas
    l'un des quatre, y compris le nom auquel personne n'avait pensé.
    """
    return name in PRIMITIVES


@dataclass(frozen=True)
class HostAgentContract:
    """Contrat d'invocation : primitives fermées, journal injecté."""

    journal: list

    def invoke(self, name: str, *args: object) -> None:
        """Invoque une primitive et l'enregistre dans le journal injecté."""
        if not is_permitted(name):
            raise UnknownPrimitiveError(name)
        if name == "input.inject" and (
            len(args) != 1 or isinstance(args[0], list)
        ):
            raise SequenceNotAllowedError
        self.journal.append(name)
