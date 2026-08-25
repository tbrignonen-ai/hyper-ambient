"""Événements d'alerte produits par WATCH."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AlertRaised:
    """Alerte levée par WATCH."""

    source: str
    severity: str
    subject: str
    evidence: str
    raised_at: datetime
