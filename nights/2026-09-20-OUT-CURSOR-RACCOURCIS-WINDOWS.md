---
date: 2026-09-20
heure: ~22:40 Europe/Paris
type: out
lane: RACCOURCIS-WINDOWS
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-IMPLEMENTATIONS-FUTURES]]"
---

# OUT — Raccourcis Windows (bureau + menu Demarrer utilisateur)

Perimetre : `packaging/windows/installer_raccourcis.ps1`,
`packaging/windows/README.md`, `dev/tests/test_raccourcis_windows.py`.
Aucun autre fichier. Aucune commande git. Pas d'installateur .exe,
pas de PyInstaller.

## Ce qui est pose

Le script se deduit de `$PSScriptRoot` (repli `MyInvocation`) et
remonte de `packaging/windows/` a la racine du depot. Il fonctionne
quel que soit le repertoire courant.

Il cree (ou ecrase) le meme `hyper-ambient.lnk` :

- Bureau utilisateur : `[Environment]::GetFolderPath('Desktop')`
- Menu Demarrer utilisateur : `[Environment]::GetFolderPath('Programs')`

Pas le dossier machine. Pas d'elevation. Cible :
`native/presence/hyper-ambient.bat`, repertoire de travail = racine
du depot. Icone : `native/presence/assets/hyper-ambient.ico` si le
fichier est la, sinon `pythonw.exe` / `python.exe`. `-Supprimer`
retire les deux .lnk ; un fichier deja absent n'est pas une erreur.

Forme PowerShell : `Set-Location`, `Join-Path`, `-LiteralPath`.
Pas de `cd /d`, pas de `start` cmd. `Start-Process` n'apparait pas :
le script pose un raccourci, il ne lance pas l'application.

Une ligne par action. Echec = `Echec : ...` puis `exit 1`, sans
trace. Relancer deux fois ecrase les memes chemins : pas de doublon.

Le README (7 lignes) donne la commande d'install, celle de retrait,
et dit clairement que ceci pose le raccourci, pas le produit.

## Pytest

Reference demandee :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Resultat :

```
4 failed, 1404 passed, 53 skipped, 2 xfailed in 18.94s
```

Reference : 1403 passes, 4 echecs. Ici : +1 passe, +11 sauts.
Aucun echec nouveau. Les quatre echecs sont les pre-existants sans
`tkinter` dans l'image.

`mother-core-dev` ne monte pas `packaging/` (seulement `dev/`,
`native/`, `src/`). Dans le conteneur :
`test_le_lanceur_vise_par_le_raccourci_existe` passe ; les onze
autres sautent. Sur l'hote Windows, arbre complet :

```
12 passed in 0.03s
```

Le parseur PowerShell 5.1 dit `PARSE_OK`. Le script n'a pas ete
execute contre le bureau reel.

## Hors perimetre, non touche

`native/presence/hyper-ambient.bat`, `dev/scripts/*`, `src/*`,
aucun .exe, aucun paquetage.
