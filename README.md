# hyper-ambient

**Français** · [English — full description in English](README.en.md)

hyper-ambient est une présence vocale ambiante et locale. Elle écoute, répond à voix
haute, et garde le temps réel sur la machine : un tour ordinaire revient en 650
millisecondes, sans quitter le poste.

Son originalité tient en une phrase : **ce n'est pas un assistant qui contient des
capacités, c'est une voix qui branche celles que vous possédez déjà.** Quand vous lui
demandez du travail de développement, elle ne l'invente pas — elle le confie aux outils
installés sur votre machine, avec votre compte et vos sessions, puis vous rapporte le
résultat à la voix.

Pour du développement intensif, ce n'est pas l'outil adapté, et elle le dit elle-même :
elle n'a pas d'interface visuelle pour lire ou modifier un résultat détaillé. Elle vous
en donne le résumé, puis vous invite à ouvrir l'outil concerné.

## Ce à quoi elle se branche

| Outil | Ce qu'elle en fait |
|---|---|
| **Codex** | Lui confie une tâche, récupère le résultat, l'annonce à la voix |
| **Claude Code** | Idem |

Ces deux-là sont le périmètre, et c'est volontaire. Si vous nommez un outil qui n'est pas
branché, elle vous le dit plutôt que d'en saisir un autre en silence : quand on nomme un
outil, on a une raison de le nommer — une session ouverte, un contexte déjà chargé, un
abonnement.

## Architecture

- **Cœur en conteneur** — les modèles locaux et le service de raisonnement temps réel
  tournent dans un conteneur Docker.
- **Agent hôte** — il relie le micro et les haut-parleurs au cœur par un canal local.
  C'est le seul composant qui touche le matériel audio.
- **Presence** — une petite fenêtre qui affiche l'état, les transcriptions, les réponses,
  et signale les appels distants.

Le modèle local tient les tours brefs. Un classifieur local décide à chaque tour, et
n'envoie au modèle distant que ce qui le nécessite : une demande complexe, ou une demande
qui nomme un outil de développement. Détail dans [DONNEES.md](DONNEES.md).

## Prérequis

- Windows 10 version 2004 ou ultérieure, ou Windows 11 ; PowerShell ; une connexion
  réseau pour l'installation et, si vous l'activez, pour le modèle distant.
- GPU NVIDIA. Le budget visé est **8 Go de mémoire graphique**, et l'ensemble ne doit pas
  dépasser 10 Go. Prévoyez au moins 15 Go de mémoire vive, environ 40 Go libres, et un
  pilote compatible CUDA.
- Virtualisation activée dans le BIOS ou l'UEFI. Docker Desktop, WSL2 et Python sont
  installés ou vérifiés par l'installeur.
- Un clone local du dépôt. Les clés des services facultatifs restent à fournir par leur
  titulaire ; elles ne figurent jamais ici.

## Installation sous Windows

C'est la plateforme prise en charge aujourd'hui. Depuis **n'importe quel** répertoire
PowerShell, remplacez le chemin par celui de votre clone et commencez par le diagnostic :

```powershell
& "C:\chemin\vers\hyper-ambient\packaging\windows\installer.ps1" -Diagnostic
```

Puis, pour installer ou reprendre une installation interrompue :

```powershell
& "C:\chemin\vers\hyper-ambient\packaging\windows\installer.ps1"
```

Ensuite, le raccourci **hyper-ambient** du bureau suffit. Il appelle ce lanceur, que vous
pouvez aussi exécuter à la main :

```powershell
& "C:\chemin\vers\hyper-ambient\packaging\windows\lancer.ps1"
```

Le lanceur regarde ce qui tourne déjà, reprend le conteneur sans le recréer, démarre les
serveurs de modèles, l'agent hôte et Presence, puis affiche l'état de chaque élément.
Lancé deux fois, il n'ouvre pas de seconde fenêtre.

Ce que fait l'installeur en détail, y compris ce qu'il ne peut pas automatiser — Docker
Desktop demande l'acceptation humaine de sa licence au premier lancement — est dans
[le guide Windows](packaging/windows/README.md).

## macOS — livré, non validé

Le portage macOS **est dans ce dépôt** : l'abstraction audio, l'abstraction d'interface,
et l'empaquetage sont dans `packaging/macos/`. Il n'a **jamais été exécuté sur une
machine réelle**, et nous ne le déclarerons pas prêt sans qu'un Mac l'ait éprouvé.

Ce que la première version macOS n'aura pas, et c'est su à l'avance :

- **La voix Sofia n'existera pas.** C'est un moteur CUDA ; un Mac impose un autre moteur,
  donc un autre timbre. C'est le vrai point de rupture, pas une question de portage.
- **Le calcul se fera sans CUDA** : Metal pour le modèle de langage, un moteur de
  transcription vraisemblablement différent, la synthèse sur processeur. Les latences
  restent à mesurer sur place.
- **L'application n'est pas notariée** : le premier lancement demandera une autorisation
  explicite.

### Le processus de validation

Le portage ne sera publié comme pris en charge qu'après ce parcours :

1. La préparation se fait sur Windows : dépendances, empaquetage, lanceur, permissions
   déclarées. Tout ce qui est vérifiable sans Mac l'est avant d'y toucher.
2. Une personne disposant d'un Mac déroule un protocole écrit — une trentaine de minutes,
   chaque étape disant quoi faire et ce qu'on doit voir ou entendre.
3. Le verdict se lit en une minute : **aucun défaut bloquant et voix jugée acceptable, on
   publie ; un seul défaut bloquant, ou voix jugée robotique, on ne publie pas.**
4. Tant que ce verdict n'est pas rendu, macOS reste annoncé comme non validé, ici et dans
   la documentation.

Si vous avez un Mac et voulez aider, c'est exactement là que ça se passe.

## Les mises à jour sont relevées une fois par semaine

Ce dépôt est suivi par une **ronde hebdomadaire** automatisée. Une fois par semaine, elle
relève ce que vous y déposez — tickets, commentaires, demandes de fusion — trie ce qui est
traitable, et prépare le travail.

Ce qu'elle ne fait jamais : décider à notre place. Elle prépare des branches et des
demandes de fusion **en brouillon** ; aucune fusion n'est automatique, et tout changement
est éprouvé à la main avant d'être publié. Les agents qui préparent ce travail tournent
dans un clone sans dépôt distant : ils sont structurellement incapables de pousser.

Concrètement, si vous ouvrez un ticket, comptez **jusqu'à une semaine** avant qu'il soit
relevé. Ce n'est pas de l'inattention, c'est le rythme choisi.

Le flux est dans `automation/n8n/`, avec ses réglages en clair : la périodicité, le nombre
de sujets par passage et l'ancienneté retenue se changent dans l'interface, sans toucher
au code.

## Ce qui vient ensuite

- **macOS** : voir plus haut. Le cœur reste volontairement sur le GPU NVIDIA.
- **Espagnol** : annoncé puis repoussé. Le français et l'anglais sont livrés.
- **Accueil guidé** : l'accueil assisté par le modèle local est spécifié, mais remplacé
  aujourd'hui par des menus classiques.
- **Interface** : vidéo optionnelle, zone de notification, raccourci global, et certains
  contrôles d'accessibilité en parcours réel restent à livrer ou à vérifier.
- **Continuité** : mémoire vocale longue, reprise après redémarrage du serveur, et sonde
  de santé adaptée restent des chantiers ouverts.

Ces limites sont assumées et suivies. Aucune ne remplace une étape que l'installeur
pourrait déjà automatiser.
