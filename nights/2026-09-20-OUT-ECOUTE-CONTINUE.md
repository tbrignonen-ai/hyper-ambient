---
date: 2026-09-20
heure: ~18:30 Europe/Paris
type: out
lane: ECOUTE-CONTINUE
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-ECOUTE-CONTINUE]]"]
---

# OUT — écoute continue (vrai mains libres)

Périmètre respecté : `native/hostagent/windows_audio.py`, `native/presence/app.py`, `dev/tests/test_ecoute_continue.py`. Presence non lancée. Aucune commande git. Fichiers interdits non touchés.

## Diff résumé

`native/hostagent/windows_audio.py`
- Constantes exposées `PLANCHER_RMS = 150.0` et `FACTEUR = 2.5` (seuil = max(plancher, bruit × facteur)).
- Classe `CaptureContinue` : flux ouvert entre `start()`/`stop()`, RMS par trame 20 ms, calage ~500 ms, début de tour ≥ 150 ms au-dessus, fin ≥ `TURN_SILENCE_MS` (env, défaut 700) en dessous, jet < 400 ms, coupe à 15 s.
- `segment_pret()` / `prendre_segment()` retirent le tour sans fermer le flux. `suspendre()` / `reprendre()` cessent/reprennent l'accumulation. `forcer_fin()` clôt sans attendre le silence (bouton Parler).
- `PushToTalkCapture` inchangé.

`native/presence/app.py`
- `_servir` instancie aussi `CaptureContinue` (même `stream_factory`).
- `_boucle_tours` : si `mains_libres` et capture continue dispo, ne pas attendre `tenu` — micro ouvert dès le canal prêt. Sinon chemin PTT identique (les tests injectent une fausse capture sans `CaptureContinue`).
- Envoi `audio.capture` + `mains_libres` identique. Front descendant de `tenu` = envoi immédiat du tour en cours.
- Anti-écho : `suspendre()` tant que `en_lecture`, reprise après lecture + garde 250 ms.

`dev/tests/test_ecoute_continue.py` (créé)
- Silence continu, parole+700 ms, trou 300 ms, salve 100 ms, suspendre/reprendre, coupe 15 s, PTT start/stop inchangé, `prendre_segment` ne ferme pas le flux.

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_ecoute_continue.py"
........                                                                 [100%]
8 passed in 0.13s
```

## Pytest (hôte Windows, tel quel)

```
$ python -m pytest -q dev/tests/test_presence_premier_tour.py dev/tests/test_presence_stop_mains_libres.py dev/tests/test_presence_mains_libres.py dev/tests/test_presence_connexion_jev.py
............................                                             [100%]
28 passed in 2.19s
```

## Difficultés

- TDD : 7 tests d'abord, rouge `ImportError: CaptureContinue`, le test PTT déjà vert ; puis vert 8/8.
- `test_boucle_reste_en_ecoute_tant_que_tenu` pince l'ancien toggle (fausse capture `start`/`stop` seulement). La boucle continue n'est armée que si `_capture_continue` a été créée par `_servir` — sinon le PTT/toggle reste strictement identique.
- Les tests VAD poussent 500 ms de silence avant le scénario : le calage ambiant sur de la parole ferait `seuil = RMS × FACTEUR` au-dessus de la parole elle-même.
- Verrou bref dans le callback, pas de `print` par bloc. `threading.Lock` non réentrant : le flux synthétique appelle le callback sur le même fil, hors de `start()`/`stop()`.
