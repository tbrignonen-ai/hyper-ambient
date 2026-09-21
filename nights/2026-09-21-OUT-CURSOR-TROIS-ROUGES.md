---
date: 2026-09-21
heure: ~03:45 Europe/Paris
type: out
lane: TROIS-ROUGES
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-TROIS-ROUGES]]"
---

# OUT — trois tests rouges sur l'hôte Windows

Périmètre : `dev/tests/`, `native/presence/reglages_ui.py`,
`packaging/windows/README.md`. Aucune commande git.

Les trois hex des pastilles étaient déjà distincts dans l'arbre de
travail (`#3dba7a` / `#d9a441` / `#d04a4a`). Le brief demandait aussi
le contraste : c'est désormais asserté, pas seulement vrai par
hasard. Les deux autres rouges étaient des tests devenus faux.

## 1. Trois états, trois couleurs, contraste non textuel

`test_les_trois_etats_ont_trois_couleurs_differents` lit les pastilles
rendues. Vert / orange / rouge restent trois fills distincts.

Contraste WCAG 1.4.11 (≥ 3:1) contre `FOND_VITRE` `#102028`, mesuré
avec `contraste_relatif` :

| état        | hex       | ratio |
|-------------|-----------|-------|
| répond      | `#3dba7a` | 6.75  |
| muet        | `#d9a441` | 7.41  |
| injoignable | `#d04a4a` | 3.78  |

Les mêmes trois couleurs sont maintenant dans
`test_palettes_a11y_respectent_wcag_non_textuel`. Une couleur unique
mais trop sombre échouerait les deux tests.

## 2. Le raccourci pointe vers le lanceur

`test_script_pointe_vers_le_bat_avec_repertoire_de_travail` vise
`lancer.ps1`, plus `hyper-ambient.bat`. Il garde ce qu'il protégeait :
`WorkingDirectory`, racine déduite de `$PSScriptRoot` / `$racine`,
cible présente sur le disque.

Ajout : `test_script_est_utf8_bom_ou_ascii_strict`. Le poseur de
raccourcis est déjà UTF-8 avec BOM (`EF BB BF`) — PowerShell 5.1, le
shell des `.lnk`, peut le lire. Le script n'a pas été retouché.

## 3. Démarrage rapide, puis le guide

`packaging/windows/README.md` reste un guide. Il commence par neuf
lignes : un bloc PowerShell de cinq commandes complètes, chemins entre
guillemets (`installer.ps1 -Diagnostic`, `installer.ps1`, `lancer.ps1`,
`installer_raccourcis.ps1`, `-Supprimer`). La première section `##`
ouvre le détail.

Le test compte ces lignes-là, pas le fichier entier. Honneteté
conservée : pas de PyInstaller, pas de `.exe`, Docker /
`mother-core-dev` / raccourcis toujours nommés.

## Vérification hôte Windows

    python -m pytest dev/tests/test_presence_onboarding.py dev/tests/test_presence_premier_tour.py \
      dev/tests/test_taquet_produit.py dev/tests/test_taquet_wire2.py \
      dev/tests/test_reglages_ui.py dev/tests/test_raccourcis_windows.py -q

    ........................................................................ [ 61%]
    ..............................................                           [100%]
    118 passed in 27.53s

(Un premier passage de la même commande a pris un `Windows fatal
exception: code 0x80000003` pendant un `destroy` Tk dans
`test_menu_voix_*`, hors des trois tests du brief. Relance propre :
118 passed. Les trois tests nommés passent aussi isolés.)

Avant : 3 failed, 113 passed, 1 skipped. Après : les trois rouges
passent ; un test d'encodage a été ajouté.

## Suite conteneur (non-régression)

    docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py

    4 failed, 1520 passed, 73 skipped, 2 xfailed, 41 warnings in 20.69s

Les quatre échecs sont les pré-existants sans `tkinter` dans l'image :

- `test_orbe_repos_reste_lisible`
- `test_un_appui_deja_relache_est_invisible_pour_la_boucle`
- `test_assurer_stdio_pythonw_ecrit_dans_un_journal`
- `test_palettes_a11y_respectent_wcag_non_textuel` (l'import
  `overlay` tire `tkinter` avant d'atteindre les pastilles)

`packaging/` n'est pas monté : les assertions `.ps1` / README sautent.
Aucun échec nouveau.
