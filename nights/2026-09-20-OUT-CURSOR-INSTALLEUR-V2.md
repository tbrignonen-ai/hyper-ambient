---
date: 2026-09-20
heure: ~22:50 Europe/Paris
type: out
lane: INSTALLEUR-WINDOWS
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-INSTALLEUR]]"
  - "[[2026-09-20-OUT-CURSOR-RACCOURCIS-WINDOWS]]"
---

# OUT — Installateur Windows v2 : faux negatif WSL2

Perimetre : `packaging/windows/installer.ps1` uniquement.
Rapport ici. Aucune commande git. Le script a ete lance en
`-Diagnostic` seulement : exit sans rien modifier.

## Le defaut

Premier ecran, faux negatif. Sortie avant correction (machine
reelle, WSL2 installe) :

```
WSL2             : wsl.exe present, WSL2 non confirme (Distribution par d?faut?: Ubuntu
  Version par d?faut?: 2)
Verdict : pas pret. Il reste :
  1. WSL2 absent ou incomplet
```

Le script affichait lui-meme `Version par defaut : 2` puis
concluait qu'il ne pouvait pas confirmer.

## La cause

`wsl.exe` ecrit en UTF-16LE. PowerShell 5.1 decodait mal
(d'ou les `d?faut`). La detection cherchait ensuite des
phrases francaises (`version par defaut`, `ne pas...installe`)
ou anglaises (`Default Version`, `not installed`). Sur un
Windows allemand ou espagnol elle echouerait autrement.
Le registre `DefaultVersion` ne sauvait pas toujours : lecture
32-bit possible via Wow6432Node.

## La correction

On ne parse plus jamais de texte localise.

1. En tete : console UTF-8 + `chcp 65001`, pour que les
   accents (et les sorties natives) restent lisibles.
2. `wsl.exe` est lu en octets, puis decode UTF-16LE si BOM
   `FF FE` ou si les nuls intercales le disent, sinon UTF-8.
   Les nuls restants sont retires. Aucune dependance a la
   page de code du terminal.
3. Signaux numeriques, dans cet ordre :
   - colonne finale `1` ou `2` de `wsl.exe -l -v`
     (aucun libelle NOM / STATE / VERSION)
   - `wsl.exe --version` : un numero `\d+\.\d+` en sortie,
     present seulement sur les WSL2 modernes
   - `DefaultVersion` du registre, vue 64-bit
   - code de `wsl.exe -l -q`, puis cle Lxss / services
     `LxssManager`, `WslService`, `WslInstaller`, puis
     `Get-WindowsOptionalFeature` (enum `Enabled`, pas un
     mot traduit)
4. Dans le doute : on le dit, on ne bloque pas. `Ok = true`,
   `Incertain = true`, ligne jaune, verdict `pret`. On ne
   declare `pas pret` que si quelque chose indique un
   probleme (exe absent, toutes les distros en version 1,
   composant Windows introuvable et lecture possible).

Les lignes d'etat du diagnostic sont colorees : vert si
confirme, jaune si incertain, rouge si manquant.

## Autres detections : audit

Aucune autre sonde ne parse une phrase traduite.

| Sonde | Signal | Locale ? |
|---|---|---|
| Windows | `BuildNumber` >= 19041 | non. Caption affichee seulement. CIM illisible : incertain, on ne bloque plus (avant : « trop ancien ») |
| Virtualisation | `VirtualizationFirmwareEnabled`, `HypervisorPresent` | non. Firmware illisible : incertain, on ne bloque plus |
| WSL2 | chiffres, codes, registre, services | corrige |
| Docker | chemin, processus, `docker info` / `version --format` | non |
| GPU | `nvidia-smi --query-gpu=...csv` puis CIM `Name` ~ NVIDIA | marque, pas une phrase. Inventaire illisible : incertain, on ne bloque plus |
| Python | `Python\s+\d+` (nom du produit) | non |
| Conteneur | `docker inspect -f '{{.State.Status}}'` == `running` | API Docker, toujours anglais |
| Raccourcis | `Test-Path` des `.lnk` | non |
| Disque | `Win32_LogicalDisk.FreeSpace` | non. Deja : lecture impossible n'etait pas un manque |

`Manques-Depuis-Diagnostic` ne pose un manque GPU que si
`Ok` est faux. Une incertitude ne produit plus de « aucune
GPU NVIDIA ».

## Verification

Parseur Windows PowerShell 5.1 :

```
PARSE_OK lines=1114 tokens=5844
```

Puis, sur cette machine, uniquement :

```
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\BGB Training\MOTHER-dev\packaging\windows\installer.ps1" -Diagnostic
```

Exit 0. Rien installe, rien demarre, aucun `winget`, aucun
`wsl --install`, aucun compose.

Sortie exacte :

```
--- Diagnostic (rien ne change pendant cette etape) ---
Racine du depot : D:\BGB Training\MOTHER-dev
Windows          : Microsoft Windows 11 Famille 10.0.26200 (build 26200)
Virtualisation   : activee ; hyperviseur present
WSL2             : present (distribution en version 2)
Docker           : installe, demarre, repond (29.6.2)
GPU NVIDIA       : NVIDIA GeForce RTX 4070, pilote 591.86
Python           : Python 3.13.14 (C:\Users\thoma\AppData\Local\Programs\Python\Python313\python.exe)
Conteneur        : mother-core-dev en marche
Raccourcis       : poses (bureau et menu Demarrer)
Disque           : depot D:\ 267.2 Go libres ; systeme C:\ 123.1 Go libres
Session          : utilisateur standard (une elevation ne sera demandee que si une etape le justifie)

--- Ce que ce script ne peut pas faire ---
Virtualisation BIOS : aucun programme ne peut l'activer, c'est du firmware. Redemarrez, entrez dans le BIOS/UEFI (souvent Del, F2, F10 ou Esc selon le PC), cherchez Intel VT-x / Intel Virtualization Technology, ou AMD-V / SVM, activez, enregistrez, repartez.
Redemarrage WSL2 : apres wsl --install, Windows doit redemarrer. Relancez ensuite exactement la meme commande ; le script reprend ou il en etait, sans refaire les etapes deja faites.
Licence Docker Desktop : au premier lancement, une fenetre Docker demande d'accepter la licence. Aucun script ne peut cliquer pour vous. Acceptez, puis relancez.
Pilote NVIDIA trop ancien : ce script ne le met pas a jour. CUDA 12.4 exige au minimum le pilote 551.61. Telechargez-le ici : https://www.nvidia.com/Download/index.aspx

Verdict : pret. Python, WSL2, Docker, mother-core-dev et les raccourcis sont en place.
Ensuite (pas ce script) : modeles dans le conteneur (make models / make models-brain), cles dans .env.local, puis le raccourci hyper-ambient.
Mode diagnostic : rien n'a ete installe ni demarre.
```

WSL2 ressort en vert : `present (distribution en version 2)`.
Plus de `d?faut`, plus de dump de `wsl --status`. Le verdict
est `pret`.

## Hors perimetre, non touche

`installer_raccourcis.ps1`, README, `native/`, `docker-compose.yml`,
`dev/`, `src/`, aucun paquet hote. Aucune commande git.
