---
date: 2026-09-17
heure: ~20:25 Europe/Paris
type: harnais-smoke
auteur: OC
---

# Harnais smoke 17 sept

## Claude relaunch
- Old PID **20212** killed
- New MOTHER-LEAD PID: **33040** (start ~20:21)
- Prompt inclut HARNAIS-ANSWERS + MUSE-HARNAIS + OUT PLAN-TECH

## Smoke table

| Step | Status | Detail |
|---|---|---|
| Codex CLI open | OK | opened C:\Users\thoma\AppData\Local\nodejs\codex.ps1 |
| Headless Codex :8765 | SKIP | listen=False ; token_present=False — pont DOWN, pas de POST |
| Headless Claude :8766 | SKIP | listen=False ; token_present=False — pont DOWN, pas de POST |
| Hermes appel only | FAIL | :8080 open, /health fail — zero config |

## Locked respecté
- Codex = ouvrir CLI
- Headless tenté : ponts 8765/8766 **DOWN** → SKIP (pas de bluff)
- Hermes : **aucune configuration** / SAWB non touché
- Workspace = MOTHER-dev

## Blockers
1. Ponts Codex/Claude non allumés (8765/8766)
2. Hermes URL health à confirmer si SKIP
3. PLAN-TECH encore à produire par Claude PID 33040

## Next
- Allumer ponts (sans toucher Hermes config) puis re-PONG
- Claude → `2026-09-17-CLAUDE-PLAN-TECH.md`