"""Phrase de progression selon l'état réel du distant (notes voix/UX, 24/09).

« Un instant. » partait avant CHAQUE réponse du distant, même rendue en
0,8 s : c'était un tic, pas une information. Désormais : rien sous
PROGRESSION_APRES_MS, une seule phrase brève si le distant n'a encore rien
produit, et jamais de relance une fois qu'il parle.
"""
import asyncio

from dev.tests.test_router_amorces import FakeChan, FakeClassify, _router


def _flux(router, prompt="Explique-moi pourquoi le ciel est bleu le soir"):
    async def go():
        return [c async for c in router.query_streaming(prompt)]

    return asyncio.run(go())


def test_distant_rapide_aucune_phrase_d_attente():
    r = _router(deep=FakeChan("deep", delay=0.0))
    r._client = FakeClassify("ESCALADE")
    r.progression_apres_ms = 200
    canaux = [c.get("channel") for c in _flux(r)]
    assert "filler" not in canaux and "holding" not in canaux


def test_distant_lent_une_seule_phrase_avant_la_reponse():
    deep = FakeChan("deep", delay=0.3, scripts=[[
        {"delta": "Parce que ", "stop_reason": None, "ttft_ms": 1.0},
        {"delta": "la lumière se diffuse.", "stop_reason": None, "ttft_ms": None},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None},
    ]])
    r = _router(deep=deep)
    r._client = FakeClassify("ESCALADE")
    r.progression_apres_ms = 100
    r.holding_after_ms = 5000
    chunks = _flux(r)
    attente = [c for c in chunks if c.get("channel") in ("filler", "holding")]
    assert len(attente) == 1
    assert chunks.index(attente[0]) < next(
        i for i, c in enumerate(chunks) if c.get("delta") == "Parce que "
    )
