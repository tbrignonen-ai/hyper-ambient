## Verdict en trois lignes

Un portage macOS non exécuté ne se présente pas le 25 comme « ça tourne ». Ce qui peut se présenter honnêtement : le Mac comme **terminal vocal** d'un cœur qui reste sur le PC Windows, à condition d'avoir obtenu 30 minutes de Mac réel avant la soutenance (location possible pour quelques euros, voir point 4). Sinon, on montre l'architecture et un artefact réel produit par un runner macOS, et on dit « non testé au micro ».

Et un constat qui change le cadrage : après lecture de `native/`, la question n'est pas « comment rendre du code aveugle fiable », c'est « comment réduire la surface aveugle à presque rien ». Le code Windows est déjà portable en très grande partie — le risque est environnemental (quel Python, TCC, réseau), pas algorithmique.

## Le principe, avant les points

Du code jamais exécuté n'est pas « statistiquement sûr » par qualité d'écriture. Il le devient par trois choix de conception :

1. **Réutiliser le chemin exercé chaque jour.** `windows_audio.py` n'a aucun code Windows (numpy, threading, sounddevice importé paresseusement) ; `platform_audio.py` en hérite au lieu de le recopier — c'est la bonne décision, un seul VAD. `app.py` fait déjà réseau + audio dans un thread et ne touche Tk que via `queue` + `after()` — c'est exactement le modèle que macOS exige. Les `ctypes.windll` de `app.py` et `overlay.py` sont déjà sous `try/except AttributeError`. Autrement dit : Presence et le host-agent ont de bonnes chances de démarrer sur macOS **sans** les modules `platform_*`, qui n'apportent que de meilleurs messages d'erreur.
2. **N'utiliser une bibliothèque qu'à son API la plus fréquentée.** `sd.InputStream(samplerate=16000, channels=1, dtype='int16')` sur le device par défaut, c'est la ligne de tous les démos Whisper sur Mac. `NSWindow` via pyobjc, `rumps`, un `NSStatusItem`, c'est de la surface non fréquentée : refuser.
3. **Mettre chaque inconnue derrière une sonde à l'exécution avec un repli dessiné à l'avance**, de sorte que l'issue de la démo ne dépende pas de la réponse à l'inconnue.

## 1. Ce qu'il faut renoncer à porter

**Le cœur ne tourne pas sur Mac. Point final.** `Dockerfile` : `FROM nvidia/cuda:12.4.1-devel-ubuntu22.04`, llama.cpp et whisper.cpp compilés `GGML_CUDA=ON` pour `sm_89`, `docker-compose.yml` avec réservation `driver: nvidia`. Sur Apple Silicon, `compose up` échoue avant même de démarrer (« could not select device driver nvidia »), et une image x86 CUDA sous Rosetta n'a aucun GPU. Metal n'est pas accessible depuis un conteneur Docker sur Mac. Ce n'est pas un portage à faire en cinq jours, c'est une seconde pile d'inférence. À couper, pas à deviner.

**La plus petite version macOS qui ait un sens produit** : Presence (fenêtre Tk) + host-agent (micro/haut-parleur) sur le Mac, connectés en LAN au cœur sur le PC Windows via `--url ws://<ip-windows>:8001/hostagent` (`app.py` a déjà l'option, `docker-compose.yml` publie `8001:8001` sur toutes les interfaces). Le Mac ne calcule rien. C'est cohérent avec l'ADR-006 et ça fait une histoire de démo : « le cœur est un serveur, n'importe quel poste est un terminal ».

À couper aussi, parce que ce sont des paris non vérifiables :
- Le bundle `.app`, `Info.plist`, `.icns`, signature, notarisation. Un `.app` non signé enveloppant un `python3` externe cumule Gatekeeper et une attribution TCC incertaine. `Info.plist` livré sans bundle est un faux signal de maturité : ne pas le présenter.
- `overlay.py` sur macOS : `overrideredirect` + `-topmost` + `-alpha` sous Aqua est notoirement capricieux, et la parité chroma-key est impossible sans pyobjc. Presence seule.
- pyobjc, `rumps`, barre de menus. Deux runloops non testées = gel garanti en démo.
- Audio Bluetooth (voir 2c).

## 2. Où macOS ne pardonne pas — mode d'échec probable et neutralisation par construction

**a. Permission micro TCC.** Le mode d'échec le plus probable n'est pas l'exception : c'est un flux qui s'ouvre normalement et **livre des zéros**. C'est le comportement connu de CoreAudio quand l'accès est refusé (les rapports « sounddevice enregistre du silence sur Mac » sont tous ça). Conséquence avec le code actuel : `micro_accessible()` répond `True`, le VAD ne déclenche jamais, l'app affiche « j'écoute » indéfiniment. Neutralisation : un **chien de garde sur le signal lui-même**, pas sur l'API — si 100 % des échantillons sont exactement `0` pendant ~1,5 s flux ouvert, émettre un état `micro_muet` vers Presence avec le chemin Réglages → Confidentialité → Microphone. Un vrai micro ne produit jamais des zéros exacts, le discriminateur est robuste. Et c'est **testable sur Windows aujourd'hui** avec une fabrique de flux injectée qui rend des zéros — la seule pièce macOS qu'on peut vraiment valider avant. Second point : lancé via `lancer.command`, le prompt TCC sera attribué à **Terminal**, pas à « Hyper Ambient ». Accepter et documenter : Terminal est signé, connu, sa permission persiste. C'est plus prévisible qu'un `.app` maison.

**b. Sandbox, signature, Gatekeeper.** Mode d'échec : quarantaine `com.apple.quarantine` sur un fichier arrivé par navigateur ou AirDrop, bit exécutable perdu au transfert, « développeur non identifié ». Neutralisation : distribuer par `git clone` (aucun attribut de quarantaine, par construction) et lancer par `sh packaging/macos/lancer.command` (pas de `chmod`, pas de Gatekeeper sur un script passé à `sh`). Ajouter `*.command text eol=lf` dans `.gitattributes` — le fichier est LF aujourd'hui, mais un checkout Windows avec `autocrlf` peut le casser.

**c. CoreAudio via PortAudio.** Trois modes d'échec : le device refuse 16 kHz/int16 (PortAudio CoreAudio ré-échantillonne en général, risque moyen-faible, mais à sonder avec `check_input_settings`) ; un casque Bluetooth bascule en profil HFP à l'ouverture du micro, avec 1–2 s de coupure et une sortie dégradée qui ressemble à un gel ; le `print(flush=True)` dans le callback temps réel. Neutralisation : **micro et haut-parleurs intégrés uniquement** pour la démo (moins de variables), device par défaut jamais désigné par index (les index diffèrent d'une machine à l'autre — `talk.py` en utilise un), latence par défaut.

**d. Tkinter et le fil principal.** Le mode d'échec numéro un de toute la liste, et le plus bête : **le mauvais Python**. `/usr/bin/python3` (Xcode CLT) embarque Tk 8.5, déprécié et instable sous Aqua ; Homebrew python sans `python-tk` n'a pas `_tkinter`. Neutralisation : un préflight qui refuse de démarrer si `tk.TkVersion < 8.6` ou `windowingsystem != "aqua"`, et imprime la commande `brew install python-tk@3.12` ou le lien python.org. Deuxième mode : un appel Tk depuis le thread session — Windows le tolère, Aqua tue le processus. `SessionVocale` passe par `file_ui.put()`, c'est correct ; à auditer une fois par grep pour être sûr qu'aucun widget n'est touché hors du fil principal. Cosmétique à accepter : la barre de menus dira « Python ».

**e. Chemins.** Déjà traité : `LOCALAPPDATA` absent → `~/.hyper-ambient`. APFS est insensible à la casse par défaut comme NTFS, les `import overlay` locaux passent. Pas d'`os.startfile` dans `native/`. Rien à faire.

**f. Docker sur Apple Silicon.** Voir point 1 : coupé. Ce qui reste, c'est le **réseau Windows → LAN** : Docker Desktop/WSL2 publie le port via un proxy, et le pare-feu Windows peut le bloquer. Testable ce soir depuis un téléphone sur le même Wi-Fi (`http://<ip>:8000`). Pour la soutenance : câble Ethernet direct ou hotspot téléphone, jamais le Wi-Fi de la salle.

## 3. Échouer proprement

- **Un `doctor` avant Tk**, script unique qui vérifie dans l'ordre : version Python, Tk ≥ 8.6 + aqua, `import sounddevice`, présence d'un device d'entrée, `check_input_settings` / `check_output_settings` à 16 kHz int16, connexion TCP vers l'URL du cœur avec timeout 2 s. Une ligne par test, un seul message actionnable en cas d'échec, sortie non nulle. Il s'écrit et se teste sur Windows.
- **Le chien de garde zéros** (2a) : dégradation visible et calme au lieu d'une écoute infinie.
- **Bannière d'état réseau** déjà présente (`sante`) ; vérifier qu'une perte de WebSocket en cours de démo ré-essaie sans figer et sans `SystemExit` depuis le thread.
- **Garder le Terminal ouvert** : `lancer.command` est un avantage en démo, les logs sont sous les yeux. Le `pythonw` sans console est un luxe Windows.
- Toute fonctionnalité cosmétique (icône, alpha, topmost) : `try/except`, log, on continue — c'est déjà le contrat de `platform_ui`.

## 4. Le runner `macos-latest`

Correction sur la prémisse : le runner GitHub macOS n'est **pas sans écran**. Il tourne dans une session Aqua ouverte, `tk.Tk()` crée une vraie fenêtre, et `screencapture` en fait un PNG. Ce qu'il valide donc : imports sur Apple Silicon, `sounddevice` + PortAudio qui se chargent, version de Tk, `platform_ui.apply_overlay_window_mode` qui rend `alpha` sans `TclError`, `iconphoto` PNG, et surtout **une capture d'écran de la fenêtre Presence rendue sur un vrai macOS**. Ce qu'il ne valide pas : le micro (aucun device ; on n'exerce que le chemin « pas de périphérique »), le prompt TCC, le son, le clavier maintenu.

Ça vaut le coût : 30 minutes de mise en place, 5 minutes par run, un seul workflow avec trois artefacts (sortie pytest, JSON du `doctor`, capture d'écran). Ne pas en faire une CI de plus.

Mais l'option supérieure, que la question écarte trop vite : **louer un Mac mini M-series à l'heure** (Scaleway, MacStadium ; minimum 24 h imposé par Apple, de l'ordre de quelques euros). Accès VNC = vraie session graphique, prompt TCC visible et cliquable, Tk visible, réseau réel vers votre PC. Il manque le micro physique ; BlackHole comme device d'entrée virtuel permet de déclencher TCC et de valider la chaîne jusqu'au cœur en y injectant un fichier audio. C'est le meilleur rapport information/euro disponible en cinq jours, et ça permet de faire la séquence du point 5 deux fois avant le 25.

## 5. Trente minutes sur un Mac, dans l'ordre

Règle : à chaque échec, capturer (`2>&1 | tee ~/ha-mac.log`), noter, passer au test indépendant suivant. On collecte, on ne corrige pas sur le chrono. Si le `doctor` existe, les étapes 1–4 prennent 3 minutes au lieu de 15.

1. **0–3 min — l'interpréteur.** `python3 -c "import tkinter; print(tkinter.TkVersion)"`. Si absent ou 8.5 : `brew install python-tk@3.12`, `export HYPERAMBIENT_PYTHON=$(brew --prefix)/bin/python3.12`. C'est l'échec le plus probable et il conditionne tout.
2. **3–6 min — PortAudio.** `pip install sounddevice numpy websockets`, puis `python3 -m sounddevice` : la liste des devices apparaît.
3. **6–8 min — le format.** `check_input_settings` et `check_output_settings` à `16000 / 1 / int16` sur le device par défaut.
4. **8–12 min — TCC, l'expérience qui tranche l'inconnue n°1.** `sd.rec(2*16000, samplerate=16000, channels=1, dtype='int16')` en parlant, puis `abs(x).max()`. Le prompt doit apparaître pour Terminal ; accepter ; le max doit être > 0. Refuser sur un second essai et **noter si c'est une exception ou des zéros**. Cette réponse dimensionne le chien de garde.
5. **12–14 min — le haut-parleur.** `sd.play` d'un sinus 440 Hz à 16 kHz. On l'entend ou pas.
6. **14–17 min — le cœur.** `nc -vz <ip-windows> 8001`, puis une connexion WebSocket Python à `/hostagent`. Si ça échoue, c'est le pare-feu Windows, pas le Mac.
7. **17–27 min — Presence.** `HYPERAMBIENT_PYTHON=... sh packaging/macos/lancer.command --url ws://<ip>:8001/hostagent`. La fenêtre s'ouvre ? `TclError` dans le Terminal ? Un aller-retour appuyer-pour-parler complet. C'est la démo.
8. **27–30 min — seulement s'il reste du temps.** `overlay.py`. On s'attend à des ratés ; on note, on ne touche pas.

## Ce qu'on montre le 25

- **Primaire, toujours** : la démo Windows, celle qui tourne tous les jours.
- **Si la séquence ci-dessus a passé les étapes 1–7 sur un Mac réel avant le 25** : le Mac en second terminal, en direct, cadré comme la preuve de l'architecture à deux composants. Jamais un premier lancement sur scène.
- **Sinon** : l'abstraction `platform_audio` / `platform_ui` et ses 15 tests, la capture d'écran du runner macOS (« cette fenêtre a été rendue par macOS »), et la phrase exacte : « le cœur reste sur GPU NVIDIA par choix ; le terminal macOS est écrit, s'importe et se rend sur macOS, il n'a pas encore été validé au micro ». C'est défendable. « Ça marche sur Mac » sans l'avoir vu ne l'est pas.

Ce que je ferais dans les cinq jours, par ordre : chien de garde zéros avec son test Windows, `doctor`, `.gitattributes`, workflow macOS avec capture d'écran, test pare-feu depuis un téléphone, location d'un Mac pour 24 h et deux passages de la séquence. Rien de cela ne touche le chemin Windows de la démo. Je n'ai modifié aucun fichier.