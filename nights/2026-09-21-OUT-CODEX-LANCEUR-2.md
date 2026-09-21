# Compte rendu — Nuit C3, lanceur 2

## Correction apportee

`packaging/windows/lancer.ps1` conserve son BOM UTF-8 (`UTF8_BOM=True`) et
s'analyse correctement avec Windows PowerShell 5.1 (`PARSE_OK`).

La detection de Presence ne depend plus du jeu de proprietes CIM par defaut :
elle execute une requete WMI qui demande explicitement `ProcessId` et
`CommandLine`. Le controle est effectue avant tout lancement externe, puis son
resultat est reutilise par le demarrage et l'etat final. Une Presence deja
active ne peut donc pas etre empilee pendant l'initialisation du reste.

Les autres controles du lanceur ne reposent pas sur `Win32_Process` : Docker
utilise `docker info`, le conteneur utilise `docker inspect`, et les serveurs
de modeles ainsi que le host-agent sont controles par connexion TCP a leur
port. Aucun autre appel a `Get-CimInstance` n'est present dans le script.

## Verification executee avec `powershell.exe`

Presence etait deja en service (PID 47484) avant le premier passage. Les
commandes suivantes ont ete executees dans cet ordre :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File packaging/windows/lancer.ps1
Get-Process pythonw | Select-Object Id,StartTime
```

### Premier passage

Sortie reellement obtenue :

```text
hyper-ambient — racine : D:\BGB Training\MOTHER-dev
Docker : deja en service.
mother-core-dev : deja en service.
BRAIN local (llama) : deja en service (127.0.0.1:8090).
EARS local (whisper) : deja en service (127.0.0.1:8091).
Host-agent : deja en service (127.0.0.1:8001).
Presence : deja en service (PID 47484).

Etat final :
  Docker : en service
  mother-core-dev : en service
  BRAIN local : en service, port 8090
  EARS local : en service, port 8091
  Host-agent : en service, port 8001
  Presence : en service
Pret : ouvrez Presence et utilisez le bouton parler. Si un element manque, executez installer.ps1 -Diagnostic.
LANCEUR_EXIT=0

   Id StartTime
   -- ---------
47484 21/09/2026 02:07:45
```

### Second passage

Sortie reellement obtenue :

```text
hyper-ambient — racine : D:\BGB Training\MOTHER-dev
Docker : deja en service.
mother-core-dev : deja en service.
BRAIN local (llama) : deja en service (127.0.0.1:8090).
EARS local (whisper) : deja en service (127.0.0.1:8091).
Host-agent : deja en service (127.0.0.1:8001).
Presence : deja en service (PID 47484).

Etat final :
  Docker : en service
  mother-core-dev : en service
  BRAIN local : en service, port 8090
  EARS local : en service, port 8091
  Host-agent : en service, port 8001
  Presence : en service
Pret : ouvrez Presence et utilisez le bouton parler. Si un element manque, executez installer.ps1 -Diagnostic.
LANCEUR_EXIT=0

   Id StartTime
   -- ---------
47484 21/09/2026 02:07:45
```

Les deux passages ont conserve une seule instance `pythonw` de Presence.
