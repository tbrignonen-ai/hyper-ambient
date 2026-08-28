"""
BRAIN backend selection.

BRAIN_SERVICE decides which deployment answers:
  stepfun  -> remote StepFun (step-3.7-flash)
  llamacpp -> local llama-server (GGUF on CUDA)
  openai   -> any other OpenAI-compatible endpoint (BRAIN_API_ENDPOINT)

All three return the same object shape, so the core event loop never branches
on which one is live. Falling back from remote to local is a swap, not a
rewrite — that is what makes BRAIN degradable instead of a hard dependency.
"""
import asyncio
import logging
import os
from typing import Optional

from src.brain.openai_compat import LlamaCppBrain, OpenAICompatBrain
from src.brain.stepfun import StepFunBrain

logger = logging.getLogger(__name__)

LLAMA_HOST = os.getenv("LLAMA_SERVER_HOST", "http://localhost:8080")


def build_brain(service: Optional[str] = None) -> OpenAICompatBrain:
    """Instantiate the configured BRAIN backend (not yet initialized)."""
    service = (service or os.getenv("BRAIN_SERVICE", "stepfun")).lower()

    if service == "llamacpp":
        return LlamaCppBrain(
            host=os.getenv("LLAMA_SERVER_HOST", LLAMA_HOST),
            model=os.getenv("BRAIN_MODEL", "local"),
        )
    if service == "stepfun":
        return StepFunBrain()
    if service in ("openai", "compat"):
        return OpenAICompatBrain()

    raise ValueError(f"Unknown BRAIN_SERVICE: {service!r}")


async def build_router():
    """
    Two-channel hyper-ambient: local reflexes + remote deliberation.

    This is the deployment shape the spec calls for. `build_brain_with_fallback`
    is the opposite arrangement (remote primary, local rescue) and is kept only
    for measuring a remote backend end-to-end — it is strictly worse in the
    realtime path, measured at 1477 ms against 876 ms for local-only, because
    its demotion deadline is pure loss.
    """
    from src.brain.router import RouterBrain

    reflex = LlamaCppBrain(
        host=os.getenv("LLAMA_SERVER_HOST", LLAMA_HOST),
        model=os.getenv("BRAIN_MODEL_LOCAL", "local"),
    )
    deep = OpenAICompatBrain()  # BRAIN_API_* from the environment
    router = RouterBrain(reflex=reflex, deep=deep)
    await router.initialize()
    return router


class FallbackBrain:
    """
    Primary backend with automatic demotion to local llama.cpp.

    A reachability probe is not enough: StepFun answers `/v1/models` with HTTP
    200 while refusing every completion with 402 quota_exceeded. Credentials
    valid, capability absent. So the switch is driven by *inference* failures,
    not by connectivity — and once demoted we stay demoted for the session
    rather than paying the remote timeout on every turn.
    """

    name = "fallback"

    def __init__(
        self,
        primary: OpenAICompatBrain,
        local: OpenAICompatBrain,
        ttft_deadline_ms: Optional[int] = None,
    ):
        self.primary = primary
        self.local = local
        self.active = primary
        self.demoted = False
        # A reachable-but-slow backend is as unusable as a dead one. Reasoning
        # models are the common case: they answer correctly, 4 s late, which
        # blows a 1200 ms budget without ever raising an error.
        self.ttft_deadline_ms = ttft_deadline_ms or int(
            os.getenv("BRAIN_TTFT_DEADLINE_MS", "600")
        )

    @property
    def api_endpoint(self) -> str:
        return self.active.api_endpoint

    async def initialize(self):
        await self.primary.initialize()
        await self.local.initialize()

    async def close(self):
        await self.primary.close()
        await self.local.close()

    async def health(self):
        return await self.active.health()

    def _demote(self, reason: str):
        if self.demoted:
            return
        logger.warning(f"BRAIN demoted {self.primary.name} -> {self.local.name}: {reason}")
        self.active = self.local
        self.demoted = True

    async def query(self, prompt: str, **kw):
        result = await self.active.query(prompt, **kw)
        if result["stop_reason"] == "error" and not self.demoted:
            self._demote(str(result.get("error"))[:120])
            result = await self.active.query(prompt, **kw)
        return result

    async def query_streaming(self, prompt: str, **kw):
        """
        Pass deltas straight through — buffering to enable a retry would cost
        exactly the TTFT this whole design exists to protect.

        A retry is therefore only possible while nothing has been emitted yet.
        Once MOUTH has spoken a word we cannot un-speak it, so a mid-stream
        failure is surfaced as an error and the demotion applies to the *next*
        turn instead.
        """
        stream = self.active.query_streaming(prompt, **kw)

        # Race the first token against the deadline. Nothing has been spoken
        # yet, so abandoning here is free; after this point it is not.
        if not self.demoted:
            try:
                first = await asyncio.wait_for(
                    stream.__anext__(), timeout=self.ttft_deadline_ms / 1000.0
                )
            except asyncio.TimeoutError:
                await stream.aclose()
                self._demote(f"no first token within {self.ttft_deadline_ms} ms")
                async for chunk in self.active.query_streaming(prompt, **kw):
                    yield chunk
                return
            except StopAsyncIteration:
                self._demote("empty stream")
                async for chunk in self.active.query_streaming(prompt, **kw):
                    yield chunk
                return

            if first["stop_reason"] == "error":
                await stream.aclose()
                self._demote(str(first.get("error"))[:140])
                async for chunk in self.active.query_streaming(prompt, **kw):
                    yield chunk
                return
            yield first

        # Past the first token: deltas flow straight through. A failure now is
        # reported, not retried — MOUTH has already spoken.
        async for chunk in stream:
            if chunk["stop_reason"] == "error":
                self._demote(str(chunk.get("error"))[:140])
                yield chunk
                return
            yield chunk


async def build_brain_with_fallback():
    """
    Initialize the configured backend wrapped in automatic local fallback.

    Returns an initialized brain-like object. Caller owns close().
    """
    # Le routeur est un montage, pas un fournisseur : il compose le local et le
    # distant. Il ne passe donc pas par build_brain(), qui ne connait que des
    # fournisseurs uniques.
    if (os.getenv("BRAIN_SERVICE", "stepfun").lower()) == "router":
        return await build_router()

    primary = build_brain()
    if isinstance(primary, LlamaCppBrain):
        await primary.initialize()
        return primary

    local = LlamaCppBrain(host=LLAMA_HOST, model=os.getenv("BRAIN_MODEL_LOCAL", "local"))
    brain = FallbackBrain(primary, local)
    await brain.initialize()
    logger.info(f"BRAIN: {primary.name} primary, {local.name} standby")
    return brain
