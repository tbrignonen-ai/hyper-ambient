"""
BRAIN: the two-channel router.

hyper-ambient is the room's authority, not its quickest voice. It is allowed to take
its time — what it is not allowed to do is leave silence. So the realtime
budget applies to the **acknowledgment**, not to the answer:

    user stops speaking
      -> classify locally           (~90 ms, prefix-cached, grammar-constrained)
      -> REFLEX  : local answers, streams straight to MOUTH
      -> ESCALATE: local speaks a filler NOW, remote answers behind it

The filler is what buys the right to be intelligent. Without it, escalation is
just latency; with it, escalation is deliberation.

Why the classifier is binary
----------------------------
A three-way SIMPLE/FAST/DEEP split was measured and rejected: asked to grade
"il est 14 h 40, réunion dans 20 min, durée 40 min, à quelle heure je finis ?",
the 2 B classifier answered FAST — routing to local the one question every
local model gets wrong (0/5 across five models, see STACK.md). A small model
cannot grade a difficulty it cannot itself handle.

So the only judgement asked of it is one it can actually make: "is this
small talk?" Everything else escalates. Ambiguity escalates. The cost of a
wrong escalation is a few hundred milliseconds; the cost of a wrong local
answer is hyper-ambient being confidently wrong, which is the one thing it must
never be.
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Grammar-constrained: the model cannot emit anything but these two tokens.
CLASSIFY_GRAMMAR = 'root ::= "REFLEXE" | "ESCALADE"'

CLASSIFY_PREFIX = """Tu tries des demandes adressées à hyper-ambient, une voix ambiante locale.

REFLEXE = salutation, politesse, remerciement, acquiescement, ou ordre direct
          sans aucun raisonnement (répète, plus fort, arrête, annule).
ESCALADE = tout le reste. Toute question de connaissance, de calcul, de
          comparaison, d'analyse, toute demande nécessitant un outil, et tout
          cas douteux.

Dans le doute, réponds ESCALADE.

Demande: Bonjour hyper-ambient.
Classe: REFLEXE
Demande: Merci, c'est noté.
Classe: REFLEXE
Demande: Répète plus fort.
Classe: REFLEXE
Demande: Quelle est la capitale de la Norvège ?
Classe: ESCALADE
Demande: Il est 14 h 40, ma réunion dure quarante minutes et commence dans vingt minutes, à quelle heure je finis ?
Classe: ESCALADE
Demande: Quel temps fait-il à Paris demain ?
Classe: ESCALADE
Demande: """

CLASSIFY_SUFFIX = "\nClasse:"

# Canned, not generated. Generating a filler would cost a round-trip of the
# very latency the filler exists to hide, and would risk a filler that does not
# fit. These are short, level, and in hyper-ambient's register: never apologetic,
# never chatty.
FILLERS = [
    "Un instant.",
    "Je vérifie.",
    "Analyse en cours.",
    "Je consulte les données.",
]

# One filler covers about a second of audio. The remote channel was measured at
# 612 ms median on short prompts but 13.8 s on a hard one — so a single filler
# leaves ten seconds of silence, which reads as a crash, not as deliberation.
# A second line keeps presence without turning into chatter.
HOLDING = [
    "Je traite toujours la demande.",
    "Encore quelques instants.",
]


class RouterBrain:
    """
    Local reflex channel + remote deliberation channel.

    Exposes the same surface as OpenAICompatBrain, so MOUTH and the core loop
    never learn which channel answered.
    """

    name = "router"

    def __init__(
        self,
        reflex,                    # OpenAICompatBrain — local llama.cpp
        deep,                      # OpenAICompatBrain — remote
        classify_host: Optional[str] = None,
        enable_filler: bool = True,
        deep_timeout_ms: Optional[int] = None,
    ):
        self.reflex = reflex
        self.deep = deep
        self.classify_host = (classify_host or os.getenv(
            "LLAMA_SERVER_HOST", "http://localhost:8080")).rstrip("/")
        self.enable_filler = enable_filler
        # Generous on purpose: hyper-ambient may deliberate. This is the point at
        # which we give up on the remote entirely, not a latency target.
        self.deep_timeout_ms = deep_timeout_ms or int(
            os.getenv("BRAIN_DEEP_TIMEOUT_MS", "20000"))
        # Silence tolerated after the last spoken word before another holding
        # line goes out. ~1 s of filler audio plus this is the perceived gap.
        self.holding_after_ms = int(os.getenv("BRAIN_HOLDING_AFTER_MS", "2500"))
        self._filler_i = 0
        self._client = None
        self.stats = {"reflex": 0, "escalate": 0, "deep_failed": 0}

    @property
    def api_endpoint(self) -> str:
        return f"reflex={self.reflex.api_endpoint} deep={self.deep.api_endpoint}"

    async def initialize(self):
        import httpx

        self._client = httpx.AsyncClient(timeout=10.0)
        await self.reflex.initialize()
        await self.deep.initialize()
        logger.info(f"router: reflex={self.reflex.name} deep={self.deep.name}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        await self.reflex.close()
        await self.deep.close()

    async def health(self):
        r = await self.reflex.health()
        d = await self.deep.health()
        return {
            "ok": r["ok"],  # the reflex channel is the one hyper-ambient cannot lose
            "detail": f"reflex {r['detail']}, deep {d['detail']}",
            "latency_ms": r["latency_ms"],
        }

    # -- classification ----------------------------------------------------

    async def classify(self, prompt: str) -> Dict[str, Any]:
        """
        Decide REFLEXE vs ESCALADE on the local model.

        Uses /completion (not /v1/chat/completions) because it takes a GBNF
        grammar and a stable prefix, so llama-server's prompt cache covers
        everything but the transcript — measured 335 ms cold, ~90 ms warm.
        """
        if self._client is None:
            return {"route": "escalate", "latency_ms": 0.0, "reason": "no client"}

        body = {
            "prompt": CLASSIFY_PREFIX + prompt.strip() + CLASSIFY_SUFFIX,
            "grammar": CLASSIFY_GRAMMAR,
            "n_predict": 4,
            "temperature": 0,
            "cache_prompt": True,
        }
        t0 = time.perf_counter()
        try:
            r = await self._client.post(f"{self.classify_host}/completion", json=body)
            elapsed = (time.perf_counter() - t0) * 1000
            verdict = (r.json().get("content") or "").strip()
            route = "reflex" if verdict == "REFLEXE" else "escalate"
            return {"route": route, "latency_ms": elapsed, "verdict": verdict}
        except Exception as e:
            # Failing open means escalating — never silently answering locally.
            logger.warning(f"classify failed ({e}); escalating")
            return {
                "route": "escalate",
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "reason": str(e)[:80],
            }

    def _next_filler(self) -> str:
        f = FILLERS[self._filler_i % len(FILLERS)]
        self._filler_i += 1
        return f

    # -- inference ---------------------------------------------------------

    async def query_streaming(
        self, prompt: str, system: Optional[str] = None, **kw
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Yield deltas. Chunks carry `channel` ("reflex" | "filler" | "deep") so
        callers can log or style them; MOUTH just speaks the text.
        """
        decision = await self.classify(prompt)
        route = decision["route"]
        logger.info(f"router: {route} ({decision['latency_ms']:.0f} ms)")

        if route == "reflex":
            self.stats["reflex"] += 1
            async for chunk in self.reflex.query_streaming(prompt, system=system, **kw):
                chunk["channel"] = "reflex"
                yield chunk
            return

        self.stats["escalate"] += 1

        # Speak first, think second. The filler goes out before the remote
        # request is even awaited, so MOUTH starts synthesising immediately.
        if self.enable_filler:
            yield {
                "delta": self._next_filler(),
                "stop_reason": None,
                "ttft_ms": decision["latency_ms"],
                "channel": "filler",
                "flush": True,   # MOUTH: synthesise this now, do not buffer
            }

        emitted = False
        try:
            stream = self.deep.query_streaming(prompt, system=system, **kw)
            holding = 0
            async for chunk in _with_holding(
                stream, self.deep_timeout_ms, self.holding_after_ms,
                len(HOLDING) if self.enable_filler else 0,
            ):
                if chunk.get("_holding"):
                    yield {
                        "delta": HOLDING[holding % len(HOLDING)],
                        "stop_reason": None,
                        "ttft_ms": None,
                        "channel": "holding",
                        "flush": True,
                    }
                    holding += 1
                    continue
                if chunk["stop_reason"] == "error":
                    raise RuntimeError(chunk.get("error", "deep channel error"))
                if chunk["delta"]:
                    emitted = True
                chunk["channel"] = "deep"
                yield chunk
            return
        except Exception as e:
            self.stats["deep_failed"] += 1
            logger.warning(f"deep channel failed ({str(e)[:100]}) — falling back to reflex")
            if emitted:
                # Already speaking the remote's answer; cannot restart cleanly.
                yield {"delta": "", "stop_reason": "error", "ttft_ms": None,
                       "channel": "deep", "error": str(e)[:200]}
                return

        # Nothing spoken past the filler — the local channel can still answer,
        # and "Un instant." followed by a local answer stays coherent.
        async for chunk in self.reflex.query_streaming(prompt, system=system, **kw):
            chunk["channel"] = "reflex"
            yield chunk

    async def query(self, prompt: str, system: Optional[str] = None, **kw):
        """Non-streaming convenience — no filler, since nothing is spoken."""
        decision = await self.classify(prompt)
        target = self.reflex if decision["route"] == "reflex" else self.deep
        result = await target.query(prompt, system=system, **kw)
        result["channel"] = decision["route"]
        if result["stop_reason"] == "error" and target is self.deep:
            self.stats["deep_failed"] += 1
            result = await self.reflex.query(prompt, system=system, **kw)
            result["channel"] = "reflex"
        return result


async def _with_holding(
    agen: AsyncIterator, timeout_ms: int, holding_after_ms: int, max_holding: int
):
    """
    Forward an async generator, emitting a `_holding` marker whenever it stays
    silent for `holding_after_ms`, and giving up entirely at `timeout_ms`.

    Two separate clocks on purpose: the holding clock resets on every chunk
    (silence since the last word), the deadline clock does not (total patience).
    """
    deadline = time.perf_counter() + timeout_ms / 1000.0
    holdings = 0
    pending: Optional[asyncio.Future] = None

    try:
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError(f"deep channel silent for {timeout_ms} ms")

            if pending is None:
                pending = asyncio.ensure_future(agen.__anext__())

            step = holding_after_ms / 1000.0 if holdings < max_holding else remaining
            # asyncio.wait — NOT wait_for. wait_for CANCELS its awaitable on
            # timeout, and cancelling __anext__() tears down the generator and
            # its HTTP stream: the holding line would kill the very channel it
            # exists to cover. asyncio.wait leaves the task running so the next
            # iteration can keep waiting on the same one.
            done, _ = await asyncio.wait({pending}, timeout=min(step, remaining))

            if not done:
                if holdings < max_holding:
                    holdings += 1
                    yield {"_holding": True}
                    continue
                raise TimeoutError(f"deep channel silent for {timeout_ms} ms")

            try:
                item = pending.result()
            except StopAsyncIteration:
                pending = None
                return
            pending = None
            holdings = 0  # it spoke; reset the silence clock
            yield item
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
        await agen.aclose()
