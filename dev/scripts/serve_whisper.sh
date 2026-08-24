#!/usr/bin/env bash
# Local EARS — whisper.cpp server (CUDA), OpenAI /v1/audio/transcriptions shape.
set -euo pipefail

MODEL="${MODEL:-/workspace/models/whisper/ggml-large-v3-turbo-q5_0.bin}"
[ -f "$MODEL" ] || { echo "Missing $MODEL — run fetch_models.sh core"; exit 1; }

echo "EARS(local) <- $(basename "$MODEL")"

exec whisper-server \
    --model "$MODEL" \
    --host 0.0.0.0 --port 8081 \
    --language "${LANG_CODE:-fr}" \
    --threads "$(nproc)" \
    --print-progress false
