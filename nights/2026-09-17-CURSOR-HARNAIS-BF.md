---
date: 2026-09-17
heure: ~21:22 Europe/Paris
type: out
auteur: Cursor (BF Thomas)
cible: Thomas + OC / Grok bot
statut: pont Codex câblé — PTT « Bonjour » = boucle d'outils (bug)
---

# Harnais BF — Codex (17 sept)

## Décisions
- Voix = HA seulement. Codex = **texte** via le cerveau local, pas de micro vers Codex.
- Jeton pont = **local**, défini par nous, pas le login Codex (déjà auth `gpt-5.6-terra`).
- Hermes / SAWB / docker recreate : **non touchés**.
- Claude `:8766` : pas allumé ce soir.

## Preuves
| Étape | Preuve |
|---|---|
| CLI Codex | `codex exec` cwd `MOTHER-dev` → **PONG** |
| Pont `:8765` | listen ; POST sans jeton **401** ; avec jeton **200 PONG** |
| `.env.local` | `CODEX_BRIDGE_TOKEN` posé (64 car., identique au pont) — pas dans le chat |
| Routeur | `relancer_routeur.sh` → pid 798 |
| Registre | **`OUTILS: ask_codex, web_search`** |

## Tours voix lus (preuves log)

**Avant jeton** (Luciole seule, `OUTILS: web_search`) :
1. « test de bois » (ASR) → réponse locale
2. « l'ecole » (ASR) → réponse locale
3. « tu m'entends » → oui
4. « connecté à CODex » → elle ne connaît pas Codex (normal : outil absent)

**Après jeton** (`OUTILS: ask_codex, web_search`) :
- **1 seul EARS** : « Bonjour. » classé **REFLEXE** (618 ms)
- Puis **tempête d'outils** (30+ appels, encore en cours au wrap) : `web_search` météo/trains/Mars/Python… + `ask_codex` ×6, tous HTTP 200
- Bug log : `tool_call web_search: arguments illisibles` (JSON tronqué)
- **Aucun** `BRAIN : "…"` final — elle n'a pas refermé le tour, elle enchaîne les annonces (« Je cherche ça sur le web. » / « Je demande à Codex… »)

## Bugs (pas bluff)
1. **Luciole 8B + schémas d'outils** : un « Bonjour » déclenche la boucle. `max_iterations=3` n'empêche pas N appels **par** itération. GATE `auto`.
2. Le réflexe local **injecte quand même** `tools=` — contraire à l'intention « un tour sans outil reste le tour d'avant ».
3. ASR FR fragile (bois / école).
4. Pont Codex **OK** (200) — le câble tient ; c'est le **cerveau local qui spam**.

## Next (pas ce lot Cursor — brain interdit ce soir)
- Couper / interrompre le PTT si ça tourne encore.
- Claude/prochain : outils **seulement en ESCALADE**, 1 outil/tour, JSON d'args borné.
- Ne pas relancer le routeur pour « réparer » pendant que le tour court.

## Pas fait
- Pont Claude 8766
- Hermes health
- Push GitHub
- Fix tool-loop (fichier brain — hors périmètre BF)
