---
date: 2026-09-20
heure: ~18:15 Europe/Paris
type: out
lane: JEV-PRECHAUFFAGE
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-JEV-PRECHAUFFAGE]]"]
---

# OUT — préchauffage JeV + maintien de connexion

Périmètre respecté : `src/ears/jev_reflexe.py`, `dev/scripts/serve_hostagent.py`, `dev/tests/test_jev_prechauffage.py`. Presence non lancée. Pas de commit. Fichiers interdits non touchés.

## Diff résumé

`src/ears/jev_reflexe.py`
- `PRECHAUFFAGE_TIMEOUT_S = 10.0` (hors budget 600 ms du tour).
- `INTERVALLE_MAINTIEN_S = 40.0` — 60 s tient encore (351 ms), 90 s expire (601 ms).
- `prechauffer()` : sans clé → False, 0 requête. Sinon une requête jetable timeout 10 s. Avalé, jamais levé.
- `maintenir(intervalle_s=40)` : sleep puis `prechauffer()`, sortie propre sur `CancelledError`.

`dev/scripts/serve_hostagent.py`
- `on_options` True : une seule tâche `prechauffer()` puis `maintenir()`. Fin du préchauffage → `{"type":"jev_pret"}`.
- `on_options` False : annulation + `JEV   : maintien arrete`.
- Log `JEV   : prechauffage ok en N ms` si la poignée a tenu.

`dev/tests/test_jev_prechauffage.py` (créé)
- sans clé → False, 0 POST
- timeout passé ≈ 10 s, pas 0,6 s
- exception transport → False
- `maintenir(0.01)` + `wait_for` : ≥ 2 appels puis arrêt
- défaut d'intervalle < 60 s

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_jev_prechauffage.py dev/tests/test_jev_reflexe.py dev/tests/test_jev_branchement.py"
................                                                         [100%]
16 passed in 1.23s
```

## Difficultés

- TDD : 5 tests d'abord, rouge `AttributeError: prechauffer` / `maintenir`, puis vert.
- `on_options` reste synchrone (le transport l'appelle sans await). La boucle part via `asyncio.create_task` ; `get_running_loop` évite un crash hors contexte async.
- `maintenir` dort d'abord : le câblage host-agent appelle déjà `prechauffer()` avant, donc pas de double ping à l'armement.
