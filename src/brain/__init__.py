"""
BRAIN — Distant LLM reasoning and conversation state.

Mandatory remote (no local duplex). Integrates:
  - StepFun (step-3.7-flash, streaming, French, recommended for v1)
  - Anthropic Claude (recommended for French, reasoning)
  - OpenAI GPT-4o / o1 (reasoning, audio-native preview)
  - Google Gemini Live (audio-native, streaming, 15 min sessions)
  - xAI Grok Voice (0.08 $/min, no EU region yet)
  - Mistral Voxtral Realtime (pesos open, Apache-2.0)
  - AssemblyAI (EU endpoints available, billing on connection duration)

CRITICAL for French EU-based product: only AssemblyAI + Anthropic/Mistral meet GDPR.
"""
