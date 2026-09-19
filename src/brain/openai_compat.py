"""
BRAIN: OpenAI-compatible chat backend.

One client, two deployments:
  - remote  : StepFun, OpenAI, Mistral, xAI, ... (any /v1/chat/completions)
  - local   : llama.cpp `llama-server` (same protocol, same SSE framing)

This is the whole point of the abstraction — swapping BRAIN between a distant
service and a local GGUF is a config change, not a code change.

Streaming yields deltas as they arrive and reports time-to-first-token (TTFT),
which is the number that actually feeds the NFR-01 latency budget.
"""
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Single source of truth: MOUTH owns what "speakable" means, BRAIN just asks
# for it. Stripping markup downstream is the safety net, not the plan.
from src.mouth.normalize import VOICE_SYSTEM_PROMPT as DEFAULT_SYSTEM  # noqa: E402
from src.brain.tools import MAX_TOOL_ARGUMENTS_CHARS, ToolCall  # noqa: E402
from src.i18n import system_prompt as LOCAL_SYSTEM_PROMPT_FN  # noqa: E402


class OpenAICompatBrain:
    """Chat backend speaking the OpenAI /v1/chat/completions protocol."""

    name = "openai-compat"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout_ms: int = 30000,
        max_tokens: int = 1024,
    ):
        self.api_key = api_key or os.getenv("BRAIN_API_KEY", "")
        self.api_endpoint = api_endpoint or os.getenv(
            "BRAIN_API_ENDPOINT", "http://localhost:8080/v1/chat/completions"
        )
        self.model = model or os.getenv("BRAIN_MODEL", "default")
        self.timeout_ms = timeout_ms
        self.max_tokens = max_tokens
        self.client = None
        logger.info(f"{self.name} brain configured: {self.model} @ {self.api_endpoint}")

    # -- lifecycle ---------------------------------------------------------

    async def initialize(self):
        """Create the HTTP client. Without it the backend stays in stub mode."""
        try:
            import httpx

            self.client = httpx.AsyncClient(timeout=self.timeout_ms / 1000.0)
            logger.info(f"{self.name} client ready ({self.api_endpoint})")
        except ImportError:
            logger.warning("httpx not available, staying in stub mode")
            self.client = None

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None
        logger.info(f"{self.name} client closed")

    async def health(self) -> Dict[str, Any]:
        """Cheap reachability probe. Returns {ok, detail, latency_ms}."""
        if self.client is None:
            return {"ok": False, "detail": "stub mode (not initialized)", "latency_ms": 0}
        start = time.perf_counter()
        try:
            base = self.api_endpoint.split("/chat/completions")[0]
            r = await self.client.get(f"{base}/models", headers=self._headers())
            return {
                "ok": r.status_code == 200,
                "detail": f"HTTP {r.status_code}",
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        except Exception as e:
            return {
                "ok": False,
                "detail": str(e),
                "latency_ms": (time.perf_counter() - start) * 1000,
            }

    # -- internals ---------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        stream: bool,
        history: Optional[List[Dict[str, str]]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # `messages` remplace entierement system + history + prompt : c'est ce
        # qui permet a la boucle d'outils de renvoyer l'assistant porteur des
        # tool_calls suivi des messages tool.
        if messages is None:
            messages = [{"role": "system", "content": system or DEFAULT_SYSTEM}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        # Insertion seulement si non vide : le chemin sans outil doit rester bit
        # pour bit celui d'avant, et "tools": [] est un risque inutile cote
        # llama-server.
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
        return payload

    @staticmethod
    def _accumulate_tool_calls(buffer: Dict[int, Dict[str, str]], fragments: List[Dict[str, Any]]):
        """Recolle les fragments `delta.tool_calls` par index.

        Les arguments arrivent en JSON morcele ; un seul fragment emis en delta
        et MOUTH epelle du JSON a voix haute. Rien ne sort d'ici.
        """
        for fragment in fragments or []:
            index = fragment.get("index", 0)
            slot = buffer.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if fragment.get("id"):
                slot["id"] = fragment["id"]
            function = fragment.get("function") or {}
            if function.get("name"):
                slot["name"] = function["name"]
            if function.get("arguments"):
                fragment = function["arguments"]
                room = MAX_TOOL_ARGUMENTS_CHARS - len(slot["arguments"])
                if room > 0:
                    slot["arguments"] += fragment[:room]
                elif fragment:
                    # Le JSON continue d'arriver : on le jette plutot que de
                    # gonfler un brut deja illisible (mesure 17 sept).
                    pass

    @staticmethod
    def _finalize_tool_calls(buffer: Dict[int, Dict[str, str]]) -> List[ToolCall]:
        calls = []
        for index in sorted(buffer):
            slot = buffer[index]
            raw = slot["arguments"]
            if len(raw) > MAX_TOOL_ARGUMENTS_CHARS:
                raw = raw[:MAX_TOOL_ARGUMENTS_CHARS]
            try:
                arguments = json.loads(raw) if raw.strip() else {}
                if not isinstance(arguments, dict):
                    arguments = {}
            except json.JSONDecodeError:
                # Le brut est conserve : un modele local rend regulierement du
                # JSON invalide, et la boucle doit pouvoir le refuser proprement.
                logger.warning(f"tool_call {slot['name']}: arguments illisibles ({raw[:80]!r})")
                arguments = {}
            calls.append(
                ToolCall(
                    id=slot["id"] or f"call_{index}",
                    name=slot["name"],
                    arguments=arguments,
                    raw_arguments=raw,
                )
            )
        return calls

    # -- inference ---------------------------------------------------------

    async def query(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        history: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Non-streaming completion. Use only for tests and batch work."""
        if self.client is None:
            return {
                "response": "[stub response]",
                "stop_reason": "stub",
                "tokens_used": 0,
                "latency_ms": 0,
            }

        start = time.perf_counter()
        try:
            response = await self.client.post(
                self.api_endpoint,
                json=self._payload(
                    prompt, system, temperature, False, history,
                    tools=tools, tool_choice=tool_choice, messages=messages,
                ),
                headers=self._headers(),
            )
            latency_ms = (time.perf_counter() - start) * 1000
            result = response.json()

            if response.status_code != 200:
                logger.error(f"{self.name} error {response.status_code}: {result}")
                return {
                    "response": "",
                    "stop_reason": "error",
                    "tokens_used": 0,
                    "latency_ms": latency_ms,
                    "error": str(result),
                }

            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {}) or {}
            out = {
                "response": message.get("content", "") or "",
                "stop_reason": choice.get("finish_reason", "unknown"),
                "tokens_used": result.get("usage", {}).get("completion_tokens", 0),
                "latency_ms": latency_ms,
            }
            if message.get("tool_calls"):
                buffer: Dict[int, Dict[str, str]] = {}
                self._accumulate_tool_calls(
                    buffer,
                    [
                        {**call, "index": i}
                        for i, call in enumerate(message["tool_calls"])
                    ],
                )
                out["tool_calls"] = self._finalize_tool_calls(buffer)
                out["stop_reason"] = "tool_calls"
            return out

        except Exception as e:
            logger.error(f"{self.name} query error: {e}")
            return {
                "response": "",
                "stop_reason": "error",
                "tokens_used": 0,
                "latency_ms": (time.perf_counter() - start) * 1000,
                "error": str(e),
            }

    async def query_streaming(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        history: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream deltas as they arrive.

        Yields {"delta": str, "stop_reason": None|str, "ttft_ms": float|None}.
        ttft_ms is set on the first delta only — that is the value MOUTH needs
        to start synthesising before BRAIN has finished thinking.

        Avec `tools`, les fragments `delta.tool_calls` sont accumules par index
        et rendus en un unique chunk {"delta": "", "stop_reason": "tool_calls",
        "tool_calls": [ToolCall, ...]} — jamais en delta parle.
        """
        if self.client is None:
            yield {"delta": "[stub]", "stop_reason": "stub", "ttft_ms": 0}
            return

        start = time.perf_counter()
        ttft_ms: Optional[float] = None
        reasoning_deltas = 0
        tool_buffer: Dict[int, Dict[str, str]] = {}

        try:
            async with self.client.stream(
                "POST",
                self.api_endpoint,
                json=self._payload(
                    prompt, system, temperature, True, history,
                    tools=tools, tool_choice=tool_choice, messages=messages,
                ),
                headers=self._headers(),
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "replace")
                    logger.error(f"{self.name} stream error {response.status_code}: {body}")
                    yield {
                        "delta": "",
                        "stop_reason": "error",
                        "ttft_ms": None,
                        "error": f"HTTP {response.status_code}: {body[:200]}",
                    }
                    return

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break

                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.debug(f"skipped non-JSON SSE line: {payload[:60]}")
                        continue

                    choice = (chunk.get("choices") or [{}])[0]
                    delta_obj = choice.get("delta", {})
                    delta = delta_obj.get("content") or ""
                    finish = choice.get("finish_reason")

                    # Les fragments d'appel d'outil ne sont jamais des deltas :
                    # ils sont recolles ici et rendus en une fois a la fin.
                    if delta_obj.get("tool_calls"):
                        self._accumulate_tool_calls(tool_buffer, delta_obj["tool_calls"])
                        delta = ""

                    # Reasoning models stream chain-of-thought in a separate
                    # field. It must never reach MOUTH — the user would hear
                    # the model thinking out loud — but it must be counted, or
                    # an all-reasoning response looks like silent success.
                    if delta_obj.get("reasoning") or delta_obj.get("reasoning_content"):
                        reasoning_deltas += 1
                        continue

                    if delta:
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - start) * 1000
                            yield {"delta": delta, "stop_reason": None, "ttft_ms": ttft_ms}
                        else:
                            yield {"delta": delta, "stop_reason": None, "ttft_ms": None}
                    if finish:
                        if tool_buffer or finish == "tool_calls":
                            yield {
                                "delta": "",
                                "stop_reason": "tool_calls",
                                "ttft_ms": None,
                                "tool_calls": self._finalize_tool_calls(tool_buffer),
                            }
                            return
                        if ttft_ms is None and reasoning_deltas:
                            # Thinking consumed the whole budget: no answer.
                            yield {
                                "delta": "",
                                "stop_reason": "error",
                                "ttft_ms": None,
                                "error": (
                                    f"{reasoning_deltas} reasoning deltas, zero content "
                                    f"(finish_reason={finish}). This backend is a reasoning "
                                    f"model with no usable off switch — unfit for realtime voice."
                                ),
                            }
                            return
                        yield {"delta": "", "stop_reason": finish, "ttft_ms": None}

        except Exception as e:
            logger.error(f"{self.name} streaming error: {e}")
            yield {"delta": "", "stop_reason": "error", "ttft_ms": None, "error": str(e)}


class LlamaCppBrain(OpenAICompatBrain):
    """Local BRAIN backed by llama.cpp `llama-server` (GGUF, CUDA)."""

    name = "llama.cpp"

    def __init__(self, host: str = "http://localhost:8080", model: str = "local", **kw):
        kw.setdefault("api_endpoint", f"{host.rstrip('/')}/v1/chat/completions")
        kw.setdefault("api_key", "")  # llama-server needs no key by default
        super().__init__(model=model, **kw)

    def _payload(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        stream: bool,
        history: Optional[List[Dict[str, str]]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # Le reflexe local (MiniCPM5-2B) est un modele a raisonnement : laisse
        # faire, il brule son budget en `reasoning_content` et rend un contenu
        # vide, ou recopie l'exemple du prompt. Mesure le 15 sept.
        if not system:
            system = LOCAL_SYSTEM_PROMPT_FN()
            if messages is not None:
                # `run_tool_loop` fournit déjà la liste complète. Copie-la pour
                # ne pas modifier l'historique conservé par l'appelant.
                messages = [dict(message) for message in messages]
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] = system
                else:
                    messages.insert(0, {"role": "system", "content": system})
        payload = super()._payload(
            prompt,
            system,
            temperature,
            stream,
            history,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload
