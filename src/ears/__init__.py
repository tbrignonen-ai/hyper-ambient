"""
EARS — Speech recognition in stream.

Conformance levels:
  L0 — No ASR
  L1 — Stable partial hypotheses, revisions after 2-5 words
  L2 — Stable partials, confidence per word, speaker-aware
  L3 — Multi-speaker, language detection, per-segment SIL confidence

Candidates:
  - whisper.cpp (MIT, French, ~10 MB quantized, RTF TBD)
  - nemotron-3.5-asr-streaming-0.6b (OpenMDW-1.1, fr-FR/fr-CA, 0.74 GB quantized)
"""
