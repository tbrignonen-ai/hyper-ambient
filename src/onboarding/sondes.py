"""Sondes d'onboarding : ce que chaque voyant prouve, etat par etat.

Quatre etats, dont les trois du brief :

* ``repond``      — joignable **et** une reponse verifiable est revenue ;
* ``muet``        — joignable, mais aucune reponse exploitable : jeton
                    refuse, harnais muet, harnais introuvable, delai
                    depasse, erreur du harnais ;
* ``injoignable`` — rien n'a repondu du tout ;
* ``absent``      — la cle n'est pas posee, il n'y a rien a tester.

Un statut de succes ne suffit jamais. Les deux ponts rendent un statut 200
meme quand le harnais n'a rien dit : ``{"ok": false, "error": "question
vide"}`` revient en 250 a 380 ms (mesure du 2026-09-21), contre 2,3 s a
5,0 s pour une vraie reponse. C'etait un voyant vert qui ne prouvait rien.
Chaque sonde pose donc une vraie question minimale et verifie le corps de
la reponse, pas seulement son statut.

Aucune exception ne sort. Aucune valeur de cle n'est journalisee ni
affichee : seule sa longueur l'est. Le client HTTP est injectable ; sans
lui, un client est cree pour la sonde puis referme.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse, urlunparse

from src.brain.tools_cli import CLI_BRIDGE_ENDPOINT
from src.brain.tools_codex import CODEX_BRIDGE_ENDPOINT
from src.ears.jev_reflexe import JEV_ENDPOINT, QUESTIONS, modele_jev
from src.i18n import t

logger = logging.getLogger(__name__)

# Delai d'un appel qui ne doit pas durer : joignabilite du pont, modele
# distant, JeV. Annonce tel quel dans la fenetre de reglages.
DELAI_S = 5.0

# Un vrai aller-retour vers un harnais est bien plus long que cinq secondes :
# mesures du 2026-09-21 sur cette machine, PONG rendu en 5,0 s par Codex et
# 2,3 s par Claude. Les ponts se bornent eux-memes — 40 s pour
# `native/codexbridge`, 90 s pour `native/clibridge` — et rendent alors
# `{"ok": false, "error": "delai depasse"}`. La borne du client doit rester
# au-dessus, sinon un pont qui a repondu serait dit injoignable.
DELAI_HARNAIS_S = 100.0

# La question minimale. Sa reponse est verifiable : le mot attendu est dans
# la question, donc un harnais qui repond autre chose ne passe pas en vert.
# Les ponts la font preceder de leur propre consigne de forme, ce qui ne
# change rien : le mot attendu reste reconnaissable.
QUESTION_SONDE = "Reponds par un seul mot : PONG. N'ajoute aucun autre mot."
MARQUEUR_SONDE = "pong"

ETAT_REPOND = "repond"
ETAT_MUET = "muet"
ETAT_INJOIGNABLE = "injoignable"
ETAT_ABSENT = "absent"
ETATS = frozenset({ETAT_REPOND, ETAT_MUET, ETAT_INJOIGNABLE, ETAT_ABSENT})

# Phrases a lire a voix haute. Aucune ne cite un statut, une adresse ou une
# valeur de cle : elles disent ce qui est prouve, rien de plus.
_TEXTES: dict[str, dict[str, str]] = {
    "absent": {
        "brain_distant": "La cle du modele distant n'est pas encore posee.",
        "codex": "Le jeton Codex n'est pas encore pose.",
        "claude": "Le jeton Claude n'est pas encore pose.",
        "jev": "La cle JeV n'est pas encore posee.",
    },
    "injoignable": {
        "brain_distant": "Le modele distant ne repond pas : rien n'a repondu.",
        "codex": "Le pont Codex ne repond pas : rien n'a repondu.",
        "claude": "Le pont Claude ne repond pas : rien n'a repondu.",
        "jev": "JeV ne repond pas : rien n'a repondu.",
    },
    "refuse": {
        "brain_distant": "Le modele distant est joignable, mais il refuse cette cle.",
        "codex": "Le pont Codex est joignable, mais il refuse ce jeton.",
        "claude": "Le pont Claude est joignable, mais il refuse ce jeton.",
        "jev": "JeV est joignable, mais il refuse cette cle.",
    },
    "repond": {
        "brain_distant": "Le modele distant a repondu.",
        "codex": "Codex a repondu a la question de test.",
        "claude": "Claude a repondu a la question de test.",
        "jev": "JeV a repondu.",
    },
    "muet": {
        "brain_distant": "Le modele distant est joignable, mais il n'a rien rendu d'exploitable.",
        "codex": "Le pont Codex est joignable, mais Codex n'a pas donne la reponse attendue.",
        "claude": "Le pont Claude est joignable, mais Claude n'a pas donne la reponse attendue.",
        "jev": "JeV est joignable, mais la reponse attendue n'est pas venue.",
    },
    "delai": {
        "brain_distant": "Le modele distant est joignable, mais il n'a pas repondu dans le delai.",
        "codex": "Le pont Codex est joignable, mais Codex n'a pas repondu dans le delai.",
        "claude": "Le pont Claude est joignable, mais Claude n'a pas repondu dans le delai.",
        "jev": "JeV est joignable, mais il n'a pas repondu dans le delai.",
    },
    "echec": {
        "codex": "Le pont Codex est joignable, mais Codex n'a pas abouti. "
        "Si la connexion n'est pas faite, dans PowerShell : codex login",
        "claude": "Le pont Claude est joignable, mais Claude n'a pas abouti. "
        "Si la connexion n'est pas faite, dans PowerShell : claude",
    },
    "introuvable": {
        "codex": "Le pont Codex est joignable, mais Codex est introuvable sur la machine qui l'heberge.",
        "claude": "Le pont Claude est joignable, mais Claude est introuvable sur la machine qui l'heberge.",
    },
    "pas_le_pont": {
        "brain_distant": "Quelque chose repond a cette adresse, mais ce n'est pas le modele attendu.",
        "codex": "Quelque chose repond a cette adresse, mais ce n'est pas le pont Codex.",
        "claude": "Quelque chose repond a cette adresse, mais ce n'est pas le pont Claude.",
        "jev": "Quelque chose repond a cette adresse, mais ce n'est pas JeV.",
    },
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

# Le champ ou les deux ponts (`native/codexbridge`, `native/clibridge`)
# posent la reponse du harnais. Verifie sur le pont en marche le 2026-09-21.
_CHAMP_REPONSE_HARNAIS = "answer"


@dataclass
class Sonde:
    """Verdict d'une sonde.

    ``etat`` dit ce qui est prouve ; ``ok`` dit si le service est utilisable.
    Un appel ancien qui ne donne pas d'``etat`` obtient le plus prudent :
    ``repond`` si ``ok``, sinon ``injoignable`` — jamais l'inverse.
    """

    service: str
    ok: bool
    detail: str
    latence_ms: float | None
    etat: str = ""

    def __post_init__(self) -> None:
        if not self.etat:
            self.etat = ETAT_REPOND if self.ok else ETAT_INJOIGNABLE


@dataclass(frozen=True)
class VoixTts:
    voix: tuple[str, ...]
    depuis_serveur: bool
    langues: tuple[str, ...] = ()


# Repli si Magpie ne répond pas. Jamais la source du menu : extraire_voix_modele
# et extraire_langues_modele suivent data[] tel que le serveur le rend.
VOIX_TTS_REPLI = ("John", "Sofia", "Aria", "Jason", "Leo")
LANGUES_TTS_REPLI = (
    "en-US",
    "es-ES",
    "de-DE",
    "fr-FR",
    "it-IT",
    "vi-VN",
    "hi-IN",
)
_MAGPIE_PORT_DEFAUT = "8092"
_DELAI_EXTRAIT_S = 20.0


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


def _corps(response: Any) -> dict | None:
    """Le corps JSON en dict, ou ``None`` s'il est absent ou illisible.

    Un corps illisible n'est jamais une reponse : c'est le cas d'un proxy qui
    rend une page d'erreur avec un statut de succes.
    """
    lire = getattr(response, "json", None)
    if not callable(lire):
        return None
    try:
        valeur = lire()
    except Exception:
        return None
    return valeur if isinstance(valeur, dict) else None


def _verifier_harnais(payload: dict | None) -> bool:
    """Le harnais a-t-il vraiment repondu la question de test ?

    Les deux ponts rendent un statut de succes meme quand le harnais n'a rien
    dit : ``{"ok": false, "error": "question vide"}`` revient en quelques
    dizaines de millisecondes. Le statut seul ne prouve donc rien.
    """
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return False
    reponse = str(payload.get(_CHAMP_REPONSE_HARNAIS) or "").strip()
    return MARQUEUR_SONDE in reponse.lower()


def _raison_harnais(payload: dict | None) -> str:
    """Traduit l'erreur du pont en raison dicible.

    Le texte brut du pont n'est jamais repris : il peut citer un chemin, un
    code de sortie, ou une ligne de la sortie du harnais.
    """
    if not isinstance(payload, dict):
        return "muet"
    erreur = str(payload.get("error") or "").strip().lower()
    if not erreur:
        return "muet"
    if "delai" in erreur:
        return "delai"
    if "introuvable" in erreur or "indisponible" in erreur:
        return "introuvable"
    return "echec"


def _verifier_brain(payload: dict | None) -> bool:
    """Une completion de dialogue avec un contenu non vide."""
    if not isinstance(payload, dict):
        return False
    choix = payload.get("choices")
    if not isinstance(choix, list) or not choix:
        return False
    premier = choix[0]
    if not isinstance(premier, dict):
        return False
    message = premier.get("message")
    if isinstance(message, dict) and str(message.get("content") or "").strip():
        return True
    return bool(str(premier.get("text") or "").strip())


def _verifier_jev(payload: dict | None) -> bool:
    """La reponse au seul signal que la sonde pose."""
    if not isinstance(payload, dict):
        return False
    answers = payload.get("answers")
    return isinstance(answers, dict) and "phrase_finished" in answers


def _texte(raison: str, service: str) -> str:
    return _TEXTES[raison][service]


def _rendre(
    service: str, raison: str, debut: float | None, cle_len: int
) -> Sonde:
    """Construit le verdict et le journalise sans jamais citer la cle.

    L'etat decoule de la raison : seul « repond » allume le vert.
    """
    if raison == "repond":
        etat = ETAT_REPOND
    elif raison == "absent":
        etat = ETAT_ABSENT
    elif raison == "injoignable":
        etat = ETAT_INJOIGNABLE
    else:
        etat = ETAT_MUET
    latence = None if debut is None else (time.perf_counter() - debut) * 1000
    logger.info(
        "sonde %s: etat=%s raison=%s (cle_len=%s, latence_ms=%s)",
        service,
        etat,
        raison,
        cle_len,
        "n/a" if latence is None else f"{latence:.0f}",
    )
    return Sonde(service, etat == ETAT_REPOND, _texte(raison, service), latence, etat)


async def _avec_client(client: Any, corps: Callable[[Any], Awaitable[Any]]) -> Any:
    possede = False
    try:
        if client is None:
            import httpx

            client = httpx.AsyncClient(timeout=DELAI_HARNAIS_S)
            possede = True
        return await corps(client)
    finally:
        if possede and client is not None:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()


async def _poster(http: Any, url: str, charge: dict, jeton: str, delai: float) -> Any:
    return await asyncio.wait_for(
        http.post(
            url,
            json=charge,
            headers={
                "Authorization": f"Bearer {jeton}",
                "Content-Type": "application/json",
            },
            timeout=delai,
        ),
        timeout=delai,
    )


async def _poster_avec_repli(
    http: Any, cibles: list[str], charge: dict, jeton: str, delai: float
) -> tuple[Any, str]:
    """Essaie chaque adresse, rend la reponse et celle qui a tenu."""
    derniere: Exception | None = None
    for cible in cibles:
        try:
            return await _poster(http, cible, charge, jeton, delai), cible
        except Exception as exc:  # noqa: BLE001 — aucune exception ne sort
            derniere = exc
    assert derniere is not None
    raise derniere


def _cibles(url: str) -> list[str]:
    """L'adresse demandee, puis l'hote alterne s'il y en a un.

    Mesure du 2026-09-20 : depuis l'hote, ``host.docker.internal`` tombe et
    ``127.0.0.1`` repond — et l'inverse depuis le conteneur.
    """
    cibles = [url]
    alterne = _url_alternee(url)
    if alterne and alterne != url:
        cibles.append(alterne)
    return cibles


async def _sonder_service(
    service: str,
    url: str,
    charge: dict,
    jeton: str,
    client: Any,
    verifier: Callable[[dict | None], bool],
    delai: float,
) -> Sonde:
    """Un seul appel : joignabilite, puis verifications du corps."""
    jeton = _secret(jeton)
    if not jeton:
        logger.info("sonde %s: jeton absent (cle_len=0)", service)
        return Sonde(service, False, _texte("absent", service), None, ETAT_ABSENT)
    debut = time.perf_counter()

    async def corps(http: Any) -> Sonde:
        try:
            reponse, _cible = await _poster_avec_repli(
                http, _cibles(url), charge, jeton, delai
            )
        except Exception:  # noqa: BLE001 — aucune exception ne sort
            # Un depassement ici ne prouve pas que le service est joignable :
            # rien n'a repondu dans le delai, c'est le cas le plus prudent.
            return _rendre(service, "injoignable", debut, len(jeton))
        statut = _statut(reponse)
        if statut in (401, 403):
            return _rendre(service, "refuse", debut, len(jeton))
        if statut != 200:
            return _rendre(service, "pas_le_pont", debut, len(jeton))
        payload = _corps(reponse)
        if verifier(payload):
            return _rendre(service, "repond", debut, len(jeton))
        return _rendre(service, "muet", debut, len(jeton))

    try:
        return await _avec_client(client, corps)
    except Exception:  # noqa: BLE001
        return _rendre(service, "injoignable", debut, len(jeton))


async def _sonder_harnais(
    service: str, url: str, jeton: str, client: Any, agent: str | None
) -> Sonde:
    """Deux temps : le pont repond-il, puis le harnais repond-il.

    Le premier temps pose une question vide, borne a cinq secondes : il ne
    lance pas le harnais et sert seulement a distinguer « rien n'ecoute »,
    « le jeton est refuse » et « le pont est la ». Seul le second temps peut
    mettre le voyant en vert.
    """
    jeton = _secret(jeton)
    if not jeton:
        logger.info("sonde %s: jeton absent (cle_len=0)", service)
        return Sonde(service, False, _texte("absent", service), None, ETAT_ABSENT)
    debut = time.perf_counter()

    def charge_vide() -> dict:
        charge: dict = {"question": ""}
        if agent:
            charge["agent"] = agent
        return charge

    def charge_reelle() -> dict:
        # Les ponts ne lisent que `question` (et `agent` pour le pont CLI) :
        # aucun delai ne se commande depuis la requete.
        charge: dict = {"question": QUESTION_SONDE}
        if agent:
            charge["agent"] = agent
        return charge

    async def corps(http: Any) -> Sonde:
        try:
            reponse, cible = await _poster_avec_repli(
                http, _cibles(url), charge_vide(), jeton, DELAI_S
            )
        except Exception:  # noqa: BLE001 — aucune exception ne sort
            # Rien n'a repondu dans le delai court : on ne peut pas dire que
            # le pont est joignable, donc cas le plus prudent.
            return _rendre(service, "injoignable", debut, len(jeton))

        statut = _statut(reponse)
        if statut in (401, 403):
            return _rendre(service, "refuse", debut, len(jeton))
        if statut != 200:
            return _rendre(service, "pas_le_pont", debut, len(jeton))

        # Le pont est la et accepte ce jeton. Reste la seule question qui
        # compte : le harnais repond-il ?
        try:
            reponse = await _poster(
                http, cible, charge_reelle(), jeton, DELAI_HARNAIS_S
            )
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, TimeoutError):
                return _rendre(service, "delai", debut, len(jeton))
            return _rendre(service, "echec", debut, len(jeton))

        if _statut(reponse) != 200:
            # Le premier temps a deja prouve que c'est bien le pont : un
            # statut inattendu ici est un echec de l'appel, pas une erreur
            # d'adresse.
            return _rendre(service, "echec", debut, len(jeton))
        payload = _corps(reponse)
        if _verifier_harnais(payload):
            return _rendre(service, "repond", debut, len(jeton))
        return _rendre(service, _raison_harnais(payload), debut, len(jeton))

    try:
        return await _avec_client(client, corps)
    except Exception:  # noqa: BLE001
        return _rendre(service, "injoignable", debut, len(jeton))


async def sonder_brain_distant(
    endpoint: str, cle: str, modele: str, client=None
) -> Sonde:
    """Prouve : l'adresse repond, cette cle est acceptee, le modele rend du
    texte. Ne prouve pas : que le modele est celui attendu."""
    try:
        adresse = _secret(endpoint)
        if _secret(cle) and not adresse:
            return Sonde(
                "brain_distant",
                False,
                _texte("injoignable", "brain_distant"),
                None,
                ETAT_INJOIGNABLE,
            )
        charge = {
            "model": modele,
            "messages": [{"role": "user", "content": QUESTION_SONDE}],
            "max_tokens": 8,
            "stream": False,
        }
        return await _sonder_service(
            "brain_distant", adresse, charge, cle, client, _verifier_brain, DELAI_S
        )
    except Exception:
        return Sonde(
            "brain_distant",
            False,
            _texte("injoignable", "brain_distant"),
            None,
            ETAT_INJOIGNABLE,
        )


async def sonder_codex(url: str, jeton: str, client=None) -> Sonde:
    """Prouve : le pont repond, ce jeton est accepte, et Codex a repondu le
    mot attendu. Coute un vrai appel au harnais, d'ou le delai long."""
    try:
        adresse = _secret(url) or CODEX_BRIDGE_ENDPOINT
        return await _sonder_harnais("codex", adresse, jeton, client, None)
    except Exception:
        return Sonde(
            "codex", False, _texte("injoignable", "codex"), None, ETAT_INJOIGNABLE
        )


async def sonder_claude(url: str, jeton: str, client=None) -> Sonde:
    """Prouve : le pont repond, ce jeton est accepte, et Claude a repondu le
    mot attendu."""
    try:
        adresse = _secret(url) or CLI_BRIDGE_ENDPOINT
        return await _sonder_harnais("claude", adresse, jeton, client, "claude")
    except Exception:
        return Sonde(
            "claude", False, _texte("injoignable", "claude"), None, ETAT_INJOIGNABLE
        )


async def sonder_jev(cle: str, client=None, modele: str | None = None) -> Sonde:
    """Prouve : l'adresse repond, cette cle est acceptee, et le signal pose
    est revenu. Ne prouve pas : que le modele choisi est le bon."""
    try:
        nom = (modele or "").strip() or modele_jev()
        charge = {
            "state": {"transcription": "bonjour"},
            "model": nom,
            "questions": {"phrase_finished": QUESTIONS["phrase_finished"]},
        }
        return await _sonder_service(
            "jev", JEV_ENDPOINT, charge, cle, client, _verifier_jev, DELAI_S
        )
    except Exception:
        return Sonde(
            "jev", False, _texte("injoignable", "jev"), None, ETAT_INJOIGNABLE
        )


def _maison() -> Path:
    """Dossier personnel. Fonction a part pour que les tests la fixent."""
    return Path.home()


def _libelle(cle: str, defaut: str, **kwargs: Any) -> str:
    """``t()`` d'abord, francais local sinon.

    Les cles nouvelles ne sont pas encore dans ``src/i18n`` (hors perimetre
    de ce lot). Afficher la cle brute a l'ecran serait pire que du francais :
    on dit la phrase, et ajouter la cle dans ``src/i18n`` suffit a traduire.
    """
    texte = t(cle)
    if texte == cle:
        texte = defaut
    return texte.format(**kwargs) if kwargs else texte


def _lire_json(chemin: Path) -> Any:
    try:
        if not chemin.is_file():
            return None
        with open(chemin, "r", encoding="utf-8") as flux:
            return json.load(flux)
    except Exception:  # noqa: BLE001 — illisible veut dire « on ne sait pas »
        return None


def _jeton_non_vide(valeur: Any) -> bool:
    if isinstance(valeur, str):
        return bool(valeur.strip())
    if isinstance(valeur, dict):
        return any(_jeton_non_vide(item) for item in valeur.values())
    return False


def connexion_outil_posee(nom: str, maison: Path | None = None) -> bool | None:
    """Trace locale laissee par l'outil officiel apres une connexion.

    Lecture du fichier, rien d'autre : aucun appel reseau, aucun jeton OAuth
    interroge hors de l'outil officiel. Rend ``None`` quand la trace existe
    mais ne se lit pas — on ne sait pas, donc on ne dit pas « oui ».

    Ce que cela prouve : une connexion a ete faite sur cette machine. Ce que
    cela ne prouve pas : que l'abonnement est encore valable.
    """
    racine = Path(maison) if maison is not None else _maison()
    identifiant = (nom or "").strip().lower()
    try:
        if identifiant == "codex":
            chemin = racine / ".codex" / "auth.json"
            if not chemin.is_file():
                return False
            donnees = _lire_json(chemin)
            if not isinstance(donnees, dict):
                return None
            return bool(
                _jeton_non_vide(donnees.get("OPENAI_API_KEY"))
                or _jeton_non_vide(donnees.get("tokens"))
            )
        if identifiant == "claude":
            chemin = racine / ".claude" / ".credentials.json"
            if chemin.is_file():
                if _jeton_non_vide(_lire_json(chemin)):
                    return True
            donnees = _lire_json(racine / ".claude.json")
            if isinstance(donnees, dict) and _jeton_non_vide(
                donnees.get("oauthAccount")
            ):
                return True
            return None if chemin.is_file() else False
        return False
    except Exception:  # noqa: BLE001
        return None


def outil_cli_pret(nom: str) -> Sonde:
    """Un harnais est-il utilisable ici : executable **et** connexion posee.

    La presence de l'executable seul ne prouvait rien : un `codex` installe
    sans `codex login` tombe a la premiere question, et le voyant vert
    annoncait exactement l'inverse de la realite. On verifie donc aussi la
    trace locale que laisse l'outil officiel apres une connexion.

    Rien n'est envoye sur le reseau et aucune valeur d'identifiant n'est lue
    au-dela de sa presence : interroger l'OAuth hors des outils officiels
    serait contraire a leurs conditions. La preuve qu'un harnais repond
    vraiment reste l'appel au pont (`sonder_codex`, `sonder_claude`).
    """
    debut = time.perf_counter()
    identifiant = (nom or "").strip().lower() or "outil"

    def rendre(ok: bool, detail: str, etat: str) -> Sonde:
        latence = (time.perf_counter() - debut) * 1000
        logger.info("sonde outil %s: etat=%s", identifiant, etat)
        return Sonde(identifiant, ok, detail, latence, etat)

    try:
        if identifiant not in _OUTILS_CLI:
            return rendre(False, t("sondes.outil_inconnu"), ETAT_ABSENT)
        etiquette = _OUTILS_CLI[identifiant]
        commandes = _COMMANDES_PS[identifiant]
        if not shutil.which(identifiant):
            return rendre(
                False,
                t(
                    "sondes.outil_absent",
                    nom=etiquette,
                    commande=commandes["absent"],
                ),
                ETAT_INJOIGNABLE,
            )
        connexion = connexion_outil_posee(identifiant)
        if connexion is None:
            return rendre(
                False,
                _libelle(
                    "sondes.outil_connexion_illisible",
                    "L'outil {nom} est installé, mais sa connexion n'a pas pu "
                    "être lue. Dans PowerShell : {commande}",
                    nom=etiquette,
                    commande=commandes["present"],
                ),
                ETAT_MUET,
            )
        if not connexion:
            return rendre(
                False,
                _libelle(
                    "sondes.outil_sans_connexion",
                    "L'outil {nom} est installé, mais aucune connexion {nom} "
                    "n'est posée sur cette machine. Dans PowerShell : {commande}",
                    nom=etiquette,
                    commande=commandes["present"],
                ),
                ETAT_MUET,
            )
        return rendre(
            True,
            _libelle(
                "sondes.outil_connecte",
                "L'outil {nom} est installé, et une connexion {nom} est posée "
                "sur cette machine. Cela ne prouve pas encore l'abonnement : "
                "seul un appel au pont {nom} le prouve.",
                nom=etiquette,
            ),
            ETAT_REPOND,
        )
    except Exception:
        etiquette = _OUTILS_CLI.get(identifiant, identifiant)
        return rendre(
            False, t("sondes.outil_echec", nom=etiquette), ETAT_INJOIGNABLE
        )


def detecter_abonnements() -> list[Sonde]:
    """Codex puis Claude : executable present et connexion posee sur cette
    machine. Rien n'est envoye sur le reseau."""
    return [outil_cli_pret("codex"), outil_cli_pret("claude")]


async def sonder_tout(reglages: dict, client=None) -> list[Sonde]:
    """Les quatre services d'un coup, dans l'ordre d'affichage.

    Les deux ponts servent chaque requete sur son propre fil et n'ont pas de
    place unique : les quatre sondes partent donc ensemble, et le temps total
    est celui du plus lent, pas la somme.
    """
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
            Sonde(
                nom,
                False,
                _texte("injoignable", nom),
                None,
                ETAT_INJOIGNABLE,
            )
            for nom in ("brain_distant", "codex", "claude", "jev")
        ]


def _extraire_liste_modele(payload: Any, champ: str) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()
    data = payload.get("data")
    if not isinstance(data, list):
        return ()
    valeurs: list[str] = []
    vues: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        noms = item.get(champ)
        if not isinstance(noms, list):
            continue
        for nom in noms:
            texte = str(nom).strip() if nom is not None else ""
            if texte and texte not in vues:
                vues.add(texte)
                valeurs.append(texte)
    return tuple(valeurs)


def extraire_voix_modele(payload: Any) -> tuple[str, ...]:
    """Lit ``data[].voices`` du GET /v1/models Magpie. Rien d'autre."""
    return _extraire_liste_modele(payload, "voices")


def extraire_langues_modele(payload: Any) -> tuple[str, ...]:
    """Lit ``data[].languages`` du GET /v1/models Magpie. Rien d'autre."""
    return _extraire_liste_modele(payload, "languages")


def _port_magpie() -> str:
    brut = str(os.getenv("MOUTH_MAGPIE_PORT") or _MAGPIE_PORT_DEFAUT).strip()
    return brut or _MAGPIE_PORT_DEFAUT


def urls_voix_tts() -> tuple[str, ...]:
    port = _port_magpie()
    return (
        f"http://{_HOTE_LOCAL}:{port}/v1/models",
        f"http://{_HOTE_DOCKER}:{port}/v1/models",
    )


def urls_extrait_tts() -> tuple[str, ...]:
    return tuple(
        url.replace("/v1/models", "/v1/audio/speech") for url in urls_voix_tts()
    )


async def _get_json(client: Any, url: str) -> Any:
    response = await asyncio.wait_for(client.get(url, timeout=DELAI_S), timeout=DELAI_S)
    if _statut(response) != 200:
        return None
    lire = getattr(response, "json", None)
    if not callable(lire):
        return None
    return lire()


async def lister_voix_tts(client: Any = None) -> VoixTts:
    """GET /v1/models. Si le serveur ne rend pas de voix, repli connu."""

    async def une(http: Any, url: str) -> VoixTts | None:
        try:
            payload = await _get_json(http, url)
        except Exception:
            return None
        voix = extraire_voix_modele(payload)
        if not voix:
            return None
        return VoixTts(voix, True, extraire_langues_modele(payload))

    async def tenter(http: Any) -> VoixTts:
        vues: list[str] = []
        for url in urls_voix_tts():
            if url in vues:
                continue
            vues.append(url)
            resultat = await une(http, url)
            if resultat is not None:
                return resultat
            alterne = _url_alternee(url)
            if alterne and alterne not in vues:
                vues.append(alterne)
                resultat = await une(http, alterne)
                if resultat is not None:
                    return resultat
        return VoixTts(VOIX_TTS_REPLI, False, LANGUES_TTS_REPLI)

    try:
        return await _avec_client(client, tenter)
    except Exception:
        return VoixTts(VOIX_TTS_REPLI, False, LANGUES_TTS_REPLI)


async def synthetiser_extrait_tts(
    voix: str, langue: str, texte: str, client: Any = None
) -> bytes:
    """POST /v1/audio/speech. Voix et langue de phonétique, telles quelles."""

    charge = {
        "input": texte,
        "voice": voix,
        "language": langue,
        "response_format": "wav",
    }

    async def une(http: Any, url: str) -> bytes | None:
        try:
            response = await asyncio.wait_for(
                http.post(url, json=charge, timeout=_DELAI_EXTRAIT_S),
                timeout=_DELAI_EXTRAIT_S,
            )
        except Exception:
            return None
        if _statut(response) != 200:
            return None
        contenu = getattr(response, "content", None) or b""
        if not contenu:
            return None
        return bytes(contenu)

    async def tenter(http: Any) -> bytes:
        vues: list[str] = []
        for url in urls_extrait_tts():
            if url in vues:
                continue
            vues.append(url)
            wav = await une(http, url)
            if wav:
                return wav
            alterne = _url_alternee(url)
            if alterne and alterne not in vues:
                vues.append(alterne)
                wav = await une(http, alterne)
                if wav:
                    return wav
        return b""

    try:
        return await _avec_client(client, tenter)
    except Exception:
        return b""
