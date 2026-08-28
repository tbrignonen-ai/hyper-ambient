# hyper-ambient — Development Environment

hyper-ambient (HA) is a local ambient voice: it listens and answers out loud in French, English, and Spanish. GPU-accelerated, containerized. First-to-end pipeline: **500 ms round-trip**, 96 % endpoint accuracy, local BRAIN with remote escalade.

## Quick Start

```bash
# Build container (caches CUDA & PyTorch on rebuild)
make build

# Start container
make up

# Enter container shell
make shell

# Run smoke test: verify all capabilities in one call
make smoke    # Expected: 9/9 ✓

# Download required models (~1.2 GB core + 2.5 GB GGUF for BRAIN)
make models
make models-brain
```

## Makefile Targets

All targets run inside the container. Common workflow:

| Target | Purpose |
|--------|---------|
| `make build` | Rebuild image (CUDA + torch cached) |
| `make up` | Start container background |
| `make down` | Stop container |
| `make shell` | Interactive bash in container |
| `make logs` | Stream container output |
| `make gpu` | Check GPU availability: `nvidia-smi` |
| `make smoke` | Run smoke test (9 capability checks) |
| `make test` | Run pytest suite |
| `make models` | Download VAD + TTS models (~1.2 GB) |
| `make models-brain` | Download GGUF weights for llama-server (~2.5 GB) |
| `make llama` | Launch llama-server (BRAIN local) on port 8090 |
| `make whisper` | Launch whisper-server (EARS local) on port 8091 |
| `make demo` | Run end-to-end pipeline with latency breakdown |
| `make demo-local` | Same, force BRAIN to local only (no remote) |
| `make clean` | Stop container and prune volumes |

## Structure

```
src/
  core/        Orchestration, event loop, lifecycle
  ears/        ASR (faster-whisper CTranslate2, GPU)
  turn/        Turn detection (Silero VAD L1, Smart Turn v3 L2)
  mouth/       TTS (Pocket TTS primary, Piper fallback)
  brain/       BRAIN local (llama.cpp + Luth-2-2B) + remote escalade (MiniMax-M3)
  acoustic/    Acoustic descriptors, event classification
  gate/        Permission control, audit log, execution modes

dev/
  tests/       Unit and integration tests
  scripts/     Build & runtime helpers, measurement bancs
  notebooks/   Interactive analysis
```

## Hardware Requirements

- **GPU**: NVIDIA RTX 4070 or equivalent (≥ 12 GB VRAM)
  - GPU reservation in docker-compose **mandatory** — without it, `torch.cuda.is_available()` returns `False`
- **CPU**: 8+ cores recommended
- **RAM**: 15+ GB host (15 GB WSL2 tested)
- **Storage**: 25+ GB for models (`models/` directory, bind-mounted, survives rebuilds)
- **Audio**: No `/dev/snd` in Docker Desktop Windows (no ALSA). Audio capture/render is the native host-agent's job.

## Network Ports

| Service | Host Port | Container | Purpose |
|---------|-----------|-----------|---------|
| hyper-ambient Core API | 8000 | 8000 | FastAPI / REST |
| WebSocket (host-agent) | 8001 | 8001 | Bidirectional event stream |
| llama-server (BRAIN local) | 8090 | 8080 | OpenAI-compatible completions |
| whisper-server (EARS local) | 8091 | 8081 | Whisper transcription |

Note: 8080 on host is reserved by SearXNG; remapped container 8080→8090 in docker-compose.

## Development Scripts

Located in `dev/scripts/`, run via `docker exec` or `make`:

| Script | Purpose |
|--------|---------|
| `smoke_test.py` | Verify all 9 capabilities load + run once (< 10 s) |
| `pipeline_demo.py` | End-to-end BRAIN → MOUTH with latency breakdown |
| `bench_brain.py` | Compare BRAIN models (TTFT, tokens/s, markup, WER) |
| `loopback_test.py` | MOUTH → EARS roundtrip (WER, RTF) |
| `voice_lab.py` | A/B test TTS voices + DSP profiles |
| `router_demo.py` | Demonstrate local-vs-remote routing strategy |
| `fetch_models.sh` | Download model weights (core or GGUF) |
| `serve_llama.sh` | Launch llama-server (blocking) |
| `serve_whisper.sh` | Launch whisper-server (blocking) |

## Capabilities Matrix (Measured 2026-08-21)

| Capability | Model | License | Metric | Value | VRAM | Status |
|---|---|---|---|---|---|---|
| **EARS** | faster-whisper `large-v3-turbo` int8_float16 | MIT | WER (loopback) | 2.6 % | 1.6 GB | ✅ Active |
| **TURN-L1** | Silero VAD ONNX | Apache-2.0 | Latency | 20 ms | CPU | ✅ Active |
| **TURN-L2** | Smart Turn v3 | BSD-2 | Accuracy (FR) | 96.01 % | 8 MB | ⏳ Ready, not installed |
| **MOUTH** | Kyutai Pocket TTS `estelle` | CC-BY-4.0 | TTFA | 75 ms (63 ms warm) | 1.49 GB | ✅ Active |
| **BRAIN-L1** | Luth-2-2B (llama.cpp CUDA) | ? | TTFT | 38 ms | 1.5 GB | ✅ Active |
| **BRAIN-Escalade** | MiniMax-M3 (CommandCode API) | Proprietary | TTFC p50 | 612 ms | 0 (remote) | ✅ Active |
| **Round-trip** | Composed | — | End-to-end | 500 ms | — | ✅ Executable |

## Critical Health Checks

Before claiming "working":

```bash
# 1. GPU detection
make gpu    # Should show RTX 4070

# 2. All capabilities load
make smoke  # Should print: 9/9 ✓

# 3. Local BRAIN works
make llama &
curl http://localhost:8090/v1/models  # Should return list

# 4. Local EARS works
make whisper &
curl http://localhost:8091/v1/models  # Should return list
```

## Model Storage

Downloaded to `./models/` (bind-mounted, persistent):

```
models/gguf/       18 GB   Candidate LLMs (Luth active, Ministral/Luciole/LFM2.5/Qwen for evaluation)
models/pocket-tts/ 724 MB  Pocket TTS + 3 voices (estelle, eve, vera)
models/hf-cache/   1.7 GB  faster-whisper turbo + base
models/tts/        1.4 Go  Qwen3-TTS (offline only, not real-time)
models/whisper/    548 MB  GGML Whisper (fallback)
models/piper/      268 MB  Piper voices (MOUTH fallback, zero VRAM)
```

Run `make models` and `make models-brain` once; they survive rebuilds.

## API Endpoints (WIP)

See `src/core/api.py` for current stubs. Planned:

- `GET /health` — health check
- `POST /converse` — one-turn voice I/O (placeholder)
- `WS /ws` — bidirectional event stream
- `GET /capabilities` — list loaded components

## References

- **Implementation log**: `dev/sessions/2026-08-21-implementation.md` (source of truth for this state)
- **Technical stack**: `STACK.md` (design rationale, benchmarks, model selection)
- **Spec**: `D:\BGB Training\Projet MOTHER\` (separate directory; this is code)

---

**Status**: First executable pipeline. Smoke test 9/9. Round-trip 500 ms.  
**Updated**: 2026-08-21
