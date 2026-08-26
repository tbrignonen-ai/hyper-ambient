"""Règle d'expiration de délégation.

WATCH ne parle que si une règle le déclare. Cette règle existe parce que
REQ-D3-03 exige qu'une délégation restée muette au-delà d'un délai
*configuré* soit signalée — le critère d'acceptation porte sur le délai
injecté par la fabrique, pas sur une valeur figée dans le code. Un
timeout en dur ici ferait de cette valeur le défaut du système ; c'est
exactement ce qu'il faut éviter.

La sévérité reste sobre (REQ-D6-01) : une délégation muette n'interrompt
pas une conversation en cours. Le registre dramatique est réservé aux
alertes qui interrompent tout. Tout autre genre d'événement laisse
WATCH se taire (ADR-018) : le silence est le régime normal.
"""

from datetime import datetime
from typing import Callable

from .events import AlertRaised


def delegation_timeout_rule(timeout_s: float) -> Callable[[dict], AlertRaised | None]:
    """Fabrique une règle qui lève une alerte sobre si le silence dépasse `timeout_s`.

    Le délai est injecté : deux appels avec des délais distincts produisent
    deux comportements sur le même événement.
    """

    def rule(event: dict) -> AlertRaised | None:
        if event.get("kind") != "delegation_timeout":
            return None
        silence_s = event.get("silence_s")
        if silence_s is None or silence_s <= timeout_s:
            return None
        return AlertRaised(
            source="D3-AGENTBUS",
            severity="sober",
            subject="delegation_timeout",
            evidence=f"silence {silence_s} s au-delà de {timeout_s} s",
            raised_at=datetime.now(),
        )

    return rule
