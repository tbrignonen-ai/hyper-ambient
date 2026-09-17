"""Plafonds d'outils : un appel par tour, JSON d'args borné, pas d'outils en reflexe.

Mesure du 17 sept, chaine reelle (PTT « Bonjour. ») :

    EARS  « Bonjour. »  classe REFLEXE (618 ms)
    puis  30+ web_search / ask_codex, GATE auto, arguments illisibles
    aucun tour BRAIN final

`max_iterations=3` ne plafonnait que les allers-retours avec le modele, pas
le nombre d'appels *dans* une reponse. Ce fichier pince les trois garde-fous :

  1. N `tool_calls` dans un seul chunk → un seul s'execute
  2. un tour REFLEXE ne declare aucun schema au canal local
  3. le chemin ESCALADE peut appeler `ask_codex` une fois, puis s'arrete
"""
from __future__ import annotations

import asyncio
import functools
import json

from src.brain.openai_compat import OpenAICompatBrain
from src.brain.router import RouterBrain
from src.brain.tool_loop import (
    MAX_ITERATIONS_MESSAGE,
    MAX_TOOL_CALLS_PER_ITERATION,
    MAX_TOOL_CALLS_PER_TURN,
    run_tool_loop,
)
from src.brain.tools import MAX_TOOL_ARGUMENTS_CHARS, ToolCall, ToolRegistry, ToolSpec
from src.brain.tools_codex import register_ask_codex


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class FakeGate:
    def __init__(self, allowed=True, reason=""):
        self.allowed = allowed
        self.reason = reason
        self.requests = []

    async def check(self, request):
        self.requests.append(request)
        return _Decision(self.allowed, self.reason)


class _Decision:
    def __init__(self, allowed, reason):
        self.allowed = allowed
        self.reason = reason


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


class FakeChan:
    def __init__(self, name, scripts=None):
        self.name = name
        self.api_endpoint = f"http://{name}"
        self.scripts = list(scripts or [])
        self.calls = []

    async def query_streaming(self, prompt, **kw):
        self.calls.append({"prompt": prompt, **kw})
        script = self.scripts.pop(0) if self.scripts else [
            {"delta": f"{self.name}-reponse", "stop_reason": None, "ttft_ms": 1.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ]
        for chunk in script:
            yield chunk


class FakeClassify:
    def __init__(self, verdict="ESCALADE"):
        self.verdict = verdict

    async def post(self, url, json=None):
        verdict = self.verdict

        class _R:
            def json(inner):
                return {"content": verdict}

        return _R()


class _FakeResponse:
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b""


class _FakeStreamCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeHTTPClient:
    def __init__(self, lines=(), status_code=200):
        self.lines = list(lines)
        self.status_code = status_code
        self.payloads = []

    def stream(self, method, url, json=None, headers=None):
        self.payloads.append(json)
        return _FakeStreamCtx(_FakeResponse(self.lines, self.status_code))


def sse(obj):
    return "data: " + json.dumps(obj)


def _call(name="web_search", args=None, raw=None, call_id="c1"):
    arguments = args if args is not None else {"query": "meteo"}
    if raw is None:
        raw = json.dumps(arguments, separators=(",", ":"))
    return ToolCall(id=call_id, name=name, arguments=arguments, raw_arguments=raw)


def tool_calls_chunk(calls):
    return {
        "delta": "",
        "stop_reason": "tool_calls",
        "ttft_ms": None,
        "tool_calls": calls,
    }


async def _echo(**kwargs):
    return "echo:" + json.dumps(kwargs, sort_keys=True)


def make_registry(*specs):
    registry = ToolRegistry()
    if specs:
        for spec in specs:
            registry.register(spec)
        return registry
    registry.register(
        ToolSpec(
            name="web_search",
            description="Cherche sur internet.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            danger="read",
            handler=_echo,
        )
    )
    return registry


def test_plafonds_par_defaut():
    assert MAX_TOOL_CALLS_PER_ITERATION == 1
    assert MAX_TOOL_CALLS_PER_TURN == 1
    assert MAX_TOOL_ARGUMENTS_CHARS == 800


@runs_async
async def test_trente_appels_paralleles_un_seul_s_execute():
    seen = []

    async def handler(query):
        seen.append(query)
        return "ok:" + query

    calls = [
        _call("web_search", {"query": f"q{i}"}, call_id=f"c{i}")
        for i in range(30)
    ]
    brain = FakeBrain([
        [tool_calls_chunk(calls)],
        [{"delta": "Voila.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    registry = make_registry(
        ToolSpec(
            name="web_search",
            description="Cherche sur internet.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            danger="read",
            handler=handler,
        )
    )
    chunks = [c async for c in run_tool_loop(brain, "Bonjour.", registry, FakeGate())]

    assert seen == ["q0"]
    tools = [c for c in chunks if c.get("channel") == "tool"]
    assert [c["tool"] for c in tools] == ["web_search", "web_search"]
    assert [c["phase"] for c in tools] == ["call", "result"]
    assistant = brain.calls[1]["messages"][-2]
    assert len(assistant["tool_calls"]) == 1
    assert assistant["tool_calls"][0]["id"] == "c0"
    assert "Voila." in "".join(c["delta"] for c in chunks)


@runs_async
async def test_second_outil_sequentiel_est_refuse_par_defaut():
    seen = []

    async def handler(query):
        seen.append(query)
        return "r:" + query

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={"query": "un"}, call_id="c1")])],
        [tool_calls_chunk([_call(args={"query": "deux"}, call_id="c2")])],
        [{"delta": "ne doit pas sortir", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [
        c async for c in run_tool_loop(brain, "x", make_registry(
            ToolSpec(
                name="web_search",
                description="Cherche.",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
                danger="read",
                handler=handler,
            )
        ), FakeGate())
    ]
    assert seen == ["un"]
    assert len(brain.calls) == 2
    assert not brain.calls[1].get("tools")
    assert chunks[-1]["stop_reason"] == "max_tool_calls"
    assert chunks[-1]["delta"] == MAX_ITERATIONS_MESSAGE
    assert "ne doit pas sortir" not in "".join(c["delta"] for c in chunks)


@runs_async
async def test_bonjour_reflexe_n_appelle_aucun_outil():
    called = []

    async def handler(query=None, question=None, **kw):
        called.append({"query": query, "question": question, **kw})
        return "ne devrait pas"

    reflex = FakeChan("reflex")
    deep = FakeChan("deep")
    router = RouterBrain(reflex, deep, enable_filler=False)
    router._client = FakeClassify("REFLEXE")

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="web_search",
            description="Cherche.",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            danger="read",
            handler=handler,
        )
    )
    register_ask_codex(registry, token="jeton", client=object())

    chunks = [
        c async for c in run_tool_loop(router, "Bonjour.", registry, FakeGate())
    ]

    assert called == []
    assert reflex.calls, "le reflexe local n'a pas repondu"
    assert "tools" not in reflex.calls[0]
    assert deep.calls == []
    assert any(c.get("delta") == "reflex-reponse" for c in chunks)
    assert all(c.get("channel") != "tool" for c in chunks)


@runs_async
async def test_escalade_appelle_ask_codex_une_fois():
    questions = []

    async def handler(question):
        questions.append(question)
        return "Neuf fichiers dans src/brain."

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="ask_codex",
            description="Pose une question a Codex.",
            parameters={
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
            danger="read",
            handler=handler,
        )
    )

    deep = FakeChan("deep", scripts=[
        [tool_calls_chunk([
            _call(
                "ask_codex",
                {"question": "Que fait tool_loop ?"},
                call_id="codex1",
            )
        ])],
        [
            {"delta": "Neuf fichiers.", "stop_reason": None, "ttft_ms": 4.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
    ])
    reflex = FakeChan("reflex")
    router = RouterBrain(reflex, deep, enable_filler=False)
    router._client = FakeClassify("ESCALADE")

    chunks = [
        c
        async for c in run_tool_loop(
            router,
            "Demande à Codex ce que fait tool_loop.",
            registry,
            FakeGate(),
        )
    ]

    assert questions == ["Que fait tool_loop ?"]
    assert deep.calls[0].get("tools"), "l'escalade doit declarer les schemas"
    assert not deep.calls[1].get("tools"), "un seul outil : plus de schemas ensuite"
    assert reflex.calls == []
    tools = [c for c in chunks if c.get("channel") == "tool"]
    assert [c["tool"] for c in tools] == ["ask_codex", "ask_codex"]
    assert [c["phase"] for c in tools] == ["call", "result"]
    assert "Neuf fichiers." in "".join(c["delta"] for c in chunks)


@runs_async
async def test_arguments_sse_sont_bornes():
    """Un JSON trop long n'est plus accumule jusqu'a `arguments illisibles`."""
    trop = "x" * (MAX_TOOL_ARGUMENTS_CHARS + 400)
    payload = '{"query":"' + trop + '"}'
    mid = len(payload) // 2
    brain = OpenAICompatBrain(
        api_key="k", api_endpoint="http://local/v1/chat/completions", model="m"
    )
    brain.client = FakeHTTPClient(
        [
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "c1", "function": {
                    "name": "web_search", "arguments": payload[:mid],
                }}
            ]}}]}),
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": payload[mid:]}}
            ]}}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
            "data: [DONE]",
        ]
    )
    chunks = [c async for c in brain.query_streaming("x", tools=[{"type": "function"}])]
    call = chunks[-1]["tool_calls"][0]
    assert len(call.raw_arguments) <= MAX_TOOL_ARGUMENTS_CHARS
    assert call.raw_arguments.startswith('{"query":"')
    # Tronque au milieu du JSON → illisible, mais borne, et jamais de delta parle.
    assert call.arguments == {}
    assert all(c["delta"] == "" for c in chunks)
