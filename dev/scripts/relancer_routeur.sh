#!/usr/bin/env bash
# Relance le host-agent avec le routeur, sans sourcer .env.local en entier.
# Seule la cle distante est lue du fichier ; l'option 2 est posee explicitement
# ci-dessous pour ne pas heriter d'un ancien environnement du conteneur.
#
# Ce fichier doit rester en fins de ligne UNIX. Ecrit depuis Windows sans
# precaution il finit en CRLF, et bash refuse alors la premiere option qu'il lit.
set -eu
cd /workspace

# Le tr n'est pas decoratif : .env.local est edite sous Windows, ses lignes
# finissent en CRLF, et le retour chariot reste colle a la cle. L'en-tete
# Authorization devient alors illegal et les DEUX voies du routeur tombent, la
# locale comme la distante. Symptome : Illegal header value sur le Bearer.
lire_env_local() {
  # Ne source jamais .env.local : une valeur avec espaces ou metacaracteres ne
  # doit pas devenir du shell. Une cle absente vaut vide et ne casse pas set -e.
  grep -E "^$1=" .env.local 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\015' || true
}

BRAIN_API_KEY="$(lire_env_local BRAIN_API_KEY)"
SEARXNG_URL="$(lire_env_local SEARXNG_URL)"
TAVILY_API_KEY="$(lire_env_local TAVILY_API_KEY)"
CODEX_BRIDGE_URL="$(lire_env_local CODEX_BRIDGE_URL)"
CODEX_BRIDGE_URL="${CODEX_BRIDGE_URL:-http://host.docker.internal:8765/ask}"
CODEX_BRIDGE_TOKEN="$(lire_env_local CODEX_BRIDGE_TOKEN)"
CLI_BRIDGE_URL="$(lire_env_local CLI_BRIDGE_URL)"
CLI_BRIDGE_URL="${CLI_BRIDGE_URL:-http://host.docker.internal:8766/ask}"
CLI_BRIDGE_TOKEN="$(lire_env_local CLI_BRIDGE_TOKEN)"
MUSE_BRIDGE_URL="$(lire_env_local MUSE_BRIDGE_URL)"
export BRAIN_API_KEY SEARXNG_URL TAVILY_API_KEY
export CODEX_BRIDGE_URL CODEX_BRIDGE_TOKEN
export CLI_BRIDGE_URL CLI_BRIDGE_TOKEN MUSE_BRIDGE_URL
export BRAIN_SERVICE=router
export BRAIN_API_ENDPOINT=https://api.commandcode.ai/provider/v1/chat/completions
export BRAIN_MODEL=MiniMaxAI/MiniMax-M3
export BRAIN_MODEL_LOCAL=mother-local

# Option 2 (13 septembre) : Qwen3-ASR 0.6B en 4 bits sur CUDA. Le cache est
# monte par docker-compose ; aucun telechargement reseau au demarrage.
export HF_HOME=/workspace/models/hf-cache
export HF_HUB_OFFLINE=1
export EARS_BACKEND=qwen3
export EARS_MODEL=0.6B
export EARS_DEVICE=cuda
export EARS_COMPUTE_TYPE=q4

# Pocket TTS FR estelle + aurora (13 sept, soir). Piper siwis/upmc/tom
# rejetes. 0 VRAM : inference CPU. MOUTH_*_FORCE ecrase le defaut sans
# heriter de l env compose. Repli Piper tom+aurora :
# docker exec -e MOUTH_BACKEND_FORCE=piper \
#   -e MOUTH_VOICE_FORCE=/workspace/models/piper/fr_FR-tom-medium.onnx \
#   -e MOUTH_PROFILE_FORCE=aurora \
#   mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
export BRAIN_REFLEX_ANSWERS="${BRAIN_REFLEX_ANSWERS_FORCE:-1}"
export MOUTH_BACKEND="${MOUTH_BACKEND_FORCE:-supertonic}"
export MOUTH_STYLE="${MOUTH_STYLE_FORCE:-F5}"
export MOUTH_SPEED="${MOUTH_SPEED_FORCE:-0.88}"
export MOUTH_VOICE_NAME="${MOUTH_VOICE_NAME_FORCE:-estelle}"
export MOUTH_LANGUAGE="${MOUTH_LANGUAGE_FORCE:-french_24l}"
export MOUTH_DEVICE="${MOUTH_DEVICE_FORCE:-cpu}"
export MOUTH_PROFILE="${MOUTH_PROFILE_FORCE:-aurora}"
export MOUTH_OUTPUT_GAIN_DB="${MOUTH_OUTPUT_GAIN_DB_FORCE:-3}"
export MOUTH_VOICE="${MOUTH_VOICE_FORCE:-/workspace/models/piper/fr_FR-tom-medium.onnx}"

echo "cle brain de ${#BRAIN_API_KEY} caracteres, routeur arme"
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
