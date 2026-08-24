"""
TURN — Turn detection and break prediction.

Conformance levels:
  L0 — No turn detection (VAD fallback only)
  L1 — Voice activity detection
  L2 — Learned turn detection (confidence per endpoint candidate)
  L3 — Multi-speaker, conversation state awareness

Candidates:
  - Pipecat Smart Turn v3.2 (BSD-2, French, 8 MB, 10 ms on CPU, single-component dependency)
  - Fallback: VAD-based endpoint detection (no learned model)

CRITICAL: This is OQ-15 — no other learned turn model is available. Measure false_endpoint_rate.
"""
