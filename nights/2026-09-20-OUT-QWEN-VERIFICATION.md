---
date: 2026-09-20
heure: "23:35"
type: out
lane: verification-independante-avant-publication
auteur: Qwen
surface: lecture seule — aucun fichier de code modifié
related:
  - "[[2026-09-20-BRIEF-QWEN-VERIFICATION]]"
  - "[[2026-09-20-OUT-QWEN-ONBOARDING-ROBUSTESSE]]"
  - "[[2026-09-20-OUT-CURSOR-ACCENT]]"
  - "[[2026-09-20-OUT-CURSOR-INSTALLEUR-V2]]"
  - "[[2026-09-20-OUT-CODEX-LANGUE-CONNEXIONS]]"
---

# Qwen — Vérification indépendante avant publication

Réponse au brief `nights/2026-09-20-BRIEF-QWEN-VERIFICATION.md`.
Les cinq étapes ont été exécutées dans l'ordre, leurs sorties **exactes** sont
collées ci-dessous. Verdict global en fin de document.

---

## 0. Périmètre, méthode, et trois avertissements à lire avant le reste

### Contraintes du brief respectées

- **Aucun fichier de code modifié.** Vérifié par horodatage : les fichiers que
  j'ai lus n'ont pas bougé sous mes doigts du fait de mes propres actions
  (`installer.ps1` 22:47:20, `test_parite_anglaise.py` 22:21:53,
  `docker-compose.yml` 28-08 03:04, `.gitignore` 21:17:24). Ceux qui ont changé
  pendant mon analyse l'ont été **par d'autres agents** — voir l'avertissement 3.
- **Rien installé.** Python hôte jamais invoqué : toutes les exécutions Python
  sont passées par `docker exec mother-core-dev` (Python 3.11 du conteneur).
  Les seuls appels à l'hôte sont `docker`, `powershell` (étape 3 + listages de
  fichiers) et `dir`.
- **`installer.ps1` jamais lancé sans `-Diagnostic`** (une seule exécution, à
  l'étape 3, avec le paramètre).
- **Aucune commande git exécutée** — voir l'avertissement 1, qui explique ce que
  cela coûte à l'étape 5.
- **Un seul fichier écrit par moi : ce rapport.**

### ⚠ Avertissement 1 — le brief se contredit, et cela affaiblit l'étape 5

L'étape 5 demande de comparer les valeurs aux fichiers rendus par
`git ls-files`. La section « Règles » interdit **toute** commande git. J'ai
appliqué la règle la plus stricte : **je n'ai lancé aucun git**, y compris
`git ls-files`, qui est pourtant en lecture seule.

Conséquence assumée : je n'ai pas la liste exacte des fichiers suivis. J'ai
balayé à la place **l'arbre de travail entier**, ce qui est un *sur-ensemble*
des fichiers suivis (il inclut les fichiers non suivis et non ignorés comme
`packaging/windows/` et les `nights/*-OUT-*.md` de ce soir, qui seront publiés).
Pour un scan de secrets, un sur-ensemble est **plus sévère**, pas moins : rien de
suivi ne peut m'avoir échappé. Les exclusions de balayage (`.git/`, `models/`,
`data/`, `logs/`, `__pycache__/`, `.pytest_cache/`, `node_modules/`,
`.env.local*`) correspondent exactement à des motifs de `.gitignore`, donc aucun
fichier suivi n'a été écarté.

**Mais l'exclusion de `.git/` a un prix, et c'est le point le plus important de
ce rapport : l'historique n'est pas certifié.** Voir §5.

### ⚠ Avertissement 2 — mes runs pytest ont écrit des `.pyc` côté hôte

`dev/`, `src/` et `native/` sont montés en bind dans le conteneur
(`docker-compose.yml`). Mes runs pytest dans le conteneur ont donc produit des
`__pycache__/*.cpython-311.pyc` **sur le disque hôte** :

```
20/09/2026 23:26:20 native\hostagent\__pycache__\platform_audio.cpython-311.pyc
20/09/2026 23:26:06 src\hostagent\__pycache__\transport.cpython-311.pyc
20/09/2026 23:26:06 dev\scripts\__pycache__\serve_hostagent.cpython-311.pyc
```

Aucun impact sur la publication (`__pycache__/` et `*.py[cod]` sont dans
`.gitignore`), aucun fichier source touché. Je le signale parce que la règle du
brief est « ton seul fichier en écriture est ton rapport » et que je ne l'ai pas
tenue à la lettre. Le rapport Qwen précédent avait le bon réflexe : lancer avec
`PYTHONDONTWRITEBYTECODE=1`. Je ne l'ai pas fait. Les `.pyc` en `cpython-313`
(23:18:10-11) ne viennent **pas** de moi : c'est un autre agent qui lance pytest
sur l'hôte. Le cache pytest du conteneur (`/workspace/.pytest_cache`) n'a pas été
réécrit par mes runs (fichiers datés de 21:17 et 21:27), et celui de l'hôte non
plus (`lastfailed` à 22:25:15, antérieur à mon premier run).

### ⚠ Avertissement 3 — l'instantané est daté, le dépôt bougeait pendant l'analyse

Quatre runs de la même commande exacte, entre 23:05 et 23:26, ont donné
**trois résultats différents** :

| # | heure | résultat |
|---|-------|----------|
| 1 | ~23:05 | `5 failed, 1430 passed, 58 skipped, 2 xfailed` |
| 2 | ~23:18 | `4 failed, 1437 passed, 61 skipped, 2 xfailed` |
| 3 | 23:23 | `4 failed, 1437 passed, 61 skipped, 2 xfailed` |
| 4 | 23:25:53 | `4 failed, 1437 passed, 61 skipped, 2 xfailed` |

Cause identifiée, pas un flake : **d'autres agents écrivent dans le dépôt pendant
que je mesure**. `src/i18n/__init__.py` a été réécrit à **23:16:08**, entre mon
run 1 et mon run 2 — c'est ce qui a fait disparaître le 5ᵉ échec (§1.3). Ont
aussi bougé pendant la fenêtre : `src/onboarding/sondes.py` 23:07:26,
`src/hostagent/transport.py` 23:14:51, `dev/tests/test_presence_onboarding.py`
23:15:20, `dev/tests/test_reglages_ui.py` 23:15:46, `native/presence/app.py`
23:16:57, `native/presence/reglages_ui.py` 23:17:20,
`dev/scripts/serve_hostagent.py` 23:20:38, et
`nights/2026-09-20-OUT-CODEX-LANGUE-CONNEXIONS.md` 23:25:02.

**Les états définitifs cités dans ce rapport sont ceux de 23:25:43 (sondes) et
23:25:53 (tests).** Le nombre de tests collectés est passé de 1495 à 1504 pendant
la session : la suite grossit en direct. Toute personne qui relit ce rapport plus
tard doit rejouer les commandes, pas recopier les chiffres.

---

## 1. Suite de tests

### 1.1 Commande et sortie exacte (run de référence, 23:25:53)

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

```
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
4 failed, 1437 passed, 61 skipped, 2 xfailed, 41 warnings in 18.57s
```

Code de sortie : **1** (échec). Les quatre échecs ont **une seule et même
cause** :

```
E   ModuleNotFoundError: No module named 'tkinter'
```

### 1.2 Comparaison à la référence du brief

Référence annoncée : « 1423 passes, 4 échecs pré-existants (`test_c11_identity`,
`test_presence_onboarding`, deux de `test_taquet_produit`) ».

| Échec | Attendu par le brief | Constaté à 23:25:53 |
|---|---|---|
| `test_presence_onboarding::test_orbe_repos_reste_lisible` | oui | **présent** |
| `test_taquet_produit::test_assurer_stdio_pythonw_ecrit_dans_un_journal` | oui | **présent** |
| `test_taquet_produit::test_palettes_a11y_respectent_wcag_non_textuel` | oui | **présent** |
| `test_c11_identity` | oui | **absent — il passe désormais** |
| `test_presence_premier_tour::test_un_appui_deja_relache_est_invisible_pour_la_boucle` | non | **NOUVEAU par rapport à la référence** |

**La référence du brief est périmée, dans les deux sens.**

`test_c11_identity` ne casse plus. Preuve, commande dédiée :

```
docker exec mother-core-dev python -m pytest dev/tests -q -k "c11_identity" -rs --ignore=dev/tests/test_health_sondes.py
```
```
..                                                                       [100%]
2 passed, 4 skipped, 1492 deselected in 4.74s
```

### 1.3 Les deux échecs « nouveaux » nommés, et ce qu'ils valent vraiment

**(a) `test_presence_premier_tour::test_un_appui_deja_relache_est_invisible_pour_la_boucle`**
— nouveau par rapport à la référence, mais **pas une régression de code** : même
`ModuleNotFoundError: No module named 'tkinter'` que les trois autres, sur
`native/presence/app.py:24`. C'est un échec d'environnement de plus, pas un
comportement cassé. Il apparaît dans la liste parce que la référence du brief a
été prise à un moment où ce test n'était pas dans ce cas.

**(b) `test_parite_anglaise::test_anglais_ui_sans_reliquat_francais`** — je l'ai
vu échouer au run 1, et **il a disparu au run 2**. Sortie exacte du run 1 :

```
>       assert not identiques, f"EN calque FR : {identiques}"
E       AssertionError: EN calque FR : ['reglages.accent_titre', 'reglages.accent.autre']
E       assert not ['reglages.accent_titre', 'reglages.accent.autre']

dev/tests/test_parite_anglaise.py:125: AssertionError
```

C'était, au run 1, **le seul échec de contenu réel de toute la suite** — les
quatre autres étant tous tkinter. Il a été corrigé par un autre agent à 23:16:08
(pendant mon analyse), en réécrivant les libellés anglais et non la liste blanche
du test (`test_parite_anglaise.py` n'a pas bougé depuis 22:21:53). État courant :

```
FR 'Accent'          -> EN 'Voice accent'
FR 'Accent ({code})' -> EN '{code} accent'
```

Contrôle de l'état courant :

```
docker exec mother-core-dev python -m pytest dev/tests/test_parite_anglaise.py -q
```
```
13 passed, 2 xfailed in 0.18s
```

### 1.4 Preuve que les quatre échecs sont propres au conteneur, pas au code

La démo du 25 septembre tourne sur l'hôte Windows. J'ai vérifié les deux côtés
**sans jamais exécuter le Python de l'hôte** (simple listage de fichiers) :

```
conteneur :  find_spec('tkinter') -> None
hôte       :  Python313\DLLs\_tkinter.pyd  +  tk86t.dll  +  Python313\tcl\tcl8.6, tk8.6
```

Le Python hôte (3.13.14, trouvé par l'installateur à
`C:\Users\thoma\AppData\Local\Programs\Python\Python313\python.exe`) **a** tkinter ;
le conteneur ne l'a **pas**. Les quatre échecs sont donc des artefacts du
conteneur, pas des régressions. Je ne les ai pas validés sur l'hôte (interdit par
le brief) : c'est une inférence à partir de la présence des fichiers, pas une
mesure d'exécution.

### 1.5 ⚠ Angle mort : 61 tests sautés, et ce sont précisément ceux de la démo

Détail obtenu avec `-rs` (sortie filtrée sur les motifs de skip) :

```
SKIPPED [1] dev/tests/test_indicateur_conversation.py:6: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_connexion_jev.py:6: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_interruption.py:14: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_stop_mains_libres.py:12: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_barge_in.py:206: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_barge_in.py:297: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_barge_in.py:325: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_barge_in.py:353: could not import 'tkinter': No module named 'tkinter'
SKIPPED [2] dev/tests/test_barge_in.py:388: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_integration.py:59: Model loading not available: PocketTTS.load_model() got an unexpected keyword argument 'device'
SKIPPED [1] dev/tests/test_platform_audio.py:233: délégation Windows
SKIPPED [1] dev/tests/test_platform_audio.py:250: délégation Windows
SKIPPED [2] dev/tests/test_presence_mains_libres.py:113: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_onboarding.py:27: could not import 'tkinter': No module named 'tkinter'
SKIPPED [7] dev/tests/test_presence_onboarding.py:156: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_premier_tour.py:79: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_sante.py:69: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_raccourcis_windows.py:43: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:48: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:53: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:59: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:70: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:75: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:81: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:87: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:97: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:102: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [1] dev/tests/test_raccourcis_windows.py:108: packaging/ n'est pas monte dans mother-core-dev
SKIPPED [24] dev/tests/test_reglages_ui.py:60: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_taquet_produit.py:79: could not import 'tkinter': No module named 'tkinter'
```

Lecture sévère : sur 61 skips, **~49 viennent de l'absence de tkinter** et
**11 de l'absence de montage de `packaging/`**. Autrement dit, la suite lancée
dans le conteneur — celle dont le « 1437 passed » servira de preuve de santé —
**n'exécute ni l'interface Tk (24 tests de `test_reglages_ui` seuls), ni
l'installateur Windows, ni les raccourcis**. Ce sont exactement les trois surfaces
que le jury verra le 25 septembre. Le vert du conteneur est un vert **partiel**,
et il ne faut pas le citer comme une validation de la démo.

`test_health_sondes.py` est ignoré par la commande du brief ; pour information, il
n'est de toute façon pas collectable :
`ModuleNotFoundError: No module named 'handlers'` (il importe `handlers` depuis
`workers/night_health_vault_note/`, non monté dans le conteneur).

---

## 2. Sondes réelles des services

### 2.1 Commande et sortie exacte (23:25:43)

```
docker exec mother-core-dev python /workspace/dev/scripts/_probe_sondes_reel.py
```

```
cles presentes : {'BRAIN_API_ENDPOINT': 55, 'BRAIN_API_KEY': 93, 'BRAIN_MODEL': 20, 'CODEX_BRIDGE_URL': 36, 'CODEX_BRIDGE_TOKEN': 64, 'CLI_BRIDGE_URL': 36, 'CLI_BRIDGE_TOKEN': 40, 'TYPESAFE_API_KEY': 108}
--- sondes reelles en 2.12 s ---
  brain_distant  ok=True  2115ms | Le modele distant repond.
  codex          ok=True  13ms | Codex repond.
  claude         ok=True  22ms | Claude repond.
  jev            ok=True  743ms | JeV repond.
```

Aucune valeur de clé affichée — le script n'imprime que des **longueurs**, ce que
j'ai vérifié en le lisant avant de le lancer (`dev/scripts/_probe_sondes_reel.py`,
ligne `print("cles presentes :", {k: (len(v) if v else 0) ...})`).

Un run antérieur (23:1x, avant la réécriture de `sondes.py` à 23:07:26) donnait
les mêmes états : `brain_distant ok=True 2914ms`, `codex ok=True 23ms`,
`claude ok=True 17ms`, `jev ok=True 745ms`. Les quatre sont donc stables et
reproductibles, et le résultat est valable sur le code courant.

### 2.2 État et latence

| Service | État | Latence | Nature réelle de l'appel |
|---|---|---|---|
| `brain_distant` | **ok=True** | 2115 ms | vrai appel : `POST` avec `messages:[{"role":"user","content":"ping"}]`, `max_tokens:1` |
| `codex` | **ok=True** | 13 ms | **appel vide** — voir 2.3 |
| `claude` | **ok=True** | 22 ms | **appel vide** — voir 2.3 |
| `jev` | **ok=True** | 743 ms | vrai appel : classification sur `{"transcription":"bonjour"}` |

Les quatre sont `ok=True`, comme attendu par le brief.

### 2.3 ⚠ Ce que `codex ok=True` et `claude ok=True` ne prouvent PAS

C'est le point que je signale le plus volontiers, parce qu'un `ok=True` à 13 ms
est physiquement incompatible avec un vrai travail de harnais. La cause est
écrite dans le code lui-même, `src/onboarding/sondes.py:231` :

```python
async def sonder_codex(url: str, jeton: str, client=None) -> Sonde:
    # Question vide : le pont authentifie puis rend tout de suite
    # `question vide`, sans lancer Codex (un PONG reel depasse 5 s).
```

`sonder_claude` (ligne 247) fait la même chose avec `{"question": "", "agent": "claude"}`.

Donc, pour Codex et Claude, `ok=True` prouve exactement deux choses : **le pont
local est joignable** et **le jeton est accepté**. Cela ne prouve **ni** que le
harnais sait produire un résultat, **ni** que l'abonnement ChatGPT Plus / Claude
Pro est connecté. Le code le dit explicitement aussi pour la sonde d'outil CLI
(`outil_cli_pret`, docstring) : *« Pas de verification d'abonnement : interroger
l'OAuth hors des outils officiels serait contraire a leurs conditions »*, et elle
se réduit à un `shutil.which(identifiant)`.

Conséquence pour la démo : si le mandat « je demande à Codex de… » échoue devant
le jury pour cause d'abonnement déconnecté, **l'écran de réglages aura affiché
vert juste avant**. Ce n'est pas un bug de la sonde (le choix est documenté et
défendable : un vrai PONG dépasse 5 s), mais c'est un écart entre ce que l'UI
promet et ce qu'elle a vérifié — et un message vert trompeur compte presque
autant qu'un plantage. À trancher avant publication, au minimum par un libellé
honnête du type « pont joignable, abonnement non vérifié ».

`brain_distant` (2115 ms) et `jev` (743 ms) sont en revanche des preuves solides :
ces deux-là font un véritable aller-retour avec le service distant.

---

## 3. Installateur, en lecture seule

### 3.1 Ce que j'ai vérifié AVANT de lancer le script

Le brief interdit de le lancer sans `-Diagnostic`, parce qu'il installerait des
composants sur une machine qui porte un entraînement en cours. Je ne me suis pas
contenté de la promesse du paramètre : j'ai lu le script pour confirmer que le
chemin diagnostic est réellement inoffensif.

- `installer.ps1:1082-1085` — la branche diagnostic se termine par
  `Manques-Depuis-Diagnostic` puis `Dire-Verdict -ModeDiagnostic $true`, et
  `Dire-Verdict` contient **`exit 0` ou `exit 1` dans les deux cas** (lignes
  1043 et 1052). Aucune fonction d'action n'est donc atteignable en mode
  diagnostic : `Installer-Python`, `Installer-WSL2`, `Installer-DockerDesktop`,
  `Demarrer-Docker`, `Demarrer-Conteneur`, `Poser-Raccourcis` sont toutes après.
- Les seules fonctions qui écrivent sont hors du chemin diagnostic :
  `Sauver-Etat` (`New-Item` + `Set-Content`, lignes 253-255) n'est appelée
  qu'après les actions, et `Preparer-Compose` (ligne 951, qui crée un
  `.env.local` vide) n'est appelée que depuis `Demarrer-Conteneur`.
- Tout ce qui précède la branche diagnostic est en lecture seule :
  `Charger-Etat` ne fait que `Test-Path` + `Get-Content` ; `Diagnostiquer`
  n'appelle que `Get-CimInstance`, des lectures de registre (`Lire-Registre64`,
  `Get-ItemProperty`, `Get-WindowsOptionalFeature`, `Get-Service`),
  `wsl -l -v`, `wsl --version`, `wsl -l -q`, `docker info`, `docker version`,
  `docker inspect`, `docker image inspect`, `nvidia-smi --query-gpu`,
  `Get-Command`, `Get-Process`, `Test-Path` et `python --version`.
- Aucune élévation n'est demandée en mode diagnostic (`Lancer-Eleve` n'est
  appelé que depuis les fonctions d'installation). La sortie le confirme :
  « Session : utilisateur standard ».

### 3.2 Commande et sortie exacte

```
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\BGB Training\MOTHER-dev\packaging\windows\installer.ps1" -Diagnostic
```

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
Disque           : depot D:\ 267.2 Go libres ; systeme C:\ 123 Go libres
Session          : utilisateur standard (une elevation ne sera demandee que si une etape le justifie)

--- Ce que ce script ne peut pas faire ---
Virtualisation BIOS : aucun programme ne peut l'activer, c'est du firmware. Redemarrez, entrez dans le BIOS/UEFI (Del, F2, F10 ou Esc selon le PC), cherchez Intel VT-x / Intel Virtualization Technology, ou AMD-V / SVM, activez, enregistrez, repartez.
Redemarrage WSL2 : apres wsl --install, Windows doit redemarrer. Relancez ensuite exactement la meme commande ; le script reprend ou il en etait, sans refaire les etapes deja faites.
Licence Docker Desktop : au premier lancement, une fenetre Docker demande d'accepter la licence. Aucun script ne peut cliquer pour vous. Acceptez, puis relancez.
Pilote NVIDIA trop ancien : ce script ne le met pas a jour. CUDA 12.4 exige au minimum le pilote 551.61. Telechargez-le ici : https://www.nvidia.com/Download/index.aspx

Verdict : pret. Python, WSL2, Docker, mother-core-dev et les raccourcis sont en place.
Ensuite (pas ce script) : modeles dans le conteneur (make models / make models-brain), cles dans .env.local, puis le raccourci hyper-ambient.
Mode diagnostic : rien n'a ete installe ni demarre.
```

**Code de sortie : 0.** Les deux attendus du brief sont remplis : la sortie se
termine bien par `Verdict : pret` et le code est 0.

### 3.3 Preuve a posteriori qu'aucune écriture n'a eu lieu

`Sauver-Etat` est la seule écriture d'état du script, dans
`%LOCALAPPDATA%\hyper-ambient\installeur-etat.json` :

```
--- ETAT INSTALLATEUR (LOCALAPPDATA) ---
absent : C:\Users\thoma\AppData\Local\hyper-ambient\installeur-etat.json
```

Le fichier n'existe toujours pas après mon run : le mode diagnostic n'a rien
écrit. Confirmation indépendante de l'analyse de code du §3.1.

### 3.4 ⚠ Ce que « Verdict : pret » ne couvre pas

Le script le dit lui-même dans sa dernière ligne utile : les **modèles** et les
**clés** ne font pas partie du verdict. `Verdict : pret` signifie « Python + WSL2
+ Docker + conteneur + raccourcis en place », pas « la démo va marcher ». Sur une
machine vierge, il reste `make models` / `make models-brain` (téléchargements
lourds) et la création de `.env.local`. Le verdict est vrai dans son périmètre ;
il serait trompeur s'il était lu comme un feu vert global pour le 25 septembre.

---

## 4. Parité français / anglais

### 4.1 Méthode — et un écart assumé au brief

Le brief demande un petit script jetable dans `/tmp` du conteneur. J'ai utilisé
`python -c` à la place, ce qui revient au même et n'écrit **rien du tout**, pas
même dans `/tmp` — cohérent avec la règle « ton seul fichier en écriture est ton
rapport ». Les commandes sont collées intégralement, donc reproductibles telles
quelles. J'ai bien rechargé `src.i18n` avec `importlib.reload` comme demandé ;
à noter que ce reload n'est pas porteur ici, `t()` relit `os.getenv("HA_LANG")`
**à chaque appel** et non à l'import.

### 4.2 Commande et sortie exacte (état courant, après 23:16:08)

```
docker exec mother-core-dev python -c "import sys,os,importlib;sys.path.insert(0,'/workspace');import src.i18n as i;cles=sorted(set(i._FR)|set(i._EN)|set(i._ES));os.environ['HA_LANG']='fr';fr=importlib.reload(i);bfr=[c for c in cles if fr.t(c)==c];os.environ['HA_LANG']='en';en=importlib.reload(i);ben=[c for c in cles if en.t(c)==c];print('cles_catalogue:',len(cles),'| FR:',len(fr._FR),'| EN:',len(en._EN),'| ES:',len(en._ES));print('HA_LANG=fr -> t(cle)==cle :',len(bfr),bfr);print('HA_LANG=en -> t(cle)==cle :',len(ben),ben);print('cles_absentes_de_EN:',sorted(set(fr._FR)-set(fr._EN)));print('cles_absentes_de_FR:',sorted(set(fr._EN)-set(fr._FR)));print('EN strictement egal a FR:',sorted([c for c in fr._FR if en._EN.get(c)==fr._FR[c]]));print('accent_titre FR/EN:',ascii(fr._FR['reglages.accent_titre']),ascii(en._EN['reglages.accent_titre']));print('accent.autre FR/EN:',ascii(fr._FR['reglages.accent.autre']),ascii(en._EN['reglages.accent.autre']))"
```

```
cles_catalogue: 167 | FR: 167 | EN: 167 | ES: 2
HA_LANG=fr -> t(cle)==cle : 0 []
HA_LANG=en -> t(cle)==cle : 0 []
cles_absentes_de_EN: []
cles_absentes_de_FR: []
EN strictement egal a FR: ['ui.feedback', 'ui.feedback_url', 'ui.stop']
accent_titre FR/EN: 'Accent' 'Voice accent'
accent.autre FR/EN: 'Accent ({code})' '{code} accent'
```

**Attendu du brief atteint : aucune clé ne retombe sur sa clé brute, ni en `fr`
ni en `en`.** Le run identique effectué avant la réécriture de 23:16:08 donnait
déjà `167 / 0 / 0` et aucune asymétrie : ce résultat n'a pas changé, seul le
contenu de deux libellés anglais a changé.

Les trois seules clés dont l'anglais est strictement identique au français
(`ui.feedback` = « Feedback », `ui.feedback_url` = une URL GitHub, `ui.stop` =
« Stop ») sont exactement les trois de la liste blanche
`_EN_IDENTIQUE_FR_OK` de `dev/tests/test_parite_anglaise.py:22`. Aucun calque
résiduel.

### 4.3 ⚠ Le test demandé est structurellement aveugle au vrai risque

Le brief attend « aucune clé pour laquelle `t(cle)` rend la clé elle-même ». Ce
critère est nécessaire mais **très insuffisant**, à cause du repli codé dans
`t()` (`src/i18n/__init__.py`, fonction `t`) :

```python
table = _TABLES.get(langue(), _FR)
valeur = table.get(key)
if valeur is None:
    valeur = _FR.get(key, key)      # <-- repli sur le FRANCAIS avant la cle brute
```

Une clé absente de `_EN` ne rend donc **jamais** la clé brute en anglais : elle
rend **le texte français**. Le test « t(cle)==cle » passe au vert pendant qu'un
anglophone voit du français. C'est précisément le défaut que
`test_anglais_ui_sans_reliquat_francais` attrape, et il venait de le faire au
run 1 (§1.3).

J'ai donc ajouté le contrôle qui manque : la **symétrie des catalogues**
(`cles_absentes_de_EN` et `cles_absentes_de_FR`), qui est la vraie garantie
demandée par la première phrase de l'étape 4 (« chaque libellé existe dans les
deux langues »). Résultat : **les deux listes sont vides**, 167 clés de part et
d'autre. La parité est bonne, et elle est bonne pour la bonne raison.

Reste une faiblesse de conception à signaler pour plus tard : rien dans `t()`
n'empêche une régression future de passer inaperçue en anglais tant que la clé
existe en français. Le garde-fou est uniquement `test_parite_anglaise.py`, dont
la liste blanche `_EN_IDENTIQUE_FR_OK` est une liste **manuelle** — alors que le
module de test annonce en docstring « Les jeux de clés se comparent entre tables,
jamais listés à la main ». C'est cette liste manuelle qui a été prise en défaut à
22:21. Elle le sera de nouveau au prochain mot identique dans les deux langues
(« Volume », « Terminal », « Email »…).

### 4.4 Contrôle complémentaire : les clés appelées par le code existent-elles ?

Une clé utilisée dans le code mais absente du catalogue **tombe vraiment sur la
clé brute** en production (`_FR.get(key, key)`). C'est le seul cas où le critère
du brief peut mordre, donc je l'ai testé directement sur les 85 fichiers `.py`
de `src/` et `native/` :

```
docker exec mother-core-dev python -c "import sys,os,re;sys.path.insert(0,'/workspace');import src.i18n as i;cles=set(i._FR)|set(i._EN);q=chr(34)+chr(39);motif=r'\bt\(\s*['+q+']([A-Za-z0-9_.]+)['+q+']';fich=[os.path.join(r,f) for base in ['/workspace/src','/workspace/native'] for r,_,fs in os.walk(base) for f in fs if f.endswith('.py')];txt=chr(10).join(open(f,encoding='utf-8',errors='ignore').read() for f in fich);appels=set(re.findall(motif,txt));print('fichiers_py_balayes:',len(fich));print('cles_utilisees_dans_le_code:',len(appels));print('absentes_du_catalogue:',sorted(appels-cles))"
```
```
fichiers_py_balayes: 85
cles_utilisees_dans_le_code: 97
absentes_du_catalogue: []
```

**97 clés appelées dans le code, aucune absente du catalogue.** Limite de la
méthode : ne détecte que les appels à littéral de chaîne. Une clé construite
dynamiquement (`t("reglages.champ." + nom)`, et le code en contient pour les
champs de réglages) échappe à ce balayage — mais celles-là sont couvertes par la
symétrie des catalogues au §4.2, puisque la clé de repli est française.

### 4.5 Détail cosmétique (non bloquant)

`FR 'Accent ({code})' -> EN '{code} accent'` rendra, pour un code non reconnu,
quelque chose comme `fr accent` en anglais. Grammatical mais un peu sec ;
`Accent ({code})` aurait suffi puisque le mot est identique dans les deux
langues — c'était d'ailleurs la forme qui faisait échouer le test au run 1. Le
choix actuel est correct, je le note seulement parce qu'il a été fait pour
satisfaire un test plus que pour l'œil.

---

## 5. Secrets avant publication

### 5.1 Méthode (sans git, voir avertissement 1)

Lecture des 46 variables de `.env.local`, puis recherche **littérale**
(`String.Contains`, pas d'expression régulière) de chaque valeur dans chaque
fichier de l'arbre de travail. **Aucune valeur n'est affichée** : la sortie ne
contient que des longueurs, des noms de variables et des noms de fichiers.

Exclusions de balayage : `.git/`, `models/`, `data/`, `logs/`, `__pycache__/`,
`.pytest_cache/`, `node_modules/`, tout fichier nommé `.env.local*`, et tout
fichier de 5 Mo ou plus. Les six premières correspondent à des motifs de
`.gitignore` ; `.env.local*` écarte le fichier source lui-même et ses trois
sauvegardes.

**730 fichiers balayés, 0 fichier écarté pour cause de taille** — la couverture
est complète sur l'arbre de travail.

### 5.2 Passe 1 — toutes les variables (sortie exacte, extraits)

```
variables_dans_env_local=46
variables_testees_valeur_8_car_et_plus=26
variables_non_testees_valeur_trop_courte=ANTHROPIC_API_KEY, BRAIN_REFLEX_ANSWERS, BRAIN_TIMEOUT_MS, BRAIN_TTFT_DEADLINE_MS, CTX, EARS_DEVICE, EARS_LANGUAGE, HA_LANG, HF_HUB_OFFLINE, MOUTH_BACKEND, MOUTH_DEVICE, MOUTH_LANGUAGE, MOUTH_OUTPUT_GAIN_DB, MOUTH_PROFILE, MOUTH_SPEED, MOUTH_STYLE, MOUTH_VOICE_NAME, OPENAI_API_KEY, TURN_SILENCE_MS, TYPESAFE_MODEL
fichiers_balayes=730
fichiers_ignores_car_plus_de_5Mo=0 ->
FUITES=378
```

**Les 378 correspondances ne sont pas des fuites.** Ce sont des valeurs de
*configuration* non secrètes, présentes légitimement dans le code et la doc :
`EARS_MODEL`, `EARS_BACKEND`, `EARS_COMPUTE_TYPE`, `EARS_HOTWORDS`, `HF_HOME`,
`BRAIN_SERVICE`, `BRAIN_MODEL_LOCAL`, `ALIAS`, `MODEL`, `MOUTH_VOICE`,
`LLAMA_SERVER_HOST`, `DASHSCOPE_REGION`, `SEARXNG_URL`, `STEPFUN_BASE_URL`,
`CODEX_BRIDGE_URL`, `CLI_BRIDGE_URL`. Le compteur brut « FUITES=378 » est donc
**inexploitable tel quel** : un test de ce genre qui compare toutes les variables
d'un `.env` noie le signal. D'où la passe 2.

### 5.3 Passe 2 — uniquement les variables sensibles (sortie exacte)

Ciblage sur les noms contenant `KEY`, `TOKEN`, `SECRET`, `PASSWORD`,
`CREDENTIAL`, `ENDPOINT`, `_URL`, avec un seuil abaissé à 6 caractères :

```
fichiers_balayes=730
--- variable | longueur_valeur | occurrences | fichiers ---
ANTHROPIC_API_KEY | len=0 | occ=0 |
BRAIN_API_ENDPOINT | len=55 | occ=3 | nights\2026-09-13-CURSOR-FIX-VOIX.md, nights\2026-09-13-CURSOR-TTS-POCKET.md, nights\2026-09-19-C1-OUTILS.md
BRAIN_API_KEY | len=93 | occ=0 |
CLI_BRIDGE_TOKEN | len=40 | occ=0 |
CLI_BRIDGE_URL | len=36 | occ=6 | .env.example, dev\scripts\_probe_sondes_reel.py, dev\scripts\relance_hostagent.sh, dev\tests\test_onboarding_sondes.py, nights\2026-09-13-MUSE-CONNEXIONS.md, src\brain\tools_cli.py
CODEX_BRIDGE_TOKEN | len=64 | occ=0 |
CODEX_BRIDGE_URL | len=36 | occ=9 | .env.example, dev\scripts\_probe_reglages.py, dev\scripts\_probe_sondes_reel.py, dev\scripts\relance_hostagent.sh, dev\tests\test_onboarding_sondes.py, dev\tests\test_reglages_ui.py, nights\2026-09-13-MUSE-CONNEXIONS.md, nights\2026-09-18-HARNAIS.md, src\brain\tools_codex.py
DASHSCOPE_API_KEY | len=112 | occ=0 |
HF_TOKEN | len=37 | occ=0 |
OPENAI_API_KEY | len=0 | occ=0 |
SEARXNG_URL | len=32 | occ=6 | .env.example, dev\tests\test_hostagent_env_local.py, dev\tests\test_outils_voix.py, nights\2026-09-13-MUSE-CONNEXIONS.md, nights\2026-09-14-CODEX-CONNEXIONS-WEB.md, nights\2026-09-19-CLAUDE-NOTE-CODEX.md
STEPFUN_API_KEY | len=65 | occ=0 |
STEPFUN_BASE_URL | len=35 | occ=9 | .env.example, dev\scripts\_stepfun_long.py, dev\scripts\banc_oreille.py, dev\tests\test_onboarding_reglages.py, nights\2026-09-19-BRIEF-CURSOR-BANC-OREILLE.md, nights\2026-09-19-C5-OUT.md, nights\2026-09-19-CLAUDE-NOTE-CODEX.md, nights\2026-09-19-CLAUDE-POINT-SESSION.md, nights\2026-09-20-CONTACT-CARD.md
TAVILY_API_KEY | len=41 | occ=0 |
TYPESAFE_API_KEY | len=108 | occ=0 |
```

### 5.4 Verdict de l'étape 5 : aucune clé réelle ne fuit

**Les huit secrets réels du dépôt ont une occurrence zéro dans les 730 fichiers
de l'arbre de travail** :

| Variable | Longueur | Occurrences |
|---|---|---|
| `BRAIN_API_KEY` | 93 | **0** |
| `CODEX_BRIDGE_TOKEN` | 64 | **0** |
| `CLI_BRIDGE_TOKEN` | 40 | **0** |
| `TYPESAFE_API_KEY` | 108 | **0** |
| `DASHSCOPE_API_KEY` | 112 | **0** |
| `STEPFUN_API_KEY` | 65 | **0** |
| `TAVILY_API_KEY` | 41 | **0** |
| `HF_TOKEN` | 37 | **0** |

`ANTHROPIC_API_KEY` et `OPENAI_API_KEY` sont **vides** (`len=0`) : elles
n'apparaissaient dans la liste « valeur trop courte » de la passe 1 que pour
cette raison, et ne représentent aucun risque. La couverture est donc complète :
**toute variable de `.env.local` portant un nom de secret a été testée**, aucune
ne fuit.

Les URL qui apparaissent (`CODEX_BRIDGE_URL`, `CLI_BRIDGE_URL` = adresses de ponts
locaux ; `SEARXNG_URL`, `STEPFUN_BASE_URL` = points d'entrée publics de services)
sont les mêmes valeurs que celles de `.env.example` et des défauts du code :
publiées par conception, non sensibles.

### 5.5 ⚠ Le seul vrai doute : `BRAIN_API_ENDPOINT` dans trois rapports publiés

`BRAIN_API_ENDPOINT` (55 caractères) apparaît dans trois fichiers `nights/*.md`
qui seront publiés :

- `nights/2026-09-13-CURSOR-FIX-VOIX.md`
- `nights/2026-09-13-CURSOR-TTS-POCKET.md`
- `nights/2026-09-19-C1-OUTILS.md`

Ce n'est **pas une clé** et cela ne donne accès à rien sans `BRAIN_API_KEY`. Mais
ce n'est **pas non plus** la valeur d'exemple : `.env.example` ne la contient pas
(elle n'apparaît pas dans la liste des fichiers touchés), donc il s'agit de
l'adresse réelle du fournisseur de modèle distant utilisé. Publier le dépôt
révèle donc publiquement **quelle passerelle / quel fournisseur** le fondateur
utilise, et probablement un identifiant de déploiement dans l'URL. À trancher
sciemment avant ce soir : soit c'est accepté, soit ces trois lignes doivent être
expurgées. Je le classe en « douteux », pas en « cassé ».

### 5.6 ⚠ Limite principale : l'historique git n'est PAS certifié

J'ai exclu `.git/` du balayage, et la règle « aucune commande git » m'interdisait
de toute façon d'inspecter l'historique. Or **publier un dépôt, c'est publier son
historique complet** : tous les objets de tous les commits, y compris les
versions effacées depuis.

Mon verdict « aucune clé ne fuit » vaut donc pour **l'arbre de travail au
2026-09-20 23:26**, pas pour les commits passés. Si une clé a été committée un
jour — puis retirée, ou retirée seulement de `.env.local` — elle est toujours
dans les objets et elle partira avec la publication. Le contexte rend ce risque
crédible, pas théorique : `.env.local` est modifié le 20-09 à 22:57, trois
fichiers de sauvegarde en clair dorment à la racine, et des dizaines de rapports
`nights/*.md` collent des sorties de sondes et de configuration.

**C'est le seul point de cette vérification que je ne peux pas trancher, et c'est
celui qui a la plus grande conséquence sur la publication.** Il faut une personne
autorisée à lancer git pour lever le doute, par exemple un
`git log -p --all -S <valeur>` par secret, ou plus simplement un
`git grep <valeur> $(git rev-list --all)`. Je ne l'ai pas fait : le brief me
l'interdit. Je le remonte donc comme bloqueur de décision, pas comme feu vert.

### 5.7 ⚠ Trois fichiers de clés en clair à la racine du dépôt

Constaté en listant le répertoire (pas en les lisant) :

```
20/09/2026 22:57  .env.local                                     (4 217 o)
20/09/2026 21:02  .env.local.sauvegarde-2026-09-20-clibridge     (4 126 o)
20/09/2026 22:57  .env.local.sauvegarde-2026-09-20-halang        (4 153 o)
20/09/2026 21:02  .env.local.sauvegarde.tmp                      (4 137 o)
```

Les trois sauvegardes contiennent les vraies clés. Elles **sont** couvertes par
`.gitignore` (motifs `.env.local.sauvegarde*`, `.env.*.sauvegarde*`,
`*.sauvegarde-*`, `*.tmp`) : vérifié en lisant `.gitignore`, pas en lançant git.
Elles ne partiront donc pas dans la publication. Mais elles restent trois copies
en clair des secrets, à un `git add -f` ou à une réécriture malencontreuse du
`.gitignore` de l'exposition — et deux d'entre elles datent de ce soir
(21:02 et 22:57), donc elles sont produites en routine par le flux de travail.
Recommandation : les supprimer après la soutenance, ou les sortir du dépôt.

---

## Verdict global

**Ce qui est bon.** Les quatre services réels répondent `ok=True` avec les vraies
clés (brain_distant 2115 ms, jev 743 ms = de vrais aller-retours ; codex 13 ms,
claude 22 ms) ; l'installateur en `-Diagnostic` rend exactement
`Verdict : pret` avec le code 0 et n'écrit rien (prouvé : son fichier d'état
n'existe toujours pas) ; la parité FR/EN est saine — 167 clés de part et d'autre,
aucune asymétrie, aucune clé brute, les 97 clés appelées par le code existent
toutes, et les 3 seuls libellés identiques FR/EN sont dans la liste blanche du
test ; **aucune des huit clés réelles de `.env.local` n'apparaît dans les 730
fichiers de l'arbre de travail** ; la suite tourne à `4 failed, 1437 passed,
61 skipped` et les quatre échecs ont une cause unique et environnementale
(`tkinter` absent du conteneur, présent sur l'hôte), donc aucune régression de
code n'est visible à 23:25:53.

**Ce qui est cassé.** Rien qui casse le produit, mais deux choses cassent la
*vérification* : (1) la suite du conteneur est **aveugle aux trois surfaces de la
démo** — ~49 skips faute de `tkinter` (dont les 24 tests de `test_reglages_ui`) et
11 skips faute de montage de `packaging/`, si bien que le « 1437 passed » ne
valide ni l'interface Tk, ni l'installateur, ni les raccourcis ; (2) la référence
du brief est **périmée** — `test_c11_identity` ne casse plus, et un échec de
contenu bien réel (`test_anglais_ui_sans_reliquat_francais`, « EN calque FR :
`reglages.accent_titre`, `reglages.accent.autre``) que j'ai mesuré au run 1 a été
corrigé par un autre agent à 23:16:08 *pendant* mon analyse : quatre runs de la
même commande ont donné trois résultats différents, donc aucun chiffre de ce
rapport n'est réutilisable sans rejouer les commandes.

**Ce qui est douteux.** (1) **L'historique git n'est pas certifié** — la règle
« aucune commande git » du brief contredit son étape 5 (`git ls-files`), je n'ai
donc lancé aucun git et je n'ai scanné que l'arbre de travail : or publier le
dépôt publie tous les commits passés, et si une clé a été committée un jour elle
partira ce soir ; c'est le seul point que je ne peux pas trancher et celui qui a
la plus grande conséquence. (2) `BRAIN_API_ENDPOINT` réel (55 caractères, absent
de `.env.example`) est écrit en clair dans trois `nights/*.md` publiés — pas une
clé, mais divulgue le fournisseur/passelle du fondateur. (3) `codex ok=True` et
`claude ok=True` ne prouvent que « pont joignable + jeton accepté » : les sondes
envoient une **question vide** et ne lancent jamais le harnais, et
`outil_cli_pret` ne vérifie **aucun** abonnement — si l'abonnement est déconnecté
le 25 septembre, l'écran de réglages affichera vert juste avant que le mandat
échoue devant le jury. (4) Le critère de l'étape 4 (« t(cle) rend la cle ») est
structurellement incapable de détecter le vrai risque : `t()` retombe sur `_FR`
avant de retomber sur la clé, donc une clé manquante en anglais affiche du
**français** en passant tous les tests — seule la symétrie des catalogues, que
j'ai ajoutée, le couvre ; et son garde-fou `test_parite_anglaise.py` repose sur
une liste blanche **manuelle** (`_EN_IDENTIQUE_FR_OK`), déjà prise en défaut ce
soir, qui le sera au prochain mot identique dans les deux langues. (5) Trois
sauvegardes de `.env.local` contenant les vraies clés dorment à la racine du
dépôt, produites ce soir même ; elles sont bien ignorées par `.gitignore`, mais à
un `git add -f` de la fuite. (6) Détail : `.pytest_cache` et des
`__pycache__/*.cpython-311.pyc` ont été écrits côté hôte par mes propres runs
pytest (détail au §0, avertissement 2) — rien de suivi par git, aucun source
touché, mais je ne l'ai pas fait exprès et je le signale.
