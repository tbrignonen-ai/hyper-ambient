"""`ask_muse` : le deuxieme agent que la voix peut interroger.

Codex lit le depot. Muse ne le lit pas — son pont tourne dans WSL avec son
propre espace de travail (`~/.local/share/muse-bridge/hermes/workspace`). Les
deux outils ne sont donc pas redondants : l'un repond sur **les fichiers de
cette machine**, l'autre donne **un second avis** d'un autre modele. C'est la
description de l'outil qui porte cette distinction, puisque c'est elle, et rien
d'autre, que le modele lit pour choisir.

Mesure du 13 septembre, depuis le conteneur vers `host.docker.internal:19124` :
HTTP 200 en 23,8 s, `{"text", "session_id", "model"}`, modele `muse-spark-1.3`.
Le pont etait deja debout (il servait a Hermes) : **on ne rallume rien**, on
s'adresse a ce qui ecoute.

Meme contrat que `ask_codex`, pour les memes raisons vocales : client injecte,
aucun appel sans configuration explicite, et **tout ce qui sort est une phrase
prononcable** — jamais de JSON, de code HTTP ni de trace.
"""
from __future__ import annotations

import asyncio
import functools

from src.brain.tools import MAX_TOOL_CONTENT_CHARS, ToolRegistry
from src.brain.tools_muse import MuseBridge, register_ask_muse


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class _Reponse:
    def __init__(self, status_code=200, payload=None, illisible=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._illisible = illisible

    def json(self):
        if self._illisible:
            raise ValueError("corps illisible")
        return self._payload


class _ClientDouble:
    """Retient l'appel. Ne joint jamais le reseau."""

    def __init__(self, reponse=None, exception=None):
        self.reponse = reponse
        self.exception = exception
        self.appels = []

    async def post(self, url, **kw):
        self.appels.append({"url": url, **kw})
        if self.exception is not None:
            raise self.exception
        return self.reponse


# --- la sortie est toujours prononcable --------------------------------------


def _est_prononcable(phrase: str) -> bool:
    """Ni JSON, ni code HTTP, ni trace : ce qui sort d'ici part vers MOUTH."""
    if not phrase or not phrase.strip():
        return False
    interdits = ("{", "}", "[", "]", "HTTP", "Traceback", "Error", "None", "http://")
    return not any(marque in phrase for marque in interdits)


@runs_async
async def test_sans_url_aucun_appel_et_une_phrase():
    pont = MuseBridge(url="", client=_ClientDouble())
    phrase = await pont(question="peu importe")
    assert _est_prononcable(phrase)
    assert pont.client.appels == []


@runs_async
async def test_sans_client_aucun_appel_et_une_phrase():
    pont = MuseBridge(url="http://pont:19124", client=None)
    assert _est_prononcable(await pont(question="peu importe"))


@runs_async
async def test_pont_injoignable_se_dit_et_ne_leve_pas():
    pont = MuseBridge(
        url="http://pont:19124", client=_ClientDouble(exception=OSError("refus"))
    )
    phrase = await pont(question="peu importe")
    assert _est_prononcable(phrase)
    assert "Muse" in phrase


@runs_async
async def test_erreur_http_se_dit():
    pont = MuseBridge(
        url="http://pont:19124", client=_ClientDouble(_Reponse(status_code=500))
    )
    assert _est_prononcable(await pont(question="peu importe"))


@runs_async
async def test_corps_illisible_se_dit():
    pont = MuseBridge(
        url="http://pont:19124", client=_ClientDouble(_Reponse(illisible=True))
    )
    assert _est_prononcable(await pont(question="peu importe"))


@runs_async
async def test_reponse_vide_se_dit():
    pont = MuseBridge(
        url="http://pont:19124", client=_ClientDouble(_Reponse(payload={"text": "   "}))
    )
    assert _est_prononcable(await pont(question="peu importe"))


# --- le chemin heureux --------------------------------------------------------


@runs_async
async def test_la_reponse_de_muse_ressort_telle_quelle():
    attendu = "Un modèle local garde vos données sur votre machine."
    pont = MuseBridge(
        url="http://pont:19124",
        client=_ClientDouble(_Reponse(payload={"text": attendu, "model": "muse-spark-1.3"})),
    )
    assert await pont(question="c'est quoi ?") == attendu


@runs_async
async def test_l_appel_porte_l_instruction_sur_la_route_ask():
    """Le contrat mesure du pont : POST /ask, champ `instruction`.

    Ce test exigeait d'abord la question **nue**. L'implementation lui ajoute
    une consigne de forme, et c'est l'implementation qui a raison : la reponse
    de Muse part vers MOUTH, et un pont qui rend du markdown fait epeler des
    etoiles a voix haute. Le test est donc resserre sur ce qui compte — la
    question arrive intacte, et la consigne vocale l'accompagne — au lieu
    d'etre relache sur l'egalite. La difference est importante : relacher
    aurait laisse passer une instruction vide.
    """
    client = _ClientDouble(_Reponse(payload={"text": "ok."}))
    pont = MuseBridge(url="http://pont:19124", client=client)
    await pont(question="pourquoi le ciel est bleu ?")
    appel = client.appels[0]
    assert appel["url"] == "http://pont:19124/ask"
    instruction = appel["json"]["instruction"]
    assert instruction.endswith("pourquoi le ciel est bleu ?")
    bas = instruction.lower()
    assert "parlable" in bas or "markdown" in bas


@runs_async
async def test_une_reponse_trop_longue_est_tronquee():
    """Quatre mille caracteres lus a voix haute sont une regression, pas une reponse."""
    pont = MuseBridge(
        url="http://pont:19124",
        client=_ClientDouble(_Reponse(payload={"text": "mot " * 2000})),
    )
    phrase = await pont(question="raconte")
    assert len(phrase) <= MAX_TOOL_CONTENT_CHARS


# --- l'enregistrement ---------------------------------------------------------


def test_enregistrement_en_lecture_seule():
    registre = ToolRegistry()
    register_ask_muse(registre, url="http://pont:19124", client=_ClientDouble())
    assert "ask_muse" in registre
    assert registre.danger_of("ask_muse") == "read"


def test_la_description_distingue_muse_de_codex():
    """Le modele choisit sur la description seule : elle doit trancher.

    Sans cette distinction, les deux outils se ressemblent et le modele
    interroge Codex sur des questions generales — ou Muse sur des fichiers
    qu'il ne peut pas voir.
    """
    from src.brain.tools_codex import ASK_CODEX_DESCRIPTION
    from src.brain.tools_muse import ASK_MUSE_DESCRIPTION

    assert ASK_MUSE_DESCRIPTION != ASK_CODEX_DESCRIPTION
    bas = ASK_MUSE_DESCRIPTION.lower()
    # Muse ne voit pas le depot : sa description ne doit pas le promettre.
    assert "fichier" not in bas
    assert "depot" not in bas and "dépôt" not in bas
    assert "avis" in bas or "autre" in bas


def test_le_schema_declare_une_question_obligatoire():
    registre = ToolRegistry()
    register_ask_muse(registre, url="http://pont:19124", client=_ClientDouble())
    schema = [s for s in registre.schemas() if s["function"]["name"] == "ask_muse"][0]
    params = schema["function"]["parameters"]
    assert params["required"] == ["question"]
    assert params["properties"]["question"]["type"] == "string"
