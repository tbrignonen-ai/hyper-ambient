---
date: 2026-09-20
heure: ~22:30 Europe/Paris
type: out
lane: CHAMPS-EDITABLES
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-REGLAGES-V3]]"
  - "[[2026-09-20-OUT-CURSOR-MENUS-REGLAGES]]"
---

# OUT — Champs visiblement éditables + Feedback hors page principale

Périmètre : `native/presence/reglages_ui.py`, `native/presence/app.py`,
`src/i18n/__init__.py`, `dev/tests/test_reglages_ui.py`,
`dev/tests/test_presence_onboarding.py`.
Une ligne dans `dev/tests/test_parite_anglaise.py` (voir ci-dessous).
Aucun fichier interdit. Aucune commande git. Aucune valeur de clé ici.

Le fondateur pouvait vérifier, pas configurer : les `tk.Entry` étaient
plats, fond `#142028` contre panneau `#102028`. Une valeur préchargée
se lisait comme du texte affiché.

## Correction 1 — rectangles de saisie

`ChampSaisie` (sous-classe de `tk.Entry`) :

- Fond `#1c3a4a`, nettement plus clair que le panneau `#102028`.
- Bordure `relief=SOLID`, `bd=2`, plus un anneau `highlightthickness=2`.
- Focus : la bordure passe à `#7ec8dc` (palette orbe repos). Blur :
  retour au bord `#6a9aac`.
- Police 11, `ipady=8`, espacement `pady=(2, 10)` — pas un formulaire
  dense.
- Mode contraste élevé : fond, bord et focus plus clairs
  (`couleurs_champ(True)`), transmis depuis la fenêtre principale.

Invite grise dans les champs **vides**, retirée à la première frappe
(et au collage). `get()` rend `""` tant que l'invite est affichée :
Enregistrer ne pose jamais le texte d'invite.

Champs secrets :

- L'invite reste en clair (`show=""`) : « coller une nouvelle clé »,
  jamais des étoiles qui feraient croire qu'une valeur est déjà là.
- Dès la première saisie, `show="*"`.
- Clé déjà posée : champ vide + invite + mention des quatre derniers
  caractères. On tape par-dessus pour remplacer.
- Après Enregistrer, le secret est masqué, l'invite revient, le
  suffixe est relu.

Boucle complète, testée : taper un modèle et une clé, Enregistrer,
fermer, rouvrir → le modèle est là, la clé n'apparaît que par son
suffixe, le fichier a bien les deux valeurs.

## Correction 2 — Feedback

`ui.feedback` = **Feedback** en français et en anglais.

Le bouton a quitté la page principale. Il vit dans le menu **Aide**
de la fenêtre Réglages (anglais : **Help**). Un clic ouvre l'issue
GitHub, comme avant (`ouvrir_feedback`, injectable en test).

La page principale reste : bulle, Parler, Stop, mains libres, accès
aux Réglages (et Masquer, inchangé).

## i18n

Toutes les invites (`reglages.invite.*`) et le libellé de menu
existent en FR et EN. Aucun texte en dur. Espagnol hors périmètre.

`ui.feedback` est identique FR/EN (mot international, comme `ui.stop`).
`test_anglais_ui_sans_reliquat_francais` l'aurait compté comme un
calque. Une clé ajoutée à `_EN_IDENTIQUE_FR_OK` dans
`dev/tests/test_parite_anglaise.py` — hors liste initiale, nécessaire
pour n'introduire aucun échec nouveau.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
4 failed, 1403 passed, 42 skipped, 2 xfailed in 18.64s
```

Les quatre échecs sont les pré-existants sans `tkinter` dans l'image :

- `test_orbe_repos_reste_lisible`
- `test_un_appui_deja_relache_est_invisible_pour_la_boucle`
- `test_assurer_stdio_pythonw_ecrit_dans_un_journal`
- `test_palettes_a11y_respectent_wcag_non_textuel`

Aucun échec nouveau. Le cinquième échec du brief (`test_c11_identity`)
n'apparaît plus dans cette course.

`dev/tests/test_reglages_ui.py` dans le même conteneur :

```
17 passed, 16 skipped
```

Les sauts sont les tests fenêtrés (pas de Tk dans l'image). Logique,
invites, Feedback, couleurs : verts.

Sur l'hôte Windows, avec Tcl disponible : champs, focus, première
frappe, Enregistrer → rouvrir, menu Feedback, page principale sans
bouton Feedback.

## Hors périmètre, non touché

`dev/scripts/*`, `src/brain/*`, `src/ears/*`, `src/onboarding/*`,
`native/hostagent/*`.
