"""
BRAIN: deuxieme nappe d'edges pour tool_loop / openai_compat (vague F).

La nappe D (test_tool_loop_edges.py) pince multi-outils, types JSON, max=1,
reasoning, HTTP 500. Ici : le contrat vocal restant — secrets encore vus
par le handler, danger vide → exec, raw JSON non-objet, max_iterations=0,
deux tours d'outils, _execute en direct, recolement SSE (index absent,
function None, contenu+tool_calls), query() non-stream, health stub.
Toujours hors reseau, hors llama-server, asyncio.run sans pytest-asyncio.
"""
import asyncio
import functools
import json

from src.brain.openai_compat import LlamaCppBrain, OpenAICompatBrain
from src.brain.tool_loop import (
    CALLER,
    MAX_ITERATIONS_MESSAGE,
    _assistant_message,
    _build_messages,
    _execute,
    _sanitize,
    run_tool_loop,
)
from src.brain.tools import ToolCall, ToolRegistry, ToolSpec
from src.mouth.normalize import VOICE_SYSTEM_PROMPT as DEFAULT_SYSTEM


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
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeHTTPClient:
    def __init__(self, lines=(), status_code=200, body=b"", stream_error=None):
        self.lines = list(lines)
        self.status_code = status_code
        self.body = body
        self.stream_error = stream_error
        self.payloads = []

    def stream(self, method, url, json=None, headers=None):
        self.payloads.append({"method": method, "url": url, "json": json, "headers": headers})
        if self.stream_error is not None:
            return _FakeStreamCtx(error=self.stream_error)
        return _FakeStreamCtx(_FakeResponse(self.lines, self.status_code, self.body))


class FakePostResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakePostClient:
    def __init__(self, payload=None, status_code=200, error=None, get_error=None, get_status=200):
        self.payload = payload if payload is not None else {}
        self.status_code = status_code
        self.error = error
        self.get_error = get_error
        self.get_status = get_status
        self.posts = []
        self.gets = []

    async def post(self, url, json=None, headers=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        if self.error is not None:
            raise self.error
        return FakePostResponse(self.payload, self.status_code)

    async def get(self, url, headers=None):
        self.gets.append({"url": url, "headers": headers})
        if self.get_error is not None:
            raise self.get_error

        class _R:
            status_code = self.get_status

        return _R()

    async def aclose(self):
        self.closed = True


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


# -- boucle : secrets, danger, raw, iterations --------------------------------


@runs_async
async def test_handler_voit_le_secret_la_porte_non():
    seen = {}

    async def handler(**kw):
        seen.update(kw)
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={"query": "q", "api_key": "sk-live"}, call_id="c1")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate()
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), gate,
    )]
    assert seen["api_key"] == "sk-live"
    assert "api_key" not in gate.requests[0].arguments
    assert gate.requests[0].arguments["query"] == "q"


@runs_async
async def test_danger_vide_de_la_spec_devient_exec():
    async def handler(query):
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate()
    registry = make_registry(_spec(handler=handler, danger=""))
    _ = [c async for c in run_tool_loop(brain, "x", registry, gate)]
    assert gate.requests[0].danger == "exec"
    assert gate.requests[0].caller == CALLER


@runs_async
async def test_raw_json_non_objet_est_un_mauvais_parametre():
    """raw='null' / '[]' avec arguments={} : strip non vide et dict vide → bad_arguments."""
    called = []

    async def handler(**kw):
        called.append(kw)
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={}, raw="null", call_id="c1")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate()
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), gate,
    )]
    assert called == []
    assert gate.requests == []
    content = brain.calls[1]["messages"][-1]["content"]
    assert "parametre" in content.lower() or "compris" in content.lower()


@runs_async
async def test_tool_calls_none_arrete_comme_une_liste_vide():
    brain = FakeBrain([[{
        "delta": "",
        "stop_reason": "tool_calls",
        "ttft_ms": None,
        "tool_calls": None,
    }]])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    assert len(brain.calls) == 1
    assert all(c.get("channel") != "tool" for c in chunks)


@runs_async
async def test_max_iterations_zero_n_appelle_pas_le_modele():
    brain = FakeBrain([[{"delta": "ne doit pas sortir", "stop_reason": "stop", "ttft_ms": 1.0}]])
    chunks = [c async for c in run_tool_loop(
        brain, "x", make_registry(), FakeGate(), max_iterations=0,
    )]
    assert chunks == []
    assert brain.calls == []


@runs_async
async def test_deux_tours_d_outils_puis_texte():
    seen = []

    async def handler(query):
        seen.append(query)
        return "r:" + query

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={"query": "un"}, call_id="c1")])],
        [tool_calls_chunk([_call(args={"query": "deux"}, call_id="c2")])],
        [{"delta": "fini.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), FakeGate(), max_iterations=3,
    )]
    assert seen == ["un", "deux"]
    assert len(brain.calls) == 3
    assert "fini." in "".join(c["delta"] for c in chunks)
    assert brain.calls[2]["messages"][-1]["content"] == "r:deux"


@runs_async
async def test_handler_entier_et_booleen_passent_par_json():
    async def as_int(query):
        return 42

    async def as_bool(query):
        return True

    for handler, attendu in ((as_int, "42"), (as_bool, "true")):
        brain = FakeBrain([
            [tool_calls_chunk([_call()])],
            [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
        ])
        _ = [c async for c in run_tool_loop(
            brain, "x", make_registry(_spec(handler=handler)), FakeGate(),
        )]
        assert brain.calls[1]["messages"][-1]["content"] == attendu


@runs_async
async def test_handler_objet_passe_par_default_str():
    class Piece:
        def __str__(self):
            return "une-piece"

    async def handler(query):
        return Piece()

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), FakeGate(),
    )]
    assert json.loads(brain.calls[1]["messages"][-1]["content"]) == "une-piece"


@runs_async
async def test_handler_str_n_est_pas_reencode_en_json():
    async def handler(query):
        return "bonjour"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec(handler=handler)), FakeGate(),
    )]
    assert brain.calls[1]["messages"][-1]["content"] == "bonjour"


@runs_async
async def test_systeme_vide_prend_le_prompt_voix():
    messages = _build_messages("salut", "", None)
    assert messages[0]["content"] == DEFAULT_SYSTEM
    assert messages[-1] == {"role": "user", "content": "salut"}


@runs_async
async def test_historique_vide_ne_s_insere_pas():
    messages = _build_messages("salut", "SYS", [])
    assert messages == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "salut"},
    ]


@runs_async
async def test_assistant_message_porte_le_brut_pas_le_parse():
    call = _call(args={"query": "a"}, raw='{"query": "a"}')
    msg = _assistant_message([call])
    assert msg["role"] == "assistant"
    assert msg["content"] == ""
    fn = msg["tool_calls"][0]
    assert fn["type"] == "function"
    assert fn["id"] == "c1"
    assert fn["function"]["name"] == "web_search"
    assert fn["function"]["arguments"] == '{"query": "a"}'


@runs_async
async def test_execute_inconnu_ne_consulte_pas_la_porte():
    gate = FakeGate()
    result, phase = await _execute(_call(name="fantome"), make_registry(), gate)
    assert phase == "result"
    assert result.ok is False
    assert result.error == "unknown_tool"
    assert gate.requests == []
    assert "fantome" in result.content


@runs_async
async def test_execute_json_invalide_ne_consulte_pas_la_porte():
    gate = FakeGate()
    result, phase = await _execute(
        _call(args={}, raw="{query:", call_id="c1"), make_registry(), gate,
    )
    assert phase == "result"
    assert result.error == "bad_arguments"
    assert gate.requests == []


@runs_async
async def test_execute_refus_pose_error_denied():
    gate = FakeGate(allowed=False, reason="Pas maintenant.")
    result, phase = await _execute(_call(), make_registry(), gate)
    assert phase == "denied"
    assert result.error == "denied"
    assert result.content == "Pas maintenant."
    assert result.to_message()["content"] == "Pas maintenant."


@runs_async
async def test_execute_exception_pose_error_interne_sans_le_dire():
    async def boom(query):
        raise RuntimeError("stack-secrete")

    result, phase = await _execute(
        _call(), make_registry(_spec(handler=boom)), FakeGate(),
    )
    assert phase == "result"
    assert result.ok is False
    assert result.error == "stack-secrete"
    assert "stack-secrete" not in result.content
    assert "n'a pas repondu" in result.content


@runs_async
async def test_message_d_arret_est_la_constante():
    assert MAX_ITERATIONS_MESSAGE == (
        "Je n'arrive pas a aboutir avec mes outils. Je m'arrete la."
    )


@runs_async
async def test_sanitize_none_rend_un_dict_vide():
    assert _sanitize(None) == {}


# -- openai_compat : recolement, query, health, llama ------------------------


@runs_async
async def test_accumulate_index_absent_tombe_sur_zero():
    buffer = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, [
        {"id": "a", "function": {"name": "t", "arguments": "{}"}},
    ])
    assert list(buffer) == [0]
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].id == "a"
    assert calls[0].name == "t"


@runs_async
async def test_accumulate_fragments_none_ne_plante_pas():
    buffer = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, None)
    assert buffer == {}


@runs_async
async def test_accumulate_function_none_ne_plante_pas():
    buffer = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, [
        {"index": 0, "id": "a", "function": None},
    ])
    assert buffer[0]["id"] == "a"
    assert buffer[0]["name"] == ""


@runs_async
async def test_accumulate_colle_les_arguments_en_plusieurs_morceaux():
    buffer = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, [
        {"index": 0, "id": "a", "function": {"name": "web_search", "arguments": '{"que'}},
        {"index": 0, "function": {"arguments": 'ry":"x"}'}},
    ])
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].arguments == {"query": "x"}
    assert calls[0].raw_arguments == '{"query":"x"}'


@runs_async
async def test_finalize_nombre_json_devient_dict_vide():
    buffer = {0: {"id": "a", "name": "t", "arguments": "3"}}
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].arguments == {}
    assert calls[0].raw_arguments == "3"


@runs_async
async def test_streaming_exception_ne_parle_pas():
    brain = _brain()
    brain.client = FakeHTTPClient(stream_error=RuntimeError("connexion perdue traceback"))
    chunks = [c async for c in brain.query_streaming("x")]
    assert chunks[0]["stop_reason"] == "error"
    assert chunks[0]["delta"] == ""
    assert "connexion perdue" in chunks[0]["error"]


@runs_async
async def test_streaming_http_tronque_le_corps_a_200():
    body = b"X" * 500
    brain = _brain()
    brain.client = FakeHTTPClient(status_code=502, body=body)
    chunks = [c async for c in brain.query_streaming("x")]
    assert chunks[0]["stop_reason"] == "error"
    assert chunks[0]["delta"] == ""
    assert "502" in chunks[0]["error"]
    assert chunks[0]["error"].endswith("X" * 200) or "HTTP 502:" in chunks[0]["error"]
    assert len(chunks[0]["error"]) < 30 + 200 + 10


@runs_async
async def test_streaming_finish_tool_calls_sans_buffer_rend_une_liste_vide():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x", tools=[{"type": "function"}])]
    assert chunks[-1]["stop_reason"] == "tool_calls"
    assert chunks[-1]["delta"] == ""
    assert chunks[-1]["tool_calls"] == []


@runs_async
async def test_streaming_contenu_et_tool_calls_le_contenu_est_avale():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {
            "content": "je cherche {",
            "tool_calls": [{"index": 0, "id": "a", "function": {"name": "t", "arguments": "{}"}}],
        }}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x", tools=[{"type": "function"}])]
    spoken = "".join(c["delta"] for c in chunks)
    assert "je cherche" not in spoken
    assert "{" not in spoken
    assert chunks[-1]["stop_reason"] == "tool_calls"
    assert chunks[-1]["tool_calls"][0].name == "t"


@runs_async
async def test_streaming_lignes_sans_prefixe_data_ignorees():
    brain = _brain()
    brain.client = FakeHTTPClient([
        "",
        "id: 1",
        ": keep-alive",
        sse({"choices": [{"delta": {"content": "ok"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert [c["delta"] for c in chunks if c["delta"]] == ["ok"]


@runs_async
async def test_streaming_ttft_seulement_sur_le_premier_delta():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"content": "A"}}]}),
        sse({"choices": [{"delta": {"content": "B"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert chunks[0]["delta"] == "A"
    assert chunks[0]["ttft_ms"] is not None
    assert chunks[1]["delta"] == "B"
    assert chunks[1]["ttft_ms"] is None


@runs_async
async def test_query_stub_sans_client():
    brain = _brain()
    brain.client = None
    out = await brain.query("x")
    assert out["stop_reason"] == "stub"
    assert out["response"]
    assert out["tokens_used"] == 0


@runs_async
async def test_query_http_erreur_reponse_vide():
    brain = _brain()
    brain.client = FakePostClient(payload={"error": "nope"}, status_code=503)
    out = await brain.query("x")
    assert out["stop_reason"] == "error"
    assert out["response"] == ""
    assert "nope" in out["error"]


@runs_async
async def test_query_exception_reponse_vide():
    brain = _brain()
    brain.client = FakePostClient(error=RuntimeError("socket closed"))
    out = await brain.query("x")
    assert out["stop_reason"] == "error"
    assert out["response"] == ""
    assert "socket closed" in out["error"]


@runs_async
async def test_query_non_stream_recolle_les_tool_calls():
    brain = _brain()
    brain.client = FakePostClient(payload={
        "choices": [{
            "message": {
                "content": None,
                "tool_calls": [
                    {"id": "a", "function": {"name": "web_search", "arguments": '{"query":"q"}'}},
                    {"id": "b", "function": {"name": "t1", "arguments": "{}"}},
                ],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"completion_tokens": 3},
    })
    out = await brain.query("x")
    assert out["stop_reason"] == "tool_calls"
    assert out["response"] == ""
    assert [c.name for c in out["tool_calls"]] == ["web_search", "t1"]
    assert out["tool_calls"][0].arguments == {"query": "q"}
    assert out["tokens_used"] == 3


@runs_async
async def test_health_stub_sans_client():
    brain = _brain()
    brain.client = None
    out = await brain.health()
    assert out["ok"] is False
    assert "stub" in out["detail"]
    assert out["latency_ms"] == 0


@runs_async
async def test_health_ok_et_exception():
    brain = _brain()
    brain.client = FakePostClient(get_status=200)
    ok = await brain.health()
    assert ok["ok"] is True
    assert "200" in ok["detail"]
    assert ok["latency_ms"] >= 0
    assert brain.client.gets[0]["url"].endswith("/models")

    brain.client = FakePostClient(get_error=RuntimeError("down"))
    bad = await brain.health()
    assert bad["ok"] is False
    assert "down" in bad["detail"]


@runs_async
async def test_llamacpp_hote_slash_final_n_est_pas_double(monkeypatch):
    monkeypatch.delenv("BRAIN_API_KEY", raising=False)
    llama = LlamaCppBrain(host="http://127.0.0.1:8090/", model="mother-local")
    assert llama.api_endpoint == "http://127.0.0.1:8090/v1/chat/completions"
    assert llama.model == "mother-local"
    assert llama.api_key == ""


@runs_async
async def test_payload_tool_choice_none_litteral_est_insere():
    """'none' est truthy : le champ part. Ce n'est pas tool_choice=None."""
    schemas = make_registry().schemas()
    payload = _brain()._payload("x", None, 0.7, True, None, tools=schemas, tool_choice="none")
    assert payload["tools"] == schemas
    assert payload["tool_choice"] == "none"


@runs_async
async def test_close_sans_client_ne_plante_pas():
    brain = _brain()
    brain.client = None
    await brain.close()
    client = FakePostClient()
    brain.client = client
    await brain.close()
    assert client.closed is True
    assert brain.client is None


@runs_async
async def test_streaming_choices_vide_ne_plante_pas():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": []}),
        sse({"choices": [{"delta": {"content": "ok"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert [c["delta"] for c in chunks if c["delta"]] == ["ok"]
