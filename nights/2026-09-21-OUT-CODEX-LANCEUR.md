# Compte rendu — Nuit C2, lanceur

## Réalisé

- `DONNEES.md` et `DONNEES.en.md` indiquent maintenant le chemin réellement monté :
  `data/conversations/` à la racine de l'installation, soit
  `/workspace/data/conversations/` dans le conteneur. Les deux documents précisent que
  `%LOCALAPPDATA%\hyper-ambient\conversations\` ne concerne qu'une exécution hors
  conteneur et qu'un produit installé demandera un volume supplémentaire pour y écrire.
- Ajout de `packaging/windows/lancer.ps1`. Il ne fait aucune installation, ne touche pas
  au Python de l'hôte et ne recrée aucun conteneur. Il vérifie ou démarre Docker avec une
  attente bornée, reprend uniquement `mother-core-dev` avec `docker start`, vérifie ou
  démarre les serveurs BRAIN (8090) et EARS (8091), le host-agent (8001), puis Presence.
  Son état final liste chaque service et l'action à effectuer en cas de prérequis absent.
- `packaging/windows/installer_raccourcis.ps1` pose désormais les raccourcis Bureau et
  menu Démarrer vers `powershell.exe ... -File packaging\windows\lancer.ps1`.
- Le guide Windows et les deux README principaux documentent le lanceur.

## Vérification

La syntaxe PowerShell de `packaging/windows/lancer.ps1` a été analysée sans erreur.

### Première exécution

```text
EXIT 0
hyper-ambient — racine : D:\BGB Training\MOTHER-dev
Docker : deja en service.
mother-core-dev : deja en service.
BRAIN local (llama) : deja en service (127.0.0.1:8090).
EARS local (whisper) : deja en service (127.0.0.1:8091).
Host-agent : deja en service (127.0.0.1:8001).
Presence : deja en service (PID 31136).

Etat final :
  Docker : en service
  mother-core-dev : en service
  BRAIN local : en service, port 8090
  EARS local : en service, port 8091
  Host-agent : en service, port 8001
  Presence : en service
Pret : ouvrez Presence et utilisez le bouton parler. Si un element manque, executez installer.ps1 -Diagnostic.
```

### Seconde exécution

```text
EXIT 0
hyper-ambient — racine : D:\BGB Training\MOTHER-dev
Docker : deja en service.
mother-core-dev : deja en service.
BRAIN local (llama) : deja en service (127.0.0.1:8090).
EARS local (whisper) : deja en service (127.0.0.1:8091).
Host-agent : deja en service (127.0.0.1:8001).
Presence : deja en service (PID 31136).

Etat final :
  Docker : en service
  mother-core-dev : en service
  BRAIN local : en service, port 8090
  EARS local : en service, port 8091
  Host-agent : en service, port 8001
  Presence : en service
Pret : ouvrez Presence et utilisez le bouton parler. Si un element manque, executez installer.ps1 -Diagnostic.
```
