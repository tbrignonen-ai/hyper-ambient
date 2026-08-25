"""
Tests du module watch (événements d'alerte).
"""
from datetime import datetime


def test_alert_raised_expose_les_cinq_champs():
    """Une instance AlertRaised expose source, severity, subject, evidence et raised_at."""
    from src.watch.events import AlertRaised

    raised_at = datetime(2026, 8, 25, 3, 0, 0)
    alert = AlertRaised(
        source="D3-AGENTBUS",
        severity="sober",
        subject="delegation_timeout",
        evidence="agent muet depuis 30 s",
        raised_at=raised_at,
    )
    assert alert.source == "D3-AGENTBUS"
    assert alert.severity == "sober"
    assert alert.subject == "delegation_timeout"
    assert alert.evidence == "agent muet depuis 30 s"
    assert alert.raised_at == raised_at


def test_watch_se_tait_quand_aucune_regle_ne_correspond():
    """Sans règle déclarée, Watch reste silencieux : aucune parole n'est publiée."""
    from src.watch.policy import Watch

    publie = []
    watch = Watch(rules=[], publish=publie.append)
    watch.observe({"kind": "delegation_timeout", "agent": "hermes"})
    assert publie == []


def test_watch_publie_une_alerte_quand_une_regle_correspond():
    """Watch publie une alerte uniquement lorsque la règle correspond à l'événement."""
    from src.watch.events import AlertRaised
    from src.watch.policy import Watch

    def regle_expiration(event):
        if event.get("kind") == "delegation_timeout":
            return AlertRaised(
                source="D3-AGENTBUS",
                severity="sober",
                subject="delegation_timeout",
                evidence=f"agent {event['agent']} muet",
                raised_at=datetime(2026, 8, 25, 3, 0, 0),
            )
        return None

    publie = []
    watch = Watch(rules=[regle_expiration], publish=publie.append)
    watch.observe({"kind": "delegation_timeout", "agent": "hermes"})
    watch.observe({"kind": "device_state_changed", "device": "lampe"})
    assert len(publie) == 1
    assert publie[0].subject == "delegation_timeout"
    assert publie[0].evidence == "agent hermes muet"
