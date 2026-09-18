---
date: 2026-09-15
type: wrap
auteur: OG
heure: ~21:50 PT
related:
  - "[[2026-09-15-WRAP-CLAUDE]]"
  - "[[2026-09-15-MUSE-OUTILS-PONTS]]"
  - "[[2026-09-15-CURSOR-DESIGN-ONBOARDING]]"
  - "[[2026-09-14-CODEX-ANALYSE-SEANCE]]"
---

# WRAP-SEANCE — 15 sept (DEV forcé → soutenance 25)

## Stack à la fermeture
| Élément | État |
|---|---|
| mother-core-dev | **Exited** (docker stop / 137) — pas recreate |
| :8090 / :8001 | down |
| Presence | off |
| searxng | Exited |
| Muse / Cursor agent jobs | arrêtés |
| **Cursor APP** | **gardé** |
| **Hermes / SAWB** | **gardés** (0 GPU MOTHER touché) |
| VRAM wrap | ~2.4 Go |

## Tracks

### Claude (lead voix) — [[2026-09-15-WRAP-CLAUDE]]
- Cerveau : **Luciole-8B** remis (MiniCPM5 écarté pour le live) ; `enable_thinking:false` ; VRAM séance ~8.4 Go ; load ~5m30
- Voix : **Supertonic-3 F5 @ 0.88** défaut (+3 dB) ; F3 finaliste à départager ; Pocket/Piper écartés pour le goût Thomas (« Aurora Ray »)
- Interruption bouton : **OK** (tests verts)
- Routeur : `BRAIN_REFLEX_ANSWERS=1` (local répond souvent)
- **Git poussé** `nuit/2026-08-27` (`3f4f092`..`8cac524`)

### Cursor (design) — [[2026-09-15-CURSOR-DESIGN-ONBOARDING]]
- Icône éclair distant (badge + overlay escalade)
- Onboarding Presence 3 étapes skippable + a11y ; 16 tests verts
- Pas de push Cursor (intégré via Claude/commits Presence)

### Muse (ponts outils) — [[2026-09-15-MUSE-OUTILS-PONTS]]
- 137 tests outils/ponts verts ; `ask_muse` health OK ; contrats Codex:8765 / Claude:8766 relus
- Hermes : `ask_hermes` toujours interdit à la voix ; SAWB intact
- **Bloqué sandbox** : pas démarrer 8765/8766 ni registre live (relance host-agent interdite pendant tests voix) ; 3 lignes `.env.local` manquantes (jetons + `MUSE_BRIDGE_URL`)

## Ouvert — prochaine séance (ordre)
1. **Appel distant ne part plus** — mesurer classifieur Luciole (5 questions dures) avant patch
2. Départager **F5 vs F3**, figer
3. Annulation génération côté serveur
4. Reconnexion Presence après relance host-agent
5. Latence 1er son Supertonic ~3 s
6. Ponts outils : Windows bridges → Muse WSL → `.env.local` → relance ciblée → 1 PTT/outil
7. Nouvelles voix FR hors Pocket/Supertonic

## Org
- ASSIGN/BRIEF OG écrits ; OC = horloge ; Claude session unique interactive
- Monitor séance 14 (10min) : à supprimer / rester paused