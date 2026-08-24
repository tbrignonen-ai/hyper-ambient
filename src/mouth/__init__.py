"""
MOUTH — Text-to-speech synthesis.

Conformance levels:
  L0 — No synthesis
  L1 — Chunked synthesis (paragraph-scale)
  L2 — Streaming synthesis (sub-sentence), TTFA < 500 ms
  L3 — Streaming with prosody control, multi-speaker

Candidates for PROFILE_MEDIUM:
  - Pocket TTS (MIT, French (estelle), 100M params, ~200 MB, TTFA 200 ms, 6× RTF on CPU)
  - MOSS-TTS-Nano-100M (Apache-2.0, French, 224 MB, 4-core CPU capable, no latency chiffre)
  - Distants: Deepgram/Flux-TTS (free tier), xAI Grok Voice, etc.

CRITICAL: Measure ttfa_perceived for Pocket TTS on this machine in French.
"""
