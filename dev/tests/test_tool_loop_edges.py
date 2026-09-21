"""
BRAIN: branches de la boucle d'outils non couvertes par test_tool_loop.py.

Toujours hors reseau, hors llama-server : FakeBrain / FakeGate / FakeHTTPClient.
On pince ici ce que le lot initial n'exerce pas : plusieurs appels dans le
meme tour, un handler qui rend autre chose qu'une str, un arret des le
premier tour, un motif de porte vide, et les recolements OpenAI qui ne
doivent jamais fuir en delta parle.
"""
import asyncio
import functools
import json
from pathlib import Path

from src.brain.openai_compat import LlamaCppBrain, OpenAICompatBrain
from src.brain.tool_loop import (
    CALLER,
    MAX_ITERATIONS_MESSAGE,
    _build_messages,
    _sanitize,
    run_tool_loop,
)
from src.brain.tools import (
    MAX_TOOL_CONTENT_CHARS,
    ToolCall,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class FakeGate:
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


class _BareDecision:
    """Porte mal elevee : pas de reason, pas de allowed."""


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


def sse(obj):
    return "data: " + json.dumps(obj)


async def _echo(**kwargs):
    return "echo:" + json.dumps(kwargs, sort_keys=True)


def _spec(name, handler, danger="read", **params):
    return ToolSpec(
        name=name,
        description=name,
        parameters={"type": "object", "properties": params or {"query": {"type": "string"}}},
        danger=danger,
        handler=handler,
    )


def make_registry(*specs):
    registry = ToolRegistry()
    if not specs:
        registry.register(_spec("web_search", _echo, danger="read", query={"type": "string"}))
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


# -- plusieurs appels, types de retour, arret --------------------------------


@runs_async
async def test_deux_outils_du_meme_tour_un_seul_est_execute():
    seen = []

    async def h_a(query):
        seen.append(("a", query))
        return "A"

    async def h_b(query):
        seen.append(("b", query))
        return "B"

    brain = FakeBrain([
        [tool_calls_chunk([
            _call("alpha", {"query": "un"}, call_id="c-a"),
            _call("beta", {"query": "deux"}, call_id="c-b"),
        ])],
        [{"delta": "les deux.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    registry = make_registry(_spec("alpha", h_a), _spec("beta", h_b))
    chunks = [c async for c in run_tool_loop(brain, "x", registry, FakeGate())]

    assert seen == [("a", "un")]
    tools = [c for c in chunks if c.get("channel") == "tool"]
    assert [c["phase"] for c in tools] == ["call", "result"]
    assert [c["tool"] for c in tools] == ["alpha", "alpha"]
    messages = brain.calls[1]["messages"]
    assert [m["role"] for m in messages[-2:]] == ["assistant", "tool"]
    assert messages[-1]["tool_call_id"] == "c-a"
    assert len(messages[-2]["tool_calls"]) == 1


@runs_async
async def test_deux_outils_premier_refuse_second_autorise():
    called = []

    async def h_a(query):
        called.append("a")
        return "A"

    async def h_b(query):
        called.append("b")
        return "B"

    class SelectiveGate:
        def __init__(self):
            self.requests = []

        async def check(self, request):
            self.requests.append(request)
            if request.tool == "alpha":
                return _Decision(False, "Pas alpha.", "ask")
            return _Decision(True, "ok", "auto")

    brain = FakeBrain([
        [tool_calls_chunk([
            _call("alpha", call_id="c-a"),
            _call("beta", call_id="c-b"),
        ])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    registry = make_registry(_spec("alpha", h_a), _spec("beta", h_b))
    chunks = [c async for c in run_tool_loop(brain, "x", registry, SelectiveGate())]
    assert called == []
    phases = [c.get("phase") for c in chunks if c.get("channel") == "tool"]
    assert phases == ["call", "denied"]
    assert brain.calls[1]["messages"][-1]["content"] == "Pas alpha."
    assert brain.calls[1]["messages"][-1]["tool_call_id"] == "c-a"


@runs_async
async def test_handler_qui_rend_un_dict_est_serialise():
    async def handler(query):
        return {"ville": "Paris", "deg": 18}

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(_spec("web_search", handler)), FakeGate())]
    content = brain.calls[1]["messages"][-1]["content"]
    parsed = json.loads(content)
    assert parsed == {"ville": "Paris", "deg": 18}


@runs_async
async def test_handler_qui_rend_une_liste_est_serialise():
    async def handler(query):
        return ["un", "deux"]

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(_spec("web_search", handler)), FakeGate())]
    assert json.loads(brain.calls[1]["messages"][-1]["content"]) == ["un", "deux"]


@runs_async
async def test_handler_qui_rend_none_devient_json_null():
    async def handler(query):
        return None

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(_spec("web_search", handler)), FakeGate())]
    assert brain.calls[1]["messages"][-1]["content"] == "null"


@runs_async
async def test_max_iterations_un_nexecute_rien():
    called = []

    async def handler(query):
        called.append(query)
        return "non"

    brain = FakeBrain([[tool_calls_chunk([_call()])] for _ in range(3)])
    chunks = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec("web_search", handler)), FakeGate(), max_iterations=1,
    )]
    assert called == []
    assert len(brain.calls) == 1
    spoken = "".join(c["delta"] for c in chunks)
    assert spoken == MAX_ITERATIONS_MESSAGE
    assert chunks[-1]["stop_reason"] == "max_iterations"
    assert all(c.get("channel") != "tool" for c in chunks)


@runs_async
async def test_message_d_arret_est_exact_et_dicible():
    assert "outil" in MAX_ITERATIONS_MESSAGE.lower()
    assert "{" not in MAX_ITERATIONS_MESSAGE
    brain = FakeBrain([[tool_calls_chunk([_call()])] for _ in range(4)])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate(), max_iterations=2)]
    assert chunks[-1]["delta"] == MAX_ITERATIONS_MESSAGE


@runs_async
async def test_texte_avant_tool_calls_est_cede_le_chunk_outil_non():
    brain = FakeBrain([[
        {"delta": "Je cherche.", "stop_reason": None, "ttft_ms": 4.0, "channel": "deep"},
        tool_calls_chunk([_call()]),
    ], [
        {"delta": "18 degres.", "stop_reason": "stop", "ttft_ms": 1.0},
    ]])
    chunks = [c async for c in run_tool_loop(brain, "meteo", make_registry(), FakeGate())]
    spoken_before_tools = [c["delta"] for c in chunks if c.get("channel") != "tool"]
    assert "Je cherche." in spoken_before_tools
    assert all(c["delta"] == "" for c in chunks if c.get("channel") == "tool")
    assert all(c.get("stop_reason") != "tool_calls" for c in chunks)


@runs_async
async def test_liste_d_appels_vide_arrete_la_boucle():
    brain = FakeBrain([[tool_calls_chunk([])]])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    assert len(brain.calls) == 1
    assert all(c.get("channel") != "tool" for c in chunks)


@runs_async
async def test_motif_de_porte_vide_devient_une_phrase():
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "refuse", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate(allowed=False, reason=""))]
    content = brain.calls[1]["messages"][-1]["content"]
    assert content.strip()
    assert "autorisation" in content.lower() or "droit" in content.lower()


@runs_async
async def test_decision_sans_attribut_allowed_est_un_refus():
    class WeirdGate:
        requests = []

        async def check(self, request):
            self.requests.append(request)
            return _BareDecision()

    called = []

    async def handler(query):
        called.append(query)
        return "non"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "refuse", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec("web_search", handler)), WeirdGate(),
    )]
    assert called == []
    assert "autorisation" in brain.calls[1]["messages"][-1]["content"].lower()


@runs_async
async def test_danger_write_est_celui_de_la_spec_pas_du_modele():
    async def handler(path):
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call("file_write", {"path": "/tmp/x"}, call_id="w1")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    gate = FakeGate()
    registry = make_registry(_spec("file_write", handler, danger="write", path={"type": "string"}))
    _ = [c async for c in run_tool_loop(brain, "x", registry, gate)]
    assert gate.requests[0].danger == "write"
    assert gate.requests[0].caller == CALLER
    assert gate.requests[0].tool == "file_write"


@runs_async
async def test_arguments_blancs_ne_sont_pas_un_json_invalide():
    seen = []

    async def handler(**kw):
        seen.append(kw)
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={}, raw="   ", call_id="c1")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(_spec("web_search", handler)), FakeGate())]
    assert seen == [{}]


@runs_async
async def test_json_invalide_dit_parametres_pas_compris():
    async def handler(**kw):
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call(args={}, raw="{query:", call_id="c1")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(_spec("web_search", handler)), FakeGate())]
    content = brain.calls[1]["messages"][-1]["content"]
    assert "parametre" in content.lower() or "paramètres" in content.lower() or "compris" in content.lower()


@runs_async
async def test_outil_inconnu_dit_nexiste_pas():
    brain = FakeBrain([
        [tool_calls_chunk([_call(name="fantome")])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    content = brain.calls[1]["messages"][-1]["content"]
    assert "fantome" in content
    assert "n'existe pas" in content or "existe pas" in content


@runs_async
async def test_handler_mauvais_kwargs_est_rattrape():
    async def handler():
        return "ok"

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "desole", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(
        brain, "x", make_registry(_spec("web_search", handler)), FakeGate(),
    )]
    content = brain.calls[1]["messages"][-1]["content"]
    assert "n'a pas repondu" in content or "pas repondu" in content
    assert "TypeError" not in content
    assert all(c["delta"] == "" for c in chunks if c.get("channel") == "tool")


@runs_async
async def test_deuxieme_tour_conserve_l_historique_et_les_outils():
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    history = [{"role": "user", "content": "avant"}, {"role": "assistant", "content": "oui"}]
    _ = [c async for c in run_tool_loop(
        brain, "meteo", make_registry(), FakeGate(), system="SYS", history=history,
    )]
    first = brain.calls[0]["messages"]
    assert first[0] == {"role": "system", "content": "SYS"}
    assert {"role": "user", "content": "avant"} in first
    second = brain.calls[1]["messages"]
    assert second[0]["content"] == "SYS"
    assert second[-1]["role"] == "tool"
    assert not brain.calls[1]["tools"], "apres un outil, plus de schemas au second tour"


@runs_async
async def test_build_messages_sans_systeme_n_est_pas_vide():
    messages = _build_messages("salut", None, None)
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "salut"}


@runs_async
async def test_chunk_outil_n_a_jamais_de_delta_meme_si_le_modele_en_met():
    poisoned = tool_calls_chunk([_call()])
    poisoned["delta"] = '{"query":"fuite"}'
    brain = FakeBrain([
        [poisoned],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    chunks = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    assert '{"query"' not in "".join(c["delta"] for c in chunks)


# -- openai_compat : recolement, reasoning, erreurs HTTP ---------------------


@runs_async
async def test_accumulate_par_index_desordonne():
    buffer = {}
    OpenAICompatBrain._accumulate_tool_calls(buffer, [
        {"index": 1, "id": "b", "function": {"name": "t1", "arguments": "{}"}},
        {"index": 0, "id": "a", "function": {"name": "t0", "arguments": "{}"}},
    ])
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert [c.name for c in calls] == ["t0", "t1"]
    assert [c.id for c in calls] == ["a", "b"]


@runs_async
async def test_finalize_id_vide_devient_call_index():
    buffer = {2: {"id": "", "name": "web_search", "arguments": "{}"}}
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].id == "call_2"
    assert calls[0].arguments == {}


@runs_async
async def test_finalize_tableau_json_devient_dict_vide():
    buffer = {0: {"id": "a", "name": "web_search", "arguments": "[1, 2]"}}
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].arguments == {}
    assert calls[0].raw_arguments == "[1, 2]"


@runs_async
async def test_finalize_json_vide_ou_blanc():
    buffer = {
        0: {"id": "a", "name": "t", "arguments": ""},
        1: {"id": "b", "name": "t", "arguments": "   "},
    }
    calls = OpenAICompatBrain._finalize_tool_calls(buffer)
    assert calls[0].arguments == {}
    assert calls[1].arguments == {}


@runs_async
async def test_streaming_reasoning_ne_parle_pas():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"reasoning_content": "je reflechis"}}]}),
        sse({"choices": [{"delta": {"reasoning": "encore"}}]}),
        sse({"choices": [{"delta": {"content": "bonjour"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert [c["delta"] for c in chunks if c["delta"]] == ["bonjour"]
    assert all("reflechis" not in (c.get("delta") or "") for c in chunks)


@runs_async
async def test_streaming_que_du_reasoning_est_une_erreur():
    brain = _brain()
    brain.client = FakeHTTPClient([
        sse({"choices": [{"delta": {"reasoning": "hmm"}}]}),
        sse({"choices": [{"delta": {"reasoning_content": "hmm2"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert chunks[-1]["stop_reason"] == "error"
    assert chunks[-1]["delta"] == ""
    assert "reasoning" in chunks[-1]["error"]


@runs_async
async def test_streaming_http_erreur_ne_parle_pas_le_corps():
    brain = _brain()
    brain.client = FakeHTTPClient(status_code=500, body=b"internal boom traceback")
    chunks = [c async for c in brain.query_streaming("x")]
    assert chunks[0]["stop_reason"] == "error"
    assert chunks[0]["delta"] == ""
    assert "500" in chunks[0]["error"]


@runs_async
async def test_streaming_ligne_sse_non_json_est_ignoree():
    brain = _brain()
    brain.client = FakeHTTPClient([
        "data: pas-du-json",
        "event: ping",
        sse({"choices": [{"delta": {"content": "ok"}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        "data: [DONE]",
    ])
    chunks = [c async for c in brain.query_streaming("x")]
    assert [c["delta"] for c in chunks if c["delta"]] == ["ok"]


@runs_async
async def test_streaming_sans_client_est_un_stub():
    brain = _brain()
    brain.client = None
    chunks = [c async for c in brain.query_streaming("x")]
    assert chunks[0]["stop_reason"] == "stub"
    assert chunks[0]["delta"]


@runs_async
async def test_payload_tool_choice_sans_outils_n_est_pas_insere():
    payload = _brain()._payload("x", None, 0.7, True, None, tools=[], tool_choice="auto")
    assert "tools" not in payload
    assert "tool_choice" not in payload


@runs_async
async def test_payload_tool_choice_none_avec_outils_n_ajoute_pas_le_champ():
    schemas = make_registry().schemas()
    payload = _brain()._payload("x", None, 0.7, True, None, tools=schemas, tool_choice=None)
    assert payload["tools"] == schemas
    assert "tool_choice" not in payload


@runs_async
async def test_headers_sans_cle_n_ont_pas_d_authorization(monkeypatch):
    monkeypatch.delenv("BRAIN_API_KEY", raising=False)
    brain = OpenAICompatBrain(api_key="", api_endpoint="http://local/v1/chat/completions")
    assert "Authorization" not in brain._headers()
    brain.api_key = "secret"
    assert brain._headers()["Authorization"] == "Bearer secret"


@runs_async
async def test_llamacpp_brain_pointe_chat_completions():
    llama = LlamaCppBrain(host="http://localhost:8090", model="mother-local")
    assert llama.api_endpoint.endswith("/v1/chat/completions")
    assert llama.name == "llama.cpp"


@runs_async
async def test_sanitize_filtre_keyboard_comme_sous_chaine():
    cleaned = _sanitize({"query": "q", "keyboard": "k", "refresh_token": "t", "api-key": "x"})
    assert cleaned == {"query": "q"}


@runs_async
async def test_resultat_tronque_reste_sous_la_limite_apres_json():
    async def handler(query):
        return {"blob": "z" * 5000}

    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(_spec("web_search", handler)), FakeGate())]
    content = brain.calls[1]["messages"][-1]["content"]
    assert len(content) <= MAX_TOOL_CONTENT_CHARS
    assert content.endswith("[…]") or content.endswith("…]")


# -- tool_choice force : premiere iteration seulement ------------------------

CHOIX_CODEX = {"type": "function", "function": {"name": "ask_codex"}}


@runs_async
async def test_tool_choice_present_a_la_premiere_iteration():
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(), FakeGate(), tool_choice=CHOIX_CODEX,
    )]
    assert brain.calls[0]["tool_choice"] == CHOIX_CODEX


@runs_async
async def test_tool_choice_absent_a_la_seconde_iteration():
    brain = FakeBrain([
        [tool_calls_chunk([_call()])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(), FakeGate(), tool_choice=CHOIX_CODEX,
    )]
    assert len(brain.calls) == 2
    assert "tool_choice" not in brain.calls[1]


@runs_async
async def test_tool_choice_absent_quand_tools_this_round_vide():
    brain = FakeBrain([
        [{"delta": "fin.", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(
        brain, "x", make_registry(), FakeGate(),
        tool_choice=CHOIX_CODEX, max_tool_calls=0,
    )]
    assert brain.calls[0]["tools"] == []
    assert "tool_choice" not in brain.calls[0]


@runs_async
async def test_sans_tool_choice_charge_utile_identique():
    brain = FakeBrain([
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    _ = [c async for c in run_tool_loop(brain, "x", make_registry(), FakeGate())]
    charge = brain.calls[0]
    assert "tool_choice" not in charge
    assert set(charge.keys()) == {"prompt", "system", "history", "messages", "tools"}


def _charger_serve_hostagent():
    import importlib.util
    import sys
    from pathlib import Path
    from unittest.mock import MagicMock

    racine = Path(__file__).resolve().parents[2]
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        for nom in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
            sys.modules.setdefault(nom, MagicMock(name=nom))
    chemin = racine / "dev" / "scripts" / "serve_hostagent.py"
    spec = importlib.util.spec_from_file_location(
        "serve_hostagent_forcer_outil", chemin,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_serve_hostagent_n_a_plus_de_forcage_tool_choice():
    """Le distant appelle l'outil de lui-même ; le forçage local est retiré."""
    serve = _charger_serve_hostagent()
    assert not hasattr(serve, "tool_choice_si_harnais")
    source = Path(__file__).resolve().parents[2] / "dev" / "scripts" / "serve_hostagent.py"
    texte = source.read_text(encoding="utf-8")
    assert "tool_choice=forcage" not in texte
    assert "def tool_choice_si_harnais" not in texte


@runs_async
async def test_harnais_nomme_fait_autorite_sur_le_choix_du_modele():
    """L'utilisateur a dit Claude Code ; le distant a choisi ask_codex."""
    appeles = []

    async def codex(question: str) -> str:
        appeles.append("codex")
        return "codex"

    async def claude(question: str) -> str:
        appeles.append("claude")
        return "claude"

    brain = FakeBrain([
        [tool_calls_chunk([_call("ask_codex", args={"question": "version Python"})])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    registre = make_registry(
        _spec("ask_codex", codex, question={"type": "string"}),
        _spec("ask_claude", claude, question={"type": "string"}),
    )
    chunks = [
        c
        async for c in run_tool_loop(
            brain,
            "Demande a Claude Code de me dire quelle version de Python tourne.",
            registre,
            FakeGate(),
        )
    ]
    assert appeles == ["claude"]
    outils = [c.get("tool") for c in chunks if c.get("channel") == "tool"]
    assert "ask_claude" in outils
    assert "ask_codex" not in outils


@runs_async
async def test_harnais_nomme_absent_se_dit_sans_basculer():
    appeles = []

    async def codex(question: str) -> str:
        appeles.append("codex")
        return "codex"

    brain = FakeBrain([
        [tool_calls_chunk([_call("ask_codex", args={"question": "version Python"})])],
        [{"delta": "ok", "stop_reason": "stop", "ttft_ms": 1.0}],
    ])
    registre = make_registry(_spec("ask_codex", codex, question={"type": "string"}))
    chunks = [
        c
        async for c in run_tool_loop(
            brain,
            "Demande a Claude Code de me dire quelle version de Python tourne.",
            registre,
            FakeGate(),
        )
    ]
    assert appeles == []
    texte = "".join(c.get("delta") or "" for c in chunks)
    assert "Claude Code n'est pas connecté sur cette machine" in texte
