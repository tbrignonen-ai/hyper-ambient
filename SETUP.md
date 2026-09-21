# hyper-ambient Development Setup

## Prerequisites

### Host Machine
- **Docker Desktop** with Docker Compose (Windows/macOS/Linux)
- **NVIDIA GPU**: RTX 4070 or equivalent (≥ 12 GB VRAM)
- **NVIDIA drivers**: Latest stable for your GPU
- **Docker NVIDIA runtime**: Docker Desktop must have `nvidia-smi` working (`docker run --rm --gpus all ubuntu nvidia-smi`)
- **Disk space**: 25+ GB free for model cache (`./models/`)
- **RAM**: 15+ GB allocated to WSL2 (Windows) or hypervisor

### Critical GPU Requirement
The docker-compose.yml **reserves** GPU device under `deploy.resources.reservations.devices`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```
**Without this reservation, `torch.cuda.is_available()` returns `False` inside the container.** This is not optional.

## Build & Start

### 1. Build the container

```bash
cd C:\chemin\vers\hyper-ambient
make build
```

This invokes `docker-compose build`, which:
- Downloads NVIDIA CUDA 12.4 + Ubuntu 22.04 base image
- Installs Python 3.11, PyTorch (CUDA 12.4), dependencies from `requirements.txt`
- **Compiles llama.cpp and whisper.cpp from source** (CUDA architecture `sm_89` = Ada Lovelace / RTX 4070)
- Caches CUDA and torch layers for fast rebuilds
- Adds `requirements-extra.txt` (faster-whisper, pocket-tts, etc.) after cache boundary

**Image size**: 32.3 GB (includes CUDA toolkit + compiled binaries).

### 2. Start the container

```bash
make up
```

Runs `docker-compose up -d`:
- Mounts `./src/`, `./dev/`, `./models/`, `./data/`, `./logs/` inside container as `/workspace/{src,dev,models,data,logs}`
- Mounts `.env.local` (secrets, read-only)
- Maps ports: 8000, 8001 (hyper-ambient), 8090→8080, 8091→8081 (local services)
- Allocates 2 GB shared memory (`shm_size`)
- Keeps container running in background

### 3. Enter container shell

```bash
make shell
```

Runs `docker exec -it mother-core-dev bash`. You are now in `/workspace/`.

### 4. Verify GPU inside container

```bash
# Method 1: nvidia-smi
nvidia-smi
# Should show: NVIDIA RTX 4070, Driver Version, CUDA Version 12.4

# Method 2: PyTorch
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name()}')"
# Expected output:
# CUDA available: True
# Device: NVIDIA GeForce RTX 4070
```

If either fails, the GPU reservation is not working. See **Troubleshooting** below.

## Download Model Weights

Models live in `./models/` (bind-mounted, survived container rebuilds and restarts).

### Core Models (required for smoke test)
```bash
make models
```

Downloads (~1.2 GB):
- Silero VAD ONNX (turn detection L1)
- faster-whisper `large-v3-turbo` CTranslate2 (EARS, GPU)
- Piper TTS voices (MOUTH fallback)

### BRAIN Models (required for llama-server)
```bash
make models-brain
```

Downloads (~2.5 GB):
- `LiquidAI/LFM2.5-2.6B-GGUF` (`LFM2.5-2.6B-Q5_K_M.gguf`, active default BRAIN via `mother-local` on :8090)
- `kurakurai/Luth-2-2B-GGUF` (Q5_K_M quantization — **fallback / historique 2026-08-21**, plus le défaut)
- Ministral-3-8B, Luciole-8B, LFM2.5-VL-3B, Qwen candidates (for evaluation)

These scripts call `dev/scripts/fetch_models.sh {core|brain}` which uses huggingface-hub to download.

## Verify Everything Works: Smoke Test

```bash
make smoke
```

Runs `dev/scripts/smoke_test.py` inside container. Expected output:

```
smoke_test.py — 9 capability checks

[1/9] TURN-L1 (VAD)           OK  20 ms
[2/9] EARS (faster-whisper)   OK  370 ms, WER 2.6%
[3/9] BRAIN-L1 (LFM2.5 local)  OK  27 ms TTFT
[4/9] BRAIN-remote check      OK  reachable
[5/9] MOUTH (Pocket TTS)      OK  75 ms TTFA
[6/9] Router (escalade logic) OK  classification 90 ms
[7/9] TURN-L2 ready check     OK  not installed (expected)
[8/9] Acoustic descriptors    OK  real-time
[9/9] Audit chain             OK  verifies

9/9 ✓
```

All 9 checks should pass. If any fail, check **Troubleshooting** below.

## Running Tests & Benchmarks

### Unit tests
```bash
make test
# Runs: docker exec -it mother-core-dev python3 -m pytest dev/tests -v
```

### Smoke test (quick verification)
```bash
make smoke
# Runs all 9 capabilities once
```

### Benchmarks (measure latency on this machine)
Use individual measurement scripts:

```bash
# BRAIN model comparison (TTFT, throughput)
docker exec -it mother-core-dev python3 dev/scripts/bench_brain.py

# MOUTH→EARS loopback (WER, RTF)
docker exec -it mother-core-dev python3 dev/scripts/loopback_test.py

# End-to-end pipeline with breakdown
docker exec -it mother-core-dev python3 dev/scripts/pipeline_demo.py --text "Explique-moi ce qu'est un LLM."

# Local-vs-remote routing demo
docker exec -it mother-core-dev python3 dev/scripts/router_demo.py

# TTS voice A/B testing
docker exec -it mother-core-dev python3 dev/scripts/voice_lab.py
```

## Running Local Services

BRAIN and EARS can run as standalone OpenAI-compatible servers, useful for debugging:

### Launch local BRAIN (llama-server)
```bash
make llama
# Starts: llama-server -m models/gguf/LFM2.5-2.6B-Q5_K_M.gguf --port 8080 (via serve_llama.sh)
# Listen on: http://localhost:8090 (mapped from container 8080, alias mother-local)
```

Test it:
```bash
curl -X POST http://localhost:8090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mother-local","messages":[{"role":"user","content":"Bonjour"}]}'
```

### Launch local EARS (whisper-server)
```bash
make whisper
# Starts: whisper-server --port 8081 -m models/whisper/ggml-large-v3-turbo-q5_0.gguf
# Listen on: http://localhost:8091 (mapped from container 8081)
```

Test it:
```bash
curl -X POST http://localhost:8091/v1/audio/transcriptions \
  -F "file=@path/to/audio.wav" \
  -F "model=whisper"
```

## Container Lifecycle

### Stop (preserves models and logs)
```bash
make down
# or: docker-compose down
```

### Full cleanup (removes volumes, containers, networks)
```bash
make clean
# or: docker-compose down -v && docker system prune -a --volumes
```

## Environment Variables

Secrets live in `.env.local` (git-ignored), mounted read-only. Example:

```
# .env.local (create this file)
BRAIN_REMOTE_API_KEY=sk-...
BRAIN_REMOTE_ENDPOINT=https://api.commandcode.ai/provider/v1
BRAIN_SERVICE=commandcode    # or: llamacpp (local only)
```

At runtime, `src/` reads `.env.local` via `python-dotenv` (if installed). See `src/brain/factory.py` for env var keys.

## Troubleshooting

### "CUDA available: False" inside container

**Symptom**: `torch.cuda.is_available()` returns `False`, but host GPU works.

**Fix**:
1. Verify host Docker runtime: `docker run --rm --gpus all ubuntu nvidia-smi`
2. Check docker-compose.yml has `deploy.resources.reservations.devices[0].driver: nvidia`
3. Rebuild: `make down && make build && make up`
4. Re-enter and verify: `make shell` then `nvidia-smi`

### "No module named 'llama_cpp'" or import errors

**Symptom**: Startup fails with missing dependencies.

**Fix**:
1. Ensure requirements.txt and requirements-extra.txt are in place
2. Rebuild: `make build`
3. Verify: `docker exec mother-core-dev pip list | grep -E 'llama-cpp|faster-whisper|'`

### Models stuck downloading

**Symptom**: `make models` or `make models-brain` hangs.

**Fix**:
1. Check internet connectivity inside container: `docker exec mother-core-dev curl https://huggingface.co`
2. Check disk space: `docker exec mother-core-dev df -h`
3. Retry with verbose: `docker exec mother-core-dev bash -x dev/scripts/fetch_models.sh core`
4. If timeout, manually download one model:
   ```bash
   docker exec mother-core-dev python3 -c \
     "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cuda', compute_type='int8_float16')"
   ```

### "Port 8000 already in use"

**Symptom**: `docker-compose up` fails with port conflict.

**Fix**:
1. Find what's using 8000: `netstat -ano | findstr :8000` (Windows) or `lsof -i :8000` (Unix)
2. Stop conflicting process or remap in docker-compose.yml: `ports: ["8000:8000"]` → `"8002:8000"`

## File Structure (in container)

```
/workspace/
├── src/              Python modules (mounted from ./src/)
├── dev/
│   ├── tests/        Unit tests
│   ├── scripts/      Runtime scripts (smoke_test.py, bench_*.py, etc.)
│   └── sessions/     Session logs (2026-08-21-implementation.md, etc.)
├── models/           Downloaded weights (bind-mounted, persistent)
│   ├── gguf/         GGUF LLMs (LFM2.5-2.6B actif ; Luth = repli/historique 2026-08-21, Ministral, etc.)
│   ├── pocket-tts/   TTS weights + voices
│   ├── hf-cache/     faster-whisper CTranslate2 + Hugging Face cache
│   ├── whisper/      GGML Whisper (fallback)
│   └── piper/        Piper TTS voices (fallback)
├── data/             Test corpora, audio samples (mounted from ./data/)
├── logs/             Runtime logs, audit chain (mounted from ./logs/)
└── .env.local        Secrets, read-only mount
```

## Next Steps

1. **Build**: `make build`
2. **Start**: `make up && make shell`
3. **Verify GPU**: `nvidia-smi`
4. **Download models**: `make models && make models-brain`
5. **Smoke test**: `exit` container, then `make smoke`
6. **Try a demo**: `make demo` (end-to-end BRAIN → MOUTH)
7. **Explore**: Launch individual services (`make llama`, `make whisper`) or run measurement scripts

See `README.md` for API endpoints and capability descriptions.
