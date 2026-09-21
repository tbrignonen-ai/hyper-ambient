---
date: 2026-09-21
heure: ~02:05 Europe/Paris
type: out
lane: NUIT-A2
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-NUIT-A2]]"
  - "[[2026-09-21-OUT-STEPFUN-CONTEXTE]]"
---

# OUT — Nuit A2 : harnais utilisable, canal juste, contexte

Périmètre : `dev/scripts/serve_hostagent.py`, `dev/scripts/parler_ecrit.py`,
`src/brain/`, `src/ears/`, `dev/tests/`.
`carte_figee.env` intact. Aucune commande git.

## Tâche 1 — l'écho de consigne

Cause racine : deux contrats de sortie empilés. `mandat._courir`
préfixait `PREFIXE_CONTRAT` (JSON exclusif) ; le pont ajoute encore
`_VOICE_PREFIX` (« Réponds en français, deux ou trois phrases parlables,
sans markdown »). Codex réconciliait les deux en une phrase
(`Je répondrai uniquement en français avec un objet JSON valide`) et
s'arrêtait là. `analyser` prenait cette phrase pour `resume_voix`.

Correctif : le pont reçoit la question de travail, sans enveloppe JSON.
`analyser` parse toujours ce qui revient (JSON ou texte libre).
`resume_voix` vient de la réponse du harnais, pas d'une phrase écrite
par le pont. Journalisation brute posée pendant l'investigation, puis
retirée. `envelopper` et le contrat restent disponibles ; ils ne
partent plus vers Codex.

Le pont (`native/codexbridge/bridge.py`) est hors périmètre : son
préfixe vocal n'a pas été touché.

## Tâche 2 — la question reformulée

Ce n'était pas un repli dans le modèle. `run_tool_loop` n'émettait pas
les arguments de l'appel ; `parler_ecrit` et le serveur recopiaient le
prompt utilisateur. Le chunk `phase=call` porte maintenant
`arguments` (sanitisés). L'affichage et le journal prennent
`question`, plus le prompt brut.

## Tâche 3 — le canal

Le libellé partait de `reflex` et ne voyait jamais `deep` : le chunk
`tool_calls` est avalé par la boucle, le filler vaut `filler`, le
mandat n'a pas de canal. Premier morceau porteur : `filler` / `holding`
/ `tool` / `deep` → `deep` ; `reflex` seulement s'il arrive en premier.

## Tâche 4 — horodatage local

`datetime.now()` du conteneur est UTC. `maintenant_local()` force
`Europe/Paris` pour le nom du fichier, le titre et chaque ligne.
Repli `_Paris` (CET/CEST) si `tzdata` manque — c'est le cas du
conteneur. Le fuseau du conteneur n'a pas été changé.

## Tâche 5 — quatre tests carte

Mis à jour sur l'état réel : `BRAIN_SERVICE=router`,
`BRAIN_MODEL=MiniMaxAI/MiniMax-M3`, `BRAIN_MODEL_LOCAL=mother-local`.
La carte n'a pas bougé. Ils gardent : la carte **écrase** l'environnement,
`charger_env_local` ne touche pas aux clés modèle.

Les quatre échecs restants du conteneur sont bien `tkinter` :
`test_orbe_repos_reste_lisible`,
`test_un_appui_deja_relache_est_invisible_pour_la_boucle`,
`test_assurer_stdio_pythonw_ecrit_dans_un_journal`,
`test_palettes_a11y_respectent_wcag_non_textuel`.
Sur l'hôte, où `tkinter` 8.6 existe :

    ....                                                                     [100%]
    4 passed in 0.61s

## Tâche 6 — politique de contexte (étapes 2, 3, 5, 6)

`src/brain/contexte.py` : spine de 3 tours ; réflexe 3 tours / 512 jetons ;
profond 15 tours / 3 000 jetons. Forme prononcée seulement — les
`[résultat outil]` restent le filet d'un tour déjà payé, hors spine.

Classifieur : fenêtre adaptative déjà à 25 caractères. Troncature du
tour précédent **gardée à 160**, pas 80 — 160 est la mesure déjà
inscrite dans `router.py`. Tampon ambiant 5 s / 15 caractères, injecté
`[ambiant]` sans être prononcé. Silence : 30 s mains libres (mesure
JeV / `DUREE_FENETRE_S`, pas touchée) et 60 s bouton ; purge de la
mémoire vive ; phrase de garde s'il reste un mandat.

`MEMOIRE_MESSAGES=12` reste (test épinglé, ancienne borne du buffer
partagé). Elle ne borne plus le profond : 12 protégeait le local, qui
a maintenant sa propre fenêtre de 3 tours.

Étape 4 (registre de mandats / « et alors ? ») non faite : hors des
étapes demandées.

## Vérification demandée

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py "Bonjour, comment vas-tu ?"

    conversation : /workspace/data/conversations/2026-09-21_02-01.md
    [reflex 2187 ms] Je vais bien, merci.

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py "Demande a Codex combien de fichiers Python contient le dossier src/brain."

    conversation : /workspace/data/conversations/2026-09-21_02-01.md
    → Codex : Combien de fichiers Python contient le dossier src/brain ?
    ← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
    [deep 4458 ms] Un instant.Je demande à Codex. Je te préviens dès qu'il répond.
    ← Codex : Le dossier src/brain contient 16 fichiers Python. J’ai inclus le fichier init .py.

Canal juste, question reformulée, vraie réponse Codex, horodatage
Paris (02:01 le 21, pas 23:52 UTC le 20). `src/brain` a bien 16 `.py`
après cette nuit (`contexte.py` compris).

Fichier lu depuis le conteneur
(`/workspace/data/conversations/2026-09-21_02-01.md`) :

```
# Conversation 2026-09-21 02:01

02:01:22  Toi  Bonjour, comment vas-tu ?
02:01:24  hyper-ambient  Je vais bien, merci.
02:01:30  Toi  Demande a Codex combien de fichiers Python contient le dossier src/brain.
02:01:35  → Codex  Combien de fichiers Python contient le dossier src/brain ?
02:01:35  ← Codex  Je demande à Codex. Je te préviens dès qu'il répond.
02:01:35  hyper-ambient  Un instant.Je demande à Codex. Je te préviens dès qu'il répond.
02:01:50  ← Codex  Le dossier src/brain contient 16 fichiers Python. J’ai inclus le fichier init .py.
```

## Pytest

    docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py

    4 failed, 1476 passed, 61 skipped, 2 xfailed, 41 warnings in 18.83s

Les 4 échecs = tkinter absent du conteneur, verts sur l'hôte (ci-dessus).
Les 4 tests carte qui épinglaient `llamacpp` sont verts.

Cette lane, isolée dans le conteneur :

    docker exec mother-core-dev python -m pytest \
      dev/tests/test_contexte.py \
      dev/tests/test_conversations.py \
      dev/tests/test_parler_ecrit.py \
      dev/tests/test_mandat.py \
      dev/tests/test_tool_loop.py \
      dev/tests/test_carte_figee.py \
      dev/tests/test_router_amorces.py \
      dev/tests/test_router_contexte.py \
      dev/tests/test_outils_voix.py \
      -q

    201 passed in 2.44s
