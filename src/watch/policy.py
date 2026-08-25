from typing import Callable, Sequence

from .events import AlertRaised


class Watch:
    def __init__(self, rules: Sequence, publish: Callable[[AlertRaised], None]):
        self.rules = rules
        self.publish = publish

    def observe(self, event: dict) -> None:
        """WATCH est le point de contrôle unique de l'initiation de parole.

        Le silence est le régime par défaut — une saillance non déclarée
        par une règle ne produit aucune parole. La symétrie avec GATE
        est voulue : GATE refuse par défaut l'exécution, WATCH se tait
        par défaut.
        """
        for rule in self.rules:
            result = rule(event)
            if result is not None:
                self.publish(result)
