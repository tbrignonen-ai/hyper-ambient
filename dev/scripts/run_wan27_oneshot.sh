#!/usr/bin/env bash
# run_wan27_oneshot.sh — genere les 2 VRAIES images wan2.7-image (DashScope, 0 VRAM).
# La cle ne transite QUE par l'environnement : rien n'est ecrit sur disque.
#
# Usage recommande (pas de trace de la cle dans l'historique) :
#   DASHSCOPE_API_KEY=sk-... DASHSCOPE_REGION=singapore bash dev/scripts/run_wan27_oneshot.sh
#
# Variante (cle en argument — deconseillee : visible dans l'historique) :
#   bash dev/scripts/run_wan27_oneshot.sh sk-... [singapore|beijing]
#
# Obtenir une cle : https://help.aliyun.com/en/model-studio/get-api-key
#   Europe -> compte Singapore (host dashscope-intl.aliyuncs.com), REGION=singapore.
#   Quota gratuit 50 images/90 j -> compte Beijing, REGION=beijing.
#   Beijing et Singapore ne se melangent pas (cle + host distincts).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [ $# -ge 1 ]; then
  export DASHSCOPE_API_KEY="$1"
fi
export DASHSCOPE_REGION="${2:-${DASHSCOPE_REGION:-singapore}}"

if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
  echo "STOP: DASHSCOPE_API_KEY absent." >&2
  echo "  DASHSCOPE_API_KEY=sk-... DASHSCOPE_REGION=singapore bash dev/scripts/run_wan27_oneshot.sh" >&2
  exit 2
fi
case "$DASHSCOPE_REGION" in
  singapore|beijing) ;;
  *) echo "region inconnue: $DASHSCOPE_REGION (singapore|beijing)" >&2; exit 2 ;;
esac

python3 "$REPO/dev/scripts/gen_wan27_images.py"
echo "--- verif ---"
ls -la "$REPO/data/out/images-wan27/"
python3 -c "import json,pathlib; [print(p.name, (lambda d: (d.get('model'), d.get('region'), d.get('request_id')))(json.loads(pathlib.Path('data/out/images-wan27/'+p.with_suffix('.json').name).read_text())) if p.with_suffix('.json').exists() else None) for p in sorted(pathlib.Path('data/out/images-wan27').glob('*.png'))]"
