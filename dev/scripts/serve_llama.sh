#!/usr/bin/env bash
# Local BRAIN — llama.cpp server, OpenAI-compatible, CUDA offload.
#
# Exposes /v1/chat/completions on :8080 (host :8090).
# Same protocol as StepFun, so src/brain/openai_compat.py drives both.
set -euo pipefail

MODEL="${MODEL:-$(ls -S /workspace/models/gguf/*.gguf 2>/dev/null | head -1)}"
[ -n "$MODEL" ] || { echo "No GGUF in /workspace/models/gguf — run fetch_models.sh brain"; exit 1; }

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
    --jinja \
    --metrics
