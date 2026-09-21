# Nuit A4 — « Cursor » ne doit pas être silencieusement remplacé par Codex

Merci pour A3 : le bon harnais est saisi, l'annonce est unique et espacée, et la réponse
n'est plus tronquée. J'ai vérifié les trois. Il reste un cas que tu m'avais d'ailleurs
signalé toi-même, et tu avais raison de le faire.

## Le fait

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
      "Demande a Cursor de me resumer ce que fait le fichier src/brain/router.py."

    → Codex : Peux-tu me résumer ce que fait le fichier src/brain/router.py … ?
    ← Codex : src/brain/router.py orchestre deux cerveaux : un modèle local pour les
              réflexes simples et un modèle distant pour toute demande nécessitant
              réflexion, connaissance ou outils.

J'ai nommé **Cursor**, c'est **Codex** qui a travaillé, et elle s'est annoncée comme Codex
sans jamais signaler la substitution. La table `_NOMS_VERS_HARNAIS` de `src/brain/mandat.py`
mappe `cursor` sur `Codex`, et il n'existe pas d'outil `ask_cursor`.

## Ce que je ne veux pas cette nuit

**Ne construis pas de pont `ask_cursor`.** C'est une fonctionnalité nouvelle, le dépôt part
en public dans la matinée, et une intégration écrite à trois heures du matin sans que
personne ne la teste en conditions réelles est exactement le genre de chose qui casse une
démonstration. Elle ira dans les prochaines features.

## Ce que je veux

Que le produit soit **honnête** plutôt que silencieux. Quand l'utilisateur nomme un harnais
qui n'est pas branché, elle le dit en une phrase courte et parlable, puis propose celui
qui est disponible — sans le saisir d'autorité. Par exemple, et à toi d'ajuster la
formulation au registre du produit : « Cursor n'est pas connecté sur cette machine. Je peux
demander à Codex, si tu veux. »

Ce qui compte, et qui est la vraie règle : **elle ne fait jamais faire à un outil le travail
qu'on a demandé à un autre sans le dire.** Quelqu'un qui nomme Cursor a une raison de le
nommer — une session ouverte, un contexte déjà chargé, un abonnement.

Concrètement :

- `cursor` ne doit plus être mappé sur `Codex` dans `_NOMS_VERS_HARNAIS`. Reconnais-le
  comme un harnais à part entière, mais non configuré.
- Un harnais reconnu et non configuré produit la phrase ci-dessus, pas un mandat.
- Vérifie que le même chemin couvre Muse et Claude si leur pont est absent : le cas
  « harnais nommé mais non branché » doit être traité une seule fois, pas trois.
- Ce comportement vaut aussi sur le chemin vocal, pas seulement dans `parler_ecrit.py`.

## Tests

TDD, rouge d'abord. Un harnais nommé et branché dépose un mandat ; un harnais nommé et non
branché ne dépose rien et produit la phrase ; la phrase nomme le harnais demandé et celui
qui est proposé ; et rien ne change pour un tour qui ne nomme aucun harnais.

## Vérification attendue

Rejoue la commande ci-dessus et colle la sortie brute. Puis une commande nommant Codex,
pour prouver la non-régression. Puis la suite complète dans le conteneur.

Périmètre : `src/brain/mandat.py`, `dev/scripts/serve_hostagent.py`,
`dev/scripts/parler_ecrit.py`, `src/brain/`, `dev/tests/`. Ne touche pas à `packaging/`,
`README*`, `DONNEES*`, `src/onboarding/`, `native/presence/reglages_ui.py`. Aucune
commande git.

Compte rendu dans `nights/2026-09-21-OUT-CURSOR-CURSOR-HONNETE.md`.
