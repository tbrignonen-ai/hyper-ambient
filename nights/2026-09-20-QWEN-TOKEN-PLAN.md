---
date: 2026-09-20
heure: ~10:26 Europe/Paris
type: capacity
auteur: OG (+ WS + OC + Thomas)
---

# Qwen Code + Token Plan — capacity J-1

## CLI / endpoint
- CLI: `qwen` ; option `qwen serve --http-bridge`
- Auth Token Plan chez Thomas (**jamais** de clé ici)
- Base: `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`

## Trio LOCKED Thomas (pas 2× flash)
| Rôle | ID EXACT |
|---|---|
| DS flash volume/code overflow | `deepseek-v4-flash-0731` |
| Qwen flash volume docs/OUT | `qwen3.8-flash` |
| Qwen max (jugement léger / défaut fort) | `qwen3.8-max` |

Flags CLI: `qwen -y -m <ID> -p "…"`.  
Piège: `deepseek-v4-flash` ≠ `deepseek-v4-flash-0731`.

## Matrice
| Tache | Modèle |
|---|---|
| Volume docs / OUT / drafts | `qwen3.8-flash` |
| Overflow code rapide | `deepseek-v4-flash-0731` |
| Jugement Qwen plus fort | `qwen3.8-max` |
| Lead / démos | Claude |
| Code principal | Cursor |
| Overflow Codex | Codex |

## Pont
`native/qwenbridge` → **:8767** · défaut `qwen3.8-flash` · Bearer `$QWEN_BRIDGE_TOKEN` · Muse OUT.