#!/usr/bin/env bash
# Local BRAIN - llama.cpp server, OpenAI-compatible, CUDA offload.
#
# Exposes /v1/chat/completions on :8080 (host :8090).
# Same protocol as StepFun, so src/brain/openai_compat.py drives both.
set -euo pipefail

# Carte figée 19 sept : Granite 4.2 3B Q4_K_M. Repli LFM puis premier GGUF.
# Override: MODEL=/workspace/models/gguf/<file>.gguf
MODEL="${MODEL:-/workspace/models/gguf/granite-4.2-3b-Q4_K_M.gguf}"
if [ ! -f "$MODEL" ]; then
  MODEL="$(ls /workspace/models/gguf/LFM2.5-2.6B*.gguf 2>/dev/null | head -1)"
fi
MODEL="${MODEL:-$(ls -Sr /workspace/models/gguf/*.gguf 2>/dev/null | head -1)}"
[ -n "$MODEL" ] || { echo "No GGUF in /workspace/models/gguf - run fetch_models.sh brain"; exit 1; }

echo "BRAIN(local) <- $(basename "$MODEL")"

exec llama-server \
    --model "$MODEL" \
    --host 0.0.0.0 --port 8080 \
    --n-gpu-layers 999 \
    --ctx-size "${CTX:-4096}" \
    --batch-size 512 \
    --flash-attn on \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --no-mmap \
    --alias "${ALIAS:-mother-local}" \
    --jinja
