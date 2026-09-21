# Nuit C2 — le lanceur, et une incohérence de documentation à corriger

Merci pour la documentation : elle est bonne, et ta liste d'étapes manuelles est
exactement ce que je demandais. Tu gardes le périmètre `packaging/`, `README*.md`,
`DONNEES*.md`, `docs/`. Aucune commande git.

## Tâche 1 — corriger une affirmation fausse sur les transcriptions

Tu as écrit dans `DONNEES.md` et `DONNEES.en.md` que les transcriptions sont dans
`%LOCALAPPDATA%\hyper-ambient\conversations\`. Ce n'est pas ce que fait le code livré
cette nuit. Vérification que je viens d'exécuter :

    conversation : /workspace/data/conversations/2026-09-20_23-52.md

Le host-agent tourne dans le conteneur, et le seul volume monté qui convienne est
`./data`. Le fichier arrive donc, côté hôte, dans
`D:\BGB Training\MOTHER-dev\data\conversations\`. Le chemin `%LOCALAPPDATA%` n'est
atteint que si le processus tourne hors conteneur.

Corrige les deux fichiers pour dire le vrai : le dossier `data/conversations/` à la
racine de l'installation, avec la mention que le chemin `%LOCALAPPDATA%` est celui d'une
exécution hors conteneur. Et ajoute aux prochaines features le fait qu'un produit
installé devra écrire dans `%LOCALAPPDATA%`, ce qui demande un volume supplémentaire.

Règle générale, puisque le dépôt devient public : **ne documente que ce que tu as
vérifié.** Une documentation qui promet un chemin inexistant coûte plus cher qu'une
documentation absente.

## Tâche 2 — le lanceur

C'est le point 3 de ta propre liste, et c'est celui qui compte. Rappel de ce que le
fondateur a dit du lancement : « sur Windows, c'est pas pratique à lancer pour le
moment ; dans le produit fini, comment s'installe l'appli ? » puis, plus sèchement,
« ne te fous pas de moi, même quelqu'un qui connaît galère, il faut le minimum ».

Écris `packaging/windows/lancer.ps1` : un script qui démarre hyper-ambient et rend la
main à l'utilisateur avec un état clair. Il doit, dans cet ordre :

1. Vérifier que Docker tourne, et le démarrer s'il ne tourne pas, avec une attente
   bornée et un message si l'attente expire.
2. Démarrer le conteneur `mother-core-dev` s'il est arrêté — par `docker start`, pas
   par une recréation : la carte figée du projet précise que `docker start` est la
   seule commande de reprise, une recréation ferait retomber la configuration.
3. Vérifier que les serveurs de modèles répondent, et les démarrer sinon.
4. Démarrer le host-agent s'il ne répond pas.
5. Démarrer Presence.
6. Afficher un état final lisible : ce qui tourne, sur quel port, et quoi faire si un
   élément manque.

Exigences :

- **Idempotent.** Lancé deux fois, il ne doit pas empiler deux instances. Le fondateur
  a une règle explicite là-dessus : toujours regarder ce qui tourne déjà avant de
  lancer quelque chose. Vérifie l'existant à chaque étape et dis « déjà en service »
  plutôt que de relancer.
- **Aucune installation.** Ce script lance, il n'installe pas. S'il manque quelque
  chose, il renvoie à `installer.ps1`.
- **Rien sur le Python de l'hôte.** Aucun `pip`, aucune mise à jour de paquet : ce
  Python sert à l'entraînement d'un modèle, une installation y casserait des
  dépendances partagées.
- **PowerShell, chemins absolus ou relatifs à `$PSScriptRoot`**, guillemets autour des
  chemins contenant des espaces. Le script doit marcher depuis n'importe quel
  répertoire.
- Ne touche **pas** aux conteneurs `hermes` ni `openclaw` s'ils existent : ils
  travaillent, ils ne t'appartiennent pas.

Câble-le dans les raccourcis : le raccourci du bureau et celui du menu Démarrer doivent
appeler ce lanceur, pas une commande brute. Regarde ce que fait déjà
`packaging/windows/installer_raccourcis.ps1` et complète-le plutôt que de le doubler.

Documente-le dans `packaging/windows/README.md` et renvoie-y depuis le README principal.

## Vérification attendue

Exécute `lancer.ps1` toi-même et colle la sortie. Puis exécute-le **une seconde fois**
et colle la sortie aussi : je veux voir qu'il dit « déjà en service » au lieu de
relancer. N'exécute jamais `installer.ps1` sans `-Diagnostic`.

Compte rendu dans `nights/2026-09-21-OUT-CODEX-LANCEUR.md`.
