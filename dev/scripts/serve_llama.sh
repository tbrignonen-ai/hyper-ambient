#!/usr/bin/env bash
# Local BRAIN — llama.cpp server, OpenAI-compatible, CUDA offload.
#
# Exposes /v1/chat/completions on :8080 (host :8090).
# Same protocol as StepFun, so src/brain/openai_compat.py drives both.
set -euo pipefail

# Default to the GGUF this project actually retained (Luth-2-2B, 1.4 GB), not the
# largest file on disk. `ls -S | head -1` picked Ministral-8B (4.9 GB) — 3.5x the
# intended model — which is what exhausted memory and killed the Docker backend
# on 2026-08-25. Override with MODEL=/workspace/models/gguf/<file>.gguf
MODEL="${MODEL:-$(ls /workspace/models/gguf/Luth-2-2B*.gguf 2>/dev/null | head -1)}"
MODEL="${MODEL:-$(ls -Sr /workspace/models/gguf/*.gguf 2>/dev/null | head -1)}"
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
