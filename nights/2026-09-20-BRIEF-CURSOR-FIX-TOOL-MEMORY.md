# BRIEF Cursor — FIX tool memory + 2 tools/turn — 20 sept 15:12
Complexité: complex → NOTIFY OG via account.py close
Objectif: Thomas reprend les tests live MAINTENANT.

## Bugs prouvés (logs mother-core /tmp/hostagent.log)
1. ask_codex OK puis ask_claude → `pont injoignable` (bridge était down — OC l'a relancé).
2. Tour suivant: modèle dit « pas de texte Codex » — `_historique` ne garde que le texte *parlé* (MEMOIRE_MESSAGES=6), pas le résultat outil.
3. `max_tool_calls=1` dans serve_hostagent → impossible Codex puis Claude dans le même tour.

## Patch demandé (minimal, prouvé)
Fichiers:
- `dev/scripts/serve_hostagent.py`
- éventuellement `src/brain/tool_loop.py` / `src/brain/tools.py`

### A — Persister les résultats outils pour le tour suivant
- Après un tour avec outils, stocker un buffer `_dernier_outils` (liste {name, content} tronqué ~800–1200 car, comme MAX_TOOL_CONTENT).
- Au tour suivant, injecter dans `historique` (ou system) un message du type:
  `[résultat outil ask_codex] …`
  avant le prompt user, pour que « contre-analyse Claude du résultat Codex » ait le contenu.
- Ne pas stocker les amorces TTS. Garder MEMOIRE_MESSAGES.

### B — Autoriser 2 outils / tour
- Passer `max_tool_calls=2` (appel `run_tool_loop` dans serve_hostagent) pour permettre enchaînement ask_codex → ask_claude dans un même tour si le modèle le demande.
- Garder MAX_TOOL_CALLS_PER_ITERATION=1 (un outil par aller-retour modèle), donc 2 itérations max déjà prévu.

### C — OUT
Écrire:
- `nights/2026-09-20-OUT-FIX-TOOL-MEMORY.md` (quoi changé, comment retester)
- `nights/2026-09-20-EXIT-FIX-TOOL-MEMORY.txt` (OK ou FAIL)

### Retest manuel (Thomas)
1. Demander une info via Codex.
2. Demander à Claude de contre-analyser le résultat Codex (même tour ou tour suivant).
3. Vérifier dans log: OUTIL ask_codex puis ask_claude sans « pas de texte Codex ».

Ne touche pas Presence UI. Ne purge rien. Relance host-agent via `relance_hostagent.sh` après patch.