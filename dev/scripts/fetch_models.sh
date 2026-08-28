#!/usr/bin/env bash
# Fetch hyper-ambient model weights into /workspace/models (host-mounted, survives rebuilds).
#
# Tiers:
#   ./fetch_models.sh core   -> VAD + Piper FR voice + whisper turbo  (~1.2 GB)
#   ./fetch_models.sh brain  -> local GGUF LLM for llama-server       (~2.5 GB)
#   ./fetch_models.sh all
set -euo pipefail

MODELS=/workspace/models
TIER="${1:-core}"

dl() {  # dl <url> <dest>
    local url="$1" dest="$2"
    if [ -f "$dest" ]; then
        echo "  = $(basename "$dest") already present ($(du -h "$dest" | cut -f1))"
        return
    fi
    echo "  + $(basename "$dest")"
    mkdir -p "$(dirname "$dest")"
    curl -fL --progress-bar -o "$dest" "$url"
}

fetch_core() {
    echo "== TURN: Silero VAD (ONNX) =="
    python3 - <<'PY'
from silero_vad import load_silero_vad
load_silero_vad(onnx=True)
print("  = silero-vad ONNX cached")
PY

    echo "== MOUTH: Piper French voice (fr_FR-siwis-medium) =="
    local base="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium"
    dl "$base/fr_FR-siwis-medium.onnx"        "$MODELS/piper/fr_FR-siwis-medium.onnx"
    dl "$base/fr_FR-siwis-medium.onnx.json"   "$MODELS/piper/fr_FR-siwis-medium.onnx.json"

    echo "== EARS: whisper.cpp GGUF (large-v3-turbo q5_0) =="
    dl "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin" \
       "$MODELS/whisper/ggml-large-v3-turbo-q5_0.bin"

    echo "== EARS: faster-whisper (CTranslate2) =="
    python3 - <<'PY'
from faster_whisper import WhisperModel
# downloads into HF_HOME=/workspace/models/hf-cache
WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
print("  = faster-whisper large-v3-turbo cached")
PY
}

fetch_brain() {
    echo "== BRAIN: local GGUF for llama-server =="
    # Mistral ships official GGUF. Chosen for French: measured best register
    # and the only candidate that asks for clarification instead of guessing.
    # Use the -Instruct variant, never -Reasoning (see STACK.md §4).
    local repo="${GGUF_REPO:-mistralai/Ministral-3-8B-Instruct-2512-GGUF}"
    local file="${GGUF_FILE:-Ministral-3-8B-Instruct-2512-Q4_K_M.gguf}"
    dl "https://huggingface.co/$repo/resolve/main/$file" "$MODELS/gguf/$file"
}

case "$TIER" in
    core)  fetch_core ;;
    brain) fetch_brain ;;
    all)   fetch_core; fetch_brain ;;
    *)     echo "usage: $0 {core|brain|all}"; exit 1 ;;
esac

echo
echo "== models/ =="
du -sh "$MODELS"/* 2>/dev/null || true
