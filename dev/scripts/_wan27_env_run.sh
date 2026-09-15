#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/d/BGB Training/MOTHER-dev"
KEY=$(grep -E '^DASHSCOPE_API_KEY=' .env.local | head -1 | cut -d= -f2- | tr -d '\r\n')
export DASHSCOPE_API_KEY="$KEY"
export DASHSCOPE_REGION=singapore
bash dev/scripts/run_wan27_oneshot.sh
