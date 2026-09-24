"""La session courante d'un harnais, côté host-agent (24/09).

Partagée par les clients des ponts Claude et Codex. Le pont rend un
identifiant de session à chaque réponse ; le client le garde, et la demande
suivante reprend le même fil. « Reprends la session qui parle de X » passe
par ``chercher_session`` (``GET /sessions?q=``) puis ``adopter_session``.

Claude bifurque à la première reprise (``--fork-session``) : la session
rejointe peut être ouverte ailleurs par l'utilisateur, on n'écrit jamais
dedans ; la bifurcation porte tout l'historique et devient la nôtre.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("pont_session")

DELAI_RECHERCHE_S = 10.0


class SessionDePont:
    bifurquer_a_la_reprise = False
    session: Optional[str] = None
    _fourche = False

    def _charge(self, question: str, charge: dict) -> dict:
        if self.session:
            charge["session"] = self.session
            if self._fourche:
                charge["fork"] = True
        return charge

    def _retenir_session(self, payload: dict) -> None:
        ident = payload.get("session_id")
        if isinstance(ident, str) and ident:
            self.session = ident
            self._fourche = False

    def adopter_session(self, session: dict) -> None:
        self.session = str(session["id"])
        self._fourche = self.bifurquer_a_la_reprise

    def oublier_session(self) -> None:
        self.session = None
        self._fourche = False

    async def chercher_session(self, requete: str) -> Optional[dict[str, Any]]:
        """La session du harnais qui répond le mieux à la requête (vide : la dernière)."""
        if not getattr(self, "token", "") or getattr(self, "client", None) is None:
            return None
        url = self.endpoint.rsplit("/", 1)[0] + "/sessions"
        try:
            reponse = await self.client.get(
                url,
                params={"q": requete},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=DELAI_RECHERCHE_S,
            )
            if getattr(reponse, "status_code", 0) != 200:
                logger.warning(f"sessions : HTTP {getattr(reponse, 'status_code', '?')}")
                return None
            payload = reponse.json()
        except Exception as exc:
            logger.warning(f"sessions : pont injoignable ({exc!r})")
            return None
        session = payload.get("session") if isinstance(payload, dict) else None
        return session if isinstance(session, dict) and session.get("id") else None
