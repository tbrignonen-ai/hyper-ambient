---
date: 2026-09-21
heure: ~00:05 Europe/Paris
type: out
lane: FORCER-OUTIL-HARNAIS
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-FORCER-OUTIL-HARNAIS]]"
---

# OUT — Forcer l'appel d'outil quand l'utilisateur nomme un harnais

Perimetre : `src/brain/tool_loop.py`, `dev/scripts/serve_hostagent.py`,
`dev/tests/test_tool_loop_edges.py`. Aucun autre fichier. Carte figee
et `.env.local` intacts. Aucune commande git.

## Ce qui a change

`tool_loop.py` : `run_tool_loop` gagne `tool_choice: Optional[Any] = None`.
Il n'est transmis a `brain.query_streaming` qu'a la premiere iteration,
et seulement si `tools_this_round` est non vide. Aux tours suivants,
ou quand le plafond d'outils est atteint, le champ n'est pas pose :
un `tool_choice` maintenu ferait boucler le modele sur l'outil.

`serve_hostagent.py` :

- `tool_choice_si_harnais(prompt, registre)` deduit le nom d'outil via
  `nomme_un_harnais` (router), `extraire_harnais` et `OUTIL_PAR_HARNAIS`
  (mandat). Ces trois-la ne sont pas recrits.
- Si le harnais est nomme et que l'outil est dans le registre, rend
  `{"type": "function", "function": {"name": <nom_outil>}}`.
- Si le pont est absent du registre, ou si aucun harnais n'est nomme :
  `None`, le tour se deroule comme avant.
- `_flux_brain` calcule ce forcage avant d'appeler `run_tool_loop`.

Commentaire dans les deux fichiers : mesure du 21/09, le modele local
a refuse trois fois d'appeler `ask_codex` alors que l'outil lui etait
declare ; nommer un harnais est une intention sans ambiguite.

## Pytest

Commande demandee :

```
python -m pytest dev/tests/test_tool_loop_edges.py dev/tests/test_router_outils.py dev/tests/test_mandat.py -q
```

Rouge d'abord (tests ecrits, code intact) :

```
FFF.FFF                                                                  [100%]
6 failed, 1 passed in 0.35s
```

Les six echecs : `tool_choice` refuse par `run_tool_loop` (parametre
absent), et `tool_choice_si_harnais` absent du serveur. La
non-regression (`sans_tool_choice_charge_utile_identique`) passait
deja : la charge utile sans forcage n'avait pas change.

Vert apres le correctif :

```
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 1.27s
```

`tool_choice` est dans la premiere iteration, absent de la seconde,
absent quand `tools_this_round` est vide. Sans forcage, les cles
restees `prompt` / `system` / `history` / `messages` / `tools`.
« Demande a Codex… » force `ask_codex` si le pont est au registre ;
pont absent, ou prompt sans harnais : aucun forcage.

## Doutes

Le forcage ne s'execute que si le registre du tour est garni
(`_flux_brain` ne passe par `run_tool_loop` que dans ce cas). Un
registre vide reste le chemin d'avant, sans `tools` ni `tool_choice`.

`extraire_harnais("cursor")` rend `Codex` donc `ask_codex` — c'est
la table existante, pas une nouvelle correspondance.
