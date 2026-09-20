---
date: 2026-09-20
heure: ~20:15 Europe/Paris
type: out
lane: MANDAT-ASYNC
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-MANDAT-ASYNC]]"]
---

# OUT — mandat asynchrone (appel harnais hors tour)

Périmètre respecté. Aucune commande git. Fichiers interdits non touchés
(`src/brain/contrat_harnais.py`, `dev/tests/test_contrat_harnais.py`,
`src/ears/jev_reflexe.py`, `native/hostagent/windows_audio.py`,
`native/presence/app.py`). Espagnol non touché.

## Fait

`src/brain/mandat.py` (créé)
- `Mandat`, `RegistreMandats` (`deposer` / `en_cours` / `prets` /
  `marquer_annonce` / `oublier`), borne 3, `PleinMandats` avec phrase
  prononçable.
- `confier` rend la main tout de suite, lance `asyncio.create_task`.
  La tâche appelle `envelopper` puis `analyser` (import du voisin, tel
  quel ; repli local seulement si le module n'existe pas encore).
  Exception ou délai 300 s → `etat="echoue"`, jamais de trace.
- Accusé / rappel / arrivée : gabarits i18n. Le texte long
  (`resultat_complet`, `detail_voix`) n'est jamais lu. Offre unique.

`src/i18n/__init__.py`
- Phrases des trois temps, **fr et en seulement**.

`dev/scripts/serve_hostagent.py`
- Pipeline chargé (`_client_outils` posé) : `_registre_pour_tour`
  retire les harnais **inconditionnellement**. Avant le modèle local,
  `harnais_demande` dépose un mandat et répond par l'accusé gabarit,
  sans consulter le 3B.
- `annoncer_mandats_prets` : consultée quand le verrou de tour est
  libre (après `_tour`, et par une veille 0,5 s démarrée au `load`).
  Jamais pendant une lecture, jamais au milieu d'un tour. Rappel
  unique à 60 s si silence. Badge WS `{"type": "mandat_badge", ...}`
  seulement — pas d'élévation de fenêtre.

`dev/tests/test_mandat.py` (créé)
- 22 tests, sans réseau. `analyser` monkeypatchable.

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
...............................F........................................ [  5%]
........................................................................ [ 10%]
......................................................s................. [ 16%]
........................................................................ [ 21%]
..............................x......x.................................. [ 26%]
........................................................ss.............. [ 32%]
...........................................sss..............ssssFss.Fs.. [ 37%]
.s...................................................................... [ 43%]
........................................................................ [ 48%]
........................................................................ [ 53%]
...............................................F....F................... [ 59%]
........................................................................ [ 64%]
........................................................................ [ 70%]
........................................................................ [ 75%]
........................................................................ [ 80%]
........................................................................ [ 86%]
........................................................................ [ 91%]
........................................................................ [ 97%]
......................................                                   [100%]
FAILED dev/tests/test_c11_identity.py::test_cerveau_local_porte_identite_et_style_vocal
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
5 failed, 1313 passed, 18 skipped, 2 xfailed, 39 warnings in 14.07s
```

Les cinq échecs sont ceux déjà listés dans le brief. Aucun échec nouveau.
Référence avant : 1277 passed ; l'écart vient des tests mandat (+22) et
d'autres fichiers déjà présents dans le worktree.

## Pas fait

- Pas créé ni modifié `contrat_harnais` (import tel quel).
- Pas d'ouverture de fenêtre harnais, pas de `SetForegroundWindow`.
- Pas le suivi « le détail » / « ouvre » après l'offre.
- Presence UI : l'événement badge est émis, l'affichage n'est pas
  branché (`native/presence/app.py` interdit).
- Doublures de tests **sans** client HTTP (`test_outils_voix`) gardent
  l'ancien registre-sur-demande : le strip inconditionnel et
  l'interception n'armient que le pipeline chargé, pour ne pas
  inventer d'échec dans ce fichier hors périmètre.
