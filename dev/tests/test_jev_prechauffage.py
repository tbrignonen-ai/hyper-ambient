"""Precauffage JeV hors budget du tour, sans appel reseau reel."""
from __future__ import annotations

import asyncio
import inspect

from src.ears.jev_reflexe import JevReflexe


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def json(self):
        return {}


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else FakeResponse()
        self.error = error
        self.calls = []

    async def post(self, url, *, json, headers, timeout):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if self.error:
            raise self.error
        return self.response


def test_prechauffer_sans_cle_rend_false_sans_requete():
    transport = FakeTransport()
    client = JevReflexe(api_key="", transport=transport)

    assert asyncio.run(client.prechauffer()) is False
    assert transport.calls == []


def test_prechauffer_passe_un_timeout_genereux_pas_le_budget_du_tour():
    transport = FakeTransport()
    client = JevReflexe(api_key="cle-de-test", transport=transport)

    assert asyncio.run(client.prechauffer()) is True
    assert len(transport.calls) == 1
    timeout = transport.calls[0]["timeout"]
    assert timeout == 10 or abs(timeout - 10.0) < 0.05
    assert timeout != 0.6
    assert timeout > 1.0


def test_prechauffer_avale_l_exception_du_transport():
    transport = FakeTransport(error=RuntimeError("poignee cassee"))
    client = JevReflexe(api_key="cle-de-test", transport=transport)

    assert asyncio.run(client.prechauffer()) is False
    assert len(transport.calls) == 1


def test_maintenir_appelle_prechauffer_plusieurs_fois_puis_sarrete():
    transport = FakeTransport()
    client = JevReflexe(api_key="cle-de-test", transport=transport)

    async def scenario():
        try:
            await asyncio.wait_for(client.maintenir(intervalle_s=0.01), timeout=0.05)
        except asyncio.TimeoutError:
            pass
        return len(transport.calls)

    assert asyncio.run(scenario()) >= 2


def test_intervalle_maintien_par_defaut_est_sous_60_s():
    defaut = inspect.signature(JevReflexe.maintenir).parameters["intervalle_s"].default
    assert defaut < 60
