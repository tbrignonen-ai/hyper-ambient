#!/usr/bin/env bash
# Fetch hyper-ambient model weights into /workspace/models (host-mounted, survives rebuilds).
#
# Tiers:
#   ./fetch_models.sh core   -> VAD + Piper FR voices + whisper turbo & large-v3  (~5 GB)
#   ./fetch_models.sh brain  -> Granite 4.2 3B GGUF for llama-server              (~2.2 GB)
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

    echo "== MOUTH: Piper French voices (tom = MOUTH_VOICE default / fallback, siwis) =="
    local piper="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR"
    dl "$piper/tom/medium/fr_FR-tom-medium.onnx"        "$MODELS/piper/fr_FR-tom-medium.onnx"
    dl "$piper/tom/medium/fr_FR-tom-medium.onnx.json"   "$MODELS/piper/fr_FR-tom-medium.onnx.json"
    dl "$piper/siwis/medium/fr_FR-siwis-medium.onnx"        "$MODELS/piper/fr_FR-siwis-medium.onnx"
    dl "$piper/siwis/medium/fr_FR-siwis-medium.onnx.json"   "$MODELS/piper/fr_FR-siwis-medium.onnx.json"

    echo "== EARS: whisper.cpp GGUF (large-v3-turbo q5_0) =="
    dl "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin" \
       "$MODELS/whisper/ggml-large-v3-turbo-q5_0.bin"

    echo "== EARS: faster-whisper (CTranslate2) =="
    python3 - <<'PY'
from faster_whisper import WhisperModel
# downloads into HF_HOME=/workspace/models/hf-cache
WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
print("  = faster-whisper large-v3-turbo cached")
# Carte figée : EARS_MODEL=large-v3. Le host-agent tourne en HF_HUB_OFFLINE=1,
# il ne télécharge rien lui-même : sans ce cache, il s'arrête au boot.
WhisperModel("large-v3", device="cpu", compute_type="int8")
print("  = faster-whisper large-v3 cached")
PY
}

fetch_brain() {
    echo "== BRAIN: local GGUF for llama-server =="
    # Carte figée 19 sept : Granite 4.2 3B Q4_K_M (~2.2 GB), le fichier que
    # serve_llama.sh et carte_figee.env attendent. L'ancien défaut Ministral 8B
    # (~4.9 GB) sortait du budget VRAM et a déjà fait tomber Docker (8 Go RAM).
    # Autre modèle : GGUF_REPO=… GGUF_FILE=… ./fetch_models.sh brain
    local repo="${GGUF_REPO:-ibm-granite/granite-4.2-3b-GGUF}"
    local file="${GGUF_FILE:-granite-4.2-3b-Q4_K_M.gguf}"
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
