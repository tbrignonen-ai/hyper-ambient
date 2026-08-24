"""
Core — Orchestration and event loop.

Responsibilities:
  1. Lifecycle management (start, listen, process, speak, end)
  2. Capability negotiation via GATE (which EARS/TURN/MOUTH/BRAIN combo for this context?)
  3. Audio frame buffering and synchronization
  4. Semantic speculation: reversible reasoning, eager_end → resumed/end
  5. Integration with host-agent (capture/render/input/surface primitives)
  6. Real-time event sequencing and conflict resolution

Architecture (ADR-001):
  Containerized core handles all model inference and reasoning.
  Native host-agent (Windows/macOS) provides only four primitives:
    audio.capture(config) → 20ms frames to core
    audio.render(frames) → playback + render-reference signal for AEC
    input.inject(event) → single keyboard/mouse event
    surface.draw(frame) → UI frame (D5/ACOUSTIC feedback)

Event types:
  AudioFrame, TranscriptionPartial, TranscriptionFinal, TurnCandidate,
  BrainQuery, BrainResponse, SynthesisChunk, SynthesisEnd,
  AcousticEvent, StateChange, Error
"""
