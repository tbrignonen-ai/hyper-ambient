---
date: 2026-09-20
heure: "21:00"
type: out
lane: robustesse-premier-lancement
auteur: Qwen
surface: lecture seule — aucun fichier de code modifié
related:
  - "[[2026-09-14-CODEX-ONBOARDING-DESIGN]]"
  - "[[2026-09-15-CURSOR-DESIGN-ONBOARDING]]"
  - "[[2026-09-20-OUT-CODEX-ONBOARDING-ECARTS]]"
  - "[[2026-09-18-UI-HA]]"
  - "[[2026-09-20-OUT-JEV-CONNEXION-UI]]"
  - "[[2026-09-19-C10-PREMIER-TOUR-OUT]]"
---

# Qwen — robustesse du premier lancement de Presence (hyper-ambient)

Angle unique : **ce qui casse ou ce qui bloque**, pas l'esthétique ni l'ergonomie.
Pour chaque cas : la cause exacte (fichier:ligne), ce que l'utilisateur voit à
l'écran, le correctif minimal.

## 0. Périmètre, méthode et avertissement sur l'instantané

### Contraintes respectées

- **Aucun fichier de code source modifié.** Vérifié par horodatage avant/après :
  seuls `native/presence/app.py` (20:29:08 puis 20:37:08) et
  `native/hostagent/windows_audio.py` (20:26:10) ont bougé pendant mon analyse,
  et ce n'est pas moi — un autre agent écrivait en parallèle.
- **Aucune commande git exécutée.** L'état de suivi mentionné plus bas vient de
  l'instantané fourni en début de session, pas d'un `git status` que j'aurais lancé.
- **Un seul fichier écrit : ce rapport.**
- Les tests ont été lancés avec `PYTHONDONTWRITEBYTECODE=1` et
  `-p no:cacheprovider` : vérifié, `.pytest_cache` n'a pas été touché
  (LastWrite 08-25 03:01, antérieur à mes runs) et aucun `__pycache__` du
  périmètre n'a été réécrit par moi.

### Fichiers lus intégralement

`native/presence/onboarding.py`, `native/presence/sante.py`,
`native/presence/platform_ui.py`, `dev/tests/test_presence_onboarding.py`,
`nights/2026-09-14-CODEX-ONBOARDING-DESIGN.md`,
`nights/2026-09-15-CURSOR-DESIGN-ONBOARDING.md`, `native/presence/app.py`
(2 391 lignes), `native/presence/hyper-ambient.bat`, `.env.example`,
`requirements.txt`, `requirements-extra.txt`, `docker-compose.yml`,
`dev/scripts/carte_figee.env`, `dev/scripts/relance_hostagent.sh`.
Lus partiellement, sur le chemin critique : `native/hostagent/talk.py`,
`native/hostagent/windows_audio.py`, `src/i18n/__init__.py`,
`native/presence/overlay.py`, `dev/scripts/serve_hostagent.py`,
`workers/night_health_vault_note/handlers.py`.

### ⚠ Les numéros de ligne sont datés

`native/presence/app.py` a été **réécrit deux fois pendant cette analyse**
(20:29:08 → 87 839 o ; 20:37:08 → 88 008 o), et il est passé de 2 288 à 2 391
lignes sous mes yeux. Tous les numéros de ligne de ce rapport valent pour :

| Fichier | Taille | LastWriteTime |
|---|---|---|
| `native/presence/app.py` | 88 008 o | 2026-09-20 20:37:08 |
| `native/presence/onboarding.py` | 8 352 o | 2026-09-20 16:48:58 |
| `native/presence/sante.py` | 1 919 o | 2026-09-19 14:21:10 |
| `native/presence/platform_ui.py` | 13 835 o | 2026-09-20 20:07:55 |
| `native/presence/overlay.py` | 29 925 o | 2026-09-20 10:40:34 |
| `native/presence/hyper-ambient.bat` | 408 o | 2026-09-20 10:41:19 |
| `native/hostagent/talk.py` | 25 028 o | 2026-09-19 19:01:56 |
| `native/hostagent/windows_audio.py` | 17 549 o | 2026-09-20 20:26:10 |
| `src/i18n/__init__.py` | 24 285 o | 2026-09-20 20:11:20 |
| `dev/scripts/serve_hostagent.py` | 74 442 o | 2026-09-20 20:13:20 |
| `dev/scripts/relance_hostagent.sh` | 5 154 o | 2026-09-20 14:01:47 |
| `dev/scripts/carte_figee.env` | 735 o | 2026-09-20 19:41:36 |
| `docker-compose.yml` | 2 265 o | 2026-08-28 03:04:19 |
| `requirements.txt` | 682 o | 2026-08-21 16:50:46 |
| `workers/night_health_vault_note/handlers.py` | 10 858 o | 2026-09-19 14:18:06 |

**Revérifier chaque ligne avant d'appliquer un correctif.** Deux de mes constats
ont déjà changé de statut pendant la rédaction : le bouton Stop, qui était inerte
pendant une attente silencieuse, a été corrigé à 20:29 (`recv(timeout=0.05)`), et
un argument `--journal` est apparu à 20:37.

## 1. Verdict

**Le wizard lui-même est solide.** Il ne touche ni au micro ni au réseau, il
démarre avant toute connexion, sa configuration est défensive, et l'architecture
Tk est saine : tout le réseau et tout l'audio sont dans un fil, l'UI ne fait
jamais d'appel bloquant. Contrairement à ce que la mission redoutait, **il n'y a
aucun appel réseau sur le fil Tkinter** — je le vérifie au §5.

**Le chemin d'échec, lui, n'est pas solide.** Trois familles de problèmes :

1. **L'échec n'a pas de filet visible.** Le lanceur officiel est
   `start "" pythonw app.py` : pas de console. Toute exception avant ou pendant
   `tk.Tk()` produit **zéro pixel et zéro message**. Ce n'est pas théorique :
   `tk.Tk()` a échoué pour de vrai sur ce poste pendant mon analyse (§6).
2. **Les diagnostics sont faux, perdus ou effacés.** `SystemExit` n'est pas une
   `Exception` et remonte comme « Arrêt audio : 1 » ; l'échec du haut-parleur
   dit « Vérifiez le micro » ; le refus de poignée de main accuse le port alors
   que la cause est le secret ; appuyer sur Parler efface l'erreur affichée.
3. **La fenêtre ne sait pas dire « ça démarre, attends ».** Le serveur charge les
   modèles **avant** d'ouvrir le port — jusqu'à **180 s** d'après le script
   officiel de relance. Pendant ce temps Presence affiche en boucle
   « Impossible de joindre ws://127.0.0.1:8001 », ce qui se lit comme
   « le serveur est mort », et pousse à relancer — ce qui aggrave.

Le risque n°1 pour le 25 n'est pas un plantage : c'est **une fenêtre vivante qui
raconte autre chose que la vérité**, devant un jury.

## 2. Ce qui tient déjà — à ne pas casser

Consigné parce que plusieurs correctifs proposés ci-dessous pourraient le
détruire par accident :

- **Le wizard ne dépend de rien.** `SessionVocale` n'est démarrée qu'à la fin de
  `_afficher_application` (`app.py:1895`), jamais pendant les 4 écrans. Docker
  éteint, micro absent, réseau coupé : le parcours se termine quand même.
  Conforme au design Codex du 14.
- **Aucun `KeyError` d'i18n n'est possible.** `t()` (`src/i18n/__init__.py:485`)
  retombe sur `_FR.get(key, key)` : une clé manquante affiche la clé, elle ne
  tue pas la fenêtre. J'ai vérifié une à une les 55 clés consommées par
  `app.py`/`onboarding.py` contre `ui()` (`src/i18n/__init__.py:499`) :
  **toutes existent**, et tous les gabarits `.format()` ont les bons champs
  (`{raccourci}`, `{n}`, `{ms:.0f}`, `{indice}`, `{total}`). Aucun risque ici.
- **Config défensive.** `charger_configuration` (`onboarding.py:88-101`) attrape
  `OSError`/`UnicodeError`/`JSONDecodeError` et le JSON non-dict ; écriture
  atomique par fichier temporaire + `replace`.
- **`127.0.0.1` et jamais `localhost`** (`app.py:69`, `talk.py:31`), avec le
  piège IPv6/WSL `networkingMode=mirrored` documenté et mesuré le 2026-08-26.
  C'est exactement le bon choix pour un premier lancement.
- **`tic()` réarme sur `Exception`** (`app.py:2279-2282`) : une erreur de dessin
  ne gèle pas l'UI. (La branche `TclError`, elle, le fait — voir N1-3.)
- **`deposer()` jette les messages après l'arrêt** (`app.py:577-579`) : pas
  d'écriture dans une file d'une UI déjà détruite.
- **La sonde de santé n'écrit aucun fichier** quand elle est appelée avec `{}`
  (`handlers.py:193-195`, `snapshotPath` absent), tous ses sondages ont un
  timeout (1,5 s et 5,0 s), et si son import échoue le fil meurt silencieusement
  sans emporter l'app (`app.py:2160-2163`).
- **`sante.py:35` ne réagit qu'à `DEGRADED`**, et la sonde ne produit que `UP` ou
  `DEGRADED` (`handlers.py:166`) : pas d'angle mort où un état pire serait moins
  signalé. Contraste du bandeau `#fff8e8` sur `#7a1212` ≈ 8,9:1, conforme AA.
- **`platform_ui.py` ne lève jamais** (filets larges, replis explicites) — mais
  n'est importé par personne (§N3-4).

## 3. NIVEAU 1 — ÉCRAN NOIR OU GEL (la démo est morte)

### N1-1 · Toute exception au démarrage = aucun signe de vie, et parfois aucune trace

**Cause.** `main()` (`app.py:2381-2386`) est `analyser_arguments` →
`assurer_stdio(args.journal)` → `Application(args).boucler()`, **sans aucun
try/except**. Le lanceur officiel (`native/presence/hyper-ambient.bat`) est
`start "" pythonw native\presence\app.py` : pas de console, pas de `pause`. Sous
`pythonw`, `sys.stdout`/`sys.stderr` sont `None` : un traceback non intercepté
n'arrive nulle part.

Deux sous-cas, à distinguer :

- **N1-1a — mort sans aucune trace.** `assurer_stdio()` fait
  `journal.parent.mkdir(parents=True, exist_ok=True)` (`app.py:89`) puis
  `open(journal, "a", …)` (`app.py:90`) **hors de tout try/except**. C'est la
  première instruction de `main()`. Si `%LOCALAPPDATA%` (ou le repli
  `Path.home()`, `app.py:84-88`) est protégé, redirigé vers un lecteur réseau
  hors ligne, saturé, ou si `hyper-ambient` existe comme fichier et non comme
  dossier → `OSError` → le processus meurt **avant que le journal n'existe**, et
  comme `sys.stderr` est encore `None`, le traceback est perdu. Le mécanisme
  censé tout tracer est le seul qui puisse mourir sans laisser de trace.
- **N1-1b — trace dans le journal, rien à l'écran.** Une fois `assurer_stdio()`
  passé, tout échec (`tk.Tk()` en `app.py:960`, imports de tête
  `import overlay as visuel` en `app.py:34` et `from onboarding import …` en
  `app.py:36`) écrit bien dans
  `%LOCALAPPDATA%\hyper-ambient\presence.log`, mais **l'utilisateur ne voit
  rien** : double-clic, et il ne se passe rien.

**Ce que voit l'utilisateur.** Rien. Pas de fenêtre, pas de dialogue d'erreur,
pas de console. Le geste de secours documenté dans le `.bat`
(`python -u native\presence\app.py`) suppose de savoir ouvrir un terminal — ce
n'est pas le scénario « machine vierge devant jury ».

**Déclencheurs réels sur poste vierge.** Python installé sans Tcl/Tk (paquet
*embeddable*, ou install minimal) ; Tcl/Tk instable (observé ici, §6) ; déploiement
par copie qui oublie `overlay.py`/`sante.py`/`onboarding.py` ; profil utilisateur
verrouillé ; `assets/` absent n'est **pas** un déclencheur (bien gardé,
`app.py:969-980`).

**Correctif minimal.** Deux filets, ~12 lignes, sans effet sur le chemin nominal :

1. Mettre le corps de `assurer_stdio()` (lignes 89-90) dans un try/except qui
   retombe sur `Path(tempfile.gettempdir()) / "hyper-ambient-presence.log"`, et
   si même cela échoue, continuer avec `sys.stdout = sys.stderr = None`
   (`journaliser()` sait déjà gérer `None`, `app.py:101-110`).
2. Dans `main()`, envelopper `Application(args).boucler()` et afficher une boîte
   native avant de sortir — `ctypes` est déjà importé en tête (`app.py:23`) :
   ```python
   try:
       Application(args).boucler()
   except BaseException:
       import traceback
       detail = traceback.format_exc()
       journaliser(detail)
       try:
           ctypes.windll.user32.MessageBoxW(
               0, detail[-1200:], "hyper-ambient — démarrage impossible", 0x10)
       except Exception:
           pass
       raise SystemExit(1)
   ```
   `BaseException` et pas `Exception` : `tk.TclError` est bien une `Exception`,
   mais `SystemExit`/`KeyboardInterrupt` doivent aussi laisser une trace visible.

**Variante sans code**, si `app.py` est gelé d'ici le 25 : remplacer dans le
`.bat` `start "" pythonw` par `start "" python -u` — la console reste ouverte et
le traceback devient visible. Coût : une fenêtre noire à l'écran pendant la démo.
À ne faire qu'en repli de diagnostic.

---

### N1-2 · La fenêtre fait 800 px de haut et ne connaît pas la zone de travail

**Cause.** `self.racine.geometry("520x800")` et `self.racine.minsize(440, 700)`
(`app.py:987-988`). Aucun appel à `platform_ui.aire_utile()` — qui existe
(`platform_ui.py:350`), qui est documenté « ne rend jamais None », et qui
**n'est importé par personne**. Aucun réglage de conscience DPI
(`SetProcessDpiAwareness`/`shcore`) nulle part dans le dépôt : Windows virtualise
donc l'échelle.

**Ce que voit l'utilisateur.** Sur un vidéoprojecteur de salle en 1280×720, la
zone de travail utile fait ~680 px de haut. La fenêtre en demande 800, et
`minsize(440, 700)` **interdit de descendre sous 700** : elle ne peut pas être
redimensionnée pour tenir. Le panneau du bas (`vitre`, `expand=True`) s'effondre
alors à ~0 px, et il contient : la ligne d'état `ligne_etat`
(`app.py:1857-1867`, packée `side=tk.BOTTOM`), les zones « Compris »
(`app.py:1845`) et « Réponse » (`app.py:1855`), donc **tout le texte**. Le bouton
Parler reste atteignable, mais :

- le jury ne voit plus aucune transcription ni aucune réponse — la promesse a11y
  « transcriptions, réponses et appel distant restent affichés en texte »
  (`src/i18n` `ui.a11y`) est rompue exactement au moment où on la démontre ;
- le présentateur ne voit plus **aucune erreur** ;
- « Masquer la configuration » et « Un retour » peuvent passer sous l'écran.

Sur un portable 1366×768 ou à 125 %/150 % de mise à l'échelle (défaut courant),
même mécanisme, aggravé : 800 px logiques deviennent 1000-1200 px physiques.

**Correctif minimal.** Trois mouvements, ~10 lignes, en réutilisant ce qui est
déjà livré :

1. `import platform_ui` et borner la géométrie :
   `g, h, d, b = platform_ui.aire_utile(self.racine)` puis
   `largeur = min(520, d-g-40)`, `hauteur = min(800, b-h-40)`, et
   `self.racine.geometry(f"{largeur}x{hauteur}+{g+20}+{h+20}")` — la position
   explicite garantit que la barre de titre est sur l'écran.
2. `self.racine.minsize(380, 420)` : laisser l'utilisateur sauver la démo en
   réduisant.
3. **Le plus important** : sortir `ligne_etat` du panneau `vitre` extensible et
   la packer directement dans `cadre` avec `side=tk.BOTTOM` **avant** `vitre`,
   pour que le statut survive à l'effondrement. Une ligne d'état qui disparaît
   quand la fenêtre est petite est un défaut de robustesse, pas de mise en page.

---

### N1-3 · Une seule `TclError` dans `tic()` gèle définitivement l'animation **et** la ligne d'état

**Cause.** `tic()` (`app.py:2260-2284`) porte le commentaire « after() doit
toujours être réarmé : une exception dans le dessin gèlerait l'interface, y
compris la ligne d'état » — puis :

```python
        except tk.TclError:      # app.py:2277
            return               # ← sort SANS réarmer
        except Exception as exc: # app.py:2279
            journaliser(f"tic : {exc}")
        try:
            self.racine.after(visuel.INTERVALLE_MS, self.tic)   # app.py:2282
```

La branche `Exception` retombe bien sur le réarmement ; la branche `TclError`
**contredit le commentaire**. Or `tic()` est l'unique consommateur de la file UI
(`_traiter`, `app.py:2286`) : statut, erreurs, transcripts, états de la bulle,
éclair, indicateur de conversation. Une `TclError` → plus rien n'est jamais
traité ni repeint, alors que la fenêtre reste ouverte et cliquable. C'est la
définition même du gel qui passe pour un plantage. Les messages déjà en file
sont perdus au passage (la boucle `while True: get_nowait()` est interrompue).

**Accessibilité du déclencheur — je la donne honnêtement : latente, pas
atteignable par les chemins livrés aujourd'hui.** Les ingrédients sont en place :
`_vider()` (`app.py:1020-1037`) détruit les enfants du conteneur mais ne remet
pas à `None` `ligne_etat`, `zone_compris`, `zone_reponse`, `bouton`, `toile`,
`toile_eclair`, `bouton_masquer`, `bouton_feedback` — tous créés seulement dans
`_afficher_application`. Et `_afficher_statut` (`app.py:1956-1961`) se protège
avec `getattr(self, "ligne_etat", None) is None` : **un widget détruit n'est pas
`None`**, donc `configure()` lève `TclError`. Aucun chemin de l'UI actuelle ne
rappelle `_vider()` après `_afficher_application`, donc le gel ne se déclenche
pas aujourd'hui. Il se déclenchera au premier retour-au-wizard, changement de
vue, ou re-thémage contraste à chaud. J'ai aussi vérifié la source de `TclError`
la plus probable côté dessin et elle est **fermée** : `vers_hex`
(`overlay.py:182-187`) clampe à 0-255 et évite même la collision avec la clé de
chroma `(1,2,3)`, donc aucune couleur invalide ne peut sortir de
`melanger_palettes`.

**Correctif minimal.** Ne plus traiter toute `TclError` comme « la racine est
morte » :

```python
        except tk.TclError:
            try:
                if not self.racine.winfo_exists():
                    return
            except Exception:
                return
            journaliser("tic : TclError, boucle maintenue")
        except Exception as exc:
            journaliser(f"tic : {exc}")
```

Et, indépendamment, compléter `_vider()` avec les 8 attributs manquants mis à
`None`. Coût total ~10 lignes ; bénéfice : la seule classe d'erreur capable de
geler l'UI pour toute la session devient récupérable.

---

### N1-4 · La séquence de démarrage compte six étapes manuelles, et l'app n'en vérifie aucune

**Cause.** Rien dans `app.py` ni dans `hyper-ambient.bat` ne vérifie ni ne
démarre quoi que ce soit en amont. Le `.bat` porte seulement le commentaire
« Le serveur doit tourner dans mother-core-dev. » Or la chaîne réelle est :

1. créer `.env.local` (`.env.example:1` : « Copy to .env.local and fill in » —
   aucune commande ne le fait) ; **`docker-compose.yml:12-13` le déclare en
   `env_file`, donc `docker compose up` échoue franchement s'il manque** ;
2. `docker compose up -d` — qui exige une réservation GPU
   `driver: nvidia, count: 1` (`docker-compose.yml:24-30`) ;
3. le conteneur démarre sur `command: /bin/bash` (`docker-compose.yml:57`) :
   **compose ne lance pas le serveur** ;
4. entrer dans le conteneur et lancer `dev/scripts/relance_hostagent.sh` ;
5. attendre la fin du chargement des modèles — le script officiel attend
   `écoute sur 0.0.0.0:8001` pendant **180 iterations de 1 s**
   (`relance_hostagent.sh:105-118`), et cette ligne n'est imprimée qu'**après**
   `pipeline.load()` + `prechauffer()` dans le `lifespan`
   (`serve_hostagent.py:1745-1760`) — donc uvicorn n'ouvre le port qu'à la fin ;
6. seulement alors, double-cliquer `hyper-ambient.bat`.

**Ce que voit l'utilisateur.** Pendant les étapes 1 à 5, et pendant toute la
durée de l'étape 5, Presence affiche en boucle (toutes les 2 s,
`app.py:691`) :
`Impossible de joindre ws://127.0.0.1:8001/hostagent : [WinError 10061] …`.
Ce message dit « le serveur est mort », alors qu'à l'étape 5 il dit la vérité
inverse : **il démarre, il faut attendre jusqu'à trois minutes**. Rien dans l'UI
ne distingue les deux. Le réflexe naturel — relancer — repart pour 180 s.

**Gravité.** La fenêtre reste vivante, donc ce n'est pas au sens strict un écran
noir ; mais je le classe ici parce que c'est, de très loin, **la façon la plus
probable que la démo meure le 25**, et que l'échec est illisible.

**Correctif minimal.** Côté Presence, deux choses peu coûteuses :

1. Traduire le refus de connexion et le rendre patient
   (`app.py:683-689`) : si `isinstance(exc, ConnectionRefusedError)` ou
   `"10061" in str(exc)` → « Le serveur hyper-ambient n'écoute pas encore sur le
   port 8001. S'il démarre, le chargement des modèles prend jusqu'à trois
   minutes. » et afficher un compteur d'essais.
2. Ajouter un `--diagnostic` qui sonde une fois `127.0.0.1:8001`,
   `:8090/health`, `:8765`, `:8766` en stdlib avec timeout 1,5 s (le code existe
   déjà : `handlers.sonder_url`, `handlers.py:39-49`) et affiche une checklist
   textuelle dans la fenêtre. Cinq lignes de réutilisation, et cela transforme
   « ça ne marche pas » en « il manque l'étape 4 ».

Côté organisation, et c'est le vrai correctif : **répéter la séquence complète
sur le poste du jury**, chrono en main, et écrire les six étapes dans un fichier
unique à côté du `.bat`.

## 4. NIVEAU 2 — DÉGRADÉ MAIS VIVANT

### D2-1 · `SystemExit` n'est pas une `Exception` : micro refusé → « Arrêt audio : 1 », et le fil meurt

C'est le défaut le plus coûteux de tout ce rapport, et le plus probable.

**Cause, chaîne complète.** `_servir` n'ouvre **pas** le micro :
`PushToTalkCapture(stream_factory=fabrique)` (`app.py:630`) et
`CaptureContinue(stream_factory=fabrique)` (`app.py:633`) ne font que mémoriser
la fabrique (`windows_audio.py:121-131` et `217-232`, `self._stream = None`).
Le micro n'est ouvert qu'à `capture.start()` — `app.py:728` en maintien,
`app.py:793` en mains libres — qui appelle `windows_audio.py:161`, donc la
fabrique de `talk.py:_fabrique_entree`, dont le `except` fait
`_echouer_peripherique(exc)` → `print(decrire_erreur_peripherique(exc))` +
`raise SystemExit(1)` (`talk.py:226-227`).

`SystemExit` hérite de `BaseException` : le `except Exception as exc:` de la
boucle WebSocket (`app.py:682`) **ne l'attrape pas**. Elle traverse les deux
`finally` (`app.py:692-706`) et remonte jusqu'à `run()` :

```python
        except SystemExit as exc:                                    # app.py:595
            self.deposer({"type": "erreur", "texte": f"Arrêt audio : {exc}"})  # 597
```

`str(SystemExit(1))` vaut `"1"`.

**Ce que voit l'utilisateur.** La ligne d'état affiche **« Arrêt audio : 1 »**.
Le vrai diagnostic — « Le périphérique audio a refusé l'ouverture. Lancez
--lister… » (`talk.py:145-149`) — est `print`é dans `presence.log` et n'atteint
jamais l'écran ; `--lister` n'existe d'ailleurs pas dans l'UI. Et le fil
`session-vocale` est **mort** : aucune reconnexion, `canal_pret` jamais levé,
donc chaque appui sur Parler affiche « Canal pas encore prêt. »
(`app.py:1978-1981`) jusqu'à fermeture de l'app.

**Déclencheurs.** Micro refusé par Windows (Paramètres → Confidentialité →
Microphone), micro en mode exclusif occupé par Teams/Zoom, périphérique retiré
entre l'énumération et l'ouverture, casque USB débranché après le wizard.
**En mains libres, ça tire dès la connexion** (`app.py:793`), sans aucun geste :
donc immédiatement après « Commencer ».

**Correctif minimal.** Deux niveaux :

- *2 lignes, à faire quoi qu'il arrive* : en `app.py:597`, remplacer
  `f"Arrêt audio : {exc}"` par un texte qui nomme la cause probable et l'action :
  « Le micro a refusé de s'ouvrir. Vérifiez l'accès au microphone dans
  Paramètres → Confidentialité et pertinence, puis relancez l'application. »
- *le vrai correctif, ~8 lignes* : dans `_boucle_tours`, entourer
  `capture.start()` (`app.py:728`) d'un `try/except BaseException` qui relaie
  `moteur.decrire_erreur_peripherique(exc)` via `deposer`, puis `continue` après
  `self.arreter.wait(2.0)` — symétrique de ce que la boucle WebSocket fait déjà.
  Le canal reste alors en réessai au lieu de mourir, et l'utilisateur n'a pas à
  relancer l'app.

### D2-2 · Le micro reste ouvert (voyant allumé) si `start()` échoue

**Cause.** `windows_audio.py:161-162` : `self._stream = self._stream_factory(…)`
puis `self._stream.start()`. Si la ligne 162 lève, `_stream` est affecté et
jamais fermé — et côté `app.py`, `capture.start()` (728) n'est **pas** dans un
`try/finally`, contrairement à `_boucle_tours_continus` qui a bien
`finally: capture.stop()` (`app.py:838-839`). De plus `PushToTalkCapture.start()`
réaffecte `self._stream` sans fermer l'ancien.

**Ce que voit l'utilisateur.** Rien à l'écran. Mais l'indicateur Windows « micro
en cours d'utilisation » reste allumé, le périphérique peut passer en « occupé »
pour un second lancement, et le jury voit un voyant micro allumé sur une app
qui paraît inactive — le pire signal possible pour un produit qui promet
« aucun son n'est enregistré pendant cette configuration » (`ui.no_recording`).

**Correctif minimal.** Fermer le flux en cas d'échec de `start()`
(`windows_audio.py:161-162`), et mettre `capture.start()` (`app.py:728`) dans un
`try/finally` symétrique de `_boucle_tours_continus`. ~6 lignes.

### D2-3 · « Vérifiez le micro » est affiché quand c'est le haut-parleur qui a échoué

**Cause.** `app.py:627-642` : un seul `except SystemExit` couvre
`choisir_peripherique` (628, micro), `choisir_sortie` (634) **et**
`_ouvrir_sortie` (635, sortie). Les trois aboutissent au même texte
« Périphérique audio indisponible. Vérifiez le micro. » (`app.py:640`).

**Ce que voit l'utilisateur.** La démo est muette et l'app accuse le micro.
Cas concrets en salle : projecteur HDMI sans audio devenu sortie par défaut,
casque débranché, sortie exclusive. Le détail réel
(« Aucun canal de sortie disponible sur ce périphérique. », `talk.py:151-156`)
part dans le journal.

**Correctif minimal.** Scinder le bloc en deux try/except — micro d'un côté,
sortie de l'autre — avec « Aucun haut-parleur utilisable. » côté sortie. ~6
lignes, et cela évite de faire chercher au présentateur un problème de micro
pendant trois minutes devant le jury.

### D2-4 · Poignée de main : `recv()` sans timeout, blocage illimité

**Cause.** `talk.py:478-488` : `ws.send(hello)` puis `brut = ws.recv()` —
**aucun timeout**. `connect()` (`app.py:648`) bénéficie de l'`open_timeout`
par défaut de websockets (10 s) pour la négociation, mais une fois la socket
ouverte l'attente du `ready` est illimitée.

**Ce que voit l'utilisateur.** « Connexion… » (`app.py:933`) **indéfiniment**.
La fenêtre respire, l'orbe tourne : rien ne distingue « ça charge » de « c'est
mort ». Parler affiche « Canal pas encore prêt. ». Aucune erreur, aucune relance.
Seule issue : fermer.

**Cas réels.** Le serveur accepte le TCP mais le cerveau n'est pas prêt ;
pare-feu/proxy qui accepte puis avale ; et le piège déjà mesuré du dépôt —
`talk.py:24-30` documente qu'avec `.wslconfig` en `networkingMode=mirrored`,
`localhost`/`::1` **ouvrent la poignée puis expirent sans réponse**, alors que
`127.0.0.1` répond. Si quelqu'un retape l'URL à la main en `localhost` le jour
J, on retombe exactement ici.

**Correctif minimal.** `ws.recv(timeout=5.0)` avec le repli `TypeError` déjà
utilisé ailleurs (`app.py:266-268` et `app.py:557-561` le font), puis
`raise SystemExit(1)` : le bloc `except SystemExit` d'`app.py:653-662` affiche
déjà un message et relance toutes les 2 s. ~3 lignes, et un blocage silencieux
devient une boucle de diagnostic visible.

### D2-5 · Aucun délai maximal par tour : un cœur muet rend l'assistante définitivement sourde

**Cause.** `consommer_reponse` (`app.py:206-338`) ne sort que sur `frames == []`
(`app.py:309`), sur exception socket (`app.py:272-273`), ou sur `arreter`.
Le `while not arreter.is_set()` (`app.py:260`) tourne à 20 Hz sur
`recv(timeout=0.05)`. **Aucune échéance globale.**

Progrès à porter au crédit de la réécriture de 20:29 : `_trancher_interruption()`
(`app.py:232-258`) est maintenant appelé sur timeout, donc **le bouton Stop
fonctionne pendant une attente silencieuse** — ce n'était pas le cas avant.
Mais il coupe l'audio et affiche « Interrompue. » **sans terminer le tour** :
sur timeout il fait `continue` (`app.py:269-271`), sur trames `continue`
(`app.py:310`). Tant que le serveur n'envoie pas son marqueur vide, la boucle
reste dedans.

**Conséquence.** Si le conteneur thrash (VRAM saturée, repli CPU, modèle en
cours de chargement) sans fermer la socket, le tour reste ouvert indéfiniment.
`en_lecture` reste levé (`app.py:777`, `app.py:869`) → en mains libres
`capture.regime_lecture(True)`/`suspendre()` garde le micro suspendu → **plus
aucune détection de voix** ; en maintien, `_boucle_tours` ne revient jamais à
l'attente de `tenu` → les appuis suivants sont ignorés.

**Ce que voit l'utilisateur.** L'orbe respire, la ligne d'état reste sur
« Interrompue. » ou « N trames envoyées, attente de la réponse… », Parler ne fait
plus rien. Fenêtre parfaitement vivante, produit mort. Seule la fermeture s'en
sort (`fermer()` → `demander_arret()` → `ws.close()` débloque `recv`).

**Correctif minimal.** Une échéance dans `consommer_reponse` : horodater le
dernier message reçu, et si rien n'est arrivé depuis 45 s (assez pour un
chargement de modèle, assez court pour ne pas paraître mort), poster
`{"type": "erreur", "texte": "Le moteur n'a pas répondu depuis 45 s."}` et
`return`. ~6 lignes.

### D2-6 · Coupure en plein tour : `canal_pret` reste levé sur une socket morte

**Cause.** `app.py:272-273` : `except Exception: return barge_in` — retour
**silencieux**, aucune erreur postée. Et `canal_pret` n'est effacé que dans le
`finally` d'`app.py:692-694`, qui ne s'exécute qu'à la sortie du bloc
`with connect(…)`. Or après un retour de `consommer_reponse`, `_boucle_tours`
revient attendre `tenu` **à l'intérieur** du bloc `with` : `canal_pret` reste
donc levé sur une connexion cassée.

**Ce que voit l'utilisateur.** La ligne d'état reste sur « N trames envoyées,
attente de la réponse… » ; l'app a l'air connectée. L'utilisateur appuie sur
Parler, l'orbe passe en écoute, le micro capture, puis `ws.send` lève →
« Impossible de joindre … » (`app.py:687`) → 2 s → reconnexion. **Un tour entier
est perdu**, et cela ressemble à un bug aléatoire.

**Déclencheur identifié dans le dépôt.** `docker-compose.yml:44-49` plafonne le
conteneur à `mem_limit: 8g` avec ce commentaire : « Measured on 2026-08-25:
loading a 4.9 GB GGUF here killed the daemon. With this cap an OOM kills the
container alone (exit 137). » Un OOM en pleine réponse, c'est exactement ce cas —
et rien dans l'UI ne dira « le cœur a été tué (exit 137), relancez-le ».

**Correctif minimal.** Dans `consommer_reponse`, poster une erreur explicite
avant le `return` (272) et remonter un signal « canal cassé » qui fait sortir
`_boucle_tours` du bloc `with` (lever une exception dédiée suffit : elle sera
attrapée par `app.py:682`, qui efface `canal_pret` et relance). ~4 lignes.

### D2-7 · Appuyer sur Parler efface le diagnostic

**Cause.** `app.py:1978-1981` : si `canal_pret` n'est pas levé,
`_afficher_statut(ui_presence()["channel_not_ready"])` **écrase** la ligne
d'état, qui portait jusqu'ici la vraie cause. Il n'y a qu'une ligne d'état, pas
d'historique ; la seule trace durable est `presence.log`.

**Ce que voit l'utilisateur.** Plus il essaie, plus l'explication disparaît.
Devant un jury, le réflexe du présentateur est précisément de ré-appuyer : il
efface la seule information disponible.

**Correctif minimal.** Mémoriser la dernière erreur (`self.derniere_erreur`
alimenté dans `_traiter`, `app.py:2187`) et, tant que le canal n'est pas prêt,
l'afficher à la place de « Canal pas encore prêt. » — ou les deux. ~5 lignes.

### D2-8 · `sounddevice` n'est déclaré dans aucun fichier d'exigences

**Cause.** Grep `sounddevice` sur tous les `*.txt` du dépôt : **zéro résultat**.
`requirements.txt` (lu intégralement, 682 o) liste numpy, scipy, librosa,
soundfile, websockets, torch, transformers, openai, anthropic,
google-generativeai, python-dotenv, pyyaml, loguru, click, pytest — pas de
`sounddevice`. `requirements-extra.txt` non plus (faster-whisper, av, qwen-asr,
bitsandbytes, silero-vad, piper-tts, onnxruntime-gpu, pyloudnorm). Il n'existe
que ces deux fichiers (`glob **/requirements*.txt`), tous deux orientés
conteneur : **aucun fichier d'exigences pour l'hôte Windows**, qui est pourtant
le seul à avoir besoin de `sounddevice`.

**Preuve que l'écart est invisible ici.** Sur ce poste : `python 3.13.14`,
`numpy 2.3.5`, `websockets 15.0.1`, `sounddevice 0.5.6`. Or `requirements.txt`
épingle `numpy==1.24.3` et `websockets==12.0`. L'environnement hôte réel
**n'est décrit nulle part** et ne correspond à aucun fichier du dépôt.

**Ce que voit l'utilisateur.** Sur une machine préparée par
`pip install -r requirements.txt` : le wizard se termine normalement, puis
« sounddevice ou websockets absent sur l'hôte. » (`app.py:622`, via
`talk.py:52-63`) et le canal ne s'ouvre jamais. Le message est honnête et en
français — bon point — mais l'échec est garanti par la documentation elle-même.

**Aggravant.** Les épingles de `requirements.txt` sont antérieures à Python 3.13 :
`numpy==1.24.3`, `torch==2.0.0`, `pydantic==2.5.0` n'ont pas de roue cp313
(support 3.13 ajouté dans numpy 2.1). Sur une machine vierge avec un Python
récent, l'installation **elle-même** échoue ou tente une compilation depuis les
sources. *Déduction : je n'ai pas exécuté d'installation pour le confirmer.*

**Correctif minimal.** Créer `requirements-host.txt` avec `sounddevice` et
`websockets` épinglés aux versions réellement utilisées (0.5.6 / 15.0.1 ici), et
le référencer dans `SETUP.md` + dans le commentaire du `.bat`. **C'est le
correctif le moins cher de tout ce rapport : deux lignes.**

### D2-9 · `.env.local` absent : `docker compose` refuse de démarrer, et l'app ne dit rien

**Cause.** `.gitignore:52-53` ignore `.env` et `.env.local` → absents d'un clone
vierge. `docker-compose.yml:12-13` déclare `env_file: - .env.local` : Compose
échoue si le fichier manque (sauf `required: false`, non utilisé ici). De plus
`docker-compose.yml:37` monte `./.env.local:/workspace/.env.local:ro` : si
`env_file` était retiré sans créer le fichier, Docker Desktop créerait à la
place un **répertoire** nommé `.env.local`, ce qui casserait ensuite
`_appliquer_env_boot` (`serve_hostagent.py:208-219`) de façon très obscure.

**Côté Presence, l'absence est bien tolérée.** `talk.py:37-49` : sans
`MOTHER_HOSTAGENT_SECRET`, avertissement sur stderr puis retour de
`SECRET_DEVELOPPEMENT = "partage-installation"` (`talk.py:29`). **L'app ne
plante pas pour cette seule absence** — c'est le bon comportement.

**Mais le message d'échec est faux — et pas de la façon que j'avais d'abord
écrite.** Je l'ai revérifié côté serveur : `src/hostagent/transport.py:92-105`
fait `await websocket.accept()`, puis sur `ChannelRefused` (secret faux,
`src/hostagent/channel.py:53-54`, ou adresse non-loopback, `channel.py:50-51`)
appelle `_fermer_admission(websocket)` et `return` — **sans rien envoyer**. Le
`ws.recv()` du client (`talk.py:480`) lève donc une `ConnectionClosed`, pas un
JSON non-`ready`. Conséquence : la branche « Poignée de main refusée. Le serveur
tourne-t-il sur le port 8001 ? » (`app.py:653-662`) est **inatteignable** avec le
transport actuel ; un secret faux tombe dans le `except Exception` générique
(`app.py:682`) et affiche **« Impossible de joindre ws://127.0.0.1:8001/hostagent
: … »** — c'est-à-dire « le serveur est injoignable » alors qu'il tourne et nous
rejette. En boucle toutes les 2 s. L'avertissement
« MOTHER_HOSTAGENT_SECRET est absent » reste dans le journal.

Aggravant vérifié : **`MOTHER_HOSTAGENT_SECRET` ne figure pas dans
`.env.example`** (lu intégralement ; grep `SECRET` : zéro résultat). L'opérateur
de bonne foi qui recopie le modèle fourni ne peut donc pas définir ce secret, et
n'a aucun moyen de savoir qu'il existe. Les deux côtés retombent alors sur le
même `SECRET_DEVELOPPEMENT` (`talk.py:29` et `serve_hostagent.py:520-531`) et la
poignée passe — le désaccord n'apparaît que si la variable est posée d'un seul
côté, ce qui est justement le cas le plus probable : `.env.local` est monté dans
le conteneur (`docker-compose.yml:37`) mais **n'est lu par personne côté hôte
Windows** (`talk.py:39` lit `os.environ` uniquement, aucun `dotenv` dans
`talk.py` ni dans `app.py`).

**Ce que voit l'utilisateur.** « Impossible de joindre … » en boucle, alors que
le serveur est vivant et refuse l'authentification. Aucune indication sur le
secret, ni sur le fichier à créer.

**Correctif minimal.** (a) Une ligne `MOTHER_HOSTAGENT_SECRET=` dans
`.env.example`, et un `make install-local` qui copie le modèle vers `.env.local` ;
(b) côté client, faire remonter à `_servir` la distinction « connexion refusée »
/ « connexion fermée pendant la poignée » et écrire, pour le second cas,
« Le serveur a rejeté l'authentification : vérifiez MOTHER_HOSTAGENT_SECRET. » ;
(c) afficher une fois « secret de développement utilisé » quand
`lire_secret()` retombe sur le repli (`talk.py:37-49` le sait déjà, il ne fait
que l'imprimer). ~8 lignes au total.

### D2-10 · Clés API vides : démarrage correct, échec différé au pire moment

**Cause.** `.env.example` livre `BRAIN_API_KEY=`, `TAVILY_API_KEY=`,
`BRAVE_API_KEY=`, `EXA_API_KEY=`, `JINA_API_KEY=`, `SERPER_API_KEY=`,
`CODEX_BRIDGE_TOKEN=`, `CLI_BRIDGE_TOKEN=`, `MUSE_BRIDGE_URL=`,
`ANTHROPIC_API_KEY=`, `OPENAI_API_KEY=` **toutes vides**. Et
`relance_hostagent.sh:22-48` les lit avec `lire_fichier … || true` sous
`set -eu` : une clé vide **n'arrête pas** le script. Il imprime simplement
`cle brain de 0 caracteres` (ligne 66) et `config outils: searxng=… tavily=non
codex=non claude=non muse=non` (ligne 68) — dans le stdout du conteneur, jamais
dans Presence.

Deux comportements distincts, à connaître :

- **Bien conçu :** `.env.example:29-31` précise « Un outil reste absent du
  registre si son URL/jeton requis est vide. » Donc pas d'outil web/pont =
  dégradation propre, pas d'erreur.
- **Piège :** `.env.example:11` pose `BRAIN_SERVICE=stepfun` (distant) avec
  `BRAIN_API_KEY=` vide. Sans la carte figée, le premier tour part vers StepFun
  sans clé → échec d'authentification **au premier tour de parole**, pas au
  démarrage. La carte figée (`carte_figee.env`) bascule sur
  `BRAIN_SERVICE=llamacpp` + GGUF local, « no key needed » — donc tout repose sur
  le fait que `carte_figee.env` soit bien chargé. `CARTE_FIGEE=0`, un oubli, ou
  un `.env.local` qui pose `BRAIN_SERVICE=stepfun` après la carte, et la démo
  tombe en panne **au moment de parler**, avec l'air d'un caprice.

**Ce que voit l'utilisateur.** Au démarrage, rien d'anormal. Puis un tour qui ne
rend rien, ou une erreur distante brute.

**Correctif minimal.** Ajouter au `--diagnostic` de N1-4 une ligne
« cerveau : llamacpp local / stepfun distant (clé : 32 caractères) », reprise de
`relance_hostagent.sh:66`. Et vérifier, sur le poste du jury, que la carte figée
est bien appliquée — `serve_hostagent.py:1723-1729` imprime
`CARTE : … depuis carte_figee.env` au démarrage : **cette ligne doit apparaître**.

### D2-11 · Pas de GPU : le conteneur ne démarre même pas, et la carte figée impose CUDA

**Cause, deux verrous indépendants.**

1. `docker-compose.yml:24-30` : `deploy.resources.reservations.devices:
   driver: nvidia, count: 1, capabilities: [gpu]`. Sans GPU NVIDIA +
   nvidia-container-toolkit, `docker compose up` échoue (« could not select
   device driver "nvidia" »). Le commentaire du fichier est explicite :
   « without this torch.cuda.is_available() == False ».
2. `carte_figee.env` — la « source de vérité pour le host-agent » — pose
   `EARS_DEVICE=cuda`, `EARS_COMPUTE_TYPE=int8_float16`, `MOUTH_DEVICE=cuda`.
   `.env.example:47` pose aussi `EARS_DEVICE=cuda`. Le script de relance prévoit
   `EARS_DEVICE_FORCE` et `MOUTH_DEVICE_FORCE` (`relance_hostagent.sh:56-63`)
   et `carte_figee.env:4` documente `MOUTH_DEVICE_FORCE=cpu` — **mais il
   n'existe aucune voie CPU documentée pour l'ensemble de la pile**, et
   `requirements-extra.txt` installe `onnxruntime-gpu`.

**VRAM saturée.** Le budget empilé est lourd : `granite-4.2-3b-Q4_K_M.gguf`
(~2 Go) + Whisper `large-v3` en `int8_float16` (~3 Go) + Magpie TTS + silero-vad
ONNX. Sur une carte 8 Go partagée avec un bureau Windows, la saturation est
probable. `docker-compose.yml:44-49` plafonne la mémoire à 8 g et annonce la
couleur : un OOM tue le conteneur en **exit 137**. Côté Presence, cela se
manifeste par D2-6 (socket coupée en plein tour, statut périmé, `canal_pret`
levé) puis par la boucle « Impossible de joindre » — **sans jamais nommer
l'OOM**.

**Ce que voit l'utilisateur.** Soit `docker compose up` refuse (étape 2 de N1-4
impossible), soit la démo meurt en cours de route sans explication.

**Correctif minimal.** (a) **Vérifier que le poste du jury a un GPU NVIDIA** —
c'est la seule action vraiment nécessaire, et elle est organisationnelle ;
(b) prévoir un `docker-compose.cpu.yml` de repli sans la réservation de
périphérique, et une carte `carte_figee.cpu.env` avec `EARS_DEVICE=cpu`,
`EARS_COMPUTE_TYPE=int8`, `MOUTH_DEVICE=cpu`, et un modèle EARS plus petit que
`large-v3` ; (c) côté Presence, détecter la fermeture brutale de la socket
pendant un tour et écrire « Le cœur s'est arrêté (probable manque de mémoire).
Relancez le conteneur. » au lieu de se taire (D2-6).

### D2-12 · Modèles absents : le port ne s'ouvre jamais, et le client dit « impossible de joindre »

**Cause.** `.gitignore:41-42` ignore `models/` et `data/` → vides sur machine
vierge. `relance_hostagent.sh:52` pose `HF_HUB_OFFLINE=1` (et `.env.example:59`
aussi) : **aucun téléchargement au démarrage**, volontairement. Les chemins de
la carte sont des chemins de conteneur (`MODEL=/workspace/models/gguf/
granite-4.2-3b-Q4_K_M.gguf`, `HF_HOME=/workspace/models/hf-cache`,
`LLAMA_CACHE=/workspace/models/gguf`), montés depuis `./models`
(`docker-compose.yml:34`). Enfin, `serve_hostagent.py:1745-1760` charge et
préchauffe **dans le `lifespan`, avant** que uvicorn n'ouvre le port : si
`pipeline.load()` échoue, uvicorn démarre en « Application startup failed.
Exiting. » et **le port 8001 ne s'ouvre jamais**.

**Ce que voit l'utilisateur.** `relance_hostagent.sh:106-109` détecte le cas et
imprime « host-agent mort pendant le demarrage » suivi du journal — mais dans le
conteneur. Côté Presence : « Impossible de joindre ws://127.0.0.1:8001 » en
boucle, indéfiniment. Aucune différence visible avec « Docker éteint ».

**Correctif minimal.** Le `--diagnostic` de N1-4 doit distinguer trois états, et
c'est faisable en stdlib : port fermé (rien n'écoute) / port ouvert mais poignée
muette (le serveur charge) / poignée refusée (secret). Trois causes, trois
phrases. Côté préparation : un contrôle `test -f /workspace/models/gguf/
granite-4.2-3b-Q4_K_M.gguf` dans `relance_hostagent.sh` avant de lancer Python,
avec un message explicite — le script a déjà `set -eu`, il lui manque juste cet
aiguillage.

### D2-13 · La sonde de santé affiche une alerte rouge sans rapport, et vole le focus toutes les 2 s

**Cause, chaîne complète.** `main()` : `if args.sante is None: args.sondes = True`
(`app.py:2385`) → au lancement par double-clic, la sonde est **toujours** active.
`_afficher_application` démarre le fil (`app.py:1886-1892`) → `_boucle_sondes`
(`app.py:2155`) appelle `handle_health_check({})` toutes les 2 s.

Appelée avec `{}`, la sonde utilise `DEFAULT_ENDPOINTS` (`handlers.py:31-36`) :
`pont_codex` :8765, `pont_claude` :8766, `host_agent` :8001, `modele_local`
:8090 — plus Camunda sur `http://127.0.0.1:8088/v2/topology`
(`handlers.py:143`). Sur poste vierge, **tout est refusé**. `en_panne[0]` est
`pont_codex` (`handlers.py:165-168`), donc
`alertMessage = "Le pont vers Codex ne répond plus, je continue en local."`
(`handlers.py:16`, repris comme repli par `sante.py:9`).

Puis `appliquer_etat_sante` (`app.py:2115`) affiche un bandeau `#7a1212` et
appelle `self.bandeau_alerte.focus_set()` **à chaque message** (`app.py:2145`),
donc toutes les 2 secondes.

**Ce que voit l'utilisateur.** Deux secondes après « Commencer », un grand
bandeau rouge annonce que **le pont vers Codex** ne répond pas — sur une machine
où Codex n'a jamais été prévu, et sans un mot sur le vrai problème (le canal
vocal). Et le focus saute sur ce bandeau toutes les 2 s : impossible de tabuler,
impossible de garder le focus sur un réglage ; pour un utilisateur NVDA/Narrator,
le bandeau est ré-annoncé en boucle, ce que le design a11y du 14 voulait
explicitement éviter.

**Pire : cela reste vrai en configuration de démo nominale.** `.env.example:29`
qualifie les ponts d'« optionnels » et `CODEX_BRIDGE_TOKEN=`/`CLI_BRIDGE_TOKEN=`
sont vides → `pont_codex` et `pont_claude` seront en panne **pendant toute la
soutenance**, bandeau rouge permanent compris.

**Correctif minimal, trois niveaux :**

1. *3 lignes, le plus urgent* : ne `focus_set()` qu'à la **transition** vers
   `DEGRADED` (mémoriser l'état précédent dans `appliquer_etat_sante`), pas à
   chaque rafraîchissement.
2. *1 ligne* : ne classer que les composants pertinents pour la voix. La sonde
   accepte déjà `endpoints` dans `variables` (`handlers.py:58-60`) : appeler
   `handle_health_check({"endpoints": [host_agent, modele_local]})` depuis
   `app.py:2165` suffit à faire disparaître Codex/Claude/Camunda du bandeau.
3. *Organisationnel* : décider si le bandeau rouge a sa place pendant la
   soutenance. `--sante` vers un fichier neutre, ou `--sondes` non forcé en
   `app.py:2385`, le désactivent sans toucher au code de la sonde.

**Note annexe, réseau d'établissement scolaire.** `sonder_url` utilise
`urllib.request.urlopen` (`handlers.py:43`) sans `ProxyHandler({})` : urllib
honore le proxy système/registre Windows. Sur un réseau d'école avec proxy et
sans `no_proxy` couvrant 127.0.0.1, **les quatre sondages partent dans le proxy**
au lieu de la boucle locale → tout est déclaré en panne, et chaque itération
peut coûter jusqu'à 5,0 + 4 × 1,5 = 11 s. Correctif : un opener sans proxy pour
ces sondages de boucle locale.

### D2-14 · « Mains libres prêtes. » s'affiche sans aucune preuve

**Cause.** `_basculer_mains_libres` affiche « Connexion… » puis arme un repli de
`DELAI_JEV_PRET_MS = 3000` (`app.py:163`, `_armer_repli_jev_pret` `app.py:1583`).
Trois secondes plus tard, `_afficher_jev_pret_si_en_connexion` (`app.py:1606-1613`)
vérifie seulement que le statut vaut encore « Connexion… », puis affiche
`hands_free_connected` = **« Mains libres prêtes. »**. Aucun `jev_pret` du
serveur n'est exigé. Le garde-fou existe (`app.py:1609-1611`) et empêche bien le
faux positif quand le WS est cassé — mais pas quand le WS est ouvert et que
l'écoute continue n'a jamais été armée.

**Ce que voit l'utilisateur.** L'app affirme que le mode mains libres est prêt.
Le présentateur parle sans appuyer. Rien ne se passe. Aucune erreur n'est
affichée, puisque l'app vient de déclarer le contraire.

**Aggravant.** `_aspirer_jev_pret` (`app.py:554-575`) **jette silencieusement**
tout message qui n'est ni `jev_pret` ni `conversation` ; comme `_attendre_jev`
reste vrai tant qu'aucun `jev_pret` n'arrive, un `state` ou un `report` arrivé
dans cette fenêtre est perdu.

**Correctif minimal.** N'afficher « Mains libres prêtes. » que sur un vrai
`jev_pret` (`app.py:2200-2202` le traite déjà) ; à l'échéance des 3 s, afficher
« Mains libres : en attente de l'écoute continue… » — honeste, et conforme à
l'exigence du document LLM V1 relevée par l'audit Codex du 20/09 (« interdit de
laisser croire à une connexion sans preuve »). ~3 lignes.

### D2-15 · Aucun micro-mètre : un micro muet est indiscernable d'un micro qui marche

**Cause.** Pendant l'appui, `_boucle_tours` ne fait que
`while … tenu.is_set(): time.sleep(0.03)` (`app.py:739-740`) : **aucun niveau
n'est remonté**. `enfoncer` fait `bulle.appliquer_etat("ecoute", niveau=None)`
(`app.py:1989-1990`) et `appliquer_etat` (`app.py:420-428`) ne remet pas
`niveau_cible` à 0 quand `etat == "ecoute"` : l'orbe garde donc un niveau
périmé et donne l'impression d'entendre.

**Ce que voit l'utilisateur.** Si Windows autorise l'ouverture du flux mais livre
des zéros (micro muet, désactivé dans les Paramètres, mauvais périphérique par
défaut, casque dont le micro est coupé), l'orbe passe en écoute **exactement
comme si tout allait bien**, des trames de silence partent, et le serveur ne
transcrit rien. L'écran affiche « N trames envoyées, attente de la réponse… »
puis « Aucune trame de réponse — rien à restituer. » (`app.py:331`).

C'est le scénario le plus probable et le plus coûteux en soutenance : le
présentateur parle, rien ne se passe, et **l'interface affirme que tout va bien**.

**Correctif minimal.** Pendant la capture, échantillonner le RMS des trames déjà
accumulées et poster `{"type": "etat", "etat": "ecoute", "niveau": rms}` toutes
les ~80 ms → l'orbe respire avec la voix. Le calcul existe déjà
(`windows_audio._rms_int16`, `windows_audio.py:170-179`). ~10 lignes, et c'est
en même temps une **preuve visuelle pour le jury** que le micro fonctionne — le
meilleur rapport valeur/coût de ce rapport après D2-8.

Note : `choisir_peripherique` (`talk.py:312-372`) cherche d'abord
`"USB PnP"` puis `"USB Desk Microphone"` (`talk.py:30-33`) — des noms de
périphériques de démo codés en dur. Sur une autre machine, le repli sur le
défaut système est correct, mais le microphone visé n'est pas garanti.

### D2-16 · Double lancement : deux fenêtres, deux micros, deux réponses

**Cause.** `app.py` ne lie aucun port et ne prend aucun verrou ;
`hyper-ambient.bat` fait `start "" pythonw native\presence\app.py` sans test
d'instance existante. (Bonne nouvelle au passage : comme l'app n'écoute sur
aucun port, **« port déjà occupé » ne peut pas casser Presence** — le risque
d'occupation porte uniquement sur le serveur, qui publie 8000, 8001, 8090 et
8091 dans `docker-compose.yml:38-42`.)

**Ce que voit l'utilisateur.** Deux fenêtres « hyper-ambient » identiques.
Les deux ouvrent leur flux d'entrée (WASAPI partagé le permet) et les deux se
connectent au host-agent → deux tours pour une seule phrase → **deux réponses
vocales qui se chevauchent**. Aucune des deux ne signale l'autre. Sous stress,
un double-clic en trop est très probable.

**Correctif minimal.** Un mutex nommé Win32 en tête de `main()`
(`ctypes.windll.kernel32.CreateMutexW(None, True, "HyperAmbient.Presence")`,
puis `GetLastError() == 183` → ramener l'instance existante au premier plan et
sortir). ~10 lignes. Alternative sans code Python : tester dans le `.bat`.

### D2-17 · Erreurs brutes, non traduites, dans la seule zone de texte disponible

**Cause.** `app.py:598-600` : `except Exception as exc:` →
`texte = f"{exc}"`, le texte brut de l'exception. `app.py:687` :
`f"Impossible de joindre {self.url} : {exc}"`. `app.py:281` :
`f"Erreur du transport : {message}"` — le **dictionnaire JSON brut du serveur**.

**Ce que voit l'utilisateur.** `Impossible de joindre ws://127.0.0.1:8001/hostagent
: [WinError 10061] Aucune connexion n'a pu être établie…`, ou
`Erreur du transport : {'type': 'error', 'code': …}`, dans une étiquette de
440 px. Technique, partiellement en anglais, et c'est ce qui s'affichera le plus
souvent si quelque chose tourne mal.

**Correctif minimal.** Une petite table (`10061` → « Le serveur hyper-ambient ne
tourne pas sur le port 8001. » ; `10049`/`InvalidURI` → « Adresse invalide. »),
et ne jamais afficher `{message}` brut. ~10 lignes.

### D2-18 · Préférences non enregistrées : échec silencieux

**Cause.** `_achever_onboarding` (`app.py:1154-1166`) et `_appliquer_options`
(`app.py:1413-1457`) attrapent `OSError` et se contentent de `journaliser`, si
`enregistrer_configuration` (`onboarding.py:104-117`) échoue
(`%LOCALAPPDATA%\hyper-ambient` non écrivable, antivirus qui verrouille le
`.tmp`, disque plein).

**Ce que voit l'utilisateur.** Rien. Le wizard se termine, puis **recommence à
zéro au lancement suivant** : langue, raccourci, mains libres perdus. Devant un
jury qui relance l'app, cela donne « ça ne mémorise rien ».

**Correctif minimal.** Afficher une fois « Préférences non enregistrées (dossier
local inaccessible) » dans la ligne d'état au lieu de ne l'écrire qu'au journal.
~2 lignes.

### D2-19 · Le rendu 30 images/s ne s'arrête jamais, même fenêtre masquée

**Cause.** `tic()` se réarme inconditionnellement (`app.py:2282`) avec
`INTERVALLE_MS = 33` (`overlay.py:40`). `_dessiner_champ` (`app.py:2238-2258`)
redessine la nappe sur **toute la fenêtre** (`etendre=True`, `ampleur=0.58`, donc
`portee = max(largeur, hauteur)` → quatre polygones *smooth* de ~460 px de rayon
plus deux ou trois arcs, `overlay.py:278-352`), puis l'orbe de 260 px et
l'éclair. `masquer_configuration()` fait `iconify()` (`app.py:1921`) et
**n'arrête rien** : la boucle redessine indéfiniment un canvas invisible.

**Conséquences.** (a) Un cœur CPU occupé en permanence par du rendu GDI logiciel,
sur la même machine que l'inférence ; (b) contention du GIL avec le fil audio —
`_boucle_tours_continus` poll à `time.sleep(0.03)` et le callback PortAudio fait
une FFT par bloc de 20 ms (`windows_audio._trame_voix`, `np.fft.rfft`) — donc
risque de xruns et de voix hachée en mains libres ; (c) ventilateur audible
pendant la soutenance.

**Ce que voit l'utilisateur.** Rien de direct : une machine qui chauffe et qui
rame, et potentiellement de l'audio haché.

**Correctif minimal.** `if not self.racine.winfo_viewable(): return` après le
vidage de la file et avant les dessins, en gardant le réarmement. ~3 lignes.
*Honnêteté : je n'ai pas mesuré la charge réelle ; le risque GIL/audio est une
déduction du code, pas une observation.*

## 4bis. NIVEAU 3 — COSMÉTIQUE

Rien de ce qui suit n'empêche la démo, mais trois de ces points touchent à la
**crédibilité** devant un jury, ce qui n'est pas neutre.

### N3-1 · `assets/` n'est pas suivi par git : plus d'icône sur une machine clonée

**Cause.** L'instantané de suivi fourni en début de session liste
`?? native/presence/assets/` — le dossier entier n'est pas suivi. Localement il
existe bien (10 fichiers, dont `hyper-ambient.ico`, `hyper-ambient-32.png`, et
six `_tmp_*.png` qui n'ont rien à faire là). `app.py:969-980` garde correctement
avec `is_file()`, et `_appliquer_icone_win32` (`app.py:2287-2293`) sort dès
`if not path.is_file()` : **l'app démarre, sans icône**.

**Ce que voit l'utilisateur.** Le plumet Python générique dans la barre des
tâches. Or la promesse affichée à l'étape 4 est « Masquer la configuration réduit
la fenêtre dans la barre des tâches. **Un clic sur son icône la rappelle.** »
(`src/i18n` `ui.hide_body`, repris par `onboarding.TEXTE_MASQUAGE`). Avec une
icône générique, éventuellement parmi d'autres fenêtres Python, **le geste de
rappel enseigné par le wizard devient ambigu** — c'est pour ça que je le classe
au-dessus du purement décoratif.

**Correctif minimal.** Suivre `assets/hyper-ambient.ico` et
`assets/hyper-ambient-32.png`, supprimer les `_tmp_*.png`. Aucune ligne de code.

### N3-2 · Le bouton « Un retour » ouvre un navigateur depuis le fil Tk, sans filet

**Cause.** `app.py:1798-1801` : `command=ouvrir_feedback` →
`onboarding.ouvrir_feedback` (`onboarding.py:170-174`) →
`webbrowser.open(URL_FEEDBACK)`, exécuté **sur le fil Tkinter**. Aucune capture
d'exception côté appelant.

**Ce que voit l'utilisateur.** Trois cas, tous médiocres : sans navigateur par
défaut associé, `os.startfile` lève `OSError` dans le callback → traceback dans
`presence.log` et **rien à l'écran** ; sans réseau, le navigateur s'ouvre sur une
page d'erreur ; et dans tous les cas un clic accidentel — le bouton est packé
juste sous « Masquer la configuration », même largeur, même style
(`app.py:1784-1810`) — **ouvre un navigateur par-dessus la démo**.

**Correctif minimal.** Entourer l'appel d'un try/except qui écrit le résultat
dans la ligne d'état, et écarter visuellement ce bouton de « Masquer » pendant la
soutenance. ~4 lignes.

### N3-3 · Le journal croît sans rotation ni démarcation de session

**Cause.** `app.py:90` : `open(journal, "a", …)`, jamais tronqué. La boucle de
reconnexion écrit toutes les 2 s (`app.py:689`), la sonde toutes les 2 s
(`app.py:2165-2171`), et `_boucle_tours_continus` ajoute un pouls toutes les 5 s
(`app.py:804-813`).

**Ce que voit l'utilisateur.** Rien — sauf le jour où il faut ouvrir
`presence.log` pour diagnostiquer devant le jury : plusieurs lancements sont
mêlés sans ligne de début, et le fichier peut être volumineux. `.gitignore:46`
ignore `*.log`, donc aucune pollution du dépôt.

**Correctif minimal.** Écrire une ligne de démarcation horodatée au démarrage
(dans `assurer_stdio`, juste après l'ouverture) et tronquer au-delà d'une taille
seuil. ~5 lignes. C'est aussi ce qui rendra les autres diagnostics exploitables.

### N3-4 · `platform_ui`/`platform_audio` livrés mais importés par personne ; trois gardes Win32 dupliquées

**Cause.** Grep `platform_ui|platform_audio` sur tout `native/` : **zéro
résultat**. Les deux modules d'abstraction (13 835 o et 9 149 o, écrits le 20/09)
ne sont appelés nulle part — état cohérent avec la phase 1 du portage macOS.
Pendant ce temps `app.py` réimplémente trois gardes Windows en direct, avec
`import ctypes` **au niveau module** (`app.py:23`), ce que la docstring de
`platform_ui.py` interdit explicitement (« aucun `ctypes.windll` au niveau
module ») :

| Garde | Dans `app.py` | Équivalent `platform_ui` | Lequel est le plus défensif |
|---|---|---|---|
| AppUserModelID | `964` | `set_app_identity` | équivalents |
| Icône fenêtre | `969-980` | `apply_window_icon` | **`platform_ui`** : filet `except Exception`, 5 candidats PNG, `master=root` explicite |
| WM_SETICON | `2287-2313` | `force_win32_window_icon` | équivalents |
| Zone de travail | *absent* | `aire_utile` (ne rend jamais `None`) | **`platform_ui`** — et c'est le correctif de N1-2 |

**Ce que voit l'utilisateur.** Rien sur Windows. Le coût est ailleurs : deux
implémentations de la même garde divergent silencieusement, et le module qui
contient la solution de N1-2 n'est branché nulle part.

**Correctif minimal.** **Pas avant le 25** — cela touche un fichier hors de mon
périmètre et n'apporte rien de visible le jour J. À faire après : remplacer les
trois blocs par les appels `platform_ui`, et supprimer `import ctypes` de la tête
d'`app.py`. Je le note parce que `platform_ui.aire_utile()` est la pièce manquante
de N1-2 et qu'elle est déjà écrite et testée.

### N3-5 · Échap ne ferme pas pendant le wizard, alors que l'étape 4 l'annonce

**Cause.** `self.racine.bind_all("<Escape>", self._echap)` n'est posé que dans
`_afficher_application` (`app.py:1874`). Pendant les quatre écrans, aucune
liaison Échap n'existe ; seule la croix ferme (`WM_DELETE_WINDOW`, posé lui dans
`__init__`).

**Ce que voit l'utilisateur.** À l'étape 4 il lit « La croix et Échap ferment
vraiment l'application » (`ui.hide_body`), appuie sur Échap, et rien ne se passe.
Incohérence mineure de promesse, mais elle tombe précisément sur l'écran qui
parle du masquage.

**Correctif minimal.** Poser le `bind_all("<Escape>")` dans `__init__` plutôt que
dans `_afficher_application` — `_echap` (`app.py:2067`) sait déjà se comporter
hors lecture. 1 ligne déplacée.

### N3-6 · Copies mortes dans `onboarding.py`, encore testées, contredites par l'UI

**Cause.** `onboarding.py:29-45` définit `TEXTE_BIENVENUE` (« **Trois** réglages
suffisent : comment parler, quel raccourci, comment masquer »), `TEXTE_PTT`,
`TEXTE_MASQUAGE`, `RAPPEL_A11Y`, `LIBELLE_ECLAIR_*`, `STATUT_APPEL_DISTANT`.
L'UI n'en affiche **aucun** : elle passe par `ui_presence()` →
`src/i18n/__init__.py:499`. Et `ui.welcome_body` annonce « **Quatre** réglages
suffisent : mains libres, comment parler, quel raccourci, comment masquer » —
cohérent avec `ETAPES_WIZARD` en 4 étapes, mais en contradiction avec la
constante voisine. `test_copies_du_wizard_disent_ptt_masquage_et_clavier` et
`test_copies_onboarding_restent_en_francais` vérifient ces constantes mortes.

**Ce que voit l'utilisateur.** Rien. Le coût est pour qui lit le code avant la
soutenance : deux sources de vérité pour les mêmes phrases, dont une testée et
non affichée. L'audit Codex du 20/09 relève déjà l'écart « deux/trois réglages
annoncés vs quatre livrés ».

**Correctif minimal.** Après le 25 : supprimer les constantes mortes ou les
faire devenir la source de `_FR`. Ne rien changer d'ici la soutenance — les tests
qui les portent passeraient au rouge pour rien.

## 5. Le gel Tkinter pendant une attente réseau — verdict précis

La mission demandait ce point explicitement. **L'architecture est correcte et il
faut le dire :** tout le réseau et tout l'audio vivent dans `SessionVocale`
(`threading.Thread`, `app.py:507`), la communication vers l'UI passe par une
`queue.Queue` (`app.py:577-579`), et le seul consommateur est `tic()` sur le fil
Tk. **Aucun appel réseau bloquant ne s'exécute sur le fil principal.** Le
commentaire de tête d'`app.py` l'annonce et le code le tient.

Ce qui peut malgré tout donner l'impression d'une fenêtre morte :

| Source | Fil | Bloquant ? | Ligne |
|---|---|---|---|
| `ws.recv()` / `connect()` / `ws.send()` | session | oui, mais hors UI | `app.py:266`, `648`, `768` |
| `tk.Tk()`, création des widgets | principal | non | `app.py:960` |
| `assurer_stdio()` : `mkdir` + `open` | principal | **oui, avant toute fenêtre** | `app.py:89-90` |
| `charger_configuration()` : lecture JSON | principal | oui, bref | `onboarding.py:88` |
| `webbrowser.open()` (bouton « Un retour ») | principal | oui, bref | `app.py:1801`, `onboarding.py:170-174` |
| `lire_snapshot(--sante)` : lecture fichier, 1 Hz | principal | oui | `app.py:2173-2185` |
| `ws.close()` depuis `fermer()` | principal | oui, bref | `app.py:585-590` |
| rendu canvas 30 i/s | principal | non, mais coûteux | `app.py:2260-2284` |
| `handle_health_check({})` | sonde | oui, hors UI | `app.py:2165` |

Deux risques réels, déjà traités : **N1-1a** (l'entrée/sortie disque de
`assurer_stdio()` se fait *avant* qu'une fenêtre existe — sur un profil redirigé
vers un partage réseau hors ligne, le double-clic ne produit rien pendant toute
la durée du timeout SMB) et **N1-3** (la `TclError` qui arrête définitivement le
rafraîchissement).

## 6. Le filet de sécurité ne couvre pas ce qu'il annonce

**Preuve exécutée** (quatre runs identiques, 18 minutes, rien d'écrit sur le
disque) :

```
$ python -m pytest dev/tests/test_presence_onboarding.py -q -p no:cacheprovider
................s......                                                  [100%]
22 passed, 1 skipped in 0.72s          ← run 1, 20:32

$ python -m pytest dev/tests/test_presence_onboarding.py -q -rs -p no:cacheprovider
................F......                                                  [100%]
1 failed, 22 passed in 0.83s           ← run 2, 20:47

$ python -m pytest dev/tests/test_presence_onboarding.py -q -p no:cacheprovider
22 passed, 1 skipped in 0.74s          ← run 3, 20:50

$ python -m pytest dev/tests/test_presence_onboarding.py -q -rs -p no:cacheprovider
1 failed, 22 passed in 0.83s           ← run 4, 20:52
```

L'extrait du run 2, recopié tel quel :

```
native\presence\app.py:960: in __init__
    self.racine = tk.Tk()
E   _tkinter.TclError: Can't find a usable init.tcl in the following directories:
E       {C:\Users\thoma\AppData\Local\Programs\Python\Python313\tcl\tcl8.6}
E   …couldn't read file "…\tcl8.6\init.tcl": no such file or directory
E   This probably means that Tcl wasn't installed properly.
```

**Lecture.** `test_wizard_et_eclair_distant_sont_visibles` — **le seul test de
bout en bout du wizard** — n'a passé **aucun** des quatre runs : deux fois ignoré
(`_ouvrir_tk()` attrape la `TclError` et `pytest.skip`), deux fois échoué (la
même `TclError`, mais levée plus loin, à `app.py:960` dans
`Application.__init__`). Donc « 22 passed, 1 skipped », le résultat vert que les
comptes rendus citent comme preuve, **signifie en réalité que l'UI du wizard
n'a pas été exercée**. La raison du skip n'est visible qu'avec `-rs`, et aucun
rapport ne la mentionne.

**Le dépôt connaît déjà ce flake**, et c'est important de le dire plutôt que de
le présenter comme une découverte :

- `dev/tests/test_presence_premier_tour.py:101` : « un second `Tk()` flake sous
  Python 3.13 (init.tcl) » — et ce fichier applique le bon contournement : une
  seule racine Tk par test, réutilisée.
- `nights/2026-09-18-UI-HA.md:61` : « le skip = premier `Tk()` parfois sans
  `init.tcl` sous Python 3.13 ; les tests Tk suivants passent. »
- `nights/2026-09-20-OUT-JEV-CONNEXION-UI.md:39` : « second `Tk()` parfois
  "Can't find a usable init.tcl" si `after(3000)` n'est pas annulé avant
  `destroy()`. »

`test_presence_onboarding.py` fait exactement l'inverse du contournement :
`_ouvrir_tk()` crée une racine et la détruit, **puis** `Application(args)` en
crée une seconde. Cinq tests utilisent ce motif (`test_dessiner_eclair…`,
`test_wizard_et_eclair…`, `test_dessiner_orbe…`, `test_geste_souffle…`,
`test_overlay_forme_opaque…`, `test_nappe_du_champ…`).

**Ce que j'ai écarté.** L'installation Tcl n'est pas cassée : hors pytest, six
créations successives de deux racines Tk ont toutes réussi (`1re=OK 2e=OK` ×6),
`tk.Tk()` rend `patchlevel 8.6.15`, et `tcl\tcl8.6\init.tcl` existe
(`Test-Path` → True), `TCL_LIBRARY` vide. Le déclencheur est donc propre au
processus pytest, et je ne l'ai pas identifié.

**Pourquoi c'est un sujet de robustesse et pas de tests.** (a) Le seul filet qui
couvre les quatre écrans ne s'exécute pas : aucune des régressions N1-2, D2-7,
D2-14 ou D2-15 ne serait attrapée par la suite. (b) La même instruction
`tk.Tk()` (`app.py:960`) est le point d'entrée unique de l'app, sans repli :
quand elle échoue sous `pythonw`, on est exactement en N1-1b — rien à l'écran.
L'app lancée ne crée qu'une racine, donc son exposition est plus faible que
celle du test ; mais l'instabilité est avérée sur ce poste, à cinq jours de la
soutenance.

**Correctif minimal.** (1) Dans `test_presence_onboarding.py`, supprimer l'appel
à `_ouvrir_tk()` des tests qui créent ensuite leur propre racine — une seule
racine par test, comme le fait déjà `test_presence_premier_tour.py`. (2) Rendre
le skip bruyant : un `pytest.skip` sur indisponibilité de Tk ne doit plus pouvoir
passer pour du vert — soit `--runxfail`/un marquage explicite, soit une vérification
Tk unique en `conftest.py` qui échoue au lieu de sauter quand l'UI est censée
être testée. (3) Résoudre l'instabilité Tcl/Tk du poste **avant** le 25, et
refaire une répétition interactive (`python native/presence/app.py --onboarding`)
sur le poste du jury, pas seulement sur celui-ci.

**Couverture absente, par construction.** Même verte, la suite ne teste aucun
chemin d'échec : le test Tk force `session_lancee = True`, donc ni micro, ni
WebSocket, ni sonde ne sont jamais exercés. Aucun test ne couvre
`SystemExit` remontant de `capture.start()`, l'absence de `.env.local`, le port
fermé, la poignée muette, un tour sans réponse, `DEGRADED`, ou la géométrie
fenêtre. Le constat recoupe l'audit Codex du 20/09 (« le seul fichier livré
contient 23 tests PTT/visuels ; son test Tk force `session_lancee=True` »), avec
ici la précision supplémentaire que **ce test ne s'exécute pas**.

## 7. Matrice de couverture des cas demandés

| Cas demandé | Verdict | Ce que voit l'utilisateur | Où |
|---|---|---|---|
| `.env.local` absent | **Bloque avant l'app** | `docker compose up` échoue ; Presence dit « Impossible de joindre … » | D2-9 |
| Clés API absentes/vides | Démarre, échec différé | Rien au démarrage ; le premier tour ne rend rien | D2-10 |
| Docker éteint | Dégradé vivant | « Impossible de joindre ws://…10061 » toutes les 2 s | N1-4, D2-17 |
| Docker en cours de démarrage | **Dégradé trompeur** | Même message, alors qu'il faut attendre jusqu'à 180 s | N1-4 |
| Port déjà occupé | **Ne casse pas Presence** | L'app n'écoute sur aucun port ; risque côté serveur seulement | D2-16 |
| Modèles non téléchargés | Dégradé trompeur | Port jamais ouvert → « Impossible de joindre » en boucle | D2-12 |
| Aucun périphérique micro | Dégradé, fil mort | « Périphérique audio indisponible. Vérifiez le micro. » puis « Canal pas encore prêt. » | D2-1, D2-3 |
| Micro refusé par Windows | **Dégradé illisible** | « Arrêt audio : 1 », puis plus rien ne marche | D2-1 |
| Pas de GPU | **Bloque avant l'app** | `docker compose up` refuse ; carte figée en `cuda` | D2-11 |
| VRAM saturée | Dégradé trompeur | Conteneur tué (exit 137) ; statut périmé, `canal_pret` levé | D2-5, D2-6, D2-11 |
| Premier lancement sans réseau | **Ne casse pas la voix** | Boucle locale en `127.0.0.1` ; « Un retour » (GitHub) échoue ; `stepfun` échoue | D2-10, N3-2 |
| Gel Tkinter sur attente réseau | **Absent par construction** | Aucun appel réseau sur le fil Tk ; les vrais risques sont N1-1a, N1-3 et D2-19 | §5 |

## 8. Plan minimal pour le 25, ordonné par valeur sur coût

**Moins d'une heure, risque nul pour le chemin nominal :**

1. `requirements-host.txt` avec `sounddevice==0.5.6`, `websockets==15.0.1`,
   `numpy` — et une ligne dans `SETUP.md`. *(D2-8 : 2 lignes, évite un échec
   garanti sur machine préparée proprement.)*
2. Message explicite à la place de « Arrêt audio : 1 » (`app.py:597`).
   *(D2-1 : 2 lignes.)*
3. `focus_set()` seulement à la transition vers `DEGRADED` (`app.py:2145`), et
   sonde limitée à `host_agent` + `modele_local` via le paramètre `endpoints`
   déjà prévu (`app.py:2165`). *(D2-13 : 4 lignes — supprime le bandeau rouge
   permanent et le vol de focus.)*
4. Ne plus afficher « Mains libres prêtes. » sans `jev_pret` réel
   (`app.py:1606-1613`). *(D2-14 : 3 lignes.)*
5. Séparer micro et haut-parleur dans les messages (`app.py:627-642`).
   *(D2-3 : 6 lignes.)*

**Une demi-journée, à tester :**

6. Filet `MessageBoxW` dans `main()` + try/except autour de `assurer_stdio()`
   (`app.py:89-90`, `2381-2386`). *(N1-1 : 12 lignes — transforme le pire cas,
   « rien ne se passe », en message lisible.)*
7. Géométrie bornée par `platform_ui.aire_utile()` + `minsize(380, 420)` +
   `ligne_etat` hors du panneau extensible (`app.py:987-988`, `1857-1867`).
   *(N1-2 : 10 lignes — le module est déjà écrit, il n'est appelé par personne.)*
8. `--diagnostic` : checklist stdlib des quatre ports + état du secret + modèle
   de cerveau. *(N1-4, D2-9, D2-10, D2-12 : ~40 lignes, réutilise
   `handlers.sonder_url`.)*
9. Micro-mètre pendant la capture (`app.py:739-740`, via
   `windows_audio._rms_int16`). *(D2-15 : 10 lignes — et une preuve visuelle pour
   le jury.)*
10. Échéance de 45 s par tour dans `consommer_reponse` (`app.py:260-338`) +
    erreur explicite à la place du `return` silencieux (`app.py:272-273`).
    *(D2-5, D2-6 : 10 lignes.)*
11. `recv(timeout=5.0)` dans `_poignee_de_main` (`talk.py:480`). *(D2-4 :
    3 lignes.)*
12. Corriger les cinq tests à double racine Tk et rendre le skip bruyant.
    *(§6 : 15 lignes — sans ça, rien de ce qui précède n'est vérifiable.)*

**Décisions, pas du code :**

13. Vérifier que le poste du jury a un GPU NVIDIA, que `models/` est peuplé, que
    `carte_figee.env` est bien chargé (la ligne `CARTE : …` doit apparaître au
    démarrage du serveur), et préparer `docker-compose.cpu.yml` + une carte CPU
    en repli. *(D2-11, D2-12.)*
14. Décider si les ponts Codex/Claude font partie de la démo ; sinon les retirer
    du périmètre de la sonde (fait au point 3).
15. **Publication réseau** : `docker-compose.yml:38-42` publie `8000`, `8001`,
    `8090` (llama-server, compatible OpenAI, sans authentification) et `8091` sur
    **toutes les interfaces de l'hôte**, et `serve_hostagent.py:64` écoute
    `0.0.0.0`. Avec le secret de développement par défaut
    (`talk.py:29`, `serve_hostagent.py:520-531`), sur le réseau d'un lieu de
    soutenance, **un tiers peut piloter le micro et le haut-parleur de la machine
    de démo**, ou interroger le LLM. Correctif : préfixer les publications par
    `127.0.0.1:` (`"127.0.0.1:8001:8001"`, etc.) — le client ne se connecte
    déjà qu'en boucle locale (`app.py:69`). Une ligne par port. *Hors périmètre
    strict de ma mission (ce n'est ni un écran noir ni un gel), mais je le
    signale : une voix qui répond à un inconnu pendant la soutenance est un
    échec de démonstration.*

## 9. Difficultés rencontrées

- **Le code bougeait pendant l'analyse.** `app.py` a été réécrit à 20:29:08 puis
  20:37:08, passant de 2 288 à 2 391 lignes sous mes lectures ; `windows_audio.py`
  à 20:26:10, `serve_hostagent.py` à 20:13:20, `src/i18n/__init__.py` à 20:11:20.
  J'ai dû relire `consommer_reponse` et `_boucle_tours` : un constat que j'avais
  établi (bouton Stop inerte pendant une attente silencieuse) avait été corrigé
  entre-temps, et un argument `--journal` est apparu. D'où le tableau
  d'instantané au §0.
- **Un flake environnemental non résolu.** `tk.Tk()` échoue de façon
  intermittente sous pytest alors qu'il réussit systématiquement hors pytest
  (§6). Je n'ai pas identifié le déclencheur et je ne l'ai pas corrigé, puisque
  je ne devais toucher à aucun fichier.
- **Périmètre dépassé en lecture, volontairement.** La mission listait six
  fichiers ; la chaîne d'échec du premier lancement traverse aussi `talk.py`,
  `windows_audio.py`, `serve_hostagent.py`, `relance_hostagent.sh`,
  `carte_figee.env`, `docker-compose.yml`, `.env.example`, `requirements*.txt`,
  `src/i18n/__init__.py`, `overlay.py` et `workers/night_health_vault_note/
  handlers.py`. Je les ai lus (partiellement pour les plus gros) parce que sans
  eux les cas « Docker éteint », « modèles absents », « pas de GPU » et
  « clés vides » restaient sans cause vérifiable. **Aucun n'a été modifié.**

## 10. Non vérifié

Ce que je n'ai pas pu trancher par lecture seule, et que je n'affirme donc pas :

- **Aucune installation sur machine vierge exécutée.** L'échec de
  `pip install -r requirements.txt` sous Python 3.13 (D2-8) est une déduction
  à partir des épingles et de la date de support cp313 de numpy/torch, pas une
  observation. De même pour l'échec de `docker compose up` sans `.env.local`
  et sans GPU NVIDIA (D2-9, D2-11) : déduit de la syntaxe Compose, non exécuté.
- **Aucun scénario d'échec exécuté de bout en bout.** Je n'ai ni arrêté Docker,
  ni désactivé le micro, ni occupé le port 8001, ni coupé le réseau, ni lancé
  `pythonw`. Les « ce que voit l'utilisateur » sont déduits du code : message
  exact + chemin d'exception + widget qui l'affiche. Les deux seuls faits
  observés directement sont le flake Tk du §6 et les versions de dépendances.
- **`serve_hostagent.py` (74 442 o) lu partiellement** : `main()`/`lifespan`,
  `lire_secret`, `_appliquer_env_boot` (signature et chemins). Je n'ai pas lu
  `HostPipeline.load`, `prechauffer`, ni le traitement d'un tour : la durée
  réelle de chargement des modèles, le comportement sur VRAM saturée et
  l'existence éventuelle d'un timeout serveur par tour restent à confirmer. Le
  « jusqu'à 180 s » vient du script de relance, pas d'une mesure.
- **Aucun GPU, aucun conteneur, aucun périphérique audio manipulés.** Le budget
  VRAM réel de la pile (granite 3B + Whisper large-v3 int8_float16 + Magpie +
  silero-vad) est estimé d'après les noms de modèles, non mesuré.
- **`platform_audio.py` et `platform_ui.py` ne sont importés par personne**
  (grep `platform_ui|platform_audio` sur `native/` : zéro résultat). État
  cohérent avec la phase 1 du portage macOS ; je n'ai donc évalué `platform_ui`
  que comme réservoir de correctifs disponibles (N1-2), pas comme chemin actif.
- **Accessibilité réelle non testée** : aucun passage NVDA/Narrator. Le vol de
  focus de D2-13 est déduit du code, son effet annoncé pour un lecteur d'écran
  reste à valider.
- **Charge CPU du rendu 30 i/s non mesurée** (D2-19) : aucun profilage exécuté ;
  le risque de contention GIL avec le callback audio est une déduction.
- **Deux recherches en parallèle** (chaîne Docker/host-agent/`.env`, et sonde de
  santé) ont rendu leur résultat **après** ma première rédaction. Leurs
  conclusions sont intégrées au §11 — mais uniquement après que j'ai revérifié
  moi-même chaque affirmation porteuse dans le code. L'une d'elles a d'ailleurs
  **contredit** un de mes constats, que j'ai corrigé en place (D2-9).

## 11. Compléments des deux recherches parallèles — revérifiés par moi

Les deux passes portaient sur la chaîne aval (host-agent, serveur, Docker, GPU,
i18n) et sur la sonde de santé. **Attention aux numéros de ligne** : leurs
relevés d'`app.py` datent de l'état **2 385 lignes**, le mien de l'état
**2 391 lignes** (écriture de 20:37:08). Les deux concordent jusqu'à
`analyser_arguments` ; au-delà, décaler de +6. Tout ce qui suit a été relu par
moi dans le code avant d'être écrit.

### A11-1 · La carte figée exige des modèles qu'aucun script du dépôt ne télécharge — **bloquant, et le message d'erreur accuse le mauvais remède**

C'est le complément le plus important, et il **aggrave D2-12 au point d'en faire
un bloquant de premier lancement**, pas un simple cas dégradé.

`dev/scripts/carte_figee.env` — que `relance_hostagent.sh:2` qualifie de
« source de vérité pour le host-agent » — exige :

| Étage | Exigé par la carte | Ce que `fetch_models.sh` installe réellement | Écart |
|---|---|---|---|
| EARS | `large-v3` (`carte_figee.env:13`) | `large-v3-**turbo**` (`fetch_models.sh:37-39,45-46`) | **modèle différent** |
| BRAIN | `granite-4.2-3b-Q4_K_M.gguf` (`carte_figee.env:10`) | `Ministral-3-8B-Instruct-2512-Q4_K_M.gguf` (`fetch_models.sh:55-56`) | **modèle différent** |
| MOUTH | `magpie` + voix Sofia (`carte_figee.env:19-20`) | rien — `core` installe Piper `fr_FR-**siwis**-medium` (`fetch_models.sh:32-35`) | **absent du dépôt** |
| MOUTH (repli piper) | `serve_hostagent.py:67` pointe `fr_FR-**tom**-medium.onnx` | `fr_FR-**siwis**-medium.onnx` | **chemin mort** |

Vérifié par moi : grep `granite|magpie|nemo` sur `fetch_models.sh` → **zéro
résultat** ; `fetch_models.sh:5` annonce lui-même « core -> VAD + Piper FR voice +
whisper **turbo** (~1.2 GB) ». Et `HF_HUB_OFFLINE=1` (`relance_hostagent.sh:52`,
`.env.example:59`) interdit tout rattrapage au démarrage.

**Conséquence exacte, vérifiée ligne à ligne.** `serve_hostagent.py:839-841` :
```python
        if not await self.asr.load_model():
            print("EARS  : modèle indisponible", flush=True)
            raise SystemExit(1)
```
et `serve_hostagent.py:947-952` :
```python
        if not await self.tts.load_model():
            print("MOUTH : voix indisponible — lancer dev/scripts/fetch_models.sh core", …)
            raise SystemExit(1)
```
Ces deux `SystemExit` tombent **dans le `lifespan`, avant l'ouverture du port**
(`serve_hostagent.py:1741-1758`). Donc : le serveur meurt, 8001 ne s'ouvre
jamais, et Presence affiche « Impossible de joindre … » en boucle. Et le message
MOUTH **prescrit un remède qui ne soigne rien** : `fetch_models.sh core`
n'installe ni magpie ni `nemo-speech`.

**Ce que voit l'utilisateur.** Rien côté Presence (« Impossible de joindre »).
Côté conteneur, `relance_hostagent.sh:106-109` imprime « host-agent mort pendant
le demarrage » suivi du log — mais seulement si l'opérateur sait où regarder.

**Correctif minimal.** Deux voies, à choisir **avant** le 25 :
1. *Voie rapide, recommandée* : ne pas se reposer sur le provisioning. Copier le
   `models/` du poste de dev (qui fonctionne) sur le poste du jury, et vérifier
   la présence des trois artefacts de la carte **par un test explicite** en tête
   de `relance_hostagent.sh` (`test -f "$MODEL"` etc.) avec un message nommant le
   fichier manquant. ~6 lignes de shell.
2. *Voie propre, plus longue* : aligner `fetch_models.sh` sur la carte (ou
   l'inverse), et corriger le message de `serve_hostagent.py:949` pour qu'il
   nomme le vrai remède.

### A11-2 · Pas de GPU : EARS n'a **aucun** repli CPU, MOUTH en a un

Précise D2-11, et corrige une symétrie que je supposais.

- **EARS** : `EARS_DEVICE` défaut `"cuda"` (`serve_hostagent.py:487`), passé tel
  quel à `WhisperModel` ; `int8_float16` n'existe que sur GPU
  (`faster_whisper_asr.py:38,50-63`). **Aucun repli CPU dans le code** : pas de
  GPU, ou OOM CUDA à l'allocation → `load_model` rend False → `SystemExit(1)`
  (`serve_hostagent.py:840-841`). **Le serveur ne démarre pas.**
- **MOUTH magpie** : sonde `nvidia-smi -L` (`magpie_tts.py:49-63`),
  `_resoudre_device` retombe sur `cpu` (`:65-71`), double repli CPU au boot
  (`:139-160`, log « magpie serve cuda mort au boot, repli cpu »), attente de
  disponibilité 120 s (`:296-303`). **Retombe sur CPU, ne bloque pas.**
- **MOUTH pocket** : `.to(cuda)` seulement si `torch.cuda.is_available()`
  (`pocket_tts.py:93-95`) → repli CPU silencieux.
- **BRAIN llama-server** : `--n-gpu-layers 999` (`serve_llama.sh:22`), pas de
  repli CPU dans le script.
- **`test_gpu.py`** (9 lignes, racine) est purement informatif : il imprime
  `torch.cuda.is_available()` et le nom du device, ne lève rien. `make gpu` =
  `nvidia-smi` dans le conteneur (`Makefile:26-27`).
- **VRAM** : aucun garde-fou runtime sur le chemin voix. Les seules sondes VRAM
  du dépôt sont dans `src/world/port.py:48-53,91-111,221-231` — génération
  d'images, **hors chemin de premier lancement**. Mitigations passives :
  `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512` (`docker-compose.yml:19`) et
  `mem_limit: 8g` (`:49-51`).

**Correctif minimal.** Pour un repli CPU crédibilisé le jour J : une carte
`carte_figee.cpu.env` avec `EARS_DEVICE=cpu`, `EARS_COMPUTE_TYPE=int8`, un
`EARS_MODEL` plus petit que `large-v3`, `MOUTH_DEVICE=cpu` — les variables
`*_FORCE` existent déjà (`relance_hostagent.sh:56-63`) et
`carte_figee.env:4` documente le mécanisme. **Mais EARS en CPU sur du
`large-v3` ne tiendra pas en latence** : le repli suppose aussi un modèle plus
petit, donc un essai réel. À décider avant le 25, pas le 25.

### A11-3 · Clé BRAIN vide : dégradation **silencieuse** en cascade, puis phrase parlée

Confirme et précise D2-10 — et c'est une bonne nouvelle partielle.

`BRAIN_API_KEY` vide avec `BRAIN_SERVICE=stepfun` : `StepFunBrain`
(`src/brain/stepfun.py:31`) passe `""`, `OpenAICompatBrain._headers` **omet
simplement l'en-tête `Authorization`** (`src/brain/openai_compat.py:95-98`) —
donc aucune exception au démarrage. L'échec arrive à la requête (401/402) →
`stop_reason: "error"` → `FallbackBrain._demote` bascule sur llama.cpp local
(`src/brain/factory.py:113-131,126-131`), **journalisé seulement**. Si le local
est aussi injoignable : phrase parlée de secours
« Je n'arrive pas à réfléchir. Reprends dans un instant. »
(`src/mouth/secours.py:22`, déclenchée par `serve_hostagent.py:1618-1640`).

Jetons d'outils vides : l'outil **n'est pas enregistré**
(`serve_hostagent.py:396-437`), le tour tourne sans outil
(`OUTILS: aucun backend configure — tour de parole sans outil`, `:863-865`).
`TYPESAFE_API_KEY` (clé JeV) absente : `evaluate` rend `None`
(`src/ears/jev_reflexe.py:512-517`) → repli bouton, annoncé au boot
(« JEV : réflexe en entrée (repli silencieux sans clé) », `:872`).

**Deux faits à retenir pour D2-14.** `TYPESAFE_API_KEY` **n'est pas dans
`.env.example`** (je l'ai relu : aucune occurrence), et le serveur annonce
lui-même le « repli silencieux sans clé ». Autrement dit : sans cette clé, le
`jev_pret` que `_afficher_jev_pret_si_en_connexion` (`app.py:1606-1613`) attend
n'a aucune raison d'arriver — et l'UI affiche quand même « Mains libres prêtes. »
au bout de 3 s. **D2-14 n'est pas un cas limite : c'est le comportement par
défaut d'une installation conforme au modèle fourni.**

**Correctif minimal.** Rien à changer côté serveur, qui dégrade proprement. Côté
Presence, D2-14 suffit — et ajouter `TYPESAFE_API_KEY=` (commentée) et
`MOTHER_HOSTAGENT_SECRET=` à `.env.example`, puisque ce sont les deux seules
clés dont l'absence change le comportement **visible** de l'UI.

### A11-4 · Micro livré muet : le serveur dit « Je n'ai rien entendu. Reprends » — et accuse l'orateur

Nuance importante à D2-15, à charge et à décharge.

Si Windows autorise l'ouverture du flux mais livre des zéros (micro muet,
désactivé, mauvais périphérique par défaut), aucune exception ne sort — le dépôt
documente exactement ce doute pour macOS TCC (`platform_audio.py:26-38`), sans
trancher pour Windows. Le silence est alors détecté **en aval** :
`est_silence` (`src/mouth/secours.py:86`, seuil `-50 dBFS`) appelé en
`serve_hostagent.py:1292`, qui fait parler
« **Je n'ai rien entendu. Reprends, je suis là.** » (`src/mouth/secours.py:20`).

Donc l'utilisateur n'est pas dans le silence total : il entend une phrase. Mais
cette phrase **lui impute la faute** (« reprends ») alors que la cause est un
micro muet — et le dépôt le sait : `dev/tests/test_secours.py:145` porte
littéralement le commentaire « entendre "je n'ai rien entendu" alors que le
problème est … ». Comme l'UI n'a toujours aucun micro-mètre (D2-15), rien ne
permet de distinguer « je parle trop loin » de « le micro est coupé ».

**Correctif minimal.** Inchangé : le micro-mètre de D2-15 est la seule réponse
qui tranche visuellement, et il est à ~10 lignes.

### A11-5 · Sonde de santé : trois fragilités supplémentaires, toutes vérifiées

Complète D2-13. Rappels confirmés : stdlib pure (`handlers.py:7-12`, aucun
import du dépôt, donc **aucun module lourd**), **aucune écriture disque** quand
`snapshotPath` est absent (`handlers.py:193-194`), **aucune subprocess**, les 5
sondages sont **séquentiels** avec timeout (5,0 s pour Camunda `handlers.py:99`,
1,5 s par endpoint `handlers.py:39,153`) → pire cas borné **11 s + 2 s = 13 s**
par cycle. Coût réel mesuré dans le dépôt : `UP ms=41`, `DEGRADED ms=1560`
(`nights/2026-09-19-C2-ALERTE.md:77-80`). La première sonde part immédiatement
(le `wait(2.0)` est en **fin** de boucle, `app.py:2171`) : le bandeau rouge
apparaît ~50 ms après l'écran principal, pas 2 s après.

1. **La sonde morte ne ressuscite jamais, et ne le dit pas.**
   `app.py:2158-2159` insère `workers/night_health_vault_note` en `sys.path[0]`
   **sans tester son existence** ; si le dossier manque, `from handlers import …`
   lève `ModuleNotFoundError` → attrapé (`app.py:2162-2164`) → une ligne de
   journal → `return` : le fil meurt **définitivement**. Et comme `_sondes_fil`
   reste non-`None`, le garde `elif self.sondes_actives and not self._sondes_fil`
   (`app.py:1886`) **interdit tout redémarrage**. Perte silencieuse de la fonction
   d'alerte. Correctif : tester `worker_dir.is_dir()` avant l'insertion, et
   remettre `_sondes_fil = None` en cas d'échec d'import. ~3 lignes.
2. **`resp.read()` sans plafond ni échéance globale** (`handlers.py:101`). Le
   `timeout=5.0` couvre la connexion et chaque `recv`, pas la durée totale : un
   process à moitié vivant sur `:8088` qui suinte un octet toutes les < 5 s
   bloque le fil **indéfiniment**, et `read()` sans taille max peut gonfler la
   mémoire. Faible probabilité sur machine vierge, réel si un Camunda agonise.
   Correctif : `resp.read(65536)`.
3. **Le proxy système Windows détourne les sondes loopback — vérifié dans la
   stdlib.** J'ai relu `C:\Users\thoma\AppData\Local\Programs\Python\Python313\
   Lib\urllib\request.py:2660-2663` :
   ```python
           if test == '<local>':
               if '.' not in host:
                   return True
   ```
   Le jeton `<local>` — celui que Windows coche par défaut (« Ne pas utiliser de
   serveur proxy pour les adresses locales ») — **ne bypass que les hôtes sans
   point**. `127.0.0.1` **contient des points** : il n'est donc **pas** bypassé.
   Sur un réseau d'établissement avec proxy et sans `no_proxy` explicite, les
   cinq requêtes loopback partent vers le proxy, avec résolution DNS du nom de
   proxy **non couverte** par le timeout socket. Tout est déclaré en panne, et
   chaque cycle peut dépasser largement les 11 s. Correctif : construire un
   opener sans proxy pour ces sondages (`urllib.request.build_opener(
   urllib.request.ProxyHandler({}))`).

**Précision à décharge, que je n'avais pas :** le vol de focus de D2-13
**n'empêche pas le PTT**. `_focus_autorise_ptt` (`app.py:2075-2096`) ne bloque
que `Entry`/`Text`/`Spinbox` et, hors mains libres, `Radiobutton`/`Checkbutton`/
`Button` ; un `Label` rend `True` (`:2091-2094`). Et le dépôt ne contient aucun
`tk.Entry` ni `tk.Spinbox`. Espace continue donc de parler — la nuisance est le
Tab et les annonces de lecteur d'écran, pas la parole. Je maintiens le classement
en D2-13 pour cette raison, pas plus haut.

### A11-6 · Concurrence sur la ligne d'état, et deux sondeurs le jour du filage

Deux faits neufs qui renforcent D2-7 et D2-13.

- **Même cadence, même cible.** La boucle de session réessaie le WS toutes les
  2 s (`app.py:691`) et la sonde sonde `host_agent` sur `:8001` toutes les 2 s
  (`handlers.py:34`, `app.py:2171`). Les deux écrivent dans la même ligne d'état
  (`app.py:2148` pour le bandeau, `app.py:689` pour l'erreur) : **la ligne
  alterne entre « Le pont vers Codex ne répond plus » et « Impossible de joindre
  ws://… »**, au même rythme. Aucune des deux causes n'est lisible durablement.
  C'est l'argument décisif pour D2-7 (mémoriser la dernière erreur au lieu de
  l'écraser).
- **Le filage jury lance deux sondeurs.** `nights/2026-09-19-C2-ALERTE.md:106`
  prescrit : `python native/presence/app.py` (sondes toutes les 2 s) **+**
  `python workers/night_health_vault_note/worker.py --once`. Donc le 25 :
  2 sondeurs loopback simultanés, et `worker.py --once` appelle aussi
  `handle_vault_note` (`worker.py:193`), qui **écrit réellement** dans le vault
  Obsidian (`handlers.py:211-217,284`). En mode `run_loop`, `worker.py:170-181`
  fait du long-polling Camunda **toutes les 0,5 s sans backoff** : Camunda
  éteint, cela donne 2 connexions refusées par seconde indéfiniment
  (`worker.py:83-86,179`).
- **Témoin périmé et committé.** `workers/night_health_vault_note/.worker-up`
  contient `started_at: 2026-08-31T02:39:25` alors que
  `scripts/night-2026-08-31/create-instance.ps1:30-32` ne teste que son
  **existence** — le garde-fou « pas d'instance sans worker » saute donc
  immédiatement sur machine vierge. Hors chemin de Presence, mais à savoir si le
  filage s'appuie sur ces scripts.

### A11-7 · Port 8001 occupé, côté serveur — la case manquante de ma matrice

Ma matrice (§7) disait « ne casse pas Presence », ce qui reste vrai côté client
(l'app n'écoute sur aucun port). Côté serveur, vérifié : **aucune pré-vérification
ni gestion** — grep `Address already in use|Errno 98|10048` sur le code produit :
zéro résultat. `uvicorn.run(host="0.0.0.0", port=8001)`
(`serve_hostagent.py:64-65,1765-1783`) échoue avec l'erreur standard d'uvicorn.
`relance_hostagent.sh:70-73` ne tue que les processus dont la ligne de commande
contient `serve_hostagent.py` : si **un autre** processus tient 8001, le serveur
meurt et le script imprime « host-agent mort pendant le demarrage » (`:113-117`)
ou, après 180 s, « timeout: pas d'écoute sur 0.0.0.0:8001 » (`:109-129`), exit 1.
À noter : `MagpieTTS` évite explicitement `{8001, 8080, 8090}` et retombe sur
8092 (`src/mouth/magpie_tts.py:32,41-47`) — la seule précaution de ce genre dans
le dépôt.

### A11-8 · i18n : corroboration exhaustive de mon §2

Ma conclusion (« aucune clé manquante, aucun `KeyError` possible ») est confirmée
indépendamment, clé par clé : `ui()` (`src/i18n/__init__.py:499-559`) renvoie
**58 clés**, toujours complètes ; les 57 que j'avais listées existent toutes ;
`t()` (`:485-497`) ne lève jamais et retombe sur `_FR` puis sur la clé elle-même
(`:494`) ; `langue()` (`:477-483`) ne peut pas lever. **Les huit gabarits à
placeholder ont été recoupés avec leur site de formatage** — `step`
(`{indice}`/`{total}`, `app.py:1068-1070`), `shortcut_kept`, `channel_ready`,
`channel_ready_hands_free`, `hands_free_hint` (trois sites), `frames_sent`,
`conversation_open`, `first_sound` (`{ms:.0f}`) — **aucun `.format()` orphelin,
aucun champ manquant**. Seule anomalie, cosmétique : avec `HA_LANG=es…`, deux
clés passent en espagnol (`_ES`, `:229-232`) et le reste reste en français.
Détail mineur : `ui.feedback_url` (`:547`) n'est utilisé par personne, l'UI
emploie `onboarding.URL_FEEDBACK` (`onboarding.py:11,176`) — deux sources pour
la même URL.

### A11-9 · Ce que les deux passes n'ont pas tranché

Repris tel quel, parce que cela borne aussi leurs conclusions : aucune
installation vierge ni aucun `docker compose up` exécuté (les échecs Compose
sans `.env.local` et sans runtime NVIDIA restent des comportements standard
attendus, non observés) ; `models/` du poste de soutenance non inspecté ; la
réaction réelle de PortAudio/Windows à un refus privacy du micro (exception
franche vs flux de zéros) non tranchée ; l'origine des poids Granite et des
binaires Magpie non établie — seul `dev/scripts/banc_oreille.py:470-495` (banc de
dev) les provisionne ; la version de `websockets` réellement installée côté hôte
non vérifiable (le pin conteneur dit 12.0, le commentaire serveur parle de
« websockets 17 », ce poste a 15.0.1 — **trois versions différentes** entre trois
sources, ce qui renforce D2-8) ; comportement de llama-server avec
`--n-gpu-layers 999` sans GPU non vérifié.

**Une divergence que je signale sans la trancher** : la passe aval écrit que
`verifier_registre` (`serve_hostagent.py:460-471`) « lève `RuntimeError` … appelé
sans filet dans `load()` (`:857`) ». J'ai relu `:857-860` : l'appel est
`actifs = verifier_registre(self.registre)` suivi de `if actifs:` — donc la
fonction **renvoie** une liste ici. Je n'ai pas lu son corps ; je n'intègre pas
l'affirmation, et je la laisse en suspens.

### A11-10 · Hiérarchie mise à jour pour le 25

L'arrivée de A11-1 change l'ordre du §8. Les trois premières actions deviennent :

1. **A11-1** — vérifier que les trois artefacts de la carte figée sont présents
   dans `models/` du poste du jury (Granite GGUF, Whisper `large-v3`, magpie +
   `nemo-speech`), et ajouter le test explicite en tête de
   `relance_hostagent.sh`. *Sans ça, rien d'autre ne sert : le serveur ne
   démarre pas.*
2. **A11-2** — confirmer la présence d'un GPU NVIDIA sur ce poste
   (`docker-compose.yml:24-30` + `EARS_DEVICE=cuda` sans repli). *Décision, pas
   du code.*
3. **D2-8** — `requirements-host.txt` avec `sounddevice`. *Deux lignes, évite un
   échec garanti sur une machine installée proprement.*

Puis les points 2 à 5 du §8 (message « Arrêt audio : 1 », sonde et focus,
« Mains libres prêtes » sans preuve — renforcé par A11-3, micro/haut-parleur
séparés), qui restent les correctifs côté code les plus rentables.
