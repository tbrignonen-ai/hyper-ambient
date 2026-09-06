"""
Vague J — fuzz leger du parse JSON d'outils + couplage _execute.

Sans hypothesis (absent de l'hote). Generateur deterministic (seed 20260902)
+ corpus de formes que les modeles locaux rendent vraiment.

Deux contrats vocalement visibles :

  - `_finalize_tool_calls` ne leve jamais : JSON illisible → arguments={},
    le brut est conserve.
  - `_execute` refuse les parametres illisibles *avant* la porte (pas de
    gate.check, pas de handler). Un objet vide `{}` est un JSON valide :
    l'outil sans parametre doit passer la porte, pas se faire traiter
    comme du JSON casse.

asyncio.run — pas de pytest-asyncio. Hors llama-server, hors reseau.
"""
from __future__ import annotations

import asyncio
import functools
import json
import random
import string

import pytest

from src.brain.openai_compat import OpenAICompatBrain
from src.brain.tool_loop import _execute
from src.brain.tools import ToolCall, ToolRegistry, ToolSpec


SEED = 20260902
N_RANDOM = 48


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class FakeGate:
    def __init__(self, allowed=True, reason="ok", mode="auto"):
        self.allowed = allowed
        self.reason = reason
        self.mode = mode
        self.requests = []

    async def check(self, request):
        self.requests.append(request)
        return _Decision(self.allowed, self.reason, self.mode)


class _Decision:
    def __init__(self, allowed, reason, mode):
        self.allowed = allowed
        self.reason = reason
        self.mode = mode


async def _echo(**kw):
    return "ok:" + json.dumps(kw, ensure_ascii=False, default=str)


def _registry():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            description="echo",
            parameters={"type": "object", "properties": {}},
            danger="read",
            handler=_echo,
        )
    )
    return registry


def _finalize(raw: str, *, name="echo", call_id="c0", index=0) -> ToolCall:
    buffer = {index: {"id": call_id, "name": name, "arguments": raw}}
    return OpenAICompatBrain._finalize_tool_calls(buffer)[0]


def _is_object_json(raw: str) -> bool:
    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict)


def _random_key(rng: random.Random) -> str:
    n = rng.randint(1, 8)
    alphabet = string.ascii_letters + "_"
    return "".join(rng.choice(alphabet) for _ in range(n))


def _random_leaf(rng: random.Random):
    kind = rng.randint(0, 6)
    if kind == 0:
        return rng.randint(-50, 50)
    if kind == 1:
        return rng.choice((True, False, None))
    if kind == 2:
        return round(rng.random() * 10, 3)
    if kind == 3:
        return ""
    if kind == 4:
        return "été " + "".join(rng.choice("àéïôuç") for _ in range(3))
    return "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(1, 12)))


def _random_object(rng: random.Random, depth=0) -> dict:
    n = rng.randint(0, 4 if depth == 0 else 2)
    obj = {}
    for _ in range(n):
        key = _random_key(rng)
        if depth < 2 and rng.random() < 0.25:
            obj[key] = _random_object(rng, depth + 1)
        elif rng.random() < 0.15:
            obj[key] = [_random_leaf(rng) for _ in range(rng.randint(0, 3))]
        else:
            obj[key] = _random_leaf(rng)
    return obj


def _split_fragments(raw: str, rng: random.Random) -> list[str]:
    if not raw:
        return [""]
    n = rng.randint(1, min(5, max(1, len(raw))))
    cuts = sorted(rng.sample(range(1, len(raw)), k=min(n - 1, len(raw) - 1)))
    pieces = []
    prev = 0
    for c in cuts:
        pieces.append(raw[prev:c])
        prev = c
    pieces.append(raw[prev:])
    return [p for p in pieces if p] or [raw]


# -- corpus : formes reelles d'un modele local --------------------------------


_GARBAGE = [
    "",
    "   ",
    "{",
    "{query:",
    "{'query': 'x'}",
    '{"query":',
    '{"query": "x",}',
    '{"query": "x"} trailing',
    "[1, 2]",
    "null",
    "true",
    "false",
    "0",
    "3.14",
    '"juste une string"',
    "None",
    "undefined",
    "<tool>oops</tool>",
    '{"q": "x"}{"q": "y"}',
    '{"a": 1, "a": 2,}',
    "\x00{\"q\":1}",
    "\ufeff",
    "«bonjour»",
    "`{}`",
    "query=meteo",
    "{query: meteo}",
    '{"query": "météo \\u00e9"}',
    "[]",
    "[{}]",
    '{"ok": True}',
    '{"ok": None}',
    "{\n",
    "}\n{",
    '{"a": [1,}',
    '{"a": {"b": }',
    "'" + '"' * 8,
]


@pytest.mark.parametrize("raw", _GARBAGE, ids=lambda s: repr(s)[:40])
def test_finalize_ne_leve_jamais_sur_le_corpus(raw):
    call = _finalize(raw)
    assert isinstance(call.arguments, dict)
    assert call.raw_arguments == raw
    if _is_object_json(raw):
        expected = json.loads(raw) if raw.strip() else {}
        assert call.arguments == expected
    else:
        assert call.arguments == {}


def test_property_n_random_strings_ne_levent_pas():
    rng = random.Random(SEED)
    alphabet = string.printable + "àéïôuç€{}[]:,\"'\\n"
    for i in range(N_RANDOM):
        n = rng.randint(0, 80)
        raw = "".join(rng.choice(alphabet) for _ in range(n))
        call = _finalize(raw, call_id=f"c{i}")
        assert isinstance(call.arguments, dict)
        assert call.raw_arguments == raw
        assert call.id == f"c{i}"


def test_property_objets_valides_rond_tripent():
    rng = random.Random(SEED + 1)
    for i in range(N_RANDOM):
        obj = _random_object(rng)
        raw = json.dumps(obj, ensure_ascii=False)
        call = _finalize(raw, call_id=f"o{i}")
        assert call.arguments == obj
        assert call.raw_arguments == raw


def test_property_json_valide_non_objet_devient_dict_vide():
    rng = random.Random(SEED + 2)
    samples = [
        rng.randint(-99, 99),
        rng.random(),
        True,
        False,
        None,
        [rng.randint(0, 9) for _ in range(rng.randint(0, 4))],
        "texte " + _random_key(rng),
    ]
    for value in samples:
        raw = json.dumps(value, ensure_ascii=False)
        call = _finalize(raw)
        assert call.arguments == {}
        assert call.raw_arguments == raw


def test_property_fragments_recolent_un_objet():
    rng = random.Random(SEED + 3)
    for i in range(32):
        obj = _random_object(rng)
        raw = json.dumps(obj, ensure_ascii=False)
        pieces = _split_fragments(raw, rng)
        buffer: dict = {}
        OpenAICompatBrain._accumulate_tool_calls(
            buffer,
            [{"index": 0, "id": "acc", "function": {"name": "echo", "arguments": p}} for p in pieces],
        )
        call = OpenAICompatBrain._finalize_tool_calls(buffer)[0]
        assert call.arguments == obj, (raw, pieces)
        assert call.raw_arguments == raw
        assert call.name == "echo"
        assert call.id == "acc"


def test_accumulate_ignore_arguments_falsy_sans_casser_le_recollement():
    buffer: dict = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, [
        {"index": 0, "id": "z", "function": {"name": "echo", "arguments": ""}},
        {"index": 0, "function": {"arguments": None}},
        {"index": 0, "function": {"arguments": '{"q":'}},
        {"index": 0, "function": {"arguments": '"ok"}'}},
    ])
    call = OpenAICompatBrain._finalize_tool_calls(buffer)[0]
    assert call.arguments == {"q": "ok"}
    assert call.raw_arguments == '{"q":"ok"}'


def test_finalize_cles_dupliquees_dernier_gagne():
    call = _finalize('{"a": 1, "a": 2}')
    assert call.arguments == {"a": 2}


def test_finalize_unicode_et_echappements():
    raw = '{"q": "caf\\u00e9 \\n\\t\\""}'
    call = _finalize(raw)
    assert call.arguments == {"q": 'café \n\t"'}
    assert call.raw_arguments == raw


def test_finalize_objet_vide_et_blancs_internes():
    for raw in ("{}", "{ }", "{\n}", "{\t\n  }"):
        call = _finalize(raw)
        assert call.arguments == {}
        assert call.raw_arguments == raw


def test_finalize_deux_index_mixtes_valide_et_casse():
    buffer = {
        1: {"id": "b", "name": "echo", "arguments": "{non"},
        0: {"id": "a", "name": "echo", "arguments": '{"ok": true}'},
    }
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert [c.id for c in calls] == ["a", "b"]
    assert calls[0].arguments == {"ok": True}
    assert calls[1].arguments == {}
    assert calls[1].raw_arguments == "{non"


def test_finalize_id_vide_reste_call_index_meme_si_json_casse():
    call = _finalize("{", call_id="", index=7)
    assert call.id == "call_7"
    assert call.arguments == {}


# -- _execute : illisible vs objet vide --------------------------------------


@runs_async
async def test_execute_objet_vide_valide_consulte_la_porte():
    """`{}` n'est pas du JSON casse : un outil sans parametre doit s'executer."""
    gate = FakeGate()
    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={}, raw_arguments="{}"),
        _registry(),
        gate,
    )
    assert phase == "result"
    assert result.ok is True
    assert result.error is None
    assert len(gate.requests) == 1
    assert gate.requests[0].arguments == {}
    assert result.content.startswith("ok:")


@runs_async
async def test_execute_recupere_un_objet_si_arguments_vides_mais_brut_valide():
    """ToolCall construit a la main : le brut d'objet peuple rattrape arguments={}."""
    gate = FakeGate()
    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={}, raw_arguments='{"q": "ok"}'),
        _registry(),
        gate,
    )
    assert result.ok is True
    assert phase == "result"
    assert json.loads(result.content.removeprefix("ok:")) == {"q": "ok"}
    assert gate.requests[0].arguments == {"q": "ok"}


@runs_async
async def test_execute_objet_vide_blancs_consulte_la_porte():
    gate = FakeGate()
    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={}, raw_arguments="{  }"),
        _registry(),
        gate,
    )
    assert result.ok is True
    assert phase == "result"
    assert gate.requests


@pytest.mark.parametrize("raw", [
    "{query:",
    "{",
    "null",
    "[]",
    "true",
    "0",
    '"x"',
    '{"q":',
    "{'q': 1}",
])
@runs_async
async def test_execute_json_non_objet_ou_casse_ne_consulte_pas_la_porte(raw):
    called = []

    async def handler(**kw):
        called.append(kw)
        return "nope"

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="echo", description="echo",
        parameters={"type": "object", "properties": {}},
        danger="read", handler=handler,
    ))
    gate = FakeGate()
    call = _finalize(raw)
    result, phase = await _execute(call, registry, gate)
    assert called == []
    assert gate.requests == []
    assert phase == "result"
    assert result.ok is False
    assert result.error == "bad_arguments"
    assert "parametre" in result.content.lower() or "compris" in result.content.lower()


@runs_async
async def test_property_garbage_execute_coherent_avec_finalize():
    rng = random.Random(SEED + 4)
    alphabet = "{}[]:,\"'" + string.ascii_letters + " 01"
    for i in range(24):
        raw = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 40)))
        call = _finalize(raw, call_id=f"g{i}")
        gate = FakeGate()
        result, phase = await _execute(call, _registry(), gate)
        if _is_object_json(raw):
            assert gate.requests, raw
            assert result.error != "bad_arguments"
        else:
            assert gate.requests == [], raw
            assert result.error == "bad_arguments"
            assert phase == "result"
            assert result.ok is False


@runs_async
async def test_execute_objet_peuple_passe_les_arguments_parses():
    gate = FakeGate()
    raw = '{"q": "météo", "n": 2}'
    call = _finalize(raw)
    result, phase = await _execute(call, _registry(), gate)
    assert phase == "result"
    assert result.ok is True
    assert json.loads(result.content.removeprefix("ok:")) == {"q": "météo", "n": 2}
    assert gate.requests[0].arguments == {"q": "météo", "n": 2}


@runs_async
async def test_raw_vide_arguments_vides_consulte_la_porte():
    """Pas de brut du tout : pas un JSON casse, juste un appel sans params."""
    gate = FakeGate()
    result, phase = await _execute(
        ToolCall(id="c1", name="echo", arguments={}, raw_arguments=""),
        _registry(),
        gate,
    )
    assert result.ok is True
    assert gate.requests
    assert phase == "result"


def test_is_object_helper_aligne_sur_json_std():
    assert _is_object_json("{}") is True
    assert _is_object_json("{ }") is True
    assert _is_object_json("") is True  # raw vide → finalize rend {}
    assert _is_object_json("[]") is False
    assert _is_object_json("null") is False
    assert _is_object_json("{") is False
