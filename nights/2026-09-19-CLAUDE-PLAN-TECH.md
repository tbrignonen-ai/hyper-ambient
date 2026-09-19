---
date: 2026-09-19
type: plan-tech
auteur: Claude (MOTHER-PLAN-19, planner — aucun code)
related: ["[[2026-09-19-ORGA-SESSION]]", "[[2026-09-19-KANBAN]]", "[[2026-09-19-BRIEF-CURSOR]]", "[[2026-09-19-BRIEF-CODEX]]", "[[2026-09-19-SUGGESTIONS-CASES-BGB]]", "[[2026-09-19-NOTE-JEV]]"]
---

# PLAN TECH 19 — piloté par la soutenance

## ÉTAT 19/09 ~18h50 (mise à jour Claude)
| Lane | État |
|---|---|
| C1 outils/config | ✅ correctif + 37 tests ; **preuve live faite** (boot `OUTILS: ask_claude, ask_codex, web_search`) |
| C2 alerte + reprise | ✅ code + 7 tests ; coupure réelle du pont à faire en répétition de démo |
| X1 annexe | 🟡 brouillon 344 lignes, à relire |
| Carte des modèles | cerveau **Granite 4.2 3B** ✅ · voix **Magpie Sofia** ✅ (branchée C9, 4,5 s avant 1er son en CPU → passage GPU à faire) · oreille ⏳ (Whisper large-v3 / Parakeet / Canary en banc) |
| C3–C8 (JeV, web multi, TTS distant, onboarding, natif Windows, EN) | ⏸ après carte figée — orchestration Grok (`2026-09-19-CLAUDE-POUR-GROK.md`) |
| Copie modèles retenus → SSD E: | ⏸ après carte figée |
Défauts relevés en dégustation : voir `2026-09-19-DEGUSTATION-CERVEAUX-RESULTATS.md`.


## Principe directeur
Le guide de soutenance BGB impose **deux démonstrations en direct** : (1) une **alerte déclenchée avec
sa reprise**, (2) un **service tiers en fonctionnement**. Tout le code d'aujourd'hui sert ces deux
démos et rien d'autre. Le reste (voix, tool-loop PR, UI cosmétique) passe après ou pas du tout avant lundi.

Constat live (OC) : le host-agent boote avec `OUTILS: aucun backend configure`
(`dev/scripts/serve_hostagent.py:396`). Le registre n'expose `ask_codex` / `ask_claude` / `web_search`
que si `CODEX_BRIDGE_TOKEN`, `CLI_BRIDGE_TOKEN`, `SEARXNG_URL` sont présents dans l'environnement du
processus (`construire_registre`, l. 102-160). Ponts :8765/:8766 UP → hypothèse de cause racine :
**les variables ne sont pas propagées au process host-agent** (lancement, `.env.local` CRLF déjà signalé le 18).
À confirmer par Cursor avant tout correctif. **Sans ça, pas de démo « service tiers ».**

## Ordre des lanes

| # | Lane | Owner | Fichiers possédés (disjoints) | Preuve attendue (OUT) |
|---|---|---|---|---|
| 1 | **C1 — Outils câblés** (service tiers démontrable) | Cursor | `dev/scripts/serve_hostagent.py`, `src/brain/tools*.py`, scripts de lancement host-agent, `dev/tests/test_tools*.py`, `dev/tests/test_outils_voix.py` | log boot `OUTILS: ask_codex, ask_claude, web_search…` + 1 tour vocal réel où MOTHER annonce « Je demande son analyse à Claude » et restitue la réponse → `2026-09-19-C1-OUTILS.md` |
| 2 | **C2 — Alerte + reprise visibles** | Cursor (après C1, ou en parallèle si C1 bloqué) | `native/presence/*`, `dev/tests/test_presence_*.py`, `workers/night_health_vault_note/*`, `resources/bpmn/*` | pont coupé volontairement → alerte **à l'écran + dite à voix haute + note Obsidian**, puis reprise → retour vert. Captures + log → `2026-09-19-C2-ALERTE.md` |
| 3 | **X1 — Annexe technique 15–30 p.** | Codex (overflow, docs seuls) | `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md` uniquement | brouillon complet, chaque affirmation sourcée (fichier:ligne, commit, note nights) |
| 4 | **Cadre cases dossier** | Claude (fait) → Thomas remplit | `nights/2026-09-19-SUGGESTIONS-CASES-BGB.md` | fichier livré |
| 5 | Itération Thomas / relecture annexe / filage démo | Claude ↔ Thomas | — | scénario chronométré < 14 min |
| — | Hors lundi | — | voix F5/F3, tool-loop PR, JeV | reporté (voir NOTE-JEV) |

Aucun recouvrement : Cursor ne touche pas `nights/ANNEXE`, Codex ne touche aucun fichier de code.
Si C1 et C2 tournent en parallèle, ce sont **deux runs Cursor sur des arbres de fichiers disjoints** (OK règle No Parallel Overwrite).

## Garde-fous (tous)
Pas de `docker compose up` / recreate · pas de config Hermes · aucun secret en clair (ni log, ni commit, ni OUT) ·
pas de commit sans accord Thomas · TDD : test rouge vu avant le correctif · « fait » = commande + sortie collée dans l'OUT.

## Ce que Thomas verra / entendra (critère de progrès)
- C1 : MOTHER **dit** qu'elle consulte Claude/Codex, puis répond avec leur analyse — changement audible.
- C2 : un bandeau d'alerte dans Presence + une phrase d'alerte parlée + le retour au vert — changement visible.

## Dossier BGB — articulation avec le code
- Démo « service tiers » (§11) = C1. Démo « alerte + reprise » (§10) = C2 + script `2026-09-18-SKU10-PANNE.md`.
- Tests §4 : les suites pytest existantes (T4/T5 techniques) + un test perf (latence premier son) + un contrôle accessibilité (contraste/clavier Presence, ou lecteur d'écran) — à mesurer, pas à inventer.
- **Risque n°1 du dossier** : la case « Plateformes no code/low code utilisées ». MOTHER est du code.
  Élément low-code réel du dépôt : **Camunda 8 / BPMN** (`resources/bpmn/night_health_vault_note.bpmn` + worker).
  Décision Thomas requise (voir SUGGESTIONS-CASES, § « À trancher »).
