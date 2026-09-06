#!/usr/bin/env bash
# Local BRAIN - llama.cpp server, OpenAI-compatible, CUDA offload.
#
# Exposes /v1/chat/completions on :8080 (host :8090).
# Same protocol as StepFun, so src/brain/openai_compat.py drives both.
set -euo pipefail

# Default: LFM2.5-2.6B Q5_K_M (Thomas 2026-09-02). Glob LFM2.5-2.6B* avoids VL-3B.
# Override: MODEL=/workspace/models/gguf/<file>.gguf
MODEL="${MODEL:-$(ls /workspace/models/gguf/LFM2.5-2.6B*.gguf 2>/dev/null | head -1)}"
MODEL="${MODEL:-$(ls -Sr /workspace/models/gguf/*.gguf 2>/dev/null | head -1)}"
[ -n "$MODEL" ] || { echo "No GGUF in /workspace/models/gguf - run fetch_models.sh brain"; exit 1; }

echo "BRAIN(local) <- $(basename "$MODEL")"

exec llama-server \
    --model "$MODEL" \
    --host 0.0.0.0 --port 8080 \
    --n-gpu-layers 999 \
    --ctx-size "${CTX:-8192}" \
    --batch-size 512 \
    --flash-attn on \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --alias "${ALIAS:-mother-local}" \
    --jinja
