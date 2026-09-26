#!/usr/bin/env bash
# MOUTH de la carte figée : Magpie TTS (voix Sofia) servi par NeMo-Speech.cpp.
#
# Pose, là où src/mouth/magpie_tts.py les cherche :
#   $MAGPIE_ROOT/bin/nemo-speech, $MAGPIE_ROOT/lib/   runtime NeMo-Speech.cpp
#   $MAGPIE_ROOT/models/                              Magpie + NanoCodec (GGUF) + tokenizer
#
# Aucun Python, aucun NeMo PyTorch : un binaire ggml et des poids vérifiés
# (taille + SHA-256 épinglés par `nemo-speech pull`). Idempotent.
#
#   bash dev/scripts/installer_magpie.sh            # dans mother-core-dev (CUDA)
#   MAGPIE_BACKEND=cpu bash dev/scripts/installer_magpie.sh
set -euo pipefail

ROOT="${MAGPIE_ROOT:-/workspace/models/tts-bench/magpie}"
VERSION="${NEMO_SPEECH_VERSION:-0.1.0}"
if [ -z "${MAGPIE_BACKEND:-}" ]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    MAGPIE_BACKEND=cuda
  else
    MAGPIE_BACKEND=cpu
  fi
fi

echo "== MOUTH: Magpie (NeMo-Speech.cpp $VERSION, $MAGPIE_BACKEND) -> $ROOT =="
mkdir -p "$ROOT/models"

# 1. Runtime. Le script d'installation est pris au tag de la version épinglée,
#    pas sur main ; il vérifie lui-même le SHA-256 de l'archive.
if [ -x "$ROOT/bin/nemo-speech" ] && \
   grep -q "^$VERSION .* $MAGPIE_BACKEND\$" "$ROOT/.nemo-speech-install" 2>/dev/null; then
  echo "  = nemo-speech $VERSION ($MAGPIE_BACKEND) déjà installé"
else
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL "https://raw.githubusercontent.com/NVIDIA/NeMo-Speech.cpp/v$VERSION/scripts/install.sh" \
    -o "$tmp/install.sh"
  sh "$tmp/install.sh" --version "$VERSION" --backend "$MAGPIE_BACKEND" --prefix "$ROOT"
fi

if [ "$MAGPIE_BACKEND" = cuda ] && [ ! -e "$ROOT/lib/libggml-cuda.so" ]; then
  echo "ERREUR : build CUDA sans lib/libggml-cuda.so — magpie_tts.py ne le reconnaîtrait pas." >&2
  exit 1
fi

export LD_LIBRARY_PATH="$ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$ROOT/bin/nemo-speech" --version

# 2. Poids. `pull magpie` prend aussi le tokenizer et le NanoCodec compagnon.
export NEMO_SPEECH_MODEL_DIR="$ROOT/models"
"$ROOT/bin/nemo-speech" pull magpie

# 3. Ce que magpie_tts.py doit trouver au démarrage.
magpie="$(find "$ROOT/models" -type f -iname '*magpie*.gguf' | head -1)"
codec="$(find "$ROOT/models" -type f -iname '*codec*.gguf' | head -1)"
[ -n "$magpie" ] || { echo "ERREUR : aucun GGUF Magpie sous $ROOT/models" >&2; exit 1; }
[ -n "$codec" ] || { echo "ERREUR : aucun GGUF NanoCodec sous $ROOT/models" >&2; exit 1; }
echo "  = magpie : ${magpie#"$ROOT"/}"
echo "  = codec  : ${codec#"$ROOT"/}"
echo "Magpie prêt."
