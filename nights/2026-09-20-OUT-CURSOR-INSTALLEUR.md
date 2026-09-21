---
date: 2026-09-20
heure: ~22:50 Europe/Paris
type: out
lane: INSTALLEUR-WINDOWS
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-RACCOURCIS-WINDOWS]]"
  - "[[2026-09-20-IMPLEMENTATIONS-FUTURES]]"
---

# OUT — Installateur Windows (amorcage unique)

Perimetre : `packaging/windows/installer.ps1`,
`packaging/windows/README.md`, section Installation de `README.md`.
Rapport ici. Aucun autre fichier. Aucune commande git. Le script
n'a pas ete execute : pas de winget, pas de wsl --install, pas de
Docker, pas de compose, pas de touche au Python de l'hote.

## Ce qui est pose

`installer.ps1` se deduit de `$PSScriptRoot` (repli `MyInvocation`)
et remonte de `packaging/windows/` a la racine. `Set-Location`,
`Join-Path`, `-LiteralPath`. Pas de `cd /d`.

Ordre impose : diagnostiquer tout (Windows, virtualisation, WSL2,
Docker, GPU NVIDIA + pilote, Python, place disque, plus conteneur
et raccourcis pour le verdict), afficher, dire les quatre limites,
puis agir seulement si `-Diagnostic` est absent.

Actions, chacune precede d'un test "deja fait" :

- Python absent : `winget install Python.Python.3.13` (scope user,
  puis machine avec elevation expliquee)
- WSL2 absent : `wsl --install --no-distribution` (pas Ubuntu :
  un premier lancement Ubuntu demanderait un compte que le script
  ne peut pas remplir ; Docker Desktop apporte ses distros)
- Docker Desktop absent : `winget install Docker.DockerDesktop`
- Docker arrete : lance `Docker Desktop` et attend jusqu'a 180 s
- image `mother-core:latest` absente : `docker compose build` ;
  presente : on ne reconstruit pas. Puis `up -d` si
  `mother-core-dev` ne tourne pas. Conteneur deja en marche :
  on n'y touche pas
- raccourcis : processus fils vers `installer_raccourcis.ps1`,
  aucun code de .lnk duplique

Etat de reprise : `%LOCALAPPDATA%\hyper-ambient\installeur-etat.json`.
Un redemarrage WSL2 y est note ; relancer le script apres le reboot
continue. Idempotent a chaque etape.

Verdict : `pret` seulement si plus rien ne manque. Sinon liste
numerotee. `-Diagnostic` s'arrete apres l'etape 1, meme verdict.

Elevation : jamais sans une ligne qui dit pourquoi (composant
Windows, Program Files, services Docker). Refus UAC = message
clair, pas de trace.

Forme : francais ASCII (PowerShell 5.1 lit sans BOM ; un tiret
cadratin cassait le parseur). Une ligne par action.

## Verification

Parseur uniquement, comme demande. Windows PowerShell 5.1.26100.9444
(Desktop) :

```
PARSE_OK lines=883 tokens=4454
```

Le script n'a pas ete lance. Cette machine porte l'environnement
du fondateur et un entrainement en cours.

## Ce que le script ne couvre pas

Honnement, ce n'est pas "installer le produit jusqu'a la voix".
C'est l'amorcage de la machine. Il reste hors script, a nommer :

- cloner le depot (le .ps1 vit dedans ; le README racine le dit)
- virtualisation BIOS/UEFI (firmware ; marche a suivre dans le script)
- licence Docker Desktop au premier lancement (clic humain)
- mise a jour du pilote NVIDIA (seuil 551.61 pour CUDA 12.4 ;
  lien NVIDIA, pas d'install)
- winget / App Installer s'ils manquent
- memoire WSL2 (SETUP.md vise ~15 Go) et case "Use the WSL 2
  based engine" / GPU dans Docker Desktop
- image publiee : il n'y a pas de registre a `docker pull` ;
  "recuperer" = reutiliser `mother-core:latest` locale
- construction : 20-40 min, ~32 Go, la premiere fois
- modeles (`make models`, `make models-brain`)
- host-agent, llama-server, whisper, fenetre Presence
- cles dans `.env.local` (copie de `.env.example` si le fichier
  manque, cles vides)
- searxng et les autres services hote
- VRAM minimale 12 Go (on detecte la carte et le pilote, pas
  la quantite)
- macOS / Linux (renvoi vers SETUP.md)
- paquet .msi / .exe / Release GitHub
- pare-feu Windows, ARM, version pinnee de Docker Desktop
- `nvidia-smi` et `make smoke` dans le conteneur

`wsl --install` sans argument installerait Ubuntu et bloquerait
la reprise sur un prompt de compte. `--no-distribution` est un
ecart volontaire, dit dans le script.

## README

`packaging/windows/README.md` presente les deux scripts. Il
depasse les 10 lignes de l'ancien contrat raccourcis : le test
`test_readme_tient_en_dix_lignes_et_reste_honnete` echouera
sur l'hote. Hors perimetre : le test n'a pas ete touche.

Section Installation du README racine : 7 lignes, renvoie vers
`packaging/windows/README.md`.

## Hors perimetre, non touche

`installer_raccourcis.ps1`, `native/presence/hyper-ambient.bat`,
`docker-compose.yml`, `dev/`, `src/`, aucun paquet hote.
