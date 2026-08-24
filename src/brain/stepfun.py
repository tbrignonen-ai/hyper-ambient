"""
BRAIN: StepFun API integration for LLM reasoning.

Model: step-3.7-flash
StepFun speaks the OpenAI chat protocol, so this is a thin binding over
OpenAICompatBrain — the same class that drives local llama.cpp.
"""
import logging
import os
from typing import Optional

from src.brain.openai_compat import OpenAICompatBrain

logger = logging.getLogger(__name__)


class StepFunBrain(OpenAICompatBrain):
    """StepFun LLM reasoning engine (remote, streaming, French)."""

    name = "stepfun"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_endpoint: str = "https://api.stepfun.ai/v1/chat/completions",
        model: str = "step-3.7-flash",
        timeout_ms: int = 30000,
    ):
        super().__init__(
            api_key=api_key or os.getenv("BRAIN_API_KEY"),
            api_endpoint=api_endpoint
            or os.getenv("BRAIN_API_ENDPOINT", "https://api.stepfun.ai/v1/chat/completions"),
            model=model or os.getenv("BRAIN_MODEL", "step-3.7-flash"),
            timeout_ms=timeout_ms or int(os.getenv("BRAIN_TIMEOUT_MS", "30000")),
        )
