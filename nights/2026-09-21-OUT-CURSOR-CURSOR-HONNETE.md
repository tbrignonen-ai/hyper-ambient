---
date: 2026-09-21
heure: ~02:30 Europe/Paris
type: out
lane: CURSOR-HONNETE
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-CURSOR-HONNETE]]"
  - "[[2026-09-21-OUT-CURSOR-NUIT-A3]]"
---

# OUT — Cursor n'est plus silencieusement remplacé par Codex

Périmètre : `src/brain/mandat.py`, `src/brain/tool_loop.py`,
`dev/scripts/serve_hostagent.py` (inchangé, le flux passe déjà par
`run_tool_loop`), `dev/scripts/parler_ecrit.py` (idem), tests.
Aucun pont `ask_cursor`. Aucune commande git.
Pas touché : `packaging/`, `README*`, `DONNEES*`, `src/onboarding/`,
`native/presence/reglages_ui.py`.

## Ce qui change

`_NOMS_VERS_HARNAIS["cursor"]` rend `Cursor`, plus `Codex`. Cursor est
un harnais reconnu, sans outil : `OUTIL_PAR_HARNAIS` n'a pas de clé
Cursor, on n'a pas construit `ask_cursor`.

Un harnais nommé et non branché (outil absent de la table, ou absent
du registre) produit une phrase, pas un mandat. Un seul chemin,
`phrase_si_harnais_non_branche` dans `mandat.py` : Cursor, Muse et
Claude y passent pareil. La phrase nomme le demandé et celui qui est
proposé, sans le saisir :

    Cursor n'est pas connecté sur cette machine. Je peux demander à Codex, si tu veux.

Le garde vit au début de `run_tool_loop` : le modèle n'est pas appelé,
aucun outil n'est exécuté. Voix et écrit empruntent ce flux
(`flux_cerveau`). `respecter_harnais_nomme` réutilise la même fonction
si un appel d'outil arrive malgré tout.

Un harnais nommé et branché dépose encore un mandat. Un tour qui ne
nomme personne ne change pas.

## TDD

Rouge d'abord : l'import de `phrase_si_harnais_non_branche` cassait la
collecte. Puis les assertions (Cursor n'est plus Codex ; phrase à deux
noms ; pas de mandat ; Muse/Claude même chemin ; Bonjour intact).

## Vérification demandée

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
      "Demande a Cursor de me resumer ce que fait le fichier src/brain/router.py."

    conversation : /workspace/data/conversations/2026-09-21_02-24.md
    [reflex 547 ms] Cursor n'est pas connecté sur cette machine. Je peux demander à Codex, si tu veux.

Pas de `→ Codex`. Pas de mandat. 547 ms : le distant n'a pas été
saisi.

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
      "Demande a Codex de me resumer ce que fait le fichier src/brain/router.py."

    conversation : /workspace/data/conversations/2026-09-21_02-24.md
    → Codex : Peux-tu me résumer ce que fait le fichier src/brain/router.py ?
    ← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
    [deep 2108 ms] Je demande à Codex. Je te préviens dès qu'il répond.
    ← Codex : Ce fichier orchestre les réponses entre un modèle local rapide et un modèle distant plus capable.

Codex reste Codex. Une seule annonce. Réponse complète.

## Pytest

Lane (conteneur) :

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

    197 passed in 1.75s

Suite complète (conteneur), hors deux collecteurs déjà cassés ailleurs
(`test_health_sondes.py` : `handlers` manquant ;
`test_onboarding_sondes.py` : tenu ailleurs) :

    4 failed, 1541 passed, 76 skipped, 2 xfailed, 41 warnings in 22.79s

Les quatre échecs sont les tests tkinter du 21/09 (A3) : tkinter
absent dans l'image. Pas de nouveau échec.
