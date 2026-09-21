# hyper-ambient

hyper-ambient est une présence vocale ambiante locale pour Windows. Elle écoute,
répond à voix haute et conserve le temps réel sur la machine. Pour les demandes
complexes — et systématiquement lorsqu’un harnais est nommé — elle utilise un modèle
distant pour raisonner et piloter les harnais de développement déjà installés : Codex,
Claude Code et Cursor.

Le produit est fait pour accompagner un travail sur ordinateur, pas pour remplacer un
environnement de développement. Il peut confier des tâches simples aux harnais et en
donner un résumé vocal. Pour du développement intensif, consultez directement Codex,
Claude Code ou Cursor : hyper-ambient n’a pas d’interface visuelle pour lire, modifier
ou valider leurs résultats détaillés.

English version: [README.en.md](README.en.md). Data flows: [DONNEES.md](DONNEES.md)
([English](DONNEES.en.md)).

## Architecture

- **Cœur Docker** — les modèles locaux et le service de raisonnement temps réel
  s’exécutent dans le conteneur `mother-core-dev`.
- **Agent hôte Windows** — il relie le micro, les haut-parleurs et le cœur par un
  canal local.
- **Presence Tkinter** — la petite fenêtre Windows affiche l’état, les transcriptions,
  les réponses et l’indication d’un appel distant.

Le modèle local répond aux tours brefs. Le modèle distant ne reçoit les données d’un
tour que lorsqu’il est nécessaire pour un tour complexe ou pour une demande qui nomme
un harnais ; il orchestre alors les outils disponibles. Voir le détail, y compris les
désactivations, dans [DONNEES.md](DONNEES.md).

## Prérequis

- Windows 10 version 2004 ou ultérieure, ou Windows 11 ; PowerShell ; connexion réseau
  pour télécharger les dépendances et, si configuré, utiliser le modèle distant.
- GPU NVIDIA : le budget visé est **8 Go de VRAM**, et l’ensemble des étages ne doit pas
  dépasser **10 Go**. Prévoyez au moins 15 Go de RAM système, environ 40 Go libres et un
  pilote NVIDIA compatible CUDA.
- Virtualisation activée dans le BIOS/UEFI. Docker Desktop, WSL2 et Python sont
  installés ou vérifiés par l’installeur.
- Un clone local du dépôt. Les clés des services facultatifs restent à fournir par leur
  titulaire ; elles ne figurent jamais dans ce dépôt.

## Installation Windows

L’installeur est le chemin d’installation documenté. Depuis **n’importe quel**
répertoire PowerShell, remplacez le chemin ci-dessous par celui de votre clone, puis
exécutez d’abord le diagnostic :

```powershell
& "C:\chemin\vers\hyper-ambient\packaging\windows\installer.ps1" -Diagnostic
```

Pour installer ou reprendre l’installation :

```powershell
& "C:\chemin\vers\hyper-ambient\packaging\windows\installer.ps1"
```

Le détail des vérifications, de Docker Desktop, du lanceur et des limites réellement
manuelles est dans [le guide Windows](packaging/windows/README.md). Ne lancez pas le
script sans `-Diagnostic` sur une machine que vous êtes en train de diagnostiquer.

Après l'installation, utilisez le raccourci **hyper-ambient** ou, depuis n'importe quel
répertoire PowerShell :

```powershell
& "C:\chemin\vers\hyper-ambient\packaging\windows\lancer.ps1"
```

Le lanceur vérifie l'existant, reprend le conteneur sans le recréer et ouvre Presence.

## Ce qui vient ensuite

- **macOS** : le terminal est écrit, mais n’a jamais été exécuté sur une vraie machine ;
  il n’est pas encore pris en charge. Le cœur reste volontairement sur le GPU NVIDIA du
  PC Windows.
- **Espagnol** : annoncé, puis repoussé ; le français et l’anglais sont les langues
  livrées aujourd’hui.
- **Onboarding** : l’accueil assisté par le modèle local est spécifié, mais remplacé
  pour l’instant par des menus Tkinter classiques. La déclaration et la vérification des
  services distants et des harnais n’y sont pas encore guidées.
- **Interface** : vidéo optionnelle, zone de notification, raccourci global Windows et
  certains contrôles d’accessibilité en parcours réel restent à livrer ou à vérifier.
- **Continuité** : la mémoire vocale longue, la reprise après redémarrage du serveur,
  les notifications de mandat comme tours complets et une sonde de santé adaptée restent
  des chantiers ouverts.

Ces limites sont volontaires et suivies : elles ne remplacent pas une étape que
l’installeur peut déjà automatiser.
