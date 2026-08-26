"""Canal local authentifié entre le cœur et le host-agent.

Ce canal est la surface d'attaque créée par l'architecture à deux
composants d'ADR-006 : le cœur vit dans un conteneur, le host-agent
sur l'hôte, et quelque chose doit relier les deux. Un canal ouvert au
réseau donnerait à un tiers les primitives d'entrée de l'hôte — capture
audio, injection d'entrée, dessin de surface. ADR-016 règle 3 impose
donc un canal local uniquement, authentifié par un secret partagé
généré à l'installation, refusant toute connexion non locale. ADR-004
(confiance minimale) : on n'élargit pas la surface ; on la borne à la
loopback et aux quatre primitives du contrat.

Ce module porte la logique d'admission, pas le transport. La localité
se décide sur l'adresse (is_loopback), jamais par comparaison de chaîne
avec 127.0.0.1 : ::1 est local, une adresse privée ne l'est pas.
"""
from __future__ import annotations

import hmac
import ipaddress
import json

from src.hostagent.contract import PRIMITIVES, is_permitted


class ChannelRefused(Exception):
    """Refus nommé d'admission ou d'invocation sur le canal."""


class LocalChannel:
    """Admission du canal : loopback, secret partagé, primitives fermées."""

    def __init__(self, secret: str, journal: list | None = None) -> None:
        self._secret = secret
        self._journal = journal if journal is not None else []

    def authenticate(self, peer_address: str, secret: object) -> None:
        """Admet un pair s'il est loopback et présente le secret partagé.

        La localité se vérifie avant le secret : une adresse non locale
        est refusée même avec le bon secret, et le secret n'est alors
        pas comparé. La comparaison, quand elle a lieu, passe par
        hmac.compare_digest — jamais par == — pour ne pas fuir la
        longueur ni s'arrêter au premier octet différent.
        """
        try:
            address = ipaddress.ip_address(peer_address)
        except ValueError as exc:
            raise ChannelRefused(peer_address) from exc
        if not address.is_loopback:
            raise ChannelRefused(peer_address)
        presented = secret if isinstance(secret, str) else ""
        if not hmac.compare_digest(self._secret, presented):
            raise ChannelRefused

    def handle(self, message: object) -> None:
        """Admet une invocation qui nomme une primitive du contrat."""
        try:
            payload = json.loads(message) if isinstance(message, str) else message
            if not isinstance(payload, dict):
                raise ChannelRefused
            primitive = payload["primitive"]
        except (ChannelRefused, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, ChannelRefused):
                raise
            raise ChannelRefused from exc
        if not isinstance(primitive, str) or not is_permitted(primitive):
            raise ChannelRefused(primitive)
        if primitive not in PRIMITIVES:
            raise ChannelRefused(primitive)
        self._journal.append(primitive)
