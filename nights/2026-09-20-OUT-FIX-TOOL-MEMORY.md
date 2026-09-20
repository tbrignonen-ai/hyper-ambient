---
date: 2026-09-20
heure: ~15:20 Europe/Paris
type: out
lane: FIX-TOOL-MEMORY
complexity: complex
notify: OG
cible: OG (puis OG → OC)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-FIX-TOOL-MEMORY]]"]
---

# OUT — FIX tool memory + 2 tools/turn

Thomas reprend les tests live. Patch minimal, Presence UI non touchée, rien purgé.

## Bugs

1. Tour suivant : le modèle dit « pas de texte Codex » — `_historique` ne gardait que le texte parlé (`MEMOIRE_MESSAGES=6`).
2. `max_tool_calls=1` interdisait Codex puis Claude dans le même tour.

## Changé

### `dev/scripts/serve_hostagent.py`

- Buffer `_dernier_outils` : liste `{name, content}` après un tour avec outils. Troncature `MAX_TOOL_CONTENT_CHARS` (1200). Pas d’amorces TTS.
- Au tour suivant, `_historique_pour_modele()` injecte avant le prompt user :
  `[résultat outil ask_codex] …`
  Le buffer ne compte pas dans `MEMOIRE_MESSAGES` (reste 6).
- `run_tool_loop(..., max_tool_calls=2)`.

### `src/brain/tool_loop.py`

- Le chunk `phase=result|denied` porte `content` **hors** `delta` (MOUTH ne parle toujours que les deltas non vides).
- `MAX_TOOL_CALLS_PER_ITERATION` reste **1** (un outil par aller-retour modèle).
- Défaut `MAX_TOOL_CALLS_PER_TURN` reste **1** ; seul l’appel vocal passe 2.

## Preuve (exécutée)

```
$ python -m pytest -q dev/tests/test_tool_loop.py dev/tests/test_tool_loop_cap.py \
    dev/tests/test_tool_loop_edges.py dev/tests/test_tool_loop_h_edges.py \
    dev/tests/test_tool_loop_more_edges.py
146 passed in 0.41s

$ docker exec mother-core-dev bash -lc 'cd /workspace && python -m pytest -q \
    dev/tests/test_outils_voix.py dev/tests/test_tool_loop.py \
    dev/tests/test_tool_loop_h_edges.py::test_max_tool_calls_defaut_est_un'
64 passed in 0.91s
```

## Retest manuel (Thomas)

1. Demander une info via Codex.
2. Demander à Claude de contre-analyser le résultat Codex (même tour ou tour suivant).
3. Log `/tmp/hostagent.log` : `OUTIL ask_codex` puis `ask_claude`, sans « pas de texte Codex ».

## Relance

```
$ docker exec mother-core-dev bash -lc '/workspace/dev/scripts/relance_hostagent.sh'
carte figee: brain=llamacpp model=granite-4.2-3b-Q4_K_M.gguf ears=faster-whisper/large-v3 mouth=magpie/Sofia/cuda
langue: fr
config outils: searxng=oui tavily=non codex=oui claude=oui muse=non
TERM host-agent: 2559
host-agent relance, pid 2948
host-agent pret, pid 2948

LANG  : fr
OUTILS: ask_claude, ask_codex, calculer, web_search — porte en mode auto
écoute sur 0.0.0.0:8001 /hostagent
```
