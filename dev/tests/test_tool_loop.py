"""
BRAIN: outils, permissions, boucle d'appel.

Tout tourne sans reseau, sans llama-server, sans conteneur : le client HTTP est
un double ecrit a la main, le Gate est un FakeGate local (le vrai vit dans
src/gate/, ecrit par ailleurs), et aucun test ne parle a une API distante.

Trois invariants sont testes ici parce qu'ils sont vocaux avant d'etre techniques :
  - un fragment `tool_calls` ne devient jamais un delta parle,
  - un resultat d'outil est tronque avant de remonter au modele,
  - un refus porte une phrase prononcable, jamais un silence.
"""
import asyncio
import functools
import json

import pytest  # noqa: F401  (marqueurs et fixtures de la suite)


def runs_async(fn):
    """Execute un test asynchrone sans dependre de pytest-asyncio.

    La suite tourne dans mother-core-dev, ou pytest-asyncio est installe ; sur
    l'hote il ne l'est pas, et aucune dependance ne doit etre ajoutee cette
    nuit. Ce decorateur rend le fichier verifiable des deux cotes.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper

from src.brain.tools import (
    MAX_TOOL_CONTENT_CHARS,
    ToolCall,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from src.brain.openai_compat import OpenAICompatBrain
from src.brain.tool_loop import run_tool_loop


# -- doubles ---------------------------------------------------------------


class FakeGate:
    """Porte de test : politique fixe, decisions tracees."""

    def __init__(self, allowed=True, reason="", mode="test"):
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


class FakeBrain:
    """Modele scripte : une liste de chunks par appel."""

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
    """Double du client httpx : enregistre les charges utiles, rejoue des lignes SSE."""

    def __init__(self, lines=(), status_code=200):
        self.lines = list(lines)
        self.status_code = status_code
        self.payloads = []

    def stream(self, method, url, json=None, headers=None):
        self.payloads.append(json)
        return _FakeStreamCtx(_FakeResponse(self.lines, self.status_code))


def sse(obj):
    return "data: " + json.dumps(obj)


async def _echo(**kwargs):
    return "echo:" + json.dumps(kwargs, sort_keys=True)


def make_registry(handler=None, danger="read"):
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="web_search",
            description="Cherche sur internet.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            danger=danger,
            handler=handler or _echo,
        )
    )
    return registry


# -- tools.py --------------------------------------------------------------


def test_tool_spec_rend_le_schema_openai():
    spec = make_registry().get("web_search")
    schema = spec.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "web_search"
    assert schema["function"]["description"] == "Cherche sur internet."
    assert schema["function"]["parameters"]["properties"]["query"]["type"] == "string"


def test_registry_expose_schemas_et_danger():
    registry = make_registry()
    assert [s["function"]["name"] for s in registry.schemas()] == ["web_search"]
    assert registry.danger_of("web_search") == "read"
    assert registry.danger_of("inconnu") is None
    assert registry.get("inconnu") is None


def test_registry_vide_rend_une_liste_vide():
    assert ToolRegistry().schemas() == []


def test_tool_result_tronque_a_1200_caracteres():
    result = ToolResult(call_id="c1", name="web_search", ok=True, content="x" * 10000)
    assert len(result.content) <= MAX_TOOL_CONTENT_CHARS
    assert MAX_TOOL_CONTENT_CHARS == 1200


def test_tool_result_court_nest_pas_touche():
    result = ToolResult(call_id="c1", name="web_search", ok=True, content="court")
    assert result.content == "court"


def test_tool_result_to_message():
    message = ToolResult(
        call_id="c1", name="web_search", ok=True, content="Paris"
    ).to_message()
    assert message == {"role": "tool", "tool_call_id": "c1", "content": "Paris"}


def test_tool_call_conserve_le_brut():
    call = ToolCall(id="c1", name="web_search", arguments={"query": "a"}, raw_arguments='{"query":"a"}')
    assert call.raw_arguments == '{"query":"a"}'


# -- openai_compat._payload ------------------------------------------------


def _brain():
    return OpenAICompatBrain(api_key="k", api_endpoint="http://local/v1/chat/completions", model="m")


def test_payload_sans_outil_est_inchange():
    brain = _brain()
    base = brain._payload("bonjour", None, 0.7, True, None)
    with_kw = brain._payload("bonjour", None, 0.7, True, None, tools=None, tool_choice=None)
    assert base == with_kw
    assert "tools" not in base
    assert "tool_choice" not in base


def test_payload_avec_outils_vides_ninsere_rien():
    brain = _brain()
    payload = brain._payload("bonjour", None, 0.7, True, None, tools=[], tool_choice=None)
    assert "tools" not in payload
    assert "tool_choice" not in payload


def test_payload_avec_outils_les_insere():
    brain = _brain()
    schemas = make_registry().schemas()
    payload = brain._payload("bonjour", None, 0.7, True, None, tools=schemas, tool_choice="auto")
    assert payload["tools"] == schemas
    assert payload["tool_choice"] == "auto"


def test_payload_messages_remplace_la_construction():
    brain = _brain()
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "tool", "tool_call_id": "c1", "content": "r"},
    ]
    payload = brain._payload("ignore", None, 0.7, True, None, messages=messages)
    assert payload["messages"] == messages


# -- openai_compat.query_streaming ----------------------------------------


@runs_async
async def test_streaming_sans_outil_inchange():
    brain = _brain()
    brain.client = FakeHTTPClient(
        [
            sse({"choices": [{"delta": {"content": "Bon"}}]}),
            sse({"choices": [{"delta": {"content": "jour"}}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ]
    )
    chunks = [c async for c in brain.query_streaming("salut")]
    assert [c["delta"] for c in chunks] == ["Bon", "jour", ""]
    assert chunks[0]["ttft_ms"] is not None
    assert chunks[-1]["stop_reason"] == "stop"
    assert "tools" not in brain.client.payloads[0]


@runs_async
async def test_streaming_accumule_les_tool_calls_par_index():
    brain = _brain()
    brain.client = FakeHTTPClient(
        [
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_1", "function": {"name": "web_search", "arguments": '{"que'}}
            ]}}]}),
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": 'ry":"meteo"}'}}
            ]}}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
            "data: [DONE]",
        ]
    )
    chunks = [c async for c in brain.query_streaming("meteo", tools=make_registry().schemas())]
    assert all(c["delta"] == "" for c in chunks), "un fragment tool_calls a fui en delta"
    final = chunks[-1]
    assert final["stop_reason"] == "tool_calls"
    assert len(final["tool_calls"]) == 1
    call = final["tool_calls"][0]
    assert call.id == "call_1"
    assert call.name == "web_search"
    assert call.arguments == {"query": "meteo"}
    assert call.raw_arguments == '{"query":"meteo"}'


@runs_async
async def test_streaming_deux_outils_deux_index():
    brain = _brain()
    brain.client = FakeHTTPClient(
        [
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "a", "function": {"name": "t0", "arguments": "{}"}},
                {"index": 1, "id": "b", "function": {"name": "t1", "arguments": "{}"}},
            ]}}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
            "data: [DONE]",
        ]
    )
    chunks = [c async for c in brain.query_streaming("x", tools=[{"type": "function"}])]
    calls = chunks[-1]["tool_calls"]
    assert [c.name for c in calls] == ["t0", "t1"]


@runs_async
async def test_streaming_json_invalide_garde_le_brut():
    brain = _brain()
    brain.client = FakeHTTPClient(
        [
            sse({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "a", "function": {"name": "web_search", "arguments": "{query:"}}
            ]}}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
            "data: [DONE]",
        ]
    )
    call = [c async for c in brain.query_streaming("x", tools=[{"type": "function"}])][-1]["tool_calls"][0]
    assert call.arguments == {}
    assert call.raw_arguments == "{query:"


@runs_async
async def test_streaming_transmet_les_outils_dans_la_charge_utile():
    brain = _brain()
    brain.client = FakeHTTPClient(["data: [DONE]"])
    schemas = make_registry().schemas()
    _ = [c async for c in brain.query_streaming("x", tools=schemas)]
    assert brain.client.payloads[0]["tools"] == schemas


# -- tool_loop -------------------------------------------------------------


def tool_calls_chunk(name="web_search", args='{"query":"meteo"}', call_id="c1"):
    return {
        "delta": "",
        "stop_reason": "tool_calls",
        "ttft_ms": None,
        "tool_calls": [
            ToolCall(
                id=call_id,
                name=name,
                arguments=json.loads(args) if args.strip().startswith("{") and args.endswith("}") else {},
                raw_arguments=args,
            )
        ],
    }


@runs_async
async def test_boucle_sans_outil_laisse_passer_le_texte():
    brain = FakeBrain([[
        {"delta": "Bonjour", "stop_reason": None, "ttft_ms": 12.0, "channel": "reflexe"},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None, "channel": "reflexe"},
    ]])
    chunks = [c async for c in run_tool_loop(brain, "salut", make_registry(), FakeGate())]
    assert [c["delta"] for c in chunks] == ["Bonjour", ""]
    assert chunks[0]["channel"] == "reflexe"
    assert chunks[0]["ttft_ms"] == 12.0
    assert len(brain.calls) == 1


@runs_async
async def test_boucle_execute_loutil_autorise():
    seen = {}

    async def handler(query):
        seen["query"] = query
        return "Il fait beau."

    brain = FakeBrain([
        [tool_calls_chunk()],
        [{"delta": "Il fait beau a Paris.", "stop_reason": None, "ttft_ms": 5.0},
         {"delta": "", "stop_reason": "stop", "ttft_ms": None}],
    ])
    gate = FakeGate(allowed=True)
    chunks = [c async for c in run_tool_loop(brain, "meteo", make_registry(handler), gate)]

    assert seen["query"] == "meteo"
    assert len(gate.requests) == 1
    assert gate.requests[0].tool == "web_search"
    assert gate.requests[0].danger == "read"
    assert gate.requests[0].caller == "brain.tool_loop"
    phases = [c.get("phase") for c in chunks if c.get("channel") == "tool"]
    assert phases == ["call", "result"]
    assert all(c["delta"] == "" for c in chunks if c.get("channel") == "tool")
    assert "Il fait beau a Paris." in "".join(c["delta"] for c in chunks)


@runs_async
async def test_boucle_renvoie_assistant_puis_tool_au_modele():
    brain = FakeBrain([
        [tool_calls_chunk()],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "meteo", make_registry(), FakeGate())]

    assert len(brain.calls) == 2
    messages = brain.calls[1]["messages"]
    assert messages[-2]["role"] == "assistant"
    assert messages[-2]["tool_calls"][0]["function"]["name"] == "web_search"
    assert messages[-2]["tool_calls"][0]["id"] == "c1"
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_call_id"] == "c1"
    assert brain.calls[1]["tools"], "les outils doivent rester declares au second tour"


@runs_async
async def test_refus_remonte_un_motif_prononcable():
    called = []

    async def handler(query):
        called.append(query)
        return "ne devrait pas arriver"

    brain = FakeBrain([
        [tool_calls_chunk()],
        [{"delta": "Je n'ai pas le droit de chercher.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate(allowed=False, reason="Je n'ai pas l'autorisation de chercher sur internet.", mode="deny")
    chunks = [c async for c in run_tool_loop(brain, "meteo", make_registry(handler), gate)]

    assert called == [], "l'outil refuse ne doit pas s'executer"
    phases = [c.get("phase") for c in chunks if c.get("channel") == "tool"]
    assert "denied" in phases
    assert all(c["delta"] == "" for c in chunks if c.get("channel") == "tool")
    tool_message = brain.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["content"] == "Je n'ai pas l'autorisation de chercher sur internet."


@runs_async
async def test_resultat_long_est_tronque_avant_le_modele():
    async def handler(query):
        return "y" * 10000

    brain = FakeBrain([
        [tool_calls_chunk()],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "meteo", make_registry(handler), FakeGate())]
    assert len(brain.calls[1]["messages"][-1]["content"]) <= MAX_TOOL_CONTENT_CHARS


@runs_async
async def test_max_iterations_sarrete_avec_un_message_dicible():
    brain = FakeBrain([[tool_calls_chunk()] for _ in range(6)])
    chunks = [c async for c in run_tool_loop(brain, "meteo", make_registry(), FakeGate(), max_iterations=3)]

    assert len(brain.calls) == 3
    spoken = "".join(c["delta"] for c in chunks)
    assert spoken.strip(), "l'arret doit etre dicible, pas un silence"
    assert "{" not in spoken and "tool_calls" not in spoken
    assert chunks[-1]["stop_reason"] == "max_iterations"


@runs_async
async def test_outil_inconnu_ne_plante_pas():
    brain = FakeBrain([
        [tool_calls_chunk(name="fantome")],
        [{"delta": "desole", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate()
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), gate)]
    assert gate.requests == [], "un outil inconnu ne passe pas la porte"
    assert brain.calls[1]["messages"][-1]["role"] == "tool"
    assert all(c["delta"] == "" for c in chunks if c.get("channel") == "tool")


@runs_async
async def test_arguments_illisibles_ne_plantent_pas():
    called = []

    async def handler(**kw):
        called.append(kw)
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk(args="{query:")],
        [{"delta": "desole", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(handler), FakeGate())]
    assert called == []
    assert brain.calls[1]["messages"][-1]["role"] == "tool"


@runs_async
async def test_outil_qui_leve_est_rattrape():
    async def handler(query):
        raise RuntimeError("boum")

    brain = FakeBrain([
        [tool_calls_chunk()],
        [{"delta": "desole", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(handler), FakeGate())]
    content = brain.calls[1]["messages"][-1]["content"]
    assert content and "boum" not in content, "l'erreur brute ne remonte pas au modele"
    assert all(c["delta"] == "" for c in chunks if c.get("channel") == "tool")


@runs_async
async def test_les_secrets_sont_retires_de_la_requete_de_permission():
    brain = FakeBrain([
        [{"delta": "", "stop_reason": "tool_calls", "ttft_ms": None, "tool_calls": [
            ToolCall(id="c1", name="web_search",
                     arguments={"query": "meteo", "api_key": "secret-123"},
                     raw_arguments='{"query":"meteo","api_key":"secret-123"}')
        ]}],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate()
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(lambda **kw: None), gate)]
    assert "api_key" not in gate.requests[0].arguments
    assert gate.requests[0].arguments["query"] == "meteo"


@runs_async
async def test_la_boucle_declare_les_outils_du_registre():
    brain = FakeBrain([[{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}]])
    registry = make_registry()
    _ = [c async for c in run_tool_loop(brain, "x", registry, FakeGate())]
    assert brain.calls[0]["tools"] == registry.schemas()


@runs_async
async def test_les_messages_de_la_boucle_valent_la_construction_par_defaut():
    """La boucle passe par messages= des le premier tour : la charge utile doit
    rester celle du chemin sans outil, sinon le systeme par defaut se perd."""
    brain = FakeBrain([[{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}]])
    _ = [c async for c in run_tool_loop(brain, "salut", make_registry(), FakeGate(), system="S",
                                        history=[{"role": "user", "content": "h"}])]
    compat = _brain()
    expected = compat._payload("salut", "S", 0.7, True, [{"role": "user", "content": "h"}])["messages"]
    assert brain.calls[0]["messages"] == expected
