---
date: 2026-09-21
heure: ~02:15 Europe/Paris
type: out
lane: NUIT-A3
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-NUIT-A3]]"
  - "[[2026-09-21-OUT-CURSOR-NUIT-A2]]"
  - "[[2026-09-21-OUT-CURSOR-NUIT-A]]"
---

# OUT — Nuit A3 : fidélité du harnais, une annonce, mots conservés

Périmètre : `src/brain/mandat.py`, `src/brain/tool_loop.py`,
`src/brain/router.py`, `src/brain/contrat_harnais.py`,
`dev/scripts/serve_hostagent.py`, `dev/scripts/parler_ecrit.py`, tests.
`carte_figee.env` intact. Aucune commande git.
Pas de `tool_choice` recâblé (Nuit A : « qu'est-ce que Codex ? » ne
doit pas forcer un appel).

## Défaut 1 — le harnais nommé fait autorité

Le distant choisit encore *s'il* appelle. Le nom dit par l'utilisateur
choisit *lequel*. `respecter_harnais_nomme` dans `mandat.py` s'applique
au moment du choix, dans `run_tool_loop`, après que le modèle a posé
un appel :

- harnais nommé + autre harnais saisi + outil présent → on réécrit
  l'appel (arguments conservés) ;
- harnais nommé + outil absent du registre → aucune exécution, phrase
  « Claude Code n'est pas connecté sur cette machine » (le nom est
  celui prononcé, via `nom_harnais_dit`) ;
- outil local (`calculer`, `web_search`) : on ne touche pas.

Ce n'est pas le forçage `tool_choice` retiré cette nuit : un énoncé
qui nomme un harnais sans appeler d'outil reste une question.

### Piège `cursor` → Codex

`_NOMS_VERS_HARNAIS["cursor"]` rend `Codex`. Ce n'est **pas** voulu
comme produit : README / DONNEES traitent Cursor comme un troisième
harnais, distinct de Codex. La table n'a pas de clé Cursor, il n'y a
pas d'`ask_cursor`. **Non changé** — à confirmer avant toute
modification. Un test épingle le mapping actuel.

## Défaut 2 — une seule annonce, recollée avec une espace

Les trois phrases (amorce « Un instant. », phrase du modèle, accusé
du mandat) naissent au *premier* `query_streaming`, avant tout message
`role=tool`. `est_une_suite_d_outil` ne les voit pas : le garde du
13/09 coupe l'amorce du *second* appel, après le résultat.

Choix : **l'accusé du mandat** porte le sens (qui est saisi, on
préviendra). L'amorce du routeur est coupée dès qu'un harnais est
nommé. La phrase du modèle est jetée au dépôt du mandat dans
`flux_cerveau`. Commentaire dans les deux fichiers.

`recoller_prononce` remet l'espace à la couture (`Un instant.` +
`Je…` → `Un instant. Je…`), pas à la fin de chaque libellé. Un flux
de jetons (`Hel` + `lo`) reste `Hello`.

## Défaut 3 — le nettoyage vocal garde les mots

`_nettoyer_voix` remplaçait `` `…` `` et les clotures ``` par une
espace : le contenu disparaissait. Mesure : « Le Dockerfile installe ,
le définit comme et par défaut. » — `python:3.11`, `python3`, `3.11`
avalés, phrase encore grammaticale.

Correctif : on retire les marqueurs (```langue et accents graves),
jamais le texte. Test ajouté sur le cas mesuré.

## Tâche 4 — les quatre tests tkinter

Dans le conteneur, toujours tkinter absent :

    4 failed, 1443 passed, 61 skipped, 2 xfailed, 41 warnings in 12.37s

(`test_onboarding_sondes.py` : NameError `pytest` à la collecte —
fichier tenu ailleurs, ignoré pour ce décompte.)

Sur l'hôte Windows, où `tkinter` 8.6 existe :

    python -m pytest \
      dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible \
      dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle \
      dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal \
      dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel \
      -q

    ....                                                                     [100%]
    4 passed in 0.60s

Les quatre échecs du conteneur ne sont pas réels.

## Vérification demandée

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
      "Demande a Claude Code de me dire quelle version de Python tourne dans ce projet."

    conversation : /workspace/data/conversations/2026-09-21_02-10.md
    → Claude : Quelle version de Python est utilisée dans ce projet ? Cherche dans les fichiers de configuration comme pyproject.toml, setup.py, requirements.txt, runtime.txt, .python-version, Pipfile, ou tout autre fichier indiquant la version de Python.
    ← Claude : Je demande à Claude. Je te préviens dès qu'il répond.
    [deep 2060 ms] Je demande à Claude. Je te préviens dès qu'il répond.
    ← Claude : Le projet ne déclare aucune version de Python dans ses fichiers de configuration : il n'y a ni pyproject.toml, ni .python-version, ni runtime.txt, et le requirements.txt ne fixe que des paquets.

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
      "Demande a Codex combien de fichiers Python contient le dossier src/brain."

    conversation : /workspace/data/conversations/2026-09-21_02-10.md
    → Codex : Combien de fichiers Python (.py) contient le dossier src/brain ? Donne juste le nombre.
    ← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
    [deep 1267 ms] Je demande à Codex. Je te préviens dès qu'il répond.
    ← Codex : 16

Claude Code saisit Claude, pas Codex. Une seule annonce, correctement
espacée. Réponse complète. Codex reste Codex.

## Pytest de lane

    docker exec mother-core-dev python -m pytest \
      dev/tests/test_mandat.py \
      dev/tests/test_contrat_harnais.py \
      dev/tests/test_router_outils.py \
      dev/tests/test_parler_ecrit.py \
      dev/tests/test_tool_loop.py \
      dev/tests/test_tool_loop_edges.py \
      dev/tests/test_amorces_rapport.py \
      dev/tests/test_outils_voix.py \
      -q

    190 passed in 1.72s
