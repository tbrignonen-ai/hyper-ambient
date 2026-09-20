---
date: 2026-09-20
heure: ~11:10 Europe/Paris
type: out
lane: TAQUET-WIRE2b
complexity: simple
notify: OC
cible: OC + ponts
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-19-WIRE-OUT]]", "[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-19-C8-EN-OUT]]", "[[2026-09-20-TAQUET-1H]]"]
deadline: 11:35 Europe/Paris
---

# TAQUET-WIRE2 OUT — branchements host-agent + EN 0.1

Thomas : vérifier JeV, hotwords, C11 identité, C12 `calculer`, C4 web multi-fournisseurs, C8 EN. Compléter les trous. Un run `serve_hostagent`. TDD. Pas de commit. Aucune valeur de secret. Pas de `docker compose up`.

Carte figée inchangée : **Granite 4.2 3B Q4_K_M** + **Whisper large-v3** + **Magpie Sofia** CUDA. EN 0.1 = `HA_LANG=en` (prompt / annonces / nombres), la carte ASR/TTS reste FR.

## Cause racine (trou C8)

C8 et Presence posent `HA_LANG` sur Windows. Le host-agent (conteneur) ne lisait que la whitelist C1 (`_CLES_OUTILS`) : **`HA_LANG` / `HYPER_AMBIENT_LANG` étaient ignorés** dans `.env.local`, et `relance_hostagent.sh` ne les exportait pas. Conséquence : UI EN possible, cerveau + annonces outils + Magpie (nombres) restés FR.

Les autres branchements (JeV, hotwords, C11, C12, C4) étaient déjà dans `serve_hostagent.py` depuis WIRE / P0-2 / C12 / C4. Re-prouvés, pas recâblés.

## Diff ce tour

| Fichier | Changement |
|---|---|
| `dev/scripts/serve_hostagent.py` | `_CLES_LANGUE` ; `rapport_branchements` / `dry_run` / `--dry-run` (aucun poids GPU) ; log `LANG` au `load` |
| `dev/scripts/relance_hostagent.sh` | export `HA_LANG` / `HYPER_AMBIENT_LANG` ; echo `langue:` (valeur fr/en, pas un secret) |
| `dev/tests/test_taquet_wire2.py` | 8 tests TDD (3 rouges puis verts) |

## TDD rouge → vert

**Rouge** (HA_LANG absent, pas de dry-run) :

```
$ python -m pytest -q dev/tests/test_taquet_wire2.py --tb=line
FFF.....
AssertionError: assert 'HA_LANG' in []
assert 'HA_LANG=' in '#!/usr/bin/env bash…'
AttributeError: … has no attribute 'rapport_branchements'
3 failed, 5 passed in 0.16s
```

Les 5 verts dès le rouge : C11 FR/EN, JeV ignore + harnais observation, `annonce_outil("calculer")` EN, C4 Brave sans Tavily → `web_search`+`calculer`.

**Vert** :

```
$ python -m pytest -q dev/tests/test_taquet_wire2.py
........                                                                 [100%]
8 passed in 0.15s

$ python -m pytest -q dev/tests/test_taquet_wire2.py \
    dev/tests/test_jev_branchement.py dev/tests/test_carte_figee.py \
    dev/tests/test_ears_hotwords.py dev/tests/test_c11_identity.py \
    dev/tests/test_c8_i18n.py dev/tests/test_tools_calculator.py \
    dev/tests/test_tools_web.py dev/tests/test_hostagent_env_local.py
..................................................................       [100%]
66 passed in 0.45s
```

## Un run `serve_hostagent.py --dry-run` (conteneur, live non tué)

Hôte Windows : `ModuleNotFoundError: fastapi` (attendu hors image). Conteneur `mother-core-dev` :

Défaut (FR) :

```
CARTE : BRAIN_MODEL, BRAIN_MODEL_LOCAL, BRAIN_SERVICE, EARS_BACKEND, …
BRAIN : llamacpp granite-4.2-3b-Q4_K_M.gguf
EARS  : faster-whisper / large-v3 hotwords=MOTHER Codex Camunda Claude
MOUTH : magpie Sofia cuda
LANG  : fr
C11   : Hyper Ambient
OUTILS: ask_claude, ask_codex, calculer, web_search
JEV   : on
ANNONCE calculer: Je calcule ça.
```

`docker exec -e HA_LANG=en … --dry-run` : `LANG : en` · `I'll calculate that.` · C11 Hyper Ambient inchangé. Aucun secret imprimé.

`--dry-run` n'écoute pas `:8001` et ne charge pas les poids. Relance live **non faite** (même règle que P0-2 / WIRE ; feu vert Claude).

## Branchements vérifiés

| Brique | Statut |
|---|---|
| Carte Granite + large-v3 + Magpie Sofia | **oui** (dry-run + pytest) |
| Hotwords `MOTHER Codex Camunda Claude` | **oui** (déjà P0-2, re-prouvé) |
| JeV ignore si non adressé ; harnais = log | **oui** (déjà WIRE, re-prouvé) |
| C11 identité Hyper Ambient FR + EN | **oui** (`system_prompt()` / `LlamaCppBrain`) |
| C12 `calculer` toujours au registre | **oui** |
| C4 `web_search` si SearXNG **ou** une clé (Brave testé) | **oui** |
| C8 `HA_LANG` dans le process host-agent | **oui** (trou fermé) |

## Non fait (volontaire)

- Relance live `relance_hostagent.sh` (tue `:8001`, hors feu vert)
- Commit / push
- Descriptions d'outils `web_search` encore en FR dans le schéma modèle (hors 1 h)

NOTIFY=OC — lane simple, close → OC + ponts.
