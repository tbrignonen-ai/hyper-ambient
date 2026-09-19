---
date: 2026-09-19
heure: ~11:50 Europe/Paris
type: orga-session
auteur: OC
deadline: dossier + soutenance (lundi / 25)
---

# ORGA SESSION 19 sept — Hyper Ambient

## Mode
1. **Flotte = orga tâches** (ce fichier + OG kanban + WS veille)
2. **Ensuite OC seul** parle aux harnais Claude / Codex / Cursor (économiser Grok Bot)
3. **Muse OUT** — Codex reprend sa place (quota OK, reset utilisable)

## Rôles
| Qui | Fait | Ne fait pas |
|---|---|---|
| **Thomas** | Itère avec Claude ; tests ; remplit cases dossier BGB | Micro-dispatch agents |
| **Claude Code** | Planning + itération Thomas ; interlocuteur tests | Code — délègue à Cursor |
| **Cursor** (Grok 4.6 xhigh fast) | Tout le code assigné | Décisions produit |
| **Codex** | Overflow / lanes Muse ; backup 1 lane | 4e lane parallèle libre |
| **OC** | Horloge, stack, Obsidian, pont unique harnais | How produit ; fan-out Grok |
| **OG** | Kanban / mémoire | Exec |
| **WS** | RNCP + JeV veille | Exec |
| **Muse** | **OUT** | — |

## Ordre journée
| # | Tâche | Owner orga | Done quand |
|---|---|---|---|
| 0 | Orga flotte + Obsidian (ce fichier) | OC+OG | KANBAN + ORGA |
| 1 | Rallumer stack + **vérif 3 harnais** (Claude, Codex, Cursor) | OC | 3× PONG / session OK |
| 2 | Claude plan + itération Thomas (solution finale) | Claude↔Thomas | PLAN-TECH-19 + go Cursor |
| 3 | Cursor exécute lanes code disjointes | Cursor | OUTs code |
| 4 | Codex overflow si besoin | Codex | OUT si assigné |
| 5 | Dossier BGB : suggestions cases + **annexe 15–30 p.** | Claude plan → Cursor/Codex rédige | ANNEXE + SUGGESTIONS-CASES |
| 6 | Piste JeV (petit modèle déterministe) | WS veille → Claude tranche | NOTE-JEV |

## Docs BGB (officiels, collés 19 sept)
- `D:\BGB Training\BGB_BC02_Dossier_technique_a_completer.docx`
- `D:\BGB Training\BGB_BC02_Preparer_votre_soutenance.docx`
Thomas remplit les cases. Flotte = suggestions + annexe technique (certif RNCP41889 BC02, angle **automatisation IA** même si cœur = dev: semi-auto, ex-crons nuit, Obsidian, GitHub, onboarding LLM, feedback cron, harnais outils).

## Ambition à mettre en avant (si vrai / prouvé)
- Sans les mains
- Onboarding assisté modèle
- Hybride local/distant configurable
- Harnais outils (ordres + lecture réponses), pas que conversationnel
- Agentique locale → gros modèle distant qui bosse
- Feedback utilisateur automatisé (bouton app + GitHub public, lu 1×/jour)

## Scope produit
FR only · Windows only · app clé-en-main (télécharge modèles) · public tech/IA/Jarvis multi-harnais

## Roadmap
Mac · EN/ES · Hyper-Ambient-XL (~20 Go VRAM)

## Interdits
Muse ; secrets chat/commit ; docker recreate ; config Hermes/SAWB ; OC fan-out technique après orga

## Next OC (après ack OG/WS)
→ Start stack + PONG Claude/Codex/Cursor