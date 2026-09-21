---
date: 2026-09-20
heure: ~23:20 Europe/Paris
type: out
lane: LANGUE-TAVILY
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-ACCENT]]"
  - "[[2026-09-20-OUT-CURSOR-CHOIX-VOIX]]"
---

# OUT — Langue dans Réglages + reco Tavily

Périmètre : `native/presence/reglages_ui.py`, `native/presence/app.py`,
`src/i18n/__init__.py`, `dev/tests/test_reglages_ui.py`,
`dev/tests/test_presence_onboarding.py`. Aucun fichier interdit.
Aucune commande git. Aucune valeur de clé ici. La plomberie serveur
des trois réglages de langue n'a pas été touchée.

## Demande 1 — le sélecteur de langue quitte l'écran principal

Le choix de langue est dans Réglages, catégorie **Sur votre machine**,
juste après Voix / Accent. L'écran principal n'a plus de radios
Français / Anglais. Il garde la bulle, Parler, Stop, les mains libres,
l'accès aux réglages, et le contraste (déjà immédiat, pas un choix
une-fois-dans-sa-vie).

L'onboarding garde encore le choix : on le fait une fois au premier
lancement. Ensuite c'est le sous-menu.

Le sélecteur écrit `presence.json` + `HA_LANG` via le callback déjà
là (`_appliquer_options`). Il ne touche pas `.env.local`, ni l'oreille,
ni la bouche. Un collègue aligne les trois réglages côté serveur
ce soir : ce n'est pas ce livrable.

### Immédiaté : on ne ment pas

Sous le sélecteur, une phrase :

> Ce réglage ne change que l'interface. La reconnaissance et la
> synthèse gardent leurs propres réglages ; un rechargement des
> modèles peut être nécessaire.

Pendant le changement, le libellé passe à « Changement de langue… »
puis se vide quand le callback a fini. L'interface (HA_LANG,
libellés déjà rafraîchis par `_appliquer_options`) suit. Les modèles
de reconnaissance et de synthèse, non.

## Demande 2 — Tavily dans Recherche web

Dans le bloc Recherche web, deux phrases + l'adresse cliquable :

- Tavily est recommandé pour démarrer : gratuit au début, sans carte
  bancaire.
- Sans aucune clé, la recherche est possible mais peu fiable.
- Adresse : https://app.tavily.com — bouton souligné, focus clavier,
  `webbrowser.open` (injectable en test).

L'URL n'est pas une clé i18n identique FR/EN (ça casserait la parité).
Elle est dans la phrase traduite ; `url_tavily()` l'extrait.

## i18n

FR et EN dans `src/i18n/__init__.py`. Aucun texte en dur dans l'UI
(les radios d'onboarding passent par `reglages.langue.fr` /
`reglages.langue.en`). Espagnol hors périmètre.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
.........................................ssssss......................... [  4%]
........................................................................ [  9%]
.............................................................s.......... [ 14%]
........................................................................ [ 19%]
........................................................................ [ 24%]
............................................................x......x.... [ 28%]
........................................................................ [ 33%]
..............ss........................................................ [ 38%]
.sss..............sssssFss.Fs...s................sssssssssss............ [ 43%]
....sssssssssss...sssss...sssss.sss..................................... [ 48%]
........................................................................ [ 52%]
........................................................................ [ 57%]
...............................................................Fs....F.. [ 62%]
........................................................................ [ 67%]
........................................................................ [ 72%]
........................................................................ [ 76%]
........................................................................ [ 81%]
........................................................................ [ 86%]
........................................................................ [ 91%]
........................................................................ [ 96%]
............................................................             [100%]
=================================== FAILURES ===================================
________________________ test_orbe_repos_reste_lisible _________________________
ModuleNotFoundError: No module named 'tkinter'
___________ test_un_appui_deja_relache_est_invisible_pour_la_boucle ____________
ModuleNotFoundError: No module named 'tkinter'
_______________ test_assurer_stdio_pythonw_ecrit_dans_un_journal _______________
ModuleNotFoundError: No module named 'tkinter'
________________ test_palettes_a11y_respectent_wcag_non_textuel ________________
ModuleNotFoundError: No module named 'tkinter'
=========================== short test summary info ============================
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
4 failed, 1437 passed, 61 skipped, 2 xfailed, 41 warnings in 18.65s
```

Référence d'entrée : 1423 passed, 4 échecs pré-existants. Les 4 échecs
sont les mêmes (`tkinter` absent dans l'image : overlay / app / stdio
pythonw / palettes a11y). Aucun échec nouveau. Quatorze tests de plus
que la référence (libellés, extraction d'URL, menu langue, lien
Tavily, page principale sans sélecteur). Les tests Tk du menu sont
skippés dans le conteneur, comme les autres tests de fenêtre Réglages.
Sur l'hôte Windows, `test_menu_langue_dans_reglages`,
`test_lien_tavily_ouvre_l_adresse` et
`test_page_principale_sans_selecteur_langue` passent.
