---
date: 2026-09-19
lane: C7
type: etude-technique
statut: proposition
objet: Portage de Hyper Ambient de Docker/WSL vers Windows natif
---

# C7 — Hyper Ambient natif Windows

## Conclusion

Une distribution **Windows x64 native, sans Docker Desktop ni WSL**, est réaliste sur la machine cible NVIDIA. Les briques les plus importantes ont une voie Windows maintenue :

- `llama-server` : archives officielles Windows x64 CUDA de llama.cpp ;
- EARS Whisper : roues Windows de CTranslate2/faster-whisper avec CUDA ;
- EARS Parakeet : paquets et binaires Windows de sherpa-onnx, CPU et CUDA ;
- MOUTH Magpie : NeMo-Speech.cpp publie maintenant un installateur PowerShell et des archives Windows, avec MagpieTTS dans le profil `core`/`server` ;
- audio et présence : le client matériel est déjà natif Windows via `sounddevice`/PortAudio/WASAPI.

Il ne faut cependant pas transformer directement l'image Docker en installateur. La cible robuste est un petit **superviseur exécuté dans la session utilisateur**, un Python 3.11 embarqué et des moteurs natifs versionnés côte à côte. Les modèles restent hors du répertoire de programme, sur un SSD choisi au premier lancement.

Deux réserves restent à lever par prototype :

1. la combinaison exacte `faster-whisper` / CTranslate2 / CUDA / cuDNN doit être figée et testée ensemble ; les exigences évoluent selon les versions ;
2. NeMo-Speech.cpp fonctionne sous Windows, mais sa normalisation de texte interne n'y est pas prise en charge. Magpie doit donc continuer à recevoir le texte déjà normalisé par Hyper Ambient, puis être validé en français avec la voix Sofia.

Le choix final de l'oreille n'est volontairement **pas** fait ici.

## Périmètre et méthode

Cette étude couvre l'exécution produit, les modèles et l'installation. Elle ne porte pas le banc de développement complet sous Windows et ne modifie aucun code.

Inventaire établi à partir de `Dockerfile`, `docker-compose.yml`, `requirements*.txt`, `src/`, `native/`, `dev/scripts/serve_llama.sh`, `dev/scripts/serve_whisper.sh`, `dev/scripts/fetch_models.sh` et `dev/scripts/relancer_routeur.sh`. État observé le 19 septembre 2026 ; les dépendances distantes sont vérifiées dans leurs documentations officielles listées en fin de document.

## 1. Ce qui dépend aujourd'hui de Docker ou de Linux

### 1.1 Socle du conteneur

Le conteneur n'est pas une simple enveloppe Python. Il fournit actuellement :

- Ubuntu 22.04 sur `nvidia/cuda:12.4.1-devel` ;
- Python 3.11 et ses en-têtes ;
- PyTorch CUDA 12.4 ;
- `libsndfile`, FFmpeg et SoX ;
- Git, curl, wget ;
- la chaîne C/C++ : CMake, ccache, pkg-config, GCC/build-essential ;
- OpenSSL et libcurl de développement ;
- llama.cpp et whisper.cpp compilés dans l'image pour CUDA `sm_89`, puis installés sous `/usr/local` ;
- les roues Python des piles ASR, VAD, TTS, audio et serveur web.

En production native, les compilateurs, Git, ccache, wget, SoX et les paquets `*-dev` ne doivent pas être installés chez l'utilisateur. Ils appartiennent à la CI de fabrication. L'installateur livre uniquement les exécutables, DLL, roues et notices de licences déjà construits et testés.

### 1.2 Orchestration Docker

`docker-compose.yml` apporte aujourd'hui les fonctions suivantes :

| Fonction Docker | État actuel | Besoin Windows natif |
|---|---|---|
| Injection de configuration | `.env.local` comme `env_file` et montage en lecture seule | configuration par utilisateur ; secrets hors du fichier de configuration |
| Accès GPU | réservation NVIDIA, `CUDA_VISIBLE_DEVICES=0` | pilote NVIDIA hôte + DLL CUDA nécessaires à chaque moteur |
| Montage des sources | `src`, `dev`, `native` vers `/workspace` | application installée en lecture seule, sans source de développement |
| Persistance | `models`, `data`, `logs` montés depuis l'hôte | répertoires Windows séparés du runtime |
| Ports | 8000, 8001, 8090→8080, 8091→8081 | écoute sur `127.0.0.1`, ports configurables, sans publication réseau |
| Plafond RAM | cgroup `mem_limit=8g`, swap 8 Gio | Job Objects Windows et budgets distincts par moteur |
| Mémoire partagée | `/dev/shm` à 2 Gio | aucun équivalent à recréer tant qu'aucun composant n'en dépend explicitement |
| Cycle de vie | conteneur interactif + scripts shell | superviseur Windows, arrêt ordonné et redémarrage borné |

### 1.3 BRAIN — llama-server

État actuel :

- llama.cpp est compilé depuis `main` dans le `Dockerfile` ; aucune version n'est figée ;
- le lancement passe par Bash et `dev/scripts/serve_llama.sh` ;
- découverte du GGUF par `ls`, tri et `head` ;
- modèle sous `/workspace/models/gguf` ;
- service dans le conteneur sur `0.0.0.0:8080`, publié sur l'hôte en `:8090` ;
- options actives : offload GPU complet, contexte 8192, batch 512, Flash Attention, cache K/V Q8, alias `mother-local`, gabarit Jinja ;
- le modèle retenu au moment de la note est `granite-4.2-3b-Q4_K_M.gguf` (environ 2,1 Gio sur ce poste).

Dépendances Linux à supprimer : compilation GCC, `/usr/local/bin`, `LD_LIBRARY_PATH`, Bash, `ls/head`, chemins `/workspace` et publication Docker.

Équivalent Windows : livrer une **release officielle llama.cpp Windows x64 CUDA** et les DLL CUDA correspondantes à côté de l'exécutable. L'archive officielle couvre Windows x64 CUDA ; il n'est donc pas nécessaire d'installer Visual Studio ou le CUDA Toolkit complet chez l'utilisateur. Le pilote NVIDIA compatible reste requis. Le manifeste produit doit figer une release précise et ses SHA-256, jamais télécharger « latest » au démarrage.

Le serveur doit rester un processus séparé et conserver l'API OpenAI locale. Cela limite les changements applicatifs et permet un redémarrage du cerveau sans faire tomber l'audio.

### 1.4 EARS — voies présentes ou étudiées

Le dépôt contient plusieurs voies ; le choix produit est en cours. L'installateur ne doit pas être couplé à une seule avant arbitrage.

#### faster-whisper / CTranslate2

État actuel : `src/ears/faster_whisper_asr.py`, Python, modèle `large-v3-turbo`, CUDA et `int8_float16`. Le cache Hugging Face se trouve sous `/workspace/models/hf-cache`. Le décodage audio utilise PyAV.

Équivalent Windows : voie **verte sous réserve de verrouillage des versions**. CTranslate2 publie des roues Windows x86-64 avec GPU ; faster-whisper s'installe sur Windows et PyAV embarque ses bibliothèques FFmpeg. Les versions récentes de faster-whisper demandent CUDA 12 et cuDNN 9, alors que d'autres combinaisons CTranslate2 documentent encore cuDNN 8. La distribution doit donc embarquer une matrice testée, par exemple :

`Python exact + faster-whisper exact + ctranslate2 exact + cuBLAS exact + cuDNN exact + pilote minimal`.

Les DLL sont privées au runtime Hyper Ambient ; aucune modification globale du `PATH` n'est nécessaire.

#### whisper.cpp

État actuel : construit dans l'image, modèle GGML sous `/workspace/models/whisper`, script `serve_whisper.sh`, port conteneur 8081 publié en 8091.

Équivalent Windows : comme llama.cpp, produire ou prendre une archive Windows CUDA et lancer `whisper-server.exe` sur la boucle locale. Cette voie garde une séparation de processus simple, mais n'est pas l'oreille actuellement décidée.

#### sherpa-onnx / Parakeet

État étudié : le banc référence le modèle Parakeet TDT 0.6B v3 INT8 de sherpa-onnx.

Équivalent Windows : voie **verte pour le prototype**. sherpa-onnx publie des roues CPU Windows x64 et une procédure CUDA Windows x64. Il faut figer la variante ONNX Runtime/CUDA avec ses DLL et mesurer la parité du modèle choisi. Ne pas conclure de la seule présence d'une roue que les latences et la ponctuation française conviennent.

#### NeMo-Speech.cpp / Nemotron et Canary

NeMo-Speech.cpp a maintenant une voie Windows officielle : archive native ou construction Visual Studio, backends CPU/CUDA/Vulkan, serveur HTTP et cache de modèles sous `%LOCALAPPDATA%\NeMoSpeech\models` par défaut.

Cela rend Nemotron testable sans WSL. En revanche, la compatibilité de **Canary-1B-v2** avec le runtime natif retenu doit être prouvée séparément ; ne pas confondre la prise en charge générale de NeMo-Speech.cpp avec la garantie qu'un checkpoint NeMo Python donné est convertible et supporté.

#### Qwen3-ASR existant

`src/ears/qwen3_asr.py` dépend de Transformers, PyTorch et bitsandbytes. Cette voie augmente fortement la surface de compatibilité Windows et n'appartient pas aux trois candidats cités dans la note de décision. Elle ne doit pas bloquer le premier installateur natif.

### 1.5 MOUTH — Magpie via NeMo-Speech.cpp

État actuel :

- `src/mouth/magpie_tts.py` pilote un `nemo-speech serve` persistant par HTTP ;
- le binaire est recherché dans des chemins Linux sans extension ;
- le modèle vit sous `/workspace/models/tts-bench/magpie` ;
- la détection d'un serveur existant utilise `pgrep -af` ;
- le processus est démarré avec les conventions POSIX ;
- les ports 8001, 8080 et 8090 sont réservés ;
- les poids Magpie et NanoCodec présents sur la machine occupent environ 0,51 Gio.

Équivalent Windows : voie **orange-verte**. La documentation officielle de NeMo-Speech.cpp indique :

- un installateur `install.ps1` et des archives Windows x86-64 ;
- MagpieTTS Multilingual 357M et NeMo NanoCodec dans la fonction TTS ;
- un profil `core` comprenant ASR, diarisation et TTS, et un profil `server` ajoutant l'API HTTP ;
- CUDA 12/13 en construction source, ou une archive native quand disponible ;
- un cache Windows de modèles ;
- absence de normalisation de texte interne sous Windows.

Pour Hyper Ambient, il faut privilégier l'archive binaire `server` figée. La construction source Visual Studio/CUDA est un repli de CI, pas une étape d'installation utilisateur. Le texte doit continuer à passer par la normalisation Hyper Ambient avant l'appel TTS. Critères du prototype : voix Sofia, français, nombres, ponctuation, accents, chemin contenant des espaces, démarrage à froid, deuxième phrase, arrêt et relance.

### 1.6 TURN, audio scientifique et utilitaires

- Silero VAD utilise ONNX : roues Windows disponibles via ONNX Runtime ; faible risque.
- NumPy, SciPy, librosa, soundfile et pyloudnorm ont des roues Windows, mais leurs versions doivent être verrouillées.
- `libsndfile` est aujourd'hui un paquet Ubuntu ; sous Windows, la DLL doit venir de la roue testée ou être embarquée explicitement.
- FFmpeg/SoX sont surtout utilisés par les bancs et conversions. Le runtime faster-whisper n'exige pas un `ffmpeg.exe` système, car PyAV embarque ses bibliothèques. Ne pas livrer ces outils tant qu'un appel produit ne le justifie pas.
- Les outils de développement qui invoquent `bash`, `curl`, `du`, `nproc`, `grep`, `awk`, `pgrep`, `ps`, `nohup`, `kill` ou écrivent sous `/tmp` ne sont pas portables. Ils ne doivent pas être inclus tels quels dans le produit.

### 1.7 Host-agent, audio et présence

L'appellation actuelle masque deux côtés :

- `native/hostagent/talk.py` capture et restitue déjà l'audio sous Windows avec `sounddevice`, choisit les périphériques et se connecte à `ws://127.0.0.1:8001/hostagent` ;
- `dev/scripts/serve_hostagent.py` tourne encore dans le conteneur et héberge EARS, BRAIN, MOUTH et le WebSocket ;
- `native/presence` tourne dans la session graphique Windows.

La migration la moins risquée conserve d'abord cette frontière WebSocket, mais exécute les deux côtés sous Windows. Elle évite une fusion fonctionnelle pendant le portage. Plus tard seulement, le transport local pourra être remplacé par un appel en processus si cela apporte un bénéfice mesuré.

Le lanceur ne doit pas être un Windows Service : le microphone, les haut-parleurs, l'overlay et la session utilisateur sont au cœur du produit. Le démarrage automatique doit se faire **à l'ouverture de session de l'utilisateur**, par une tâche planifiée ou une entrée de démarrage, et rester désactivable dans l'application.

## 2. Correspondance des chemins et conventions

La correction structurante future est un résolveur de chemins unique. Aucun chemin absolu Linux ou lettre de lecteur ne doit rester dans la logique métier.

| Actuel | Windows natif proposé | Règle |
|---|---|---|
| `/workspace` | répertoire de l'application pour le code ; données ailleurs | ne jamais déduire les données depuis le CWD |
| `/workspace/models` | racine SSD choisie, ex. `D:\HyperAmbient\Models` | configurable, persistante, non supprimée lors d'une mise à jour |
| `/workspace/models/gguf` | `<models_root>\brain` | un manifeste désigne le modèle actif |
| `/workspace/models/hf-cache` | `<models_root>\hf-cache` | définir `HF_HOME` seulement pour les processus concernés |
| `/workspace/models/tts-bench/magpie` | `<models_root>\mouth\magpie` | séparer runtime NeMo et poids |
| `/workspace/data` | `%LOCALAPPDATA%\Hyper Ambient\data` | données applicatives par utilisateur |
| `/workspace/logs` et `/tmp/hostagent.log` | `%LOCALAPPDATA%\Hyper Ambient\logs` | rotation, taille bornée, aucune clé |
| `/workspace/.env.local` | `%LOCALAPPDATA%\Hyper Ambient\config` | configuration non secrète ; secrets via stockage Windows protégé |
| `/usr/local/bin`, `/opt/*` | `<app_root>\runtime\<moteur>\<version>` | runtime immuable, côte à côte |
| `host.docker.internal` | `127.0.0.1` ou URL configurée | plus de passerelle Docker |
| `0.0.0.0` | `127.0.0.1` | ne pas exposer les modèles au LAN |

Le nom de répertoire contient volontairement un espace dans plusieurs tests : le portage doit fonctionner avec `Hyper Ambient`, les accents dans le nom utilisateur et un SSD autre que `C:`.

## 3. Remplacer le cgroup sans perdre l'isolation

Le plafond Docker de 8 Gio a déjà protégé le poste, mais il a aussi fait tomber le host-agent lors d'essais lourds. Windows ne fournit pas un cgroup identique, mais les **Job Objects** gèrent un groupe de processus, propagent l'appartenance aux enfants et peuvent imposer une limite de mémoire engagée au niveau du job.

Plan recommandé :

- un Job Object par moteur lourd : BRAIN, EARS et MOUTH ;
- un petit job séparé pour le cœur/transport, qui ne doit pas être sacrifié par une pointe TTS ;
- `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` pour ne laisser aucun processus orphelin ;
- limite de mémoire engagée par job avec notification, et arrêt propre avant relance ;
- seuil souple global avant chargement d'un modèle, basé sur RAM disponible ;
- trois tentatives maximum avec temporisation, puis repli explicite au lieu d'une boucle de crash.

Une limite Job Object couvre la RAM engagée, **pas la VRAM**. Le superviseur doit conserver un budget GPU séparé : interrogation `nvidia-smi` ou NVML avant chargement, réservation logique par moteur, et refus de lancer un modèle si la somme mesurée dépasse le plafond produit. Le budget de 10 Gio de VRAM utilisé par le dépôt reste une politique applicative, pas une garantie du système d'exploitation.

`shm_size: 2gb` n'a pas besoin d'un remplacement préventif : les processus actuels communiquent en HTTP/WebSocket et fichiers. Si une future optimisation utilise de la mémoire partagée, employer alors un mapping de fichier Windows nommé, avec un quota explicite.

## 4. Architecture native cible

```text
Session utilisateur Windows
  HyperAmbientLauncher.exe
    ├─ présence / PTT / WASAPI
    ├─ core Python embarqué : WebSocket 127.0.0.1:8001
    ├─ llama-server.exe : API locale, port configurable (8090 au départ)
    ├─ moteur EARS choisi : bibliothèque Python ou serveur local
    └─ nemo-speech.exe serve : Magpie, port local dédié

SSD choisi au premier lancement
  HyperAmbient\Models\
    ├─ brain\
    ├─ ears\
    ├─ mouth\
    ├─ hf-cache\
    └─ manifests\
```

Le superviseur possède les processus enfants et leurs Job Objects. Les moteurs ne modifient pas le `PATH` global, n'écoutent pas sur le réseau et n'écrivent pas dans `Program Files`.

## 5. Plan d'installateur

### 5.1 Format

Recommandation : un bootstrapper Windows signé, construit avec **WiX Burn** ou un équivalent capable de chaîner des prérequis, suivi d'un MSI ou d'un paquet applicatif par utilisateur. Burn sait chaîner MSI et EXE et gérer réparation/désinstallation ; la décision définitive doit aussi tenir compte de ses conditions de maintenance/licence au moment de l'industrialisation.

Pour le premier prototype, une installation par utilisateur dans `%LOCALAPPDATA%\Programs\Hyper Ambient` réduit les besoins d'élévation et correspond au fonctionnement audio par session. Une installation machine pourra venir plus tard si la politique d'entreprise l'exige.

### 5.2 Contenu livré, sans modèles lourds

Le paquet initial contient :

- un lanceur/superviseur signé ;
- Python 3.11 x64 embarqué, isolé du Python système ;
- le code applicatif et un `site-packages` produit en CI depuis un lockfile avec hashes ;
- les roues Windows nécessaires, sans compilation au premier lancement ;
- la release llama.cpp Windows CUDA figée et ses DLL ;
- la release NeMo-Speech.cpp Windows figée ;
- le runtime EARS correspondant au choix produit, éventuellement en composant optionnel ;
- les notices de licences et versions de toutes les dépendances ;
- aucun secret et aucun checkpoint lourd.

La distribution Python embarquée n'inclut pas pip par défaut. C'est souhaitable : pip et l'accès à PyPI ne doivent pas être requis sur le poste client. La CI assemble et teste l'environnement complet, puis l'installateur le traite comme un artefact immuable.

### 5.3 Détection des prérequis

Avant installation ou au premier lancement :

1. vérifier Windows x64 pris en charge ;
2. relever GPU, VRAM et version du pilote NVIDIA ;
3. vérifier le runtime Visual C++ exigé par les binaires ;
4. tester le chargement réel des DLL CUDA de chaque moteur, pas seulement `nvidia-smi` ;
5. proposer une voie CPU lorsque le moteur la supporte, avec avertissement de performance ;
6. vérifier ports locaux, microphone et sortie audio sans demander d'accès réseau entrant.

Ne pas imposer le CUDA Toolkit ou Visual Studio au client quand les archives redistribuables suffisent.

### 5.4 Premier lancement et modèles sur SSD

Le premier lancement présente la taille exacte du pack sélectionné et demande une racine de modèles. Comportement recommandé :

- proposer un disque fixe signalé comme SSD quand Windows expose cette information ;
- afficher espace libre, espace requis et marge de 20 % ;
- si le type de média est inconnu, avertir plutôt que bloquer ;
- accepter par exemple `D:\HyperAmbient\Models` ;
- mémoriser le chemin absolu dans la configuration utilisateur ;
- ne jamais le déplacer silencieusement lors d'une mise à jour.

Chaque modèle vient d'un **manifeste versionné et signé** contenant identifiant, URL officielle, taille, SHA-256, licence et compatibilité moteur. Le téléchargeur :

1. écrit dans un fichier `.part` ;
2. reprend un téléchargement interrompu si le serveur le permet ;
3. vérifie taille et SHA-256 ;
4. renomme atomiquement vers sa destination ;
5. conserve l'ancien modèle actif jusqu'au succès du nouveau ;
6. n'inscrit jamais de jeton dans les logs ou l'URL affichée.

Pack initial attendu : Granite 4.2 3B Q4_K_M, l'oreille finalement retenue, Magpie 357M, NanoCodec et les petits actifs VAD. La taille et les URLs doivent venir du manifeste de release, pas de nombres codés en dur dans l'interface.

### 5.5 Démarrage, santé et replis

Ordre de démarrage :

1. lanceur, journalisation et Job Objects ;
2. présence/audio ;
3. cerveau local ;
4. oreille ;
5. bouche ;
6. test de santé de bout en bout.

Un port ouvert ne suffit pas. Les sondes doivent vérifier : modèle annoncé par BRAIN, transcription d'un court échantillon local, synthèse d'une phrase puis décodage WAV, et poignée de main WebSocket. En cas d'échec : message utilisateur actionnable, backend de secours s'il existe, aucun redémarrage infini.

### 5.6 Mise à jour, réparation et désinstallation

- runtime installé par versions côte à côte ; bascule seulement après smoke test ;
- retour à la dernière version fonctionnelle en cas d'échec ;
- modèles et configuration hors du répertoire de programme ;
- mise à jour des modèles indépendante de celle du runtime ;
- binaires et installateur Authenticode signés ;
- SHA-256 contrôlé pour tous les téléchargements ;
- désinstallation : demander séparément si l'utilisateur veut conserver modèles et données ;
- ne jamais supprimer récursivement une racine SSD choisie par l'utilisateur ; supprimer uniquement les fichiers possédés et consignés dans le manifeste d'installation.

## 6. Phasage proposé

### P0 — figer le contrat de distribution

- versions exactes des quatre piles : Python, BRAIN, EARS, MOUTH ;
- manifeste des artefacts et licences ;
- convention de chemins Windows ;
- ports et protocole de santé ;
- budgets RAM/VRAM par processus.

### P1 — preuve native manuelle sur le poste cible

Sans installateur et sans toucher au choix final EARS :

- lancer la release Windows CUDA de llama.cpp avec Granite ;
- tester séparément faster-whisper/CT2 et sherpa-onnx ;
- lancer NeMo-Speech.cpp Windows avec Magpie/Sofia ;
- faire un tour micro → EARS → BRAIN → MOUTH → haut-parleur ;
- mesurer démarrage à froid, latences, RAM, VRAM et arrêt propre.

Critère de sortie : aucune commande Docker/WSL, aucun Python système requis, chemins avec espaces fonctionnels.

### P2 — superviseur et isolation

- conserver temporairement le WebSocket 8001 ;
- lancer les moteurs comme enfants ;
- Job Objects séparés ;
- détection de crash, budgets et repli ;
- démarrage à l'ouverture de session.

### P3 — installateur et téléchargement initial

- Python embarqué et wheelhouse verrouillé ;
- installateur signé ;
- sélection du SSD ;
- manifestes, reprise, SHA-256 et progression ;
- réparation, mise à jour et désinstallation sûre.

### P4 — qualification

- machine Windows propre, sans Docker, WSL, Python, CMake ni CUDA Toolkit ;
- compte utilisateur standard ;
- installation sur `C:` puis modèles sur `D:` ;
- nom utilisateur accentué et chemins longs/avec espaces ;
- SSD absent au redémarrage ;
- port déjà occupé ;
- réseau coupé après téléchargement ;
- pilote NVIDIA trop ancien ;
- manque de RAM/VRAM ;
- veille/réveil, changement de périphérique audio ;
- mise à jour, rollback et désinstallation en conservant les modèles.

## 7. Critères Go / No-Go

Go pour un premier installateur si :

- BRAIN, EARS retenue et Magpie passent chacun 30 démarrages/arrêts sans processus orphelin ;
- un tour vocal réel fonctionne sur une machine propre ;
- RAM et VRAM restent sous les budgets définis ;
- la voix Sofia reste conforme en français après normalisation applicative ;
- la reprise de téléchargement et le rollback sont démontrés ;
- aucun service n'écoute hors boucle locale ;
- aucun secret n'apparaît dans les logs.

No-Go si l'une des conditions suivantes persiste :

- Magpie Windows exige une construction locale ou un outil développeur chez l'utilisateur ;
- les DLL CUDA de BRAIN, EARS et MOUTH ne peuvent pas cohabiter dans des répertoires privés et reproductibles ;
- l'oreille retenue n'a pas de paquet Windows reproductible ;
- le superviseur ne peut pas contenir une pointe RAM sans tuer le cœur audio ;
- l'installateur peut supprimer ou écraser des modèles extérieurs à son manifeste.

## 8. Décisions et questions laissées ouvertes

| Sujet | Décision C7 |
|---|---|
| Docker/WSL requis chez le client | Non |
| Architecture CPU | Windows x64 d'abord |
| GPU cible | NVIDIA ; CPU comme repli selon moteur |
| Python | 3.11 embarqué et privé, à confirmer par matrice de roues |
| BRAIN | llama.cpp Windows CUDA, API locale conservée |
| EARS | non décidé ; adaptateur d'installation modulaire |
| MOUTH | NeMo-Speech.cpp Windows à prototyper avec Magpie/Sofia |
| Audio | processus en session utilisateur, pas Windows Service |
| Modèles | téléchargement au premier lancement, racine SSD choisie |
| Limite RAM | Job Objects séparés, pas un plafond global unique |
| Limite VRAM | politique et télémétrie applicatives |
| Fusion du host-agent et du core | différée après parité fonctionnelle |

## Sources officielles consultées

- llama.cpp, [installation et paquets précompilés](https://github.com/ggml-org/llama.cpp/blob/master/docs/install.md) et [releases Windows CUDA](https://github.com/ggml-org/llama.cpp/releases)
- faster-whisper, [prérequis Windows/CUDA et installation](https://github.com/SYSTRAN/faster-whisper)
- CTranslate2, [roues Windows et support GPU](https://opennmt.net/CTranslate2/installation.html)
- sherpa-onnx, [installation multi-plateforme](https://k2-fsa.github.io/sherpa/onnx/install/index.html) et [paquet Python](https://k2-fsa.github.io/sherpa/onnx/python/install.html)
- NVIDIA NeMo-Speech.cpp, [installation Windows](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/install.md), [construction Windows](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/build.md) et [dépôt](https://github.com/NVIDIA/NeMo-Speech.cpp)
- Python, [distribution embarquée Windows](https://docs.python.org/3/using/windows.html#the-embeddable-package)
- Microsoft, [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [limite de mémoire d'un job](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information), [WASAPI](https://learn.microsoft.com/en-us/windows/win32/coreaudio/wasapi) et [démarrage à l'ouverture de session](https://learn.microsoft.com/en-us/windows/win32/taskschd/starting-an-executable-when-a-user-logs-on)
- WiX, [bundles Burn](https://docs.firegiant.com/wix/tools/burn/) et [signature des bundles](https://docs.firegiant.com/wix/tools/signing/)

## Hors périmètre de cette lane

- aucun choix de l'oreille ;
- aucun changement dans `serve_hostagent.py`, EARS, MOUTH ou les modules natifs ;
- aucune relance de service ;
- aucun installateur ou code de portage produit ;
- aucun commit.
