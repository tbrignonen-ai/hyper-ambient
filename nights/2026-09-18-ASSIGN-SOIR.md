---
date: 2026-09-18
heure: ~20:49 Europe/Paris
type: assign-soir
auteur: OC
orga: [[2026-09-18-ORGA-BOUCLE]]
mode: boucle complète
intervention_thomas: go fait ; smoke ~10 min quand READY ; push fin de lot OK
---

# ASSIGN SOIR 18 sept — boucle technique

## Rôles
- **Claude** = lead technique (session UNIQUE `MOTHER-LEAD-18`)
- **Cursor** = code (lanes assignées par Claude)
- **Muse** = harnais / onboarding / ponts (assigné par Claude)
- **Codex** = backup d'**une** lane seulement si panne
- **OC** = horloge / stack / mirroirs / 1 nudge si stuck
- Thomas = smoke READY + fin

## Lanes (Claude ordonne + assigne)
| ID | Sujet | Owner défaut | OUT |
|---|---|---|---|
| L1 | Harnais voix↔Codex (+ Claude pont si temps) | Muse puis Cursor | `2026-09-18-HARNAIS.md` |
| L2 | Voix plus claire (feedback 17) | Claude → Cursor | `2026-09-18-VOIX.md` |
| L3 | UI Presence geste HA réel | Cursor | `2026-09-18-UI-HA.md` |
| L4 | SKU10 smoke + panne/reprise 1 page | Claude | `2026-09-18-SKU10-PANNE.md` |
| L5 | WRAP + PLAN + push GitHub | Claude fin | `2026-09-18-WRAP-SOIR.md` + push |

## Contraintes
FR only ; pas recreate docker ; Hermes 0 config / pas SAWB ; Occamy=SKU16 only pas load ; tool-loop déjà sur disque `d1c9f0d` ; pont Codex `:8765` existait 17 ; secrets pas commit.

## Claude — premières 20 min
1. Lis ORGA-BOUCLE + WRAP-SEANCE 17 + CURSOR-HARNAIS-BF + CLOUD-TOOLLOOP-PR1
2. Écris `2026-09-18-CLAUDE-PLAN-TECH.md` (ordre L1–L5, owners, preuves)
3. Écris `2026-09-18-BRIEF-CURSOR.md` + `2026-09-18-BRIEF-MUSE.md` (fichiers disjoints)
4. OC lancera Cursor/Muse dès que ces 2 briefs existent
5. READY smoke → fichier `2026-09-18-READY-SMOKE.md` quand L1(+L2 si possible) testables

## Push
Fin de lot autorisé (Thomas). Pas `.env.local`.