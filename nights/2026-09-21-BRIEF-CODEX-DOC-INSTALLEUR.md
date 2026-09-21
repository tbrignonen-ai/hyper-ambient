# Nuit C — la documentation et l'installeur d'un dépôt qui devient public

Bonjour, je suis Opus et je travaille pour Human IA. Le fondateur dort. Le dépôt
`hyper-ambient` passe en public, et il a été explicite sur ce qu'il veut y trouver :
« l'idée est de pousser vers GitHub quelque chose de fonctionnel, documenté, et on
précise les prochaines features aussi. »

Tu es **seul propriétaire** cette nuit de `README.md`, `docs/`, `packaging/`,
`DONNEES.md`, `DONNEES.en.md` et des fichiers de documentation à la racine. D'autres
agents travaillent en parallèle sur le code : **ne touche à aucun fichier sous `src/`,
`native/`, `dev/scripts/` ou `dev/tests/`.**

## Ce qu'il a déjà reproché une fois

Sur l'installation, sa remarque a été sèche : « ne te fous pas de moi. Je suis sûr que
comme tu as prévu, même quelqu'un qui connaît galère. Il faut le minimum, même sur un
GitHub. » Puis, après correction : « et ben voilà, tes points soi-disant bloquants n'en
sont pas. C'est mille fois mieux comme ça. Ton truc était totalement inutilisable avant
ma remarque. »

La leçon à appliquer partout dans ta rédaction : **ne jamais reporter une difficulté en
« implémentations futures » sans avoir vérifié qu'elle est réellement non automatisable.**
Si une étape peut être scriptée, elle doit l'être, pas documentée comme manuelle.

## Tâche 1 — le README d'un projet qu'on découvre

Un lecteur qui arrive sur le dépôt sans rien savoir doit comprendre en deux minutes ce
qu'est hyper-ambient, et savoir en dix comment l'installer. Le README actuel est à
reprendre avec ce regard-là. Ce qu'il doit contenir :

- Ce que le produit est : une voix ambiante locale sur l'ordinateur, avec une
  intelligence locale pour le temps réel et un modèle distant pour la délibération et
  le pilotage des harnais de développement déjà installés (Codex, Claude Code, Cursor).
- **Le positionnement, sans le surjouer.** Consigne littérale du fondateur :
  « clairement pour du dev intensif, hyper-ambient n'est pas l'outil adapté. Il peut
  gérer des tâches simples, mais il n'y a pas d'interface visuelle donc l'utilisateur
  devrait regarder les résultats sur Codex ou Claude Code. Hyper-ambient peut le
  préciser. Elle donne le résumé (grâce au modèle distant) puis peut encourager
  brièvement à consulter l'outil pour plus d'informations. » Écris cela comme une
  limite assumée, pas comme une excuse.
- L'architecture en deux composants : le cœur dans le conteneur Docker, l'agent hôte et
  la présence Tkinter sur Windows.
- Les prérequis réels, matériels compris : le budget mémoire graphique est de 8 Go,
  10 au maximum, tous étages confondus.
- L'installation, en renvoyant à l'installeur, pas en la réexpliquant.
- La section « prochaines features », voir tâche 3.
- Une version anglaise cohérente si le dépôt en porte une : l'anglais est au jour 1.

## Tâche 2 — l'installeur, relu comme un utilisateur

`packaging/windows/installer.ps1` existe et a été exécuté avec succès (`Verdict : pret`,
code de sortie 0). Ta tâche n'est pas de le réécrire mais de le **relire et de le
documenter honnêtement** :

- Vérifie que son `README` dit exactement quoi taper, depuis n'importe quel répertoire,
  en syntaxe PowerShell — c'est le terminal du fondateur. Pas de `cd /d`, pas de
  `start ""`, chemins entre guillemets.
- Explique ce que l'installeur fait, ce qu'il vérifie et ce qu'il ne peut pas faire.
  Sur Docker en particulier : dis précisément pourquoi une installation entièrement
  silencieuse de Docker Desktop est ou n'est pas possible, et ce que l'installeur fait
  à la place. C'est une question que le fondateur a posée explicitement.
- Signale-moi dans ton rapport, sans les corriger toi-même, les étapes encore manuelles
  qui pourraient être automatisées. Je les ferai traiter par l'agent qui tient le code.
- **N'exécute jamais `installer.ps1` sans l'option `-Diagnostic`** sur cette machine.

## Tâche 3 — les prochaines features, écrites honnêtement

Un fichier ou une section qui dit ce qui n'est pas fait et ce qui vient ensuite. Appuie-toi
sur `nights/2026-09-20-IMPLEMENTATIONS-FUTURES.md`. Points à y faire figurer :

- macOS : le portage est écrit mais n'a jamais été exécuté sur une vraie machine. Dis-le
  ainsi, sans le présenter comme supporté.
- L'espagnol, annoncé et repoussé.
- L'onboarding assisté par le modèle local, remplacé pour l'instant par des menus.
- Tout ce que tu trouves d'autre dans les rapports de nuit du dépôt.

## Tâche 4 — les données qui sortent

`DONNEES.md` et `DONNEES.en.md` existent et ont été vérifiés. Deux mises à jour :

- Un agent ajoute cette nuit l'écriture des **transcriptions de conversation** dans un
  répertoire local. Ces fichiers restent sur la machine et ne sortent jamais ; ajoute-les
  au tableau avec cette mention, en indiquant où ils se trouvent.
- Le modèle distant est désormais appelé pour tous les tours difficiles et pour tout tour
  qui nomme un harnais. Vérifie que le tableau le dit clairement, et **ne qualifie pas de
  « sortie de votre machine » un pont local** : le fondateur a relevé que c'était à la
  fois faux et alarmant.

Le ton demandé pour ce fichier est le même que celui qu'il a validé : discret et
graphique, pas anxiogène.

## Contraintes

- Aucune commande git : ni branche, ni commit, ni push. C'est mon périmètre.
- Ne révèle jamais la valeur d'une clé API, d'un jeton ou d'un point d'accès privé, ni
  dans la documentation, ni dans les exemples, ni dans ton rapport.
- Rien ne s'installe sur le Python de l'hôte.
- Compte rendu dans `nights/2026-09-21-OUT-CODEX-DOC-INSTALLEUR.md` : ce que tu as
  écrit, ce que tu as vérifié, et les étapes manuelles que tu me signales.
