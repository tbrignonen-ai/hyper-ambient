#!/bin/sh
# Lanceur DEV macOS arm64 : superviseur puis Presence.

set -eu

RACINE="$(cd "$(dirname "$0")/../.." && pwd)"

PYTHONPATH="$RACINE:$RACINE/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
INTERPRETEUR="${HYPERAMBIENT_PYTHON:-python3}"
CONFIG="${MOTHER_MAC_CONFIG:-$RACINE/packaging/macos/mac-16g.env.example}"
exec "$INTERPRETEUR" -u "$RACINE/dev/scripts/supervise_macos.py" --config "$CONFIG" "$@"
