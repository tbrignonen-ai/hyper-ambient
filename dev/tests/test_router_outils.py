"""Le routeur face a la boucle d'outils : une seule attente s'annonce.

Mesure du 13 septembre, chaine reelle (routeur -> Luciole -> pont -> Codex) :

    [ 0.5s] AMORCE  'Un instant.'
    [ 1.6s] OUTIL   ask_codex -> call    « Je demande a Codex... »
    [17.8s] OUTIL   ask_codex -> result
    [18.1s] AMORCE  'Je verifie.'        <-- celle-ci est de trop
    [18.9s] reponse

`run_tool_loop` rappelle `query_streaming` a chaque tour de boucle. Le routeur,
lui, ne sait pas qu'il s'agit du meme tour de parole : il reclassifie et remet
une amorce. Resultat a l'oreille : trois phrases d'attente pour une seule
question, dont une qui tombe APRES l'attente qu'elle etait censee couvrir.

Le signe qu'un appel est une suite, et non un tour neuf, est dans la charge
utile : `messages` porte un message de role `tool`. Un tour neuf n'en a jamais.

Conventions de `test_router_fillers_j.py` : doublures locales, `asyncio.run`,
aucun reseau, hors :8090.
"""
from __future__ import annotations

import asyncio
import functools

from src.brain.router import FILLERS, RouterBrain, est_une_suite_d_outil


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class FakeChan:
    def __init__(self, name, query_result=None):
        self.name = name
        self.api_endpoint = f"http://{name}"
        self.calls = []
        self.query_result = query_result or {
            "response": f"{name}-reponse",
            "stop_reason": "stop",
            "tokens_used": 0,
            "latency_ms": 1,
        }

    async def query_streaming(self, prompt, **kw):
        self.calls.append({"prompt": prompt, **kw})
        yield {"delta": f"{self.name}-reponse", "stop_reason": None, "ttft_ms": 1.0}
        yield {"delta": "", "stop_reason": "stop", "ttft_ms": None}

    async def query(self, prompt, **kw):
        self.calls.append({"prompt": prompt, "query": True, **kw})
        return dict(self.query_result)


class FakeClassify:
    def __init__(self, verdict="ESCALADE"):
        self.verdict = verdict
        self.appels = 0

    async def post(self, url, json=None):
        self.appels += 1
        verdict = self.verdict

        class _R:
            def json(inner):
                return {"content": verdict}

        return _R()


def _router(deep=None, reflex=None):
    return RouterBrain(
        reflex or FakeChan("reflex"),
        deep or FakeChan("deep"),
        deep_timeout_ms=2000,
    )


# Ce que `run_tool_loop` repasse au modele au second tour : la question, puis
# l'assistant porteur de l'appel, puis le resultat de l'outil.
MESSAGES_SUITE = [
    {"role": "system", "content": "consigne"},
    {"role": "user", "content": "Demande à Codex ce que fait tool_loop."},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "ask_codex", "arguments": "{}"},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": "Neuf fichiers."},
]

MESSAGES_TOUR_NEUF = [
    {"role": "system", "content": "consigne"},
    {"role": "user", "content": "Quelle est la capitale de la Norvège ?"},
]


def test_est_une_suite_d_outil_est_faux_au_premier_tour():
    """Pourquoi le garde du 13/09 ne couvre pas les trois annonces empilées.

    Les trois phrases (amorce, phrase du modèle, accusé du mandat) naissent
    pendant le premier `query_streaming`, avant qu'un message `role=tool`
    existe. `est_une_suite_d_outil` ne voit donc rien à couper.
    """
    premier = [
        {"role": "system", "content": "consigne"},
        {"role": "user", "content": "Demande a Claude Code la version de Python."},
    ]
    assert est_une_suite_d_outil(premier) is False
    assert est_une_suite_d_outil(MESSAGES_SUITE) is True
    assert est_une_suite_d_outil(MESSAGES_TOUR_NEUF) is False


@runs_async
async def test_un_tour_qui_nomme_un_harnais_n_emet_pas_d_amorce():
    """L'accusé du mandat porte l'attente ; l'amorce dirait la même chose."""
    r = _router()
    r._client = FakeClassify("ESCALADE")
    chunks = [
        c
        async for c in r.query_streaming(
            "Demande a Claude Code de me dire la version de Python."
        )
    ]
    amorces = [c for c in chunks if c.get("channel") == "filler"]
    assert amorces == [], f"amorce en trop sur un harnais nommé : {[c['delta'] for c in amorces]}"


@runs_async
async def test_une_suite_d_outil_n_emet_pas_d_amorce():
    """L'invariant : l'attente a deja ete annoncee avant l'appel d'outil."""
    r = _router()
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("peu importe", messages=MESSAGES_SUITE)]
    amorces = [c for c in chunks if c.get("channel") == "filler"]
    assert amorces == [], f"amorce en trop apres l'outil : {[c['delta'] for c in amorces]}"


@runs_async
async def test_un_tour_neuf_garde_son_amorce():
    """Garde-fou : on coupe l'amorce de la SUITE, pas l'amorce tout court.

    Sans ce test, supprimer l'amorce partout passerait pour un succes — et
    rendrait chaque escalade silencieuse pendant toute la reflexion distante.
    """
    r = _router()
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("capitale ?", messages=MESSAGES_TOUR_NEUF)]
    amorces = [c for c in chunks if c.get("channel") == "filler"]
    assert len(amorces) == 1
    assert amorces[0]["delta"] in FILLERS


@runs_async
async def test_un_tour_sans_messages_garde_son_amorce():
    """Le chemin d'avant — aucun `messages` — n'est pas touche."""
    r = _router()
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("capitale ?")]
    assert [c for c in chunks if c.get("channel") == "filler"]


@runs_async
async def test_la_suite_transmet_bien_messages_et_outils_au_canal_distant():
    """Couper l'amorce ne doit rien couper d'autre : la suite doit repondre."""
    deep = FakeChan("deep")
    r = _router(deep=deep)
    r._client = FakeClassify("ESCALADE")
    outils = [{"type": "function", "function": {"name": "ask_codex"}}]
    chunks = [
        c
        async for c in r.query_streaming(
            "peu importe", messages=MESSAGES_SUITE, tools=outils
        )
    ]
    assert deep.calls, "le canal distant n'a pas ete appele"
    assert deep.calls[0]["messages"] == MESSAGES_SUITE
    assert deep.calls[0]["tools"] == outils
    assert any(c.get("delta") == "deep-reponse" for c in chunks)


SCHEMAS_OUTILS = [
    {"type": "function", "function": {"name": "ask_codex"}},
    {"type": "function", "function": {"name": "web_search"}},
]


@runs_async
async def test_reflexe_ne_transmet_pas_les_outils_au_canal_local():
    """« Bonjour. » classé REFLEXE ne doit plus voir les schémas (17 sept)."""
    reflex = FakeChan("reflex")
    deep = FakeChan("deep")
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("REFLEXE")
    chunks = [
        c
        async for c in r.query_streaming(
            "Bonjour.", tools=SCHEMAS_OUTILS, tool_choice="auto"
        )
    ]
    assert reflex.calls, "le canal local n'a pas été appelé"
    assert "tools" not in reflex.calls[0]
    assert "tool_choice" not in reflex.calls[0]
    assert deep.calls == []
    assert all(c.get("channel") == "reflex" for c in chunks)
    assert any(c.get("delta") == "reflex-reponse" for c in chunks)


@runs_async
async def test_escalade_transmet_les_outils_au_canal_distant():
    reflex = FakeChan("reflex")
    deep = FakeChan("deep")
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("ESCALADE")
    _ = [
        c
        async for c in r.query_streaming("Demande à Codex ce que fait tool_loop.", tools=SCHEMAS_OUTILS)
    ]
    assert deep.calls
    assert deep.calls[0]["tools"] == SCHEMAS_OUTILS
    assert reflex.calls == []


@runs_async
async def test_repli_vers_le_reflexe_retire_aussi_les_outils():
    class Boom(FakeChan):
        async def query_streaming(self, prompt, **kw):
            self.calls.append({"prompt": prompt, **kw})
            yield {"delta": "", "stop_reason": "error", "ttft_ms": None, "error": "boom"}

    reflex = FakeChan("reflex")
    deep = Boom("deep")
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("ESCALADE")
    chunks = [
        c async for c in r.query_streaming("capitale ?", tools=SCHEMAS_OUTILS)
    ]
    assert deep.calls and "tools" in deep.calls[0]
    assert reflex.calls, "le repli local n'a pas eu lieu"
    assert "tools" not in reflex.calls[0]
    assert any(c.get("channel") == "reflex" for c in chunks)


@runs_async
async def test_query_non_stream_reflexe_sans_outils():
    reflex = FakeChan("reflex")
    deep = FakeChan("deep")
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("REFLEXE")
    result = await r.query("Bonjour.", tools=SCHEMAS_OUTILS, tool_choice="auto")
    assert result["channel"] == "reflex"
    assert "tools" not in reflex.calls[0]
    assert "tool_choice" not in reflex.calls[0]
    assert deep.calls == []


# Un tour qui nomme un harnais ne doit jamais partir en REFLEXE : la voie
# reflexe est la seule sans outils, donc la seule ou le mandat ne peut pas
# aboutir. Court-circuit avant le classifieur.


@runs_async
async def test_enonce_nommant_codex_escalade_sans_classifieur():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    decision = await r.classify(
        "Envoie une requete a Codex qui ouvre le programme calque.exe sur le bureau."
    )
    assert decision["route"] == "escalate"
    assert decision["verdict"] == "HARNAIS"
    assert r._client.appels == 0


@runs_async
async def test_enonce_nommant_claude_escalade_sans_classifieur():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    decision = await r.classify("Demande a Claude de relire transport.py.")
    assert decision["route"] == "escalate"
    assert decision["verdict"] == "HARNAIS"
    assert r._client.appels == 0


@runs_async
async def test_enonce_nommant_cursor_escalade_sans_classifieur():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    decision = await r.classify("Demande a Cursor d'ouvrir le fichier.")
    assert decision["route"] == "escalate"
    assert decision["verdict"] == "HARNAIS"
    assert r._client.appels == 0


@runs_async
async def test_enonce_nommant_muse_escalade_sans_classifieur():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    decision = await r.classify("Demande a Muse un plan pour la soutenance.")
    assert decision["route"] == "escalate"
    assert decision["verdict"] == "HARNAIS"
    assert r._client.appels == 0


@runs_async
async def test_bonjour_passe_encore_par_le_classifieur_et_reste_reflexe():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    decision = await r.classify("Bonjour.")
    assert decision["route"] == "reflex"
    assert decision["verdict"] == "REFLEXE"
    assert r._client.appels == 1


@runs_async
async def test_casse_et_ponctuation_ne_comptent_pas_pour_un_harnais():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    decision = await r.classify("demande a CODEX, stp")
    assert decision["route"] == "escalate"
    assert decision["verdict"] == "HARNAIS"
    assert r._client.appels == 0
