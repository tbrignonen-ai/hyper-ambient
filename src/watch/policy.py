from typing import Callable, Sequence

from .events import AlertRaised


class Watch:
    def __init__(self, rules: Sequence, publish: Callable[[AlertRaised], None]):
        self.rules = rules
        self.publish = publish

    def observe(self, event: dict) -> None:
        """L'évaluation des règles arrive au T-N01-5.

        Le silence par défaut est l'invariant de WATCH — une saillance
        non déclarée ne produit aucune parole.
        """
        return None
