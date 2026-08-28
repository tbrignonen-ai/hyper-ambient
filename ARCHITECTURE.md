# hyper-ambient Architecture

## Overview

hyper-ambient is a local ambient voice — French, English, and Spanish — that answers out loud. The core is a real-time voice AI harness with six capabilities integrated through a single permission control point (GATE).

```
┌─────────────────────────────────────────────────────────┐
│ Host Agent (Windows/macOS native)                       │
│   audio.capture()  audio.render()  input.inject()       │
│   surface.draw()                                         │
└──────────────┬──────────────────────────────────────────┘
               │ 20ms audio frames + events
               ▼
┌─────────────────────────────────────────────────────────┐
│ hyper-ambient Core (Containerized, GPU-accelerated)     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ EARS (Speech Recognition)                       │   │
│  │  - whisper.cpp (MIT, French, ~10 MB)           │   │
│  │  - nemotron-3.5 (fr-FR, fr-CA)                 │   │
│  └────────────┬────────────────────────────────────┘   │
│               │                                         │
│  ┌────────────▼────────────────────────────────────┐   │
│  │ TURN (Turn Detection & Endpoint Prediction)     │   │
│  │  - Pipecat Smart Turn v3.2 (BSD-2, 8 MB)       │   │
│  │  - Fallback: VAD-based (L1)                     │   │
│  └────────────┬────────────────────────────────────┘   │
│               │                                         │
│  ┌────────────▼────────────────────────────────────┐   │
│  │ BRAIN (LLM Reasoning, remote)                   │   │
│  │  - Anthropic Claude (recommended)               │   │
│  │  - OpenAI GPT-4o                                │   │
│  │  - Google Gemini Live                           │   │
│  │  - Mistral Voxtral, xAI, AssemblyAI            │   │
│  └────────────┬────────────────────────────────────┘   │
│               │                                         │
│  ┌────────────▼────────────────────────────────────┐   │
│  │ MOUTH (Speech Synthesis)                        │   │
│  │  - Pocket TTS (MIT, French, 200M-100M)         │   │
│  │  - MOSS-TTS (Apache-2.0, French, 224 MB)       │   │
│  └────────────┬────────────────────────────────────┘   │
│               │                                         │
│  ┌────────────▼────────────────────────────────────┐   │
│  │ ACOUSTIC (Non-speech event descriptors)         │   │
│  │  - Frontend: RMS, spectral centroid, ZCR        │   │
│  │  - L2: FunASR events (laughter, sigh, etc.)    │   │
│  └────────────┬────────────────────────────────────┘   │
│               │                                         │
│  ┌────────────▼────────────────────────────────────┐   │
│  │ GATE (Permission Control & Audit)               │   │
│  │  - Capability negotiation                       │   │
│  │  - Execution modes (plan/ask/auto/troubleshoot) │   │
│  │  - Hash-chained audit log                       │   │
│  └────────────┬────────────────────────────────────┘   │
│               │                                         │
│  ┌────────────▼────────────────────────────────────┐   │
│  │ CORE (Event loop & orchestration)               │   │
│  │  - Audio frame buffering                        │   │
│  │  - Semantic speculation (eager_end/resumed)     │   │
│  │  - Real-time event sequencing                   │   │
│  │  - Capability chaining                          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ API (HTTP + WebSocket)                          │   │
│  │  - /status, /capabilities, /converse           │   │
│  │  - /ws/{session_id} (real-time events)          │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### Normal Conversation

1. **EARS** receives audio frame (20ms)
   - Output: `TranscriptionPartial` (confidence, partial text)
   
2. **TURN** evaluates partial hypothesis
   - Output: `TurnCandidate` (endpoint probability, confidence)
   
3. **When turn is detected**:
   - Emit `TranscriptionFinal`
   - Query **BRAIN** (remote LLM)
   - Emit `BrainQuery` event
   
4. **BRAIN responds**:
   - Emit `BrainResponse` with text
   
5. **MOUTH** synthesizes response
   - Output: `SynthesisChunk` (audio data)
   - Emit `SynthesisEnd` when done
   
6. **ACOUSTIC** analyzes non-speech
   - Output: `AcousticEvent` (laughter, sigh, etc.)

### Semantic Speculation

When user is typing / providing input via `TURN-L1` (no learned model):

1. User says "Tell me a story about..."
2. Speech is not complete (TURN can't predict endpoint)
3. **BRAIN starts speculating** (eager_end mode)
   - Streams response to `MOUTH`
   - If user continues → `resumed` (cancel speculation)
   - If user stops → `end` (commit speculation)

## Capability Levels

Each capability has conformance levels L0–L3:

| Capability | L0 | L1 | L2 | L3 |
|---|---|---|---|---|
| **EARS** | None | Stable partials | Confidence per word | Multi-speaker, lang detect |
| **TURN** | None | VAD fallback | Learned endpoint | Speaker state aware |
| **MOUTH** | None | Chunked | Streaming, <500ms TTFA | Prosody control |
| **BRAIN** | None | Simple completion | Streaming reasoning | Tool use, multi-turn state |
| **ACOUSTIC** | None | Frontend descriptors | Learned events | Speaker classification |
| **DUPLEX** | None | Naive interrupt | Full bidirectional | Natural interruption |

## Profiles

Predefined deployment configurations:

| Profile | GPU | Memory | Use Case | Capabilities |
|---|---|---|---|---|
| `PROFILE_CPU_ONLY` | None | <2 GB | Embedded, offline | EARS-L1, TURN-L1, MOUTH-L1, BRAIN-remote |
| `PROFILE_SMALL` | None | <2 GB | Laptop, low-power | EARS-L1, TURN-L1, MOUTH-L1, BRAIN-remote |
| `PROFILE_MEDIUM` | RTX 4070 | <6 GB | This dev environment | EARS-L2, TURN-L2, MOUTH-L2, BRAIN-remote |
| `PROFILE_LARGE` | A100 | <10 GB | Data center | EARS-L3, TURN-L3, MOUTH-L3, BRAIN-local, ACOUSTIC-L2 |
| `PROFILE_CLOUD` | Managed | Unlimited | Serverless | Full everything |

## GATE Modes

```
plan         — Dry-run, show what would happen (no state change)
ask          — Prompt user before each action
manual       — User-triggered, batch mode
auto         — Automatic, no user interaction (default)
build        — Development/test mode, skip some checks
troubleshoot — Verbose logging, detailed tracing
yolo         — Absolute minimum checks (dangerous)
```

## Audit Log

Hash-chained append-only log of all:
- Capability negotiation decisions
- BRAIN service calls (model, prompt, response)
- Model loading and cache operations
- Permission control decisions
- Errors and fallbacks

Entry format:
```json
{
  "timestamp": "2026-08-21T16:30:45.123456",
  "hash": "sha256:...",
  "prev_hash": "sha256:...",
  "action": "brain_query",
  "params": {"model": "claude-3-5-sonnet", "tokens": 256},
  "result": "success",
  "caller": "core.event_loop",
  "user_id": "user123"
}
```

## Key Design Decisions (ADRs)

- **ADR-001**: Containerized core + native host-agent (Windows/macOS)
- **ADR-006**: Two-component architecture (see above)
- **ADR-012**: No secrets in audit log; sanitized params only
- **ADR-017**: 26–37 ms acoustic overhead budget

## Critical Dependencies

- **OQ-15**: Single-component dependency on Pipecat Smart Turn v3.2
  - Measure: `false_endpoint_rate` on corpus A01–A04
  - Blocker: If FPR > 15%, revert to VAD-only (TURN-L1)

- **[À VÉRIFIER] RTF measurements**: Whisper and nemotron on 30min audio
- **[À VÉRIFIER] TTFA measurements**: Pocket TTS and MOSS-TTS latency

## File Organization

```
src/
├── __init__.py               # Package metadata
├── __main__.py              # Entry point
├── core/                    # Orchestration
│   ├── __init__.py
│   ├── app.py              # Async main loop
│   ├── api.py              # FastAPI + WebSocket
│   ├── event.py            # Event types and queue
│   └── session.py          # Session management
├── ears/                    # ASR
│   ├── __init__.py
│   ├── whisper.py          # Whisper.cpp wrapper
│   └── nemotron.py         # Nemotron streaming
├── turn/                    # Turn detection
│   ├── __init__.py
│   ├── pipecat_adapter.py  # Pipecat Smart Turn
│   └── vad_fallback.py     # VAD-based endpoint
├── mouth/                   # TTS
│   ├── __init__.py
│   ├── pocket_tts.py       # Pocket TTS wrapper
│   └── moss_tts.py         # MOSS-TTS wrapper
├── brain/                   # Remote LLM
│   ├── __init__.py
│   ├── anthropic.py        # Anthropic Claude
│   ├── openai.py           # OpenAI GPT
│   └── providers.py        # Registry
├── acoustic/                # Event descriptors
│   ├── __init__.py
│   └── descriptors.py      # Frontend + FunASR
└── gate/                    # Permission & audit
    ├── __init__.py
    ├── permission.py       # GATE modes
    ├── audit.py            # Audit log
    └── negotiation.py      # Capability negotiation

dev/
├── tests/
│   ├── conftest.py
│   ├── test_ears.py
│   ├── test_turn.py
│   └── ...
└── measurements/
    ├── MEASUREMENT_PLAN.md
    ├── whisper_benchmark.py
    ├── pipecat_turn_eval.py
    └── pocket_tts_latency.py
```

## Next Steps

1. **Build container** (`make build`)
2. **Verify GPU** (inside container: `nvidia-smi`)
3. **Run benchmarks** (`make benchmark`) — measure RTF, FPR, TTFA
4. **Implement EARS** — whisper.cpp integration
5. **Implement TURN** — Pipecat Smart Turn + VAD fallback
6. **Implement MOUTH** — Pocket TTS + stream handler
7. **Implement BRAIN** — Anthropic Claude integration
8. **Integrate CORE** — Event loop, capability chaining
9. **API + WebSocket** — FastAPI server
10. **Host-agent** — Windows native component (separate phase)
