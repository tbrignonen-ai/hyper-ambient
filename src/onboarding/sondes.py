"""Sondes d'onboarding : est-ce que le service repond, oui ou non.

Chaque fonction rend un `Sonde`. Aucune exception ne sort. Le detail est une
phrase a lire a voix haute : jeton absent, service injoignable, ou jeton
refuse. Le client HTTP est injectable ; sans lui, un client court est cree
pour l'appel puis referme. Delai : cinq secondes, jamais plus.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import shutil
import time
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse, urlunparse

from src.brain.tools_cli import CLI_BRIDGE_ENDPOINT
from src.brain.tools_codex import CODEX_BRIDGE_ENDPOINT
from src.ears.jev_reflexe import JEV_ENDPOINT, QUESTIONS, modele_jev
from src.i18n import t

logger = logging.getLogger(__name__)

DELAI_S = 5.0

_ABSENT = {
    "brain_distant": "La cle du modele distant n'est pas encore posee.",
    "codex": "Le jeton Codex n'est pas encore pose.",
    "claude": "Le jeton Claude n'est pas encore pose.",
    "jev": "La cle JeV n'est pas encore posee.",
}
_INJOIGNABLE = {
    "brain_distant": "Le modele distant ne repond pas.",
    "codex": "Codex ne repond pas.",
    "claude": "Claude ne repond pas.",
    "jev": "JeV ne repond pas.",
}
_REFUSE = {
    "brain_distant": "Le modele distant refuse cette cle.",
    "codex": "Codex refuse ce jeton.",
    "claude": "Claude refuse ce jeton.",
    "jev": "JeV refuse cette cle.",
}
_OK = {
    "brain_distant": "Le modele distant repond.",
    "codex": "Codex repond.",
    "claude": "Claude repond.",
    "jev": "JeV repond.",
}
_OUTILS_CLI = {
    "codex": "Codex",
    "claude": "Claude",
}
_COMMANDES_PS = {
    "codex": {
        "absent": "npm install -g @openai/codex; codex login",
        "present": "codex login",
    },
    "claude": {
        "absent": "npm install -g @anthropic-ai/claude-code; claude",
        "present": "claude",
    },
}
_HOTE_DOCKER = "host.docker.internal"
_HOTE_LOCAL = "127.0.0.1"


@dataclass
class Sonde:
    service: str
    ok: bool
    detail: str
    latence_ms: float | None


def _secret(valeur: str | None) -> str:
    return (valeur or "").strip()


def _url_alternee(url: str) -> str | None:
    """host.docker.internal <-> 127.0.0.1, une fois, sans toucher au reste."""
    brut = (url or "").strip()
    if not brut:
        return None
    try:
        parsed = urlparse(brut)
    except ValueError:
        return None
    hote = parsed.hostname or ""
    if hote == _HOTE_DOCKER:
        cible = _HOTE_LOCAL
    elif hote == _HOTE_LOCAL:
        cible = _HOTE_DOCKER
    else:
        return None
    netloc = (parsed.netloc or "").replace(hote, cible, 1)
    return urlunparse(parsed._replace(netloc=netloc))


def _statut(response: Any) -> int:
    try:
        return int(getattr(response, "status_code", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _conclure(service: str, statut: int, debut: float, cle_len: int) -> Sonde:
    latence = (time.perf_counter() - debut) * 1000
    if statut in (401, 403):
        logger.info("sonde %s: jeton refuse (cle_len=%s, latence_ms=%.0f)", service, cle_len, latence)
        return Sonde(service, False, _REFUSE[service], latence)
    if statut == 200:
        logger.info("sonde %s: ok (cle_len=%s, latence_ms=%.0f)", service, cle_len, latence)
        return Sonde(service, True, _OK[service], latence)
    logger.info("sonde %s: injoignable (cle_len=%s, latence_ms=%.0f)", service, cle_len, latence)
    return Sonde(service, False, _INJOIGNABLE[service], latence)


async def _avec_client(client: Any, corps: Callable[[Any], Awaitable[Any]]) -> Any:
    possede = False
    try:
        if client is None:
            import httpx

            client = httpx.AsyncClient(timeout=DELAI_S)
            possede = True
        return await corps(client)
    finally:
        if possede and client is not None:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()


async def _poster(client: Any, url: str, charge: dict, jeton: str) -> Any:
    return await asyncio.wait_for(
        client.post(
            url,
            json=charge,
            headers={
                "Authorization": f"Bearer {jeton}",
                "Content-Type": "application/json",
            },
            timeout=DELAI_S,
        ),
        timeout=DELAI_S,
    )


async def _sonder_http(
    service: str,
    jeton: str,
    client: Any,
    appel: Callable[[Any, str, str], Awaitable[Any]],
    url: str,
) -> Sonde:
    jeton = _secret(jeton)
    if not jeton:
        logger.info("sonde %s: jeton absent (cle_len=0)", service)
        return Sonde(service, False, _ABSENT[service], None)
    debut = time.perf_counter()

    async def tenter(cible: str) -> Any:
        return await _avec_client(client, lambda http: appel(http, jeton, cible))

    try:
        response = await tenter(url)
        return _conclure(service, _statut(response), debut, len(jeton))
    except Exception:
        alterne = _url_alternee(url)
        if alterne and alterne != url:
            try:
                response = await tenter(alterne)
                return _conclure(service, _statut(response), debut, len(jeton))
            except Exception:
                pass
        latence = (time.perf_counter() - debut) * 1000
        logger.info("sonde %s: injoignable (cle_len=%s, latence_ms=%.0f)", service, len(jeton), latence)
        return Sonde(service, False, _INJOIGNABLE[service], latence)


async def sonder_brain_distant(
    endpoint: str, cle: str, modele: str, client=None
) -> Sonde:
    try:
        adresse = _secret(endpoint)
        if _secret(cle) and not adresse:
            return Sonde("brain_distant", False, _INJOIGNABLE["brain_distant"], None)
        charge = {
            "model": modele,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
        return await _sonder_http(
            "brain_distant",
            cle,
            client,
            lambda http, jeton, cible: _poster(http, cible, charge, jeton),
            adresse,
        )
    except Exception:
        return Sonde("brain_distant", False, _INJOIGNABLE["brain_distant"], None)


async def sonder_codex(url: str, jeton: str, client=None) -> Sonde:
    # Question vide : le pont authentifie puis rend tout de suite
    # `question vide`, sans lancer Codex (un PONG reel depasse 5 s).
    try:
        adresse = _secret(url) or CODEX_BRIDGE_ENDPOINT
        return await _sonder_http(
            "codex",
            jeton,
            client,
            lambda http, secret, cible: _poster(http, cible, {"question": ""}, secret),
            adresse,
        )
    except Exception:
        return Sonde("codex", False, _INJOIGNABLE["codex"], None)


async def sonder_claude(url: str, jeton: str, client=None) -> Sonde:
    try:
        adresse = _secret(url) or CLI_BRIDGE_ENDPOINT
        return await _sonder_http(
            "claude",
            jeton,
            client,
            lambda http, secret, cible: _poster(
                http, cible, {"question": "", "agent": "claude"}, secret
            ),
            adresse,
        )
    except Exception:
        return Sonde("claude", False, _INJOIGNABLE["claude"], None)


async def sonder_jev(cle: str, client=None, modele: str | None = None) -> Sonde:
    try:
        nom = (modele or "").strip() or modele_jev()
        charge = {
            "state": {"transcription": "bonjour"},
            "model": nom,
            "questions": {"phrase_finished": QUESTIONS["phrase_finished"]},
        }
        return await _sonder_http(
            "jev",
            cle,
            client,
            lambda http, secret, cible: _poster(http, cible, charge, secret),
            JEV_ENDPOINT,
        )
    except Exception:
        return Sonde("jev", False, _INJOIGNABLE["jev"], None)


def outil_cli_pret(nom: str) -> Sonde:
    """Un harnais est-il utilisable ici : l'executable est-il dans le PATH.

    Pas de verification d'abonnement : interroger l'OAuth hors des outils
    officiels serait contraire a leurs conditions, et un appel `claude` /
    `codex` assez long pour etre fiable depasserait un clic de reglages.
    On constate seulement si le programme est la, et on donne la commande
    officielle a taper dans PowerShell.
    """
    debut = time.perf_counter()
    identifiant = (nom or "").strip().lower() or "outil"
    try:
        if identifiant not in _OUTILS_CLI:
            latence = (time.perf_counter() - debut) * 1000
            return Sonde(identifiant, False, t("sondes.outil_inconnu"), latence)
        etiquette = _OUTILS_CLI[identifiant]
        trouve = shutil.which(identifiant)
        latence = (time.perf_counter() - debut) * 1000
        if not trouve:
            return Sonde(
                identifiant,
                False,
                t(
                    "sondes.outil_absent",
                    nom=etiquette,
                    commande=_COMMANDES_PS[identifiant]["absent"],
                ),
                latence,
            )
        return Sonde(
            identifiant,
            True,
            t(
                "sondes.outil_present",
                nom=etiquette,
                commande=_COMMANDES_PS[identifiant]["present"],
            ),
            latence,
        )
    except Exception:
        latence = (time.perf_counter() - debut) * 1000
        etiquette = _OUTILS_CLI.get(identifiant, identifiant)
        return Sonde(
            identifiant,
            False,
            t("sondes.outil_echec", nom=etiquette),
            latence,
        )


def detecter_abonnements() -> list[Sonde]:
    """Codex puis Claude : presence des outils officiels, rien d'autre."""
    return [outil_cli_pret("codex"), outil_cli_pret("claude")]


async def sonder_tout(reglages: dict, client=None) -> list[Sonde]:
    try:
        valeurs = reglages or {}
        return list(
            await asyncio.gather(
                sonder_brain_distant(
                    str(valeurs.get("BRAIN_API_ENDPOINT") or ""),
                    str(valeurs.get("BRAIN_API_KEY") or ""),
                    str(valeurs.get("BRAIN_MODEL") or ""),
                    client,
                ),
                sonder_codex(
                    str(valeurs.get("CODEX_BRIDGE_URL") or ""),
                    str(valeurs.get("CODEX_BRIDGE_TOKEN") or ""),
                    client,
                ),
                sonder_claude(
                    str(valeurs.get("CLI_BRIDGE_URL") or ""),
                    str(valeurs.get("CLI_BRIDGE_TOKEN") or ""),
                    client,
                ),
                sonder_jev(
                    str(valeurs.get("TYPESAFE_API_KEY") or ""),
                    client,
                    str(valeurs.get("TYPESAFE_MODEL") or "") or None,
                ),
            )
        )
    except Exception:
        return [
            Sonde(nom, False, _INJOIGNABLE[nom], None)
            for nom in ("brain_distant", "codex", "claude", "jev")
        ]
