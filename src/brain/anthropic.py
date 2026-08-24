"""
BRAIN: Anthropic Claude integration for reasoning and conversation.

Recommended for French EU users: data residency in EU, no cost issues.
Supports streaming responses via server-sent events.
"""
import asyncio
import logging
from typing import Dict, Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class AnthropicBrain:
    """Anthropic Claude reasoning engine."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        timeout_ms: int = 30000,
        api_key: Optional[str] = None
    ):
        """
        Initialize Anthropic Claude.

        Args:
            model: model identifier (e.g., claude-3-5-sonnet)
            timeout_ms: query timeout in milliseconds
            api_key: API key (if None, reads from ANTHROPIC_API_KEY env var)
        """
        self.model = model
        self.timeout_ms = timeout_ms
        self.api_key = api_key
        self.client = None
        logger.info(f"AnthropicBrain initialized: {model}")

    async def initialize(self):
        """Initialize API client."""
        try:
            from anthropic import Anthropic

            self.client = Anthropic(api_key=self.api_key)
            logger.info(f"Anthropic client initialized for {self.model}")

        except ImportError:
            logger.warning("anthropic package not available, using stub")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic: {e}")
            raise

    async def query(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Send query to Claude and get response (non-streaming).

        Args:
            prompt: user prompt
            system: system prompt (French conversation setup)
            temperature: sampling temperature

        Returns:
            {
                "response": "text response",
                "stop_reason": "end_turn",
                "tokens_used": 256,
                "latency_ms": 1200
            }
        """
        if self.client is None:
            return {
                "response": "[stub response]",
                "stop_reason": "stub",
                "tokens_used": 0,
                "latency_ms": 0
            }

        import time
        start = time.time()

        try:
            if system is None:
                system = "Tu es un assistant vocal conversationnel en français, bienveillant et utile."

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )

            latency_ms = (time.time() - start) * 1000

            return {
                "response": message.content[0].text,
                "stop_reason": message.stop_reason,
                "tokens_used": message.usage.output_tokens,
                "latency_ms": latency_ms
            }

        except Exception as e:
            logger.error(f"Query error: {e}")
            return {
                "response": "",
                "stop_reason": "error",
                "tokens_used": 0,
                "latency_ms": 0,
                "error": str(e)
            }

    async def query_streaming(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream response from Claude token by token.

        Args:
            prompt: user prompt
            system: system prompt
            temperature: sampling temperature

        Yields:
            {
                "delta": "token text",
                "stop_reason": None or "end_turn"
            }
        """
        if self.client is None:
            yield {"delta": "[stub]", "stop_reason": "stub"}
            return

        if system is None:
            system = "Tu es un assistant vocal conversationnel en français, bienveillant et utile."

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            ) as stream:
                for text in stream.text_stream:
                    yield {"delta": text, "stop_reason": None}

                # Final stop reason
                yield {"delta": "", "stop_reason": "end_turn"}

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {"delta": "", "stop_reason": "error", "error": str(e)}

    async def close(self):
        """Cleanup."""
        self.client = None
        logger.info("AnthropicBrain closed")
