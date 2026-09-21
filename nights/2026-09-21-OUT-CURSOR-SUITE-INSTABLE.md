---
date: 2026-09-21
heure: ~03:50 Europe/Paris
type: out
lane: SUITE-INSTABLE
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-SUITE-INSTABLE]]"
  - "[[2026-09-21-OUT-CURSOR-TROIS-ROUGES]]"
---

# OUT — suite Tk : 0x80000003, cause racine

Périmètre : `dev/tests/`, `native/presence/reglages_ui.py`,
`native/presence/app.py`. Aucune commande git.

## Question 1 — produit ou tests ?

**La suite plante à cause des tests.** Il n'y a pas de racine Tk, d'image
ou de `StringVar` au niveau module dans `reglages_ui.py` ni `app.py`.

Ouvrir et fermer les réglages cinq fois de suite, **sur la même racine**,
tient : `test_ouvrir_et_fermer_les_reglages_plusieurs_fois` (Toplevel
seul) et `test_ouvrir_et_fermer_reglages_depuis_l_application` (geste
utilisateur depuis Presence). Deux ouvertures successives dans une
même session ne reproduisent pas le 0x80000003.

Le produit avait quand même un trou de fermeture : `fermer()` ne
lâchait pas les `StringVar` sur le fil Tk. Un fil `reglages-sonde`
garde `FenetreReglages` ; si Python collecte la `Variable` depuis ce
fil après destruction de l'interpréteur, Tcl panique. Dans l'app, ça
ne se voit qu'à la **sortie** pendant une sonde encore en vol, pas à
la réouverture des réglages. Correctif produit quand même : ce n'est
pas « seulement un problème de suite ».

## Cause racine

Reproduit avant correctif, même commande que le brief :

    2 failed, 116 passed   (essai 1 — init.tcl + timeout de sonde)
    puis 0x80000003 sur `test_menu_voix_vient_du_serveur_pas_du_code`

Deux mécanismes, même origine (Tcl 8.6 / Python 3.13, un processus) :

1. **Racine jetable.** `_ouvrir_tk()` faisait `Tk()` + `destroy()`
   puis le test (ou `Application`) en créait une deuxième. Le second
   `Tk()` lève « Can't find a usable init.tcl » alors que le fichier
   est là — interpréteur précédent mal défait. D'où l'échec isolé de
   `test_wizard_et_eclair_distant_sont_visibles` dans la suite, jamais
   quand le fichier tourne seul.

2. **`Variable.__del__` hors du fil Tk.** Avertissement capturé :

       Exception ignored in: Variable.__del__
       RuntimeError: main thread is not in main loop

   Les tests détruisaient la racine dans un `finally` **pendant que**
   `fenetre` et ses `StringVar` vivaient encore. Le fil `reglages-sonde`
   (`lancer_hors_fil`) est souvent la dernière référence. `__del__`
   parle à Tcl depuis ce fil, interpréteur déjà mort → Windows fatal
   `0x80000003` (STATUS_BREAKPOINT), pas un échec de test. Ça tombe
   sur `test_menu_voix_*` parce que c'est là que la suite pompe le plus
   le combobox ttk après le plus grand nombre de cycles Tk.

Les `StringVar` étaient créées sans `master` (racine par défaut).
`Application.fermer()` ne fermait pas la fenêtre Réglages ni ne
lâchait `_icone_photo` avant `destroy()`.

## Correctifs

Produit :

- `StringVar(self.fenetre, …)` — plus la racine par défaut.
- `FenetreReglages.fermer()` lâche combobox / champs / variables **sur
  le fil Tk** avant `destroy()`.
- `Application.fermer()` ferme les réglages, pose `_icone_photo = None`,
  puis détruit la racine.

Tests :

- Fixture `racine_tk` (`dev/tests/conftest.py`) : une racine par test ;
  au teardown, join des fils `reglages-sonde`, `gc.collect()` **puis**
  `destroy()`. Aucune référence Tcl ne survit. Pas de skip, pas
  d'xfail, pas de réordonnancement, pas de sous-processus.
- `_ouvrir_tk()` n'importe plus que tkinter. Plus de racine jetable.

## Vérification hôte Windows

    python -m pytest dev/tests/test_presence_onboarding.py dev/tests/test_presence_premier_tour.py \
      dev/tests/test_taquet_produit.py dev/tests/test_taquet_wire2.py \
      dev/tests/test_reglages_ui.py dev/tests/test_raccourcis_windows.py -q -p no:cacheprovider

    120 passed in 25.26s
    120 passed in 25.40s
    120 passed in 25.88s
    120 passed in 25.56s
    120 passed in 25.37s

Cinq exécutions vertes, sans plantage. 118 + les deux tests d'ouverture
répétée.

## Suite conteneur (non-régression)

    docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py

    4 failed, 1520 passed, 75 skipped, 2 xfailed, 41 warnings in 18.18s

Les quatre échecs sont les pré-existants sans `tkinter` dans l'image
(`test_orbe_repos_reste_lisible`,
`test_un_appui_deja_relache_est_invisible_pour_la_boucle`,
`test_assurer_stdio_pythonw_ecrit_dans_un_journal`,
`test_palettes_a11y_respectent_wcag_non_textuel`). +2 skipped : les
nouveaux tests Tk. Aucun échec nouveau.
