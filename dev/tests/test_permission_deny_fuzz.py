"""
Vague J — chemins de refus de la porte, en propriete.

Les nappes D/F collent les 18 cellules et les motifs exacts. Ici : le refus
est une propriete, pas une ligne du tableau.

  - plan/manual refusent tout couple (outil aleatoire, danger connu)
  - un danger inconnu est refuse dans tous les modes hors ask
  - ask refuse sans resolver, si le resolver rend faux, s'il leve
  - le motif est prononcable (pas de traceback, pas le nom de l'exception)
  - `_execute` + vraie Gate : handler jamais appele, phase=denied,
    delta d'outil vide, secrets absents de la requete

asyncio.run — pas de pytest-asyncio. Hors reseau.
"""
from __future__ import annotations

import asyncio
import functools
import random
import string

from dataclasses import FrozenInstanceError

import pytest

from src.gate.permission import Gate, PermissionRequest
from src.brain.tool_loop import _execute, _sanitize, run_tool_loop
from src.brain.tools import ToolCall, ToolRegistry, ToolSpec


SEED = 20260902
DENY_MODES = ("plan", "manual")
ALLOW_MODES = ("auto", "build", "troubleshoot", "yolo")
DANGERS = ("read", "write", "exec")
INTERDITS_MOTIF = (
    "traceback", "exception", "error", "stack", "errno",
    "runtimeerror", "typeerror", "permissionerror",
)


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


def _run(coro):
    return asyncio.run(coro)


def _prononcable(reason: str) -> None:
    assert isinstance(reason, str)
    texte = reason.strip()
    assert texte
    assert len(texte) > 5
    assert "\n" not in texte
    assert "Traceback" not in reason
    bas = texte.lower()
    for mot in INTERDITS_MOTIF:
        assert mot not in bas, (mot, reason)
    # phrase francaise dicible : au moins une voyelle
    assert any(v in bas for v in "aeiouyàâéèêëîïôùû")


def _req(**kw):
    base = dict(tool="web_search", arguments={"q": "paris"}, danger="read", caller="brain.tool_loop")
    base.update(kw)
    return PermissionRequest(**base)


def _rng_name(rng: random.Random) -> str:
    return "outil_" + "".join(rng.choice(string.ascii_lowercase) for _ in range(8))


class FakeBrain:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []

    async def query_streaming(self, prompt, **kw):
        self.calls.append({"prompt": prompt, **kw})
        script = self.scripts.pop(0) if self.scripts else [
            {"delta": "fin.", "stop_reason": "stop", "ttft_ms": 1.0}
        ]
        for chunk in script:
            yield chunk


# -- proprietes sur Gate.check -----------------------------------------------


@pytest.mark.parametrize("mode", DENY_MODES)
@pytest.mark.parametrize("danger", DANGERS)
def test_plan_manual_refusent_chaque_danger(mode, danger):
    decision = _run(Gate(mode=mode).check(_req(danger=danger, tool="nimporte")))
    assert decision.allowed is False
    assert decision.mode == mode
    _prononcable(decision.reason)


def test_property_nom_outil_n_influence_pas_le_refus():
    rng = random.Random(SEED)
    for _ in range(12):
        name = _rng_name(rng)
        for mode in DENY_MODES:
            for danger in DANGERS:
                decision = _run(Gate(mode=mode).check(_req(tool=name, danger=danger)))
                assert decision.allowed is False
                assert name not in decision.reason
                _prononcable(decision.reason)


def test_property_arguments_n_influencent_pas_le_refus_plan():
    rng = random.Random(SEED + 1)
    for _ in range(8):
        args = { _rng_name(rng)[:4]: rng.randint(0, 9) for _ in range(rng.randint(0, 4)) }
        decision = _run(Gate(mode="plan").check(_req(arguments=args, danger="exec")))
        assert decision.allowed is False
        _prononcable(decision.reason)


@pytest.mark.parametrize("mode", ALLOW_MODES)
@pytest.mark.parametrize("danger", DANGERS)
def test_modes_permissifs_n_inventent_pas_un_refus(mode, danger):
    decision = _run(Gate(mode=mode).check(_req(danger=danger)))
    assert decision.allowed is True
    assert decision.mode == mode
    _prononcable(decision.reason)


@pytest.mark.parametrize("mode", ALLOW_MODES + DENY_MODES)
def test_danger_inconnu_est_refuse_hors_ask(mode):
    rng = random.Random(SEED + 2)
    danger = "nuke_" + "".join(rng.choice(string.ascii_lowercase) for _ in range(5))
    decision = _run(Gate(mode=mode).check(_req(danger=danger)))
    assert decision.allowed is False
    assert decision.mode == mode
    assert danger in decision.reason
    _prononcable(decision.reason)


def test_ask_sans_resolver_refuse_avec_motif_prononcable():
    decision = _run(Gate(mode="ask").check(_req(danger="exec")))
    assert decision.allowed is False
    assert decision.mode == "ask"
    _prononcable(decision.reason)
    assert "confirmation" in decision.reason.lower() or "disponible" in decision.reason.lower()


def test_ask_resolver_false_refuse():
    async def non(_req):
        return False

    decision = _run(Gate(mode="ask", resolver=non).check(_req()))
    assert decision.allowed is False
    assert decision.reason == "Action refusée par l'utilisateur."
    _prononcable(decision.reason)


@pytest.mark.parametrize("falsy", [0, "", None, [], {}, 0.0])
def test_ask_resolver_falsy_non_bool_refuse(falsy):
    async def resolver(_req):
        return falsy

    decision = _run(Gate(mode="ask", resolver=resolver).check(_req()))
    assert decision.allowed is False
    _prononcable(decision.reason)


def test_ask_resolver_qui_leve_n_expose_pas_l_exception():
    async def boom(_req):
        raise RuntimeError("secret-interne-xyz")

    decision = _run(Gate(mode="ask", resolver=boom).check(_req()))
    assert decision.allowed is False
    assert "secret-interne-xyz" not in decision.reason
    assert "RuntimeError" not in decision.reason
    _prononcable(decision.reason)


def test_ask_n_est_pas_dans_la_table_donc_pas_un_allow_cache():
    for danger in DANGERS:
        assert ("ask", danger) not in Gate.POLICY_TABLE


# -- _execute + vraie Gate ---------------------------------------------------


def _registry(handler):
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="echo",
        description="echo",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        danger="exec",
        handler=handler,
    ))
    return registry


@runs_async
async def test_execute_plan_n_appelle_pas_le_handler():
    called = []

    async def handler(**kw):
        called.append(kw)
        return "secret-resultat"

    gate = Gate(mode="plan")
    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={"q": "x"}, raw_arguments='{"q":"x"}'),
        _registry(handler),
        gate,
    )
    assert called == []
    assert phase == "denied"
    assert result.ok is False
    assert result.error == "denied"
    assert "secret-resultat" not in result.content
    _prononcable(result.content)
    assert result.to_message()["content"] == result.content


@runs_async
async def test_execute_manual_n_appelle_pas_le_handler():
    called = []

    async def handler(**kw):
        called.append(kw)
        return "nope"

    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={"q": "x"}, raw_arguments='{"q":"x"}'),
        _registry(handler),
        Gate(mode="manual"),
    )
    assert called == []
    assert phase == "denied"
    assert result.error == "denied"


@runs_async
async def test_execute_ask_sans_resolver_denied():
    called = []

    async def handler(**kw):
        called.append(kw)
        return "nope"

    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={"q": "x"}, raw_arguments='{"q":"x"}'),
        _registry(handler),
        Gate(mode="ask"),
    )
    assert called == []
    assert phase == "denied"
    _prononcable(result.content)


@runs_async
async def test_execute_refuse_n_envoie_pas_les_secrets_a_la_porte():
    seen = []

    async def handler(**kw):
        return "nope"

    class Spy(Gate):
        async def check(self, request):
            seen.append(request)
            return await super().check(request)

    gate = Spy(mode="plan")
    await _execute(
        ToolCall(
            id="c1",
            name="echo",
            arguments={"q": "x", "api_key": "sk-live", "token": "abc"},
            raw_arguments='{"q":"x","api_key":"sk-live"}',
        ),
        _registry(handler),
        gate,
    )
    assert seen
    args = seen[0].arguments
    assert "api_key" not in args
    assert "token" not in args
    assert args.get("q") == "x"
    blob = str(args)
    assert "sk-live" not in blob


def test_sanitize_propriete_marqueurs_sous_chaine():
    rng = random.Random(SEED + 3)
    for _ in range(16):
        suffix = "z" + "".join(rng.choice("abdfgjmnpqrsvwxyz") for _ in range(5))
        dirty = {
            "query": "ok",
            "api_key": "SECRET",
            "mytoken": "SECRET",
            "password": "SECRET",
            "keyboard": "SECRET",  # faux positif volontaire : sous-chaine "key"
            suffix: 1,
        }
        clean = _sanitize(dirty)
        assert "query" in clean
        assert suffix in clean
        assert "keyboard" not in clean
        for key, value in clean.items():
            assert value != "SECRET"
            assert not any(m in key.lower() for m in ("api_key", "token", "secret", "password", "key"))


@runs_async
async def test_boucle_refus_delta_outil_vide_et_motif_dans_le_message():
    called = []

    async def handler(q=None, **kw):
        called.append(q)
        return "nope"

    brain = FakeBrain([
        [{
            "delta": "",
            "stop_reason": "tool_calls",
            "ttft_ms": None,
            "tool_calls": [ToolCall(
                id="c1", name="echo",
                arguments={"q": "x"}, raw_arguments='{"q":"x"}',
            )],
        }],
        [{"delta": "Je ne peux pas.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(
        brain, "cherche", _registry(handler), Gate(mode="plan"),
    )]
    assert called == []
    tool_chunks = [c for c in chunks if c.get("channel") == "tool"]
    assert any(c.get("phase") == "denied" for c in tool_chunks)
    assert all(c.get("delta") == "" for c in tool_chunks)
    spoken = "".join(c["delta"] for c in chunks if c.get("channel") != "tool")
    assert "{" not in spoken
    tool_msg = brain.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    _prononcable(tool_msg["content"])


@pytest.mark.parametrize("mode,danger", [
    (m, d) for m in DENY_MODES for d in DANGERS
])
@runs_async
async def test_execute_toutes_les_cellules_deny_couplent_phase(mode, danger):
    called = []

    async def handler(**kw):
        called.append(1)
        return "nope"

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="echo", description="echo",
        parameters={"type": "object", "properties": {}},
        danger=danger, handler=handler,
    ))
    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={"q": "x"}, raw_arguments='{"q":"x"}'),
        registry,
        Gate(mode=mode),
    )
    assert called == []
    assert phase == "denied"
    assert result.error == "denied"
    _prononcable(result.content)


def test_decision_refus_est_figee():
    decision = _run(Gate(mode="plan").check(_req()))
    with pytest.raises(FrozenInstanceError):
        decision.allowed = True  # type: ignore[misc]
