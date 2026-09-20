---
date: 2026-09-20
heure: ~20:30 Europe/Paris
type: out
lane: BARGE-IN
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-BARGE-IN]]"]
---

# OUT — interruption à la voix en mains libres, Stop qui ne tue plus le mode

Périmètre respecté : `native/hostagent/windows_audio.py`, `native/presence/app.py`, `dev/tests/test_barge_in.py` (créé). `test_presence_premier_tour.py` non modifié (le contrat C10 n'était pas en cause). Presence non lancée. Aucune commande git. Fichiers interdits non touchés (`src/brain/mandat.py`, `src/brain/contrat_harnais.py`, `src/ears/jev_reflexe.py`, `dev/scripts/serve_hostagent.py`).

## Ce qui a été fait

### Défaut 1 — barge-in vocal

`native/hostagent/windows_audio.py`
- `FACTEUR_SEUIL_LECTURE = 2.5`, `_DEBUT_BARGE_IN_MS = 400.0`.
- `CaptureContinue.regime_lecture(actif, on_barge_in=None)` : pendant la TTS le micro reste ouvert (`_suspendu` reste faux). Seuil = seuil calibré × 2,5. Bande 85–3400 Hz toujours exigée. 400 ms de voix continue avant de déclarer l'interruption.
- À ce moment : `barge_in` Event + callback `on_barge_in` (abort immédiat). L'audio déjà capté n'est **pas** jeté : `regime_lecture(False)` le conserve comme début du tour suivant.
- `instantane()` : seuil RMS, dernier RMS, accumulation, suspendue, régime.

`native/presence/app.py`
- `_expedier_tour_continu` n'appelle plus `suspendre()`. Il arme `regime_lecture(True)`.
- La boucle continue ne re-suspend plus à chaque tick tant que `en_lecture`.
- `consommer_reponse` : `interrompre` = Parler **ou** barge-in vocal. Recv à 50 ms pour ne pas attendre le prochain paquet TTS.
- Après barge-in vocal : `apres_barge_in` quitte le régime **sans** `reprendre()` (qui viderait le tour).

### Défaut 2 — Stop = couper la phrase, rien d'autre

- `couper_voix` ne touche ni `mains_libres` ni la fenêtre de conversation.
- Stop pendant la lecture : `couper` armé, abort, pas de garde 250 ms, `reprendre()` immédiat.
- Stop **juste après** la lecture : l'Event peut rester levé (contrat UI existant) mais (1) la boucle le désarme hors lecture, (2) `_expedier` fait `couper.clear()` **avant** `consommer_reponse` — le tour suivant n'est pas aborté d'entrée.
- Pouls `ML : vivante` enrichi : `seuil`, `rms`, `accumulation`, `couper`. Tranche au prochain live : pas entendu / entendu mais pas fermé / envoyé mais rien n'est revenu.

### Cause racine du silence 30 s après Stop

**Non isolée.** Le journal d'origine (`lecture=non, suspendue=non`, aucun segment 5) écarte « la boucle est morte » et « Stop a éteint mains_libres ». Les trois pistes déjà écartées par le brief tiennent. Sans les chiffres du nouveau pouls, trancher entre micro sourd, VAD qui n'accumule pas, et segment jamais clos serait encore une conjecture. Livré : instrumentation + garantie de sémantique.

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
...
FAILED dev/tests/test_c11_identity.py::test_cerveau_local_porte_identite_et_style_vocal
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
5 failed, 1323 passed, 24 skipped, 2 xfailed, 39 warnings in 11.03s
```

Référence demandée : 1313 passed, 5 échecs pré-existants. **+10 passed, aucun échec nouveau.** Les 5 noms sont les mêmes.

Hôte Windows (tkinter) : `test_barge_in.py` + VAD + interruption + Stop + premier tour → 48 passed, 1 skipped.

## Ce qui n'a pas pu être fait

- Pas de test live Presence / haut-parleur + micro : le brief et l'anti-écho réel ne se tranchent pas dans Docker.
- Cause racine du hang 30 s après Stop : pas de smoking gun dans le code, seulement des gardes + traces.
- Annulation d'écho : hors périmètre, et hors décision.

## Verdict honnête — anti-écho sans AEC

**Fragile, pas faux.** Les trois conditions (seuil × 2,5, bande, 400 ms) écartent un « euh » et le bruit hors bande. Elles **n'écartent pas l'écho de sa propre voix** : le TTS est déjà dans 85–3400 Hz. Le seul vrai filtre, c'est le RMS relevé.

Si le haut-parleur est fort, le micro proche, ou le calage s'est fait dans une pièce plus calme que la lecture, l'écho passera les 400 ms et elle se coupera elle-même. Monter le facteur ou la durée ne ferait que rendre le vrai barge-in plus dur — ce serait bricoler.

Sans annulation d'écho (AEC matériel, ou soustraction du signal joué), c'est un compromis à calibrer en live, pas une solution. Si le prochain test montre des auto-coupures, la décision d'architecture (AEC) ne m'appartient pas.
