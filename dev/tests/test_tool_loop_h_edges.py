"""
BRAIN: troisieme nappe d'edges pour tool_loop / openai_compat (vague H).

D a pince le multi-outils et le recolement SSE. F a pince secrets, _execute,
query() non-stream, health. Ici ce qui restait dicible :

  - la **vraie** Gate async dans la boucle (plus un FakeGate),
  - un deuxieme `tool_calls` dans le meme flux ecrase le pending,
  - un texte *apres* `tool_calls` dans le meme tour est encore cede,
  - un `stop_reason=error` sort et arrete,
  - query() choices vide / usage absent / content None,
  - SSE : finish=length, [DONE] sans finish, buffer + finish=stop,
  - Tavily **mock** branche dans la boucle (aucun reseau).

asyncio.run — pas de pytest-asyncio. Hors llama-server, hors Tavily reel.
"""
import asyncio
import functools
import inspect
import json
from pathlib import Path

from src.brain.openai_compat import LlamaCppBrain, OpenAICompatBrain
from src.brain.tool_loop import (
    CALLER,
    _assistant_message,
    _build_messages,
    _execute,
    _sanitize,
    run_tool_loop,
)
from src.brain.tools import ToolCall, ToolRegistry, ToolSpec
from src.brain.tools_web import TAVILY_ENDPOINT, TavilySearch, register_web_search
from src.gate.permission import Gate


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


class BoomGate:
    async def check(self, request):
        raise RuntimeError("audit down")


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


class _FakeResponse:
    def __init__(self, lines, status_code=200, body=b""):
        self._lines = lines
        self.status_code = status_code
        self._body = body

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return self._body


class _FakeStreamCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeHTTPClient:
    def __init__(self, lines=(), status_code=200, body=b""):
        self.lines = list(lines)
        self.status_code = status_code
        self.body = body
        self.payloads = []

    def stream(self, method, url, json=None, headers=None):
        self.payloads.append({"method": method, "url": url, "json": json, "headers": headers})
        return _FakeStreamCtx(_FakeResponse(self.lines, self.status_code, self.body))


class FakePostResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakePostClient:
    def __init__(self, payload=None, status_code=200, get_status=200):
        self.payload = payload if payload is not None else {}
        self.status_code = status_code
        self.get_status = get_status
        self.posts = []
        self.gets = []

    async def post(self, url, json=None, headers=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return FakePostResponse(self.payload, self.status_code)

    async def get(self, url, headers=None):
        self.gets.append({"url": url, "headers": headers})

        class _R:
            status_code = self.get_status

        return _R()


class _TavilyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeTavilyClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        return _TavilyResponse(self.payload)


def sse(obj):
    return "data: " + json.dumps(obj)


async def _echo(**kwargs):
    return "echo:" + json.dumps(kwargs, sort_keys=True)


def _spec(name="web_search", handler=None, danger="read", **params):
    return ToolSpec(
        name=name,
        description=name,
        parameters={"type": "object", "properties": params or {"query": {"type": "string"}}},
        danger=danger,
        handler=handler or _echo,
    )


def make_registry(*specs):
    registry = ToolRegistry()
    if not specs:
        registry.register(_spec())
        return registry
    for spec in specs:
        registry.register(spec)
    return registry


def tool_calls_chunk(calls):
    return {
        "delta": "",
        "stop_reason": "tool_calls",
        "ttft_ms": None,
        "tool_calls": calls,
    }


def _call(name="web_search", args=None, raw=None, call_id="c1"):
    arguments = args if args is not None else {"query": "meteo"}
    if raw is None:
        raw = json.dumps(arguments, separators=(",", ":"))
    return ToolCall(id=call_id, name=name, arguments=arguments, raw_arguments=raw)


def _brain():
    return OpenAICompatBrain(api_key="k", api_endpoint="http://local/v1/chat/completions", model="m")


# -- vraie Gate async dans la boucle ------------------------------------------


@runs_async
async def test_boucle_avec_vraie_porte_auto_execute():
    seen = []

    async def handler(query):
        seen.append(query)
        return "Il fait beau."

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "beau.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(
        brain, "meteo", make_registry(_spec(handler=handler)), Gate(mode="auto"),
    )]
    assert seen == ["meteo"]
    assert "beau." in "".join(c["delta"] for c in chunks)
    assert inspect.iscoroutinefunction(Gate.check)


@runs_async
async def test_boucle_avec_vraie_porte_plan_refuse_sans_executer():
    called = []

    async def handler(query):
        called.append(query)
        return "non"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "je simule.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler, danger="exec")), Gate(mode="plan"),
    )]
    assert called == []
    assert "denied" in [c.get("phase") for c in chunks]
    motif = brain.calls[1]["messages"][-1]["content"]
    assert "simulation" in motif.lower()


@runs_async
async def test_boucle_ask_resolver_async_autorise():
    ticks = []

    async def resolver(request):
        await asyncio.sleep(0)
        ticks.append(request.tool)
        return True

    async def handler(query):
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = Gate(mode="ask", resolver=resolver)
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), gate,
    )]
    assert ticks == ["web_search"]
    assert brain.calls[1]["messages"][-1]["content"] == "ok"


@runs_async
async def test_boucle_ask_sans_resolver_refuse():
    called = []

    async def handler(query):
        called.append(query)
        return "non"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "refuse.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), Gate(mode="ask"),
    )]
    assert called == []
    content = brain.calls[1]["messages"][-1]["content"]
    assert "confirmation" in content.lower() or "disponible" in content.lower()


@runs_async
async def test_boucle_yolo_autorise_exec():
    seen = []

    async def handler(cmd):
        seen.append(cmd)
        return "fait"

    brain = FakeBrain([
        [tool_calls_chunk([_call("shell", {"cmd": "ls"}, call_id="e1")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    registry = make_registry(_spec("shell", handler=handler, danger="exec", cmd={"type": "string"}))
    _ = [c async for c in run_tool_loop(brain, "x", registry, Gate(mode="yolo"))]
    assert seen == ["ls"]


@runs_async
async def test_vraie_porte_ne_voit_pas_la_cle():
    seen = []

    async def resolver(request):
        seen.append(dict(request.arguments))
        return True

    async def handler(**kw):
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={"query": "q", "api_key": "sk-live"})])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)),
        Gate(mode="ask", resolver=resolver),
    )]
    assert seen == [{"query": "q"}]


# -- pending, error, schemas vides --------------------------------------------


@runs_async
async def test_porte_qui_leve_se_propage():
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ne doit pas", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    with __import__("pytest").raises(RuntimeError, match="audit down"):
        _ = [c async for c in run_tool_loop(brain, "x", make_registry(), BoomGate())]


@runs_async
async def test_texte_apres_tool_calls_dans_le_meme_flux_est_cede():
    """Le `continue` n'avale que le chunk outil : un delta ulterieur dans le
    meme stream sort encore. Ce n'est pas un silence, c'est le contrat actuel."""
    brain = FakeBrain([[
        tool_calls_chunk([_call()]),
        {"delta": "je cherche encore", "stop_reason": None, "ttft_ms": None},
    ], [
        {"delta": "18 degres", "stop_reason": "stop", "ttft_ms": 1.0},
    ]])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    spoken = "".join(c["delta"] for c in chunks)
    assert "je cherche encore" in spoken
    assert "18 degres" in spoken


@runs_async
async def test_deuxieme_tool_calls_du_meme_flux_ecrase_le_pending():
    seen = []

    async def h_a(query):
        seen.append("a")
        return "A"

    async def h_b(query):
        seen.append("b")
        return "B"

    brain = FakeBrain([[
        tool_calls_chunk([_call("alpha", call_id="c-a")]),
        tool_calls_chunk([_call("beta", call_id="c-b")]),
    ], [
        {"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0},
    ]])
    registry = make_registry(_spec("alpha", h_a), _spec("beta", h_b))
    _ = [c async for c in run_tool_loop(brain, "x", registry, FakeGate())]
    assert seen == ["b"]
    assert brain.calls[1]["messages"][-1]["tool_call_id"] == "c-b"


@runs_async
async def test_chunk_error_est_cede_et_arrete_sans_outil():
    brain = FakeBrain([[
        {"delta": "", "stop_reason": "error", "ttft_ms": None, "error": "HTTP 500"},
    ]])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    assert chunks[-1]["stop_reason"] == "error"
    assert chunks[-1]["delta"] == ""
    assert len(brain.calls) == 1
    assert all(c.get("channel") != "tool" for c in chunks)


@runs_async
async def test_registre_vide_transmet_une_liste_d_outils_vide():
    brain = FakeBrain([[{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}]])
    _ = [c async for c in run_tool_loop(brain, "x", ToolRegistry(), FakeGate())]
    assert brain.calls[0]["tools"] == []


@runs_async
async def test_channel_deep_est_conserve_sur_le_delta():
    brain = FakeBrain([[
        {"delta": "hmm", "stop_reason": None, "ttft_ms": 4.0, "channel": "deep"},
        {"delta": "", "stop_reason": "stop", "ttft_ms": None, "channel": "deep"},
    ]])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    assert chunks[0]["channel"] == "deep"
    assert chunks[0]["ttft_ms"] == 4.0


@runs_async
async def test_kw_system_history_messages_outils_sont_transmis():
    hist = [{"role": "user", "content": "hier"}]
    brain = FakeBrain([[{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}]])
    registry = make_registry()
    _ = [c async for c in run_tool_loop(
        brain, "aujourd", registry, FakeGate(), system="SYS", history=hist,
    )]
    call = brain.calls[0]
    assert call["system"] == "SYS"
    assert call["history"] == hist
    assert call["tools"] == registry.schemas()
    assert call["messages"][0] == {"role": "system", "content": "SYS"}
    assert call["messages"][-1] == {"role": "user", "content": "aujourd"}


def test_max_iterations_defaut_est_trois():
    assert inspect.signature(run_tool_loop).parameters["max_iterations"].default == 3


def test_max_tool_calls_defaut_est_un():
    assert inspect.signature(run_tool_loop).parameters["max_tool_calls"].default == 1


@runs_async
async def test_stop_reason_length_est_cede():
    brain = FakeBrain([[
        {"delta": "coupure", "stop_reason": None, "ttft_ms": 1.0},
        {"delta": "", "stop_reason": "length", "ttft_ms": None},
    ]])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    assert chunks[-1]["stop_reason"] == "length"
    assert "coupure" in "".join(c["delta"] for c in chunks)


@runs_async
async def test_phase_call_precede_toujours_result():
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    tools = [c for c in chunks if c.get("channel") == "tool"]
    assert [c["phase"] for c in tools] == ["call", "result"]
    assert all(c["delta"] == "" for c in tools)
    assert all("stop_reason" not in c for c in tools)


@runs_async
async def test_tavily_mock_dans_la_boucle_aucun_reseau():
    client = FakeTavilyClient({"answer": "Il fait 18 degres a Paris.", "results": []})
    registry = ToolRegistry()
    register_web_search(registry, api_key="cle-test", client=client)
    brain = FakeBrain([
        [tool_calls_chunk([_call(args={"query": "meteo paris"})])],
        [{"delta": "18 degres.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(brain, "meteo", registry, Gate(mode="auto"))]
    assert client.calls[0]["url"] == TAVILY_ENDPOINT
    assert client.calls[0]["json"]["query"] == "meteo paris"
    assert "18 degres" in brain.calls[1]["messages"][-1]["content"]
    assert "18 degres." in "".join(c["delta"] for c in chunks)
    assert "api.tavily.com" in client.calls[0]["url"]


@runs_async
async def test_tavily_sans_cle_dans_la_boucle_n_appelle_pas():
    client = FakeTavilyClient({"answer": "secret"})
    registry = ToolRegistry()
    register_web_search(registry, api_key="", client=client)
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "desole", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", registry, Gate(mode="auto"))]
    assert client.calls == []
    content = brain.calls[1]["messages"][-1]["content"]
    assert "acces" in content.lower() or "recherche" in content.lower()
    assert "secret" not in content


@runs_async
async def test_execute_pose_le_caller_de_la_boucle():
    gate = FakeGate()
    result, phase = await _execute(_call(), make_registry(), gate)
    assert phase == "result"
    assert result.ok is True
    assert gate.requests[0].caller == CALLER


@runs_async
async def test_assistant_message_liste_vide():
    msg = _assistant_message([])
    assert msg == {"role": "assistant", "content": "", "tool_calls": []}


@runs_async
async def test_sanitize_authorization_et_password():
    cleaned = _sanitize({
        "q": "ok",
        "Authorization": "Bearer x",
        "PASSWORD": "x",
        "session_token": "x",
    })
    assert cleaned == {"q": "ok"}


@runs_async
async def test_build_messages_history_none_comme_vide():
    a = _build_messages("u", "S", None)
    b = _build_messages("u", "S", [])
    assert a == b


# -- openai_compat restant ----------------------------------------------------


@runs_async
async def test_query_succes_avec_contenu():
    brain = _brain()
    brain.client = FakePostClient(payload={
        "choices": [{"message": {"content": "bonjour"}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 2},
    })
    out = await brain.query("x")
    assert out["response"] == "bonjour"
    assert out["stop_reason"] == "stop"
    assert out["tokens_used"] == 2
    assert out["latency_ms"] >= 0


@runs_async
async def test_query_choices_vide_est_une_erreur_muette():
    brain = _brain()
    brain.client = FakePostClient(payload={"choices": []})
    out = await brain.query("x")
    assert out["stop_reason"] == "error"
    assert out["response"] == ""
    assert out["error"]


@runs_async
async def test_query_usage_absent_tokens_zero():
    brain = _brain()
    brain.client = FakePostClient(payload={
        "choices": [{"message": {"content": "a"}, "finish_reason": "stop"}],
    })
    out = await brain.query("x")
    assert out["tokens_used"] == 0
    assert out["response"] == "a"


@runs_async
async def test_query_content_none_devient_chaine_vide():
    brain = _brain()
    brain.client = FakePostClient(payload={
        "choices": [{"message": {"content": None}, "finish_reason": "stop"}],
        "usage": {},
    })
    out = await brain.query("x")
    assert out["response"] == ""
    assert out["stop_reason"] == "stop"


@runs_async
async def test_query_transmet_tools_et_temperature():
    brain = _brain()
    brain.client = FakePostClient(payload={
        "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
    })
    schemas = make_registry().schemas()
    await brain.query("x", tools=schemas, tool_choice="auto", temperature=0.1)
    payload = brain.client.posts[0]["json"]
    assert payload["tools"] == schemas
    assert payload["tool_choice"] == "auto"
    assert payload["temperature"] == 0.1
    assert payload["stream"] is False


@runs_async
async def test_streaming_finish_length():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"content": "abc"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "length"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert "abc" in "".join(c["delta"] for c in chunks)
    assert chunks[-1]["stop_reason"] == "length"


@runs_async
async def test_streaming_done_sans_finish_n_invente_pas_de_stop():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"content": "coucou"}}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert [c["delta"] for c in chunks] == ["coucou"]
    assert all(c["stop_reason"] is None for c in chunks)


@runs_async
async def test_streaming_buffer_plus_finish_stop_rend_tool_calls():
    """Des fragments d'outil + finish=stop : le buffer gagne, pas le texte."""
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "a", "function": {"name": "web_search", "arguments": "{}"}},
        ]}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x", tools=[{"type": "function"}])]
    assert chunks[-1]["stop_reason"] == "tool_calls"
    assert chunks[-1]["tool_calls"][0].name == "web_search"
    assert all(c["delta"] == "" for c in chunks)


@runs_async
async def test_streaming_content_json_null_n_est_pas_parle():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"content": None}}]}),
        sse({"choices": [{"delta": {"content": "ok"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert [c["delta"] for c in chunks if c["delta"]] == ["ok"]


@runs_async
async def test_payload_history_temperature_max_tokens():
    brain = _brain()
    brain.max_tokens = 64
    hist = [{"role": "user", "content": "h"}]
    payload = brain._payload("p", "SYS", 0.2, True, hist)
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 64
    assert payload["stream"] is True
    assert payload["messages"][0]["content"] == "SYS"
    assert payload["messages"][1] == hist[0]
    assert payload["messages"][-1]["content"] == "p"


@runs_async
async def test_llamacpp_defaut_reste_8080_interne():
    """L'alias hote est :8090 ; le constructeur sans host pointe le port conteneur."""
    llama = LlamaCppBrain()
    assert llama.api_endpoint.endswith(":8080/v1/chat/completions")
    assert llama.model == "local"


@runs_async
async def test_health_http_non_200():
    brain = _brain()
    brain.client = FakePostClient(get_status=503)
    out = await brain.health()
    assert out["ok"] is False
    assert "503" in out["detail"]


@runs_async
async def test_accumulate_id_et_nom_du_second_fragment():
    buffer = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, [
        {"index": 0, "id": "old", "function": {"name": "t0", "arguments": ""}},
        {"index": 0, "id": "new", "function": {"name": "t1", "arguments": "{}"}},
    ])
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].id == "new"
    assert calls[0].name == "t1"


@runs_async
async def test_headers_content_type_toujours():
    brain = _brain()
    headers = brain._headers()
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer k"


@runs_async
async def test_streaming_transmet_post_et_endpoint():
    brain = _brain()
    brain.client = FakeHTTPClient(["data: [DONE]"])
    _ = [c async for c in brain.query_streaming("x")]
    assert brain.client.payloads[0]["method"] == "POST"
    assert brain.client.payloads[0]["url"] == brain.api_endpoint
    assert brain.client.payloads[0]["json"]["stream"] is True


def test_smoke_script_cible_ipv4_alias_lfm_sans_kill():
    src = Path(__file__).resolve().parents[1] / "scripts" / "smoke_llama_local.py"
    text = src.read_text(encoding="utf-8")
    assert "127.0.0.1:8090" in text
    assert "mother-local" in text
    assert "http://localhost" not in text
    assert "ws://localhost" not in text
    code = "\n".join(
        line.split("#", 1)[0] for line in text.splitlines()
        if not line.strip().startswith("#") and '"""' not in line
    ).lower()
    for interdit in ("stop-process", "taskkill", "os.kill", "signal.pid", "pkill"):
        assert interdit not in code
