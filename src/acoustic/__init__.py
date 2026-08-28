"""
ACOUSTIC — Acoustic event descriptors (non-speech).

Conformance levels:
  L0 — No descriptors
  L1 — Frontend descriptors only (silence, noise floor, clipping)
  L2 — Learned acoustic event classification (laughter, sigh, hesitation, etc.)

Candidates:
  - Frontend: RMS energy, spectral centroid, zero-crossing rate (Apache-2.0, hyper-ambient code)
  - Learned: FunASR event detection (permissive? check license; Chinese → dialect mapping)
  - Note: PROFILE_CPU_ONLY loses L2 due to FunASR licensing issue. L1 only.

CRITICAL: Verify FunASR can run on PROFILE_MEDIUM GPU. If license is too restrictive, implement fallback.
"""
