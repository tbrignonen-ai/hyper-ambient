"""
BRAIN : le reflexe local ne repond plus, il trie seulement (15 sept).

En direct, MiniCPM5-2B recopiait les exemples du prompt (« Hello. » ->
« Bonsoir. Ça va, oui. Et toi, ta soirée ? ») et, sans exemples, se trompait
(« capitale de l'Australie : Sydney »). Avec `reflex_answers=False`, un tour
classe REFLEXE part quand meme au canal distant.
"""
import asyncio

from dev.tests.test_router_fillers_j import FakeChan, _router


async def _reflexe(prompt, history=None):
    return {"route": "reflex", "latency_ms": 1.0}


def _tour(router):
    async def run():
        return [c async for c in router.query_streaming("Hello.")]
    return asyncio.run(run())


def test_tour_reflexe_part_au_distant_si_reponses_locales_coupees():
    reflex, deep = FakeChan("reflex"), FakeChan("deep")
    r = _router(reflex, deep, reflex_answers=False)
    r.classify = _reflexe
    chunks = _tour(r)
    assert deep.calls and not reflex.calls
    assert any(c["channel"] == "deep" for c in chunks)


def test_par_defaut_le_reflexe_repond_encore():
    reflex, deep = FakeChan("reflex"), FakeChan("deep")
    r = _router(reflex, deep)
    r.classify = _reflexe
    _tour(r)
    assert reflex.calls and not deep.calls
