---
date: 2026-09-20
heure: ~23:57 Europe/Paris
type: out
lane: ROUTEUR-HARNAIS
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-BRIEF-CURSOR-ROUTEUR-HARNAIS]]"
---

# OUT — Un tour qui nomme un harnais ne part plus en REFLEXE

Perimetre : `src/brain/router.py`, `src/brain/mandat.py` (alias
public de la constante de noms), `dev/tests/test_router_outils.py`.
Aucun autre fichier. Aucune commande git.

## Ce qui a change

`mandat.py` : `NOMS_HARNAIS = _NOMS`. La regex
`(codex|claude|muse|cursor)` n'est pas recopiee.

`router.py` :

- `nomme_un_harnais(prompt)` cherche ces noms en frontieres de mot,
  insensible a la casse, via `NOMS_HARNAIS`.
- `classify()` court-circuite AVANT le POST `/completion` : si un
  harnais est nomme, retour
  `{"route": "escalate", "latency_ms": 0.0, "verdict": "HARNAIS"}`.
  Justification dans le code : nommer un harnais est une demande
  d'action, jamais un reflexe ; la voie reflexe est la seule sans
  outils, donc la seule ou la demande ne peut pas aboutir.

Le repli de fin de `query_streaming` (distant en echec -> reflexe
local sans outils) n'est pas touche.

## Pytest

Commande demandee :

```
python -m pytest dev/tests/test_router_outils.py -q
```

Rouge d'abord (tests ecrits, code intact) :

```
........FFFF.F                                                           [100%]
5 failed, 9 passed in 0.57s
```

Les cinq echecs : Codex, Claude, Cursor, Muse, et
`demande a CODEX, stp` — tous classés `reflex` par le FakeClassify
REFLEXE, client HTTP appele. `Bonjour.` passait deja.

Vert apres le court-circuit :

```
..............                                                           [100%]
14 passed in 0.19s
```

Un enonce qui nomme un harnais n'appelle plus le classifieur
(`appels == 0`). `Bonjour.` passe encore par le client et reste
REFLEXE.

## Doutes

Si le distant tombe apres cette escalade forcee, le repli local
repond toujours sans outils : l'utilisateur peut encore entendre
le refus « je ne peux pas ouvrir… ». C'est le comportement demande
(mieux un reflexe qu'un silence), pas un oubli.

Tout mot isolé `cursor` / `muse` / `codex` / `claude` escalade,
y compris un usage de nom commun (« le curseur » ne match pas ;
« cursor » seul, si). Assume voulu : frontieres de mot, pas de
filtre semantique.
