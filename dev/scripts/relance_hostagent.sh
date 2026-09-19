#!/usr/bin/env bash
# Relance officielle du host-agent — carte figée 19 sept
# (Granite 4.2 3B / Whisper large-v3 / Magpie Sofia CUDA).
# Remplace /tmp/relance_hostagent.sh de dégustation.
# Jetons d'outils : lus de .env.local (jamais affichés).
# Modèles : lus de carte_figee.env (aucun secret).
#
# Ce fichier doit rester en fins de ligne UNIX.
set -eu
cd /workspace

lire_fichier() {
  # Ne source jamais : une valeur avec espaces ne doit pas devenir du shell.
  # tr retire un \r Windows collé à la valeur.
  grep -E "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\015' || true
}

lire_env_local() { lire_fichier "$1" .env.local; }
lire_carte() { lire_fichier "$1" /workspace/dev/scripts/carte_figee.env; }

BRAIN_API_KEY="$(lire_env_local BRAIN_API_KEY)"
SEARXNG_URL="$(lire_env_local SEARXNG_URL)"
TAVILY_API_KEY="$(lire_env_local TAVILY_API_KEY)"
BRAVE_API_KEY="$(lire_env_local BRAVE_API_KEY)"
EXA_API_KEY="$(lire_env_local EXA_API_KEY)"
JINA_API_KEY="$(lire_env_local JINA_API_KEY)"
SERPER_API_KEY="$(lire_env_local SERPER_API_KEY)"
CODEX_BRIDGE_URL="$(lire_env_local CODEX_BRIDGE_URL)"
CODEX_BRIDGE_URL="${CODEX_BRIDGE_URL:-http://host.docker.internal:8765/ask}"
CODEX_BRIDGE_TOKEN="$(lire_env_local CODEX_BRIDGE_TOKEN)"
CLI_BRIDGE_URL="$(lire_env_local CLI_BRIDGE_URL)"
CLI_BRIDGE_URL="${CLI_BRIDGE_URL:-http://host.docker.internal:8766/ask}"
CLI_BRIDGE_TOKEN="$(lire_env_local CLI_BRIDGE_TOKEN)"
MUSE_BRIDGE_URL="$(lire_env_local MUSE_BRIDGE_URL)"
export BRAIN_API_KEY SEARXNG_URL TAVILY_API_KEY
export BRAVE_API_KEY EXA_API_KEY JINA_API_KEY SERPER_API_KEY
export CODEX_BRIDGE_URL CODEX_BRIDGE_TOKEN
export CLI_BRIDGE_URL CLI_BRIDGE_TOKEN MUSE_BRIDGE_URL

export HF_HOME=/workspace/models/hf-cache
export HF_HUB_OFFLINE=1
export BRAIN_REFLEX_ANSWERS="${BRAIN_REFLEX_ANSWERS_FORCE:-1}"

# Carte figée. *_FORCE écrase une clé sans retoucher le fichier.
export BRAIN_SERVICE="${BRAIN_SERVICE_FORCE:-$(lire_carte BRAIN_SERVICE)}"
export BRAIN_MODEL="${BRAIN_MODEL_FORCE:-$(lire_carte BRAIN_MODEL)}"
export BRAIN_MODEL_LOCAL="${BRAIN_MODEL_LOCAL_FORCE:-$(lire_carte BRAIN_MODEL_LOCAL)}"
export MODEL="${MODEL_FORCE:-$(lire_carte MODEL)}"
export EARS_BACKEND="${EARS_BACKEND_FORCE:-$(lire_carte EARS_BACKEND)}"
export EARS_MODEL="${EARS_MODEL_FORCE:-$(lire_carte EARS_MODEL)}"
export EARS_LANGUAGE="${EARS_LANGUAGE_FORCE:-$(lire_carte EARS_LANGUAGE)}"
export EARS_DEVICE="${EARS_DEVICE_FORCE:-$(lire_carte EARS_DEVICE)}"
export EARS_COMPUTE_TYPE="${EARS_COMPUTE_TYPE_FORCE:-$(lire_carte EARS_COMPUTE_TYPE)}"
export EARS_HOTWORDS="${EARS_HOTWORDS_FORCE:-$(lire_carte EARS_HOTWORDS)}"
export MOUTH_BACKEND="${MOUTH_BACKEND_FORCE:-$(lire_carte MOUTH_BACKEND)}"
export MOUTH_VOICE_NAME="${MOUTH_VOICE_NAME_FORCE:-$(lire_carte MOUTH_VOICE_NAME)}"
export MOUTH_LANGUAGE="${MOUTH_LANGUAGE_FORCE:-$(lire_carte MOUTH_LANGUAGE)}"
export MOUTH_DEVICE="${MOUTH_DEVICE_FORCE:-$(lire_carte MOUTH_DEVICE)}"

echo "carte figee: brain=$BRAIN_SERVICE model=$(basename "$MODEL") ears=$EARS_BACKEND/$EARS_MODEL mouth=$MOUTH_BACKEND/$MOUTH_VOICE_NAME/$MOUTH_DEVICE"
echo "cle brain de ${#BRAIN_API_KEY} caracteres"
echo "config outils: searxng=$([ -n "$SEARXNG_URL" ] && echo oui || echo non) tavily=$([ -n "$TAVILY_API_KEY" ] && echo oui || echo non) codex=$([ -n "$CODEX_BRIDGE_TOKEN" ] && echo oui || echo non) claude=$([ -n "$CLI_BRIDGE_TOKEN" ] && echo oui || echo non) muse=$([ -n "$MUSE_BRIDGE_URL" ] && echo oui || echo non)"

hostagent_pids() {
  ps -eo pid=,args= | awk '
    /[p]ython([0-9.]+)?[[:space:]].*dev\/scripts\/serve_hostagent\.py/ { print $1 }
  '
}

anciens="$(hostagent_pids)"
if [ -n "$anciens" ]; then
  echo "TERM host-agent: $anciens"
  # word split volontaire : un pid par ligne
  # shellcheck disable=SC2086
  kill -TERM $anciens 2>/dev/null || true
  i=0
  while [ "$i" -lt 20 ]; do
    restants="$(hostagent_pids)"
    if [ -z "$restants" ]; then
      break
    fi
    sleep 0.5
    i=$((i + 1))
  done
  restants="$(hostagent_pids)"
  if [ -n "$restants" ]; then
    echo "KILL host-agent: $restants"
    # shellcheck disable=SC2086
    kill -KILL $restants 2>/dev/null || true
    j=0
    while [ "$j" -lt 10 ]; do
      if [ -z "$(hostagent_pids)" ]; then
        break
      fi
      sleep 0.2
      j=$((j + 1))
    done
  fi
fi

nohup python dev/scripts/serve_hostagent.py > /tmp/hostagent.log 2>&1 &
nouveau=$!
echo "host-agent relance, pid $nouveau"

ok=0
i=0
while [ "$i" -lt 180 ]; do
  if ! kill -0 "$nouveau" 2>/dev/null; then
    echo "host-agent mort pendant le demarrage (pid $nouveau)"
    cat /tmp/hostagent.log || true
    exit 1
  fi
  if grep -q 'écoute sur 0.0.0.0:8001' /tmp/hostagent.log 2>/dev/null; then
    ok=1
    break
  fi
  sleep 1
  i=$((i + 1))
done
if [ "$ok" -ne 1 ]; then
  echo "timeout: pas d'écoute sur 0.0.0.0:8001 (pid $nouveau)"
  cat /tmp/hostagent.log || true
  exit 1
fi
echo "host-agent pret, pid $nouveau"
