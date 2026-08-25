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
