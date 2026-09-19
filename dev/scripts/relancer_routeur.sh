#!/usr/bin/env bash
# 19 sept : la carte est figée (Granite / Whisper large-v3 / Magpie Sofia).
# L'ancien lanceur posait router + Qwen3 + Supertonic et écrasait la dégustation.
# Délègue au lanceur officiel. Fins de ligne UNIX obligatoires.
set -eu
exec "$(cd "$(dirname "$0")" && pwd)/relance_hostagent.sh" "$@"
