"""
Vague J — regression amorces FILLERS/HOLDING + classify (sans llama).

`test_router_amorces.py` couvre flush, holding lent, composer_rapport.
Ici ce qui restait a pincer pour ne pas regresser le registre vocal :

  - query() non-stream n'emet aucune amorce (rien n'est parle)
  - rotation sur plusieurs escalades consecutives
  - holding qui wrappe la liste de 2
  - few-shots du prefixe = 3 REFLEXE + 3 ESCALADE (les memes que le smoke)
  - grammaire GBNF binaire exacte
  - enable_filler=False coupe AUSSI le holding
  - filler : stop_reason None, flush True, channel filler
  - defaut classify_host = localhost:8080 (piege IPv6 / port conteneur)

asyncio.run — pas de pytest-asyncio. Hors :8090.
"""
from __future__ import annotations

import asyncio
import functools
import re

from src.brain.router import (
    CLASSIFY_GRAMMAR,
    CLASSIFY_PREFIX,
    CLASSIFY_SUFFIX,
    FILLERS,
    HOLDING,
    LONGUEUR_ANAPHORIQUE,
    RouterBrain,
    doit_joindre_contexte,
)


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class FakeChan:
    def __init__(self, name, scripts=None, query_result=None, delay=0.0):
        self.name = name
        self.api_endpoint = f"http://{name}"
        self.scripts = list(scripts or [])
        self.query_result = query_result or {
            "response": "ok", "stop_reason": "stop", "tokens_used": 0, "latency_ms": 1,
        }
        self.delay = delay
        self.calls = []

    async def query_streaming(self, prompt, **kw):
        self.calls.append({"prompt": prompt, **kw})
        if self.delay:
            await asyncio.sleep(self.delay)
        script = self.scripts.pop(0) if self.scripts else [
            {"delta": f"{self.name}-fin", "stop_reason": None, "ttft_ms": 1.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ]
        for chunk in script:
            yield chunk

    async def query(self, prompt, **kw):
        self.calls.append({"prompt": prompt, "query": True, **kw})
        return dict(self.query_result)

    async def health(self):
        return {"ok": True, "detail": self.name, "latency_ms": 1.0}

    async def initialize(self):
        return None

    async def close(self):
        return None


class FakeClassify:
    def __init__(self, verdict="ESCALADE", latency_payload=None):
        self.verdict = verdict
        self.bodies = []
        self.urls = []

    async def post(self, url, json=None):
        self.urls.append(url)
        self.bodies.append(json)

        class _R:
            def json(inner):
                return {"content": self.verdict}

        return _R()


def _router(reflex=None, deep=None, **kw):
    return RouterBrain(
        reflex or FakeChan("reflex"),
        deep or FakeChan("deep"),
        enable_filler=kw.pop("enable_filler", True),
        deep_timeout_ms=kw.pop("deep_timeout_ms", 2000),
        **kw,
    )


# -- listes : regression de registre -----------------------------------------


def test_fillers_sont_quatre_uniques_sans_excuse():
    assert FILLERS == [
        "Un instant.",
        "Je vérifie.",
        "Analyse en cours.",
        "Je consulte les données.",
    ]
    assert len(set(FILLERS)) == 4
    for f in FILLERS:
        assert f.endswith(".")
        assert f.count(".") == 1
        assert "..." not in f and "…" not in f
        bas = f.casefold()
        for mot in ("désol", "desole", "excuse", "pardon", "sorry", "attendez", "patience"):
            assert mot not in bas
        assert "REFLEXE" not in f and "ESCALADE" not in f


def test_holding_sont_deux_uniques_sans_excuse():
    assert HOLDING == [
        "Je traite toujours la demande.",
        "Encore quelques instants.",
    ]
    assert len(set(HOLDING)) == 2
    assert set(FILLERS).isdisjoint(HOLDING)
    for h in HOLDING:
        assert h.endswith(".")
        bas = h.casefold()
        for mot in ("désol", "crash", "timeout", "erreur", "sorry"):
            assert mot not in bas


def test_few_shots_prefixe_sont_trois_plus_trois():
    reflexe = re.findall(r"Classe: REFLEXE", CLASSIFY_PREFIX)
    escalade = re.findall(r"Classe: ESCALADE", CLASSIFY_PREFIX)
    assert len(reflexe) == 3
    assert len(escalade) == 3
    assert "Bonjour hyper-ambient." in CLASSIFY_PREFIX
    assert "Merci, c'est noté." in CLASSIFY_PREFIX
    assert "Répète plus fort." in CLASSIFY_PREFIX
    assert "capitale de la Norvège" in CLASSIFY_PREFIX
    assert "14 h 40" in CLASSIFY_PREFIX
    assert "Paris demain" in CLASSIFY_PREFIX
    assert CLASSIFY_SUFFIX == "\nClasse:"
    assert "Dans le doute, réponds ESCALADE." in CLASSIFY_PREFIX


def test_grammaire_gbnf_binaire_exacte():
    assert CLASSIFY_GRAMMAR == 'root ::= "REFLEXE" | "ESCALADE"'
    assert "FAST" not in CLASSIFY_GRAMMAR
    assert "DEEP" not in CLASSIFY_GRAMMAR
    assert "SIMPLE" not in CLASSIFY_GRAMMAR


def test_seuil_anaphorique_compte_le_strip():
    assert LONGUEUR_ANAPHORIQUE == 25
    assert doit_joindre_contexte("  " + "x" * 24 + "  ") is True
    assert doit_joindre_contexte("  " + "x" * 25 + "  ") is False
    assert doit_joindre_contexte("\n\t") is False


def test_classify_host_defaut_est_le_port_conteneur(monkeypatch):
    """Piege documente : 8080/localhost, pas 8090/127.0.0.1 de l'hote."""
    monkeypatch.delenv("LLAMA_SERVER_HOST", raising=False)
    r = _router()
    assert r.classify_host == "http://localhost:8080"
    monkeypatch.setenv("LLAMA_SERVER_HOST", "http://127.0.0.1:8090/")
    r2 = RouterBrain(FakeChan("r"), FakeChan("d"))
    assert r2.classify_host == "http://127.0.0.1:8090"


# -- query() vs query_streaming ----------------------------------------------


@runs_async
async def test_query_non_stream_n_emet_pas_de_filler():
    deep = FakeChan("deep", query_result={
        "response": "Paris.", "stop_reason": "stop", "tokens_used": 1, "latency_ms": 3,
    })
    r = _router(deep=deep)
    r._client = FakeClassify("ESCALADE")
    result = await r.query("capitale ?")
    assert result["channel"] == "escalate"
    assert result["response"] == "Paris."
    assert deep.calls and deep.calls[0].get("query") is True


@runs_async
async def test_query_reflexe_ne_touche_pas_le_deep():
    deep = FakeChan("deep")
    reflex = FakeChan("reflex", query_result={
        "response": "Coucou.", "stop_reason": "stop", "tokens_used": 1, "latency_ms": 2,
    })
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("REFLEXE")
    result = await r.query("Bonjour")
    assert result["channel"] == "reflex"
    assert deep.calls == []
    assert reflex.calls


@runs_async
async def test_escalades_consecutives_rotent_les_fillers():
    r = _router()
    r._client = FakeClassify("ESCALADE")
    firsts = []
    for _ in range(len(FILLERS) + 1):
        chunks = [c async for c in r.query_streaming("capitale ?")]
        firsts.append(chunks[0]["delta"])
        r._client = FakeClassify("ESCALADE")
    assert firsts[:4] == FILLERS
    assert firsts[4] == FILLERS[0]


@runs_async
async def test_filler_contrat_mouth():
    r = _router()
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("pourquoi ?")]
    filler = chunks[0]
    assert filler["channel"] == "filler"
    assert filler["flush"] is True
    assert filler["stop_reason"] is None
    assert filler["delta"] in FILLERS
    assert filler["delta"] != ""
    assert isinstance(filler["ttft_ms"], (int, float))


@runs_async
async def test_sans_filler_pas_de_holding_non_plus():
    deep = FakeChan("deep", delay=0.08, scripts=[[
        {"delta": "voici.", "stop_reason": None, "ttft_ms": 1.0},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None},
    ]])
    r = _router(deep=deep, enable_filler=False, deep_timeout_ms=2000)
    r.holding_after_ms = 20
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("question")]
    assert all(c.get("channel") not in {"filler", "holding"} for c in chunks)
    assert all(not c.get("flush") for c in chunks)
    assert any(c.get("delta") == "voici." for c in chunks)


@runs_async
async def test_holding_plafonne_a_deux_lignes_meme_si_le_deep_est_plus_lent():
    """max_holding = len(HOLDING) : une 3e ligne serait du bavardage, pas de la presence."""
    deep = FakeChan("deep", delay=0.12, scripts=[[
        {"delta": "fin.", "stop_reason": None, "ttft_ms": 1.0},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None},
    ]])
    r = _router(deep=deep, deep_timeout_ms=2000)
    r.holding_after_ms = 25
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("dur")]
    holdings = [c for c in chunks if c.get("channel") == "holding"]
    assert len(holdings) == len(HOLDING) == 2
    assert [c["delta"] for c in holdings] == list(HOLDING)
    assert all(c["flush"] is True for c in holdings)
    assert all(c["stop_reason"] is None for c in holdings)
    assert any(c.get("delta") == "fin." for c in chunks)


@runs_async
async def test_reflexe_ignore_enable_filler():
    r = _router(enable_filler=True)
    r._client = FakeClassify("REFLEXE")
    chunks = [c async for c in r.query_streaming("Merci")]
    assert all(c.get("channel") == "reflex" for c in chunks)
    assert r.stats["reflex"] == 1
    assert r.stats["escalate"] == 0


@runs_async
async def test_classify_envoie_grammaire_et_cache_prompt():
    fake = FakeClassify("REFLEXE")
    r = _router(classify_host="http://127.0.0.1:8090")
    r._client = fake
    decision = await r.classify("Bonjour hyper-ambient.")
    assert decision["route"] == "reflex"
    assert decision["verdict"] == "REFLEXE"
    body = fake.bodies[0]
    assert body["grammar"] == CLASSIFY_GRAMMAR
    assert body["n_predict"] == 4
    assert body["temperature"] == 0
    assert body["cache_prompt"] is True
    assert body["prompt"].startswith(CLASSIFY_PREFIX)
    assert body["prompt"].endswith(CLASSIFY_SUFFIX)
    assert "Bonjour hyper-ambient." in body["prompt"]
    assert fake.urls == ["http://127.0.0.1:8090/completion"]


@runs_async
async def test_verdict_vide_ou_bruit_escalade():
    for verdict in ("", "  ", "FAST", "reflexe", "Escalate", "REFLEX"):
        r = _router()
        r._client = FakeClassify(verdict)
        decision = await r.classify("x")
        assert decision["route"] == "escalate", verdict
