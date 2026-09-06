"""
Amorces du routeur : FILLERS, HOLDING, composer_rapport, flush.

Sans llama-server : le classifieur est un double HTTP, les canaux reflex
et deep sont des generateurs scripts. On verifie que l'amorce part avec
flush=True (sinon MOUTH la bufferise), qu'elle n'entre pas dans le texte
du rapport, et que le holding ne tue pas le flux distant.
"""
import asyncio
import functools
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.brain.router import (
    CLASSIFY_GRAMMAR,
    FILLERS,
    HOLDING,
    LONGUEUR_ANAPHORIQUE,
    RouterBrain,
    _with_holding,
    doit_joindre_contexte,
)


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


RACINE = Path(__file__).resolve().parents[2]


def _charger_serve_hostagent():
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    for nom in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
        sys.modules.setdefault(nom, MagicMock(name=nom))
    chemin = RACINE / "dev" / "scripts" / "serve_hostagent.py"
    spec = importlib.util.spec_from_file_location("serve_hostagent_amorces_edges", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_hostagent = _charger_serve_hostagent()


class FakeChan:
    def __init__(self, name, scripts=None, query_result=None, delay=0.0, raise_after=None):
        self.name = name
        self.api_endpoint = f"http://{name}"
        self.scripts = list(scripts or [])
        self.query_result = query_result or {
            "response": "ok", "stop_reason": "stop", "tokens_used": 0, "latency_ms": 1,
        }
        self.delay = delay
        self.raise_after = raise_after
        self.calls = []

    async def query_streaming(self, prompt, **kw):
        self.calls.append({"prompt": prompt, **kw})
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raise_after == "before":
            raise RuntimeError("deep down")
        script = self.scripts.pop(0) if self.scripts else [
            {"delta": f"{self.name}-fin", "stop_reason": None, "ttft_ms": 1.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ]
        for chunk in script:
            yield chunk
            if chunk.get("delta") and self.raise_after == "after":
                raise RuntimeError("coupe en cours")

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
    def __init__(self, verdict="ESCALADE"):
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


# -- listes d'amorces --------------------------------------------------------


def test_fillers_sont_courts_sans_excuse():
    assert len(FILLERS) >= 3
    for f in FILLERS:
        assert f.endswith(".")
        assert len(f) <= 40
        bas = f.lower()
        assert "desole" not in bas and "désolé" not in bas
        assert "pardon" not in bas
        assert "sorry" not in bas
        assert "{" not in f and "tool" not in bas


def test_holding_sont_courts_sans_excuse():
    assert len(HOLDING) >= 2
    for h in HOLDING:
        assert h.endswith(".")
        assert len(h) <= 50
        bas = h.lower()
        assert "desole" not in bas and "désolé" not in bas
        assert "crash" not in bas
        assert "timeout" not in bas


def test_fillers_et_holding_sont_disjoints():
    assert set(FILLERS).isdisjoint(HOLDING)


def test_grammaire_binaire():
    assert "REFLEXE" in CLASSIFY_GRAMMAR
    assert "ESCALADE" in CLASSIFY_GRAMMAR
    assert "FAST" not in CLASSIFY_GRAMMAR
    assert "DEEP" not in CLASSIFY_GRAMMAR


def test_seuil_anaphorique_est_strict():
    assert LONGUEUR_ANAPHORIQUE == 25
    assert doit_joindre_contexte("x" * 24) is True
    assert doit_joindre_contexte("x" * 25) is False
    assert doit_joindre_contexte("x" * 26) is False
    assert doit_joindre_contexte("") is False


# -- composer_rapport --------------------------------------------------------


def test_composer_separe_filler_et_holding_de_la_reponse():
    text, amorces = serve_hostagent.composer_rapport(
        [FILLERS[0], HOLDING[0]],
        ["Bleu", ", blanc", ", rouge"],
    )
    assert text == "Bleu, blanc, rouge"
    assert FILLERS[0] in amorces
    assert HOLDING[0] in amorces
    assert not text.startswith(FILLERS[0])
    assert HOLDING[0] not in text


def test_composer_ne_filtre_pas_un_echo_du_modele():
    """Si le modele reprend l'amorce dans reponse[], composer_rapport ne l'ote pas :
    c'est _enchainer qui trie par flush, pas un nettoyage de texte."""
    text, amorces = serve_hostagent.composer_rapport([], [FILLERS[0] + " suite"])
    assert text.startswith(FILLERS[0])
    assert amorces == ""


def test_composer_joint_les_morceaux_sans_espace_ajoute():
    text, _ = serve_hostagent.composer_rapport([], ["Bon", "jour"])
    assert text == "Bonjour"


def test_composer_ignore_amorces_blanches():
    text, amorces = serve_hostagent.composer_rapport(["  ", "", FILLERS[1]], ["ok"])
    assert text == "ok"
    assert amorces == FILLERS[1]


def test_toutes_les_amorces_hors_du_champ_text():
    for amorce in FILLERS + HOLDING:
        text, texte_amorces = serve_hostagent.composer_rapport([amorce], ["Réponse utile."])
        assert text == "Réponse utile."
        assert texte_amorces == amorce
        assert not text.startswith(amorce)


# -- rotation et flush -------------------------------------------------------


def test_rotation_des_fillers():
    r = _router()
    sequence = [r._next_filler() for _ in range(len(FILLERS) * 2)]
    assert sequence[: len(FILLERS)] == FILLERS
    assert sequence[len(FILLERS):] == FILLERS


@runs_async
async def test_escalade_emet_un_filler_flush_avant_le_deep():
    deep = FakeChan("deep", delay=0.0, scripts=[[
        {"delta": "Paris.", "stop_reason": None, "ttft_ms": 8.0},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None},
    ]])
    r = _router(deep=deep)
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("Quel temps a Paris ?")]
    assert chunks[0]["channel"] == "filler"
    assert chunks[0]["flush"] is True
    assert chunks[0]["delta"] in FILLERS
    assert chunks[0]["delta"] != ""
    assert any(c.get("channel") == "deep" and c.get("delta") == "Paris." for c in chunks)
    assert r.stats["escalate"] == 1
    assert r.stats["reflex"] == 0


@runs_async
async def test_sans_filler_aucun_flush():
    r = _router(enable_filler=False)
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("capitale")]
    assert all(c.get("channel") != "filler" for c in chunks)
    assert all(not c.get("flush") for c in chunks)
    assert any(c.get("channel") == "deep" for c in chunks)


@runs_async
async def test_reflexe_n_emet_pas_d_amorce():
    r = _router()
    r._client = FakeClassify("REFLEXE")
    chunks = [c async for c in r.query_streaming("Bonjour")]
    assert all(c.get("channel") == "reflex" for c in chunks)
    assert all(c.get("channel") != "filler" for c in chunks)
    assert r.stats["reflex"] == 1


@runs_async
async def test_verdict_imprevu_escalade():
    r = _router()
    r._client = FakeClassify("FAST")
    chunks = [c async for c in r.query_streaming("x")]
    assert chunks[0]["channel"] == "filler"
    assert r.stats["escalate"] == 1


@runs_async
async def test_sans_client_escalade_tout_de_suite():
    r = _router()
    assert r._client is None
    decision = await r.classify("bonjour")
    assert decision["route"] == "escalate"
    assert decision["reason"] == "no client"


@runs_async
async def test_contexte_joint_seulement_si_court():
    fake = FakeClassify("ESCALADE")
    r = _router()
    r._client = fake
    await r.classify("vas-y", contexte=[{"role": "assistant", "content": "Capitale de la Norvege ?"}])
    prompt = fake.bodies[0]["prompt"]
    assert "Tour precedent" in prompt
    assert "Norvege" in prompt

    fake2 = FakeClassify("ESCALADE")
    r._client = fake2
    long_q = "Il est 14 heures 40, ma reunion commence dans 20 minutes et dure 40 minutes, a quelle heure je finis ?"
    await r.classify(long_q, contexte=[{"role": "assistant", "content": "Bonjour"}])
    assert "Tour precedent" not in fake2.bodies[0]["prompt"]


@runs_async
async def test_holding_couvre_un_deep_lent():
    deep = FakeChan("deep", delay=0.12, scripts=[[
        {"delta": "voici.", "stop_reason": None, "ttft_ms": 1.0},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None},
    ]])
    r = _router(deep=deep, deep_timeout_ms=2000)
    r.holding_after_ms = 40
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("question dure")]
    holdings = [c for c in chunks if c.get("channel") == "holding"]
    assert holdings, "un deep de 120 ms a 40 ms de silence doit meubler"
    assert all(c["flush"] is True for c in holdings)
    assert all(c["delta"] in HOLDING for c in holdings)
    assert any(c.get("delta") == "voici." for c in chunks)


@runs_async
async def test_deep_mort_avant_emission_replie_sur_reflex():
    deep = FakeChan("deep", raise_after="before")
    reflex = FakeChan("reflex", scripts=[[
        {"delta": "repli.", "stop_reason": None, "ttft_ms": 1.0},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None},
    ]])
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("x")]
    assert any(c.get("channel") == "filler" for c in chunks)
    assert any(c.get("channel") == "reflex" and c.get("delta") == "repli." for c in chunks)
    assert r.stats["deep_failed"] == 1


@runs_async
async def test_deep_coupe_apres_emission_ne_redemarre_pas():
    deep = FakeChan("deep", scripts=[[
        {"delta": "debut", "stop_reason": None, "ttft_ms": 1.0},
    ]], raise_after="after")
    reflex = FakeChan("reflex")
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("ESCALADE")
    chunks = [c async for c in r.query_streaming("x")]
    assert any(c.get("delta") == "debut" for c in chunks)
    assert chunks[-1]["stop_reason"] == "error"
    assert all(c.get("channel") != "reflex" for c in chunks)
    assert reflex.calls == []


@runs_async
async def test_query_non_stream_n_a_pas_de_filler():
    r = _router()
    r._client = FakeClassify("ESCALADE")
    result = await r.query("capitale")
    assert result["channel"] in ("escalate", "deep") or "ok" in result.get("response", "")
    # query() n'emet pas de chunks d'amorce : c'est un dict unique.
    assert "delta" not in result or result.get("delta") in (None, "")


@runs_async
async def test_query_deep_en_erreur_replie_sur_reflex():
    deep = FakeChan("deep", query_result={
        "response": "", "stop_reason": "error", "tokens_used": 0, "latency_ms": 1,
    })
    reflex = FakeChan("reflex", query_result={
        "response": "local", "stop_reason": "stop", "tokens_used": 1, "latency_ms": 2,
    })
    r = _router(reflex=reflex, deep=deep)
    r._client = FakeClassify("ESCALADE")
    result = await r.query("x")
    assert result["channel"] == "reflex"
    assert result["response"] == "local"
    assert r.stats["deep_failed"] == 1


@runs_async
async def test_with_holding_timeout_sans_meubler():
    async def gen():
        await asyncio.sleep(1.0)
        yield {"delta": "trop tard"}

    with pytest.raises(TimeoutError):
        async for _ in _with_holding(gen(), timeout_ms=40, holding_after_ms=200, max_holding=0):
            pass


@runs_async
async def test_with_holding_emet_un_marqueur_puis_l_item():
    async def gen():
        await asyncio.sleep(0.08)
        yield {"delta": "la"}

    items = [c async for c in _with_holding(gen(), timeout_ms=1000, holding_after_ms=30, max_holding=2)]
    assert items[0] == {"_holding": True}
    assert items[-1] == {"delta": "la"}


@runs_async
async def test_health_suit_le_reflexe():
    reflex = FakeChan("reflex")
    deep = FakeChan("deep")
    r = _router(reflex=reflex, deep=deep)
    h = await r.health()
    assert h["ok"] is True
    assert "reflex" in h["detail"]


@runs_async
async def test_classify_poste_sur_completion_pas_chat():
    fake = FakeClassify("REFLEXE")
    r = _router(classify_host="http://localhost:8090")
    r._client = fake
    await r.classify("Bonjour")
    assert fake.urls[0].endswith("/completion")
    assert fake.bodies[0]["grammar"] == CLASSIFY_GRAMMAR
    assert fake.bodies[0]["temperature"] == 0
    assert fake.bodies[0]["cache_prompt"] is True


@runs_async
async def test_holding_par_defaut_6000(monkeypatch):
    monkeypatch.delenv("BRAIN_HOLDING_AFTER_MS", raising=False)
    assert _router().holding_after_ms == 6000
