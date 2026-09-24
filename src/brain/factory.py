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


def construire_distant(mode=None, modele=None, effort=None):
    """Le distant du routeur : clé d'API (défaut) ou abonnement de l'utilisateur.

    BRAIN_DEEP=abonnement-claude : la conversation passe par le Claude Code de
    l'utilisateur, via le pont hôte, sans clé d'API (mode abonnement, 24/09).
    Un choix explicite (bascule depuis Presence) prime sur l'environnement.
    """
    mode = (mode or os.getenv("BRAIN_DEEP") or "api").strip().lower()
    ponts = {
        "abonnement-claude": ("claude", "CLI_BRIDGE_URL", "CLI_BRIDGE_TOKEN", 8766, "claude-sonnet-5"),
        "abonnement-chatgpt": ("chatgpt", "CODEX_BRIDGE_URL", "CODEX_BRIDGE_TOKEN", 8765, "gpt-6-luna"),
    }
    if mode in ponts:
        from src.brain.abonnement import SubscriptionBrain

        harnais, cle_url, cle_jeton, port, defaut = ponts[mode]
        return SubscriptionBrain(
            bridge_url=os.getenv(cle_url, f"http://host.docker.internal:{port}/ask"),
            token=os.getenv(cle_jeton, ""),
            model=modele or os.getenv("BRAIN_ABONNEMENT_MODEL") or defaut,
            effort=effort or os.getenv("BRAIN_ABONNEMENT_EFFORT") or "low",
            harnais=harnais,
        )
    if os.getenv("MOTHER_PROFILE") == "mac-16g-voix-max":
        from native.macos.profile import model_path

        return OpenAICompatBrain(model=str(model_path("text")), max_tokens=256)
    return OpenAICompatBrain()  # BRAIN_API_* from the environment


_LIBELLES_MODELES = {
    "claude-sonnet-5": "Claude Sonnet 5",
    "sonnet": "Claude Sonnet",
    "haiku": "Claude Haiku",
    "opus": "Claude Opus",
    "fable": "Claude Fable",
}


def libelle_distant(distant) -> str:
    """Nom lisible du distant actif, pour l'indicateur de Presence."""
    nom = str(getattr(distant, "name", "") or "")
    if nom.startswith("abonnement-") and "/" in nom:
        modele = nom.split("/", 1)[1]
        if modele in _LIBELLES_MODELES:
            return _LIBELLES_MODELES[modele]
        if modele.lower().startswith("gpt-"):
            return "GPT-" + "-".join(p.capitalize() for p in modele[4:].split("-"))
        return modele
    modele = str(getattr(distant, "model", "") or nom)
    return modele.rsplit("/", 1)[-1]


def mode_distant(distant) -> str:
    nom = str(getattr(distant, "name", "") or "")
    return nom.split("/", 1)[0] if nom.startswith("abonnement-") else "api"


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

    classifier = None
    if os.getenv("MOTHER_PROFILE") == "mac-16g-voix-max" and os.getenv("BRAIN_LOCAL_BACKEND") == "mlx":
        from native.macos.profile import model_path, require_platform

        require_platform()
        reflex = OpenAICompatBrain(
            api_endpoint=os.getenv("BRAIN_API_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions"),
            model=str(model_path("text")), max_tokens=256,
        )

        async def classifier(prompt: str) -> str:
            result = await reflex.query(prompt, system="Réponds exclusivement REFLEXE ou ESCALADE.", temperature=0)
            if result.get("stop_reason") == "error":
                raise RuntimeError("classification MLX indisponible")
            return str(result.get("response") or "").strip()
    else:
        reflex = LlamaCppBrain(
            host=os.getenv("LLAMA_SERVER_HOST", LLAMA_HOST),
            model=os.getenv("BRAIN_MODEL_LOCAL", "local"),
        )
    deep = construire_distant()
    router = RouterBrain(reflex=reflex, deep=deep, classifier=classifier)
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
