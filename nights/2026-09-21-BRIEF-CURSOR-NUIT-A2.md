# Nuit A2 — la réponse du harnais est inutilisable, et quatre tests sont rouges

Merci pour la nuit A : le chemin écrit fonctionne, il m'a permis de tester la fluidité en
trois minutes. C'est précisément ce qu'il fallait. Tu gardes le même périmètre
(`dev/scripts/serve_hostagent.py`, `dev/scripts/parler_ecrit.py`, `src/brain/`,
`src/ears/`, `dev/tests/`). Aucune commande git.

## Ce que j'ai mesuré avec ton outil

Commande, dans le conteneur :

    python dev/scripts/parler_ecrit.py "Demande a Codex combien de fichiers Python contient le dossier src/brain."

Sortie :

    conversation : /workspace/data/conversations/2026-09-20_23-52.md
    → Codex : Demande a Codex combien de fichiers Python contient le dossier src/brain.
    ← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
    [reflex 1558 ms] Un instant.Je demande à Codex. Je te préviens dès qu'il répond.
    ← Codex : Je répondrai uniquement en français avec un objet JSON valide.

Quatre défauts, par ordre d'importance.

### 1. La réponse du harnais est un écho de consigne, pas une réponse

`← Codex : Je répondrai uniquement en français avec un objet JSON valide.` Le harnais
rend sa propre instruction au lieu du travail demandé. C'est **la** fonctionnalité que le
fondateur veut montrer ; en l'état elle ne sert à rien.

Cherche la cause racine, ne rafistole pas la sortie. Pistes à vérifier, dans cet ordre :
le contrat de sortie de `src/brain/contrat_harnais.py` et la façon dont il est présenté au
modèle distant ; ce que le pont renvoie réellement (journalise la réponse brute pendant
l'investigation, puis retire la journalisation) ; et le fait que le `resume_voix` soit
censé être écrit par le modèle distant, pas par le pont.

### 2. La question envoyée au harnais n'est pas reformulée

`→ Codex : Demande a Codex combien de fichiers Python contient le dossier src/brain.`
On transmet la phrase de l'utilisateur telle quelle, impératif compris. Codex reçoit donc
un ordre adressé à quelqu'un d'autre.

Or j'ai mesuré hier, en appelant `run_tool_loop` directement, que le modèle distant sait
très bien reformuler : il avait produit « Liste tous les fichiers Python (.py) présents
dans le dossier src/brain ». Quelque chose, sur le chemin de `parler_ecrit` / du serveur,
remplace la question du modèle par le prompt brut — probablement un repli qui se déclenche
à tort. Trouve-le.

### 3. Le canal affiché est faux

`[reflex 1558 ms]` alors que le tour a manifestement escaladé : il y a une amorce
(« Un instant. ») et un appel d'outil, deux choses que la voie réflexe ne fait jamais. Le
libellé est probablement pris sur le dernier morceau du flux au lieu du premier morceau
porteur. Un outil de diagnostic qui ment sur le canal est pire qu'inutile — c'est avec lui
qu'on validera le reste de la nuit.

### 4. L'horloge du conteneur est en UTC

    conteneur : Sun Sep 20 23:52:53 UTC 2026
    hôte      : Mon Sep 21 01:52:52 2026

Les fichiers de conversation sont donc nommés et horodatés deux heures en arrière, et
datés de la veille. Le fondateur les cherchera à l'heure à laquelle il a parlé. Corrige en
horodatant à l'heure locale de la machine (Europe/Paris), pas en UTC — dans le nom du
fichier, dans son titre et dans chaque ligne. Fais-le côté code plutôt qu'en changeant le
fuseau du conteneur : le conteneur peut être recréé, le code reste.

## Tâche 5 — quatre tests rouges, et ils sont de ma faute

J'ai basculé `carte_figee.env` sur le routeur. Quatre tests épinglaient `llamacpp` :

    dev/tests/test_carte_figee.py::test_carte_figee_ecrase_l_ancienne_carte
    dev/tests/test_carte_figee.py::test_charger_env_local_laisse_la_carte_au_chargeur_carte
    dev/tests/test_taquet_produit.py::test_carte_figee_charge_granite_whisper_magpie_sofia
    dev/tests/test_taquet_wire2.py::test_dry_run_rapporte_carte_figee_c11_c12_jev_en

Mets-les à jour sur le nouvel état : `BRAIN_SERVICE=router`,
`BRAIN_MODEL=MiniMaxAI/MiniMax-M3`, `BRAIN_MODEL_LOCAL=mother-local`. Ne change pas la
carte pour faire passer les tests — c'est l'inverse, la carte fait foi. Garde ce que ces
tests protégeaient vraiment : que la carte **écrase** l'environnement, et que
`charger_env_local` ne touche pas aux clés modèle.

Les quatre autres échecs (`test_presence_*`, `test_assurer_stdio_*`, palettes) viennent de
l'absence de `tkinter` dans le conteneur : laisse-les, mais confirme-moi dans ton rapport
qu'ils passent bien sur l'hôte, où `tkinter` existe.

## Tâche 6 — la politique de contexte

StepFun a rendu une conception complète dans
`nights/2026-09-21-OUT-STEPFUN-CONTEXTE.md`. Lis-la et implémente **les étapes 2, 3, 5 et
6 de sa section « Plan d'implémentation »**, dans cet ordre, en t'arrêtant dès que l'une
d'elles demanderait de toucher à un fichier hors de ton périmètre :

- le noyau partagé de trois tours et les deux projections différenciées
  (réflexe : 3 tours / 512 jetons ; profond : 15 tours / 3 000 jetons) ;
- la fenêtre adaptative du classifieur ;
- le tampon ambiant en mains libres ;
- les bornes de fin de conversation et la purge.

Deux réserves de ma part, à appliquer : ne retiens **que la forme prononcée** des tours,
jamais les résultats techniques bruts — c'est déjà la règle en vigueur et elle a été
payée cher ; et si une borne chiffrée de StepFun entre en conflit avec une mesure déjà
inscrite dans le code, garde la mesure et dis-le dans ton rapport.

## Vérification attendue

Après correction, relance toi-même le test de fluidité et **colle la sortie réelle** :

    python dev/scripts/parler_ecrit.py "Bonjour, comment vas-tu ?"
    python dev/scripts/parler_ecrit.py "Demande a Codex combien de fichiers Python contient le dossier src/brain."

Je veux voir un canal juste, une question reformulée, une vraie réponse de Codex et un
horodatage local. Puis la suite complète dans le conteneur.

Compte rendu dans `nights/2026-09-21-OUT-CURSOR-NUIT-A2.md`.
