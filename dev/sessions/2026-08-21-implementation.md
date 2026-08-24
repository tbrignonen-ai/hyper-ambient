---
date: 2026-08-21
type: session-log
repo: "D:\\BGB Training\\MOTHER-dev"
status: source-of-truth
---

# Session 2026-08-21 — première implémentation exécutable

Source de vérité factuelle de la session. Tous les chiffres ci-dessous sont
**mesurés sur la machine cible**, pas annoncés par un fournisseur. Ce fichier
sert de base aux notes du vault : ne rien y ajouter qui n'ait été exécuté.

Machine : RTX 4070 12 Go (≈9,5 Go utiles, bureau Windows allumé), 20 vCPU,
15 Go RAM WSL2, Docker Desktop.

---

## 1. Ce qui a été construit

Passage de stubs Python à une chaîne vocale qui tourne de bout en bout.

### Infrastructure

- Image `mother-core:latest`, **32,3 Go**. CUDA 12.4 devel + Python 3.11.
- **llama.cpp** et **whisper.cpp** compilés CUDA `sm_89` (Ada Lovelace) dans
  l'image. Binaires : `llama-server`, `llama-cli`, `llama-tts`, `llama-mtmd-cli`,
  `whisper-cli`, `whisper-server`.
- Couches ajoutées **après** `torch` dans le Dockerfile → un rebuild réutilise
  l'image de base CUDA et les roues torch depuis le cache, sans retéléchargement.
- `requirements-extra.txt` séparé pour la même raison.
- Poids dans `./models` (bind-mount) → survivent aux rebuilds d'image.

### Défaut d'infrastructure corrigé

`docker-compose.yml` ne réservait **aucun device NVIDIA** : `torch.cuda.is_available()`
retournait `False` et `nvidia-smi` était absent du conteneur. Ajout de la
section `deploy.resources.reservations.devices`. Sans ça, tout tournait CPU.

Autre correction : `/dev/snd` ne contient que `timer` sous Docker Desktop
Windows — il n'y a pas d'ALSA. Ce n'est pas une limite à contourner, c'est la
raison d'être de l'agent hôte natif. Passthrough retiré du compose.

Ports : 8000 API, 8001 WebSocket agent hôte, **8090**→8080 `llama-server`,
**8091**→8081 `whisper-server` (8080 hôte est pris par SearXNG).

---

## 2. Chaîne complète mesurée

Question française parlée de 4,26 s, `dev/scripts/pipeline_demo.py --audio`.

| Étage | Mesure | Détail |
|---|---|---|
| TURN | **20 ms**, RTF 0,004 | Silero VAD ONNX, CPU, endpoint à 4,30 s |
| EARS | **370 ms**, RTF 0,087 | faster-whisper `large-v3-turbo` int8_float16, GPU |
| BRAIN | **27 ms** TTFT | llama.cpp local, CUDA |
| MOUTH | **102 ms** TTFA | Piper, ouverture bornée au mot |
| **Round-trip perçu** | **500 ms** | budget NFR-01 = 1200 ms → **marge ×2,4** |

Smoke test `dev/scripts/smoke_test.py` : **9/9**.

Qualité EARS mesurée en boucle fermée (Piper génère du français, Whisper le
retranscrit) : **WER 2,6 %**, et la seule « erreur » est `un` → `1`, un artefact
de normalisation. WER réel ≈ 0.

> Le signal de test synthétique (sinus) faisait halluciner Whisper en boucle et
> gonflait le RTF ×3. Il ne mesurait rien. La boucle fermée l'a remplacé.

---

## 3. Choix de modèle BRAIN local — comparatif mesuré

`dev/scripts/bench_brain.py`, prompt vocal identique, `temperature=0.2`,
mêmes flags serveur, GGUF Q4_K_M (Q5_K_M pour Luth).

| Modèle | Params | TTFT méd. | car/s | markup | arithm. 5 tirs | VRAM | Registre FR |
|---|---|---|---|---|---|---|---|
| LFM2.5-VL-3B | 3 B | **26 ms** | 667 | 0/4 | 0/5 | 2,0 Go | « **Ton** réunion » — accord faux |
| **Luth-2-2B** ✔ | 1,9 B | 38 ms | **697** | 0/4 | 0/5 | **1,5 Go** | tutoiement cohérent |
| Ministral-3-8B-Instruct-2512 | 8 B | 39 ms | 331 | 0/4 | 0/5 | 5,4 Go | meilleure profondeur, mélange tu/vous |
| Luciole-8B-Instruct-1.1 | 8 B | 120 ms | 341 | **2/4** | 0/5 | 5,1 Go | verbeux, fuyant |
| Qwen3-4B-Instruct-2507 | 4 B | 43 ms | 389 | — | 0/5 | 2,8 Go | invente |

**Retenu : Luth-2-2B** (`kurakurai/Luth-2-2B-GGUF`, Q5_K_M). Il tient le TTFT
d'un 8B, double son débit — ce qui empêche la file audio de MOUTH de se vider —
et ne se trompe jamais de registre, seul défaut réellement audible. 1,5 Go au
lieu de 5,4 : c'est cette marge qui permet la cohabitation avec le TTS et
TURN-L2 sur une carte de 12 Go. Ministral-8B documenté comme bascule
« profondeur ».

### Deux résultats négatifs, mesurés

**Le pré-entraînement français natif ne gagne pas.** Luciole-8B (OpenLLM-France,
~30 % de corpus français) est le **pire** des cinq : 3× le TTFT, le seul à
polluer en markdown malgré le prompt vocal, le plus loin du compte en calcul.

**Les cinq modèles ratent l'arithmétique à deux étapes, 0/5 chacun.**
« Il est 14 h 40, réunion dans 20 min, durée 40 min, à quelle heure je finis ? »
→ tous répondent 15 h 20 au lieu de 15 h 40. Un 2/5 observé sur LFM2.5 était du
bruit de prompt et n'a pas survécu à un tirage contrôlé. **C'est le prix assumé
de l'exigence « non-raisonneur »**, pas un modèle à continuer de chercher.

---

## 4. Architecture BRAIN — deux canaux

Un seul protocole, deux déploiements : `llama-server` expose
`/v1/chat/completions` avec le même cadrage SSE que les fournisseurs distants,
donc `src/brain/openai_compat.py` pilote les deux. Basculer est une variable
d'environnement, pas une réécriture.

### Le routeur (`src/brain/router.py`)

```
fin de parole
  → classification locale       ~90 ms, grammaire GBNF, préfixe en cache
  → REFLEXE  : le local répond, streamé directement vers MOUTH
  → ESCALADE : meublage parlé immédiatement, le distant répond derrière
```

**Le classifieur est binaire et biaisé vers l'escalade.** Une version à trois
catégories a été mesurée puis rejetée : interrogé sur la question arithmétique,
le classifieur 2B répondait `RAPIDE` — il routait vers le local la seule
question que tous les locaux ratent. Un petit modèle ne sait pas noter une
difficulté qu'il ne sait pas résoudre. La seule question qu'on lui pose est donc
« est-ce de la conversation courante ? ». Tout le reste, et tout doute, escalade.

Coût de classification mesuré : **335 ms à froid, ~90 ms** préfixe en cache.

### Résultat sur le cas qui le justifiait

```
Bonjour MOTHER.        → reflex                 premier son 599 ms
Merci, c'est noté.     → reflex                 premier son 345 ms
[arithmétique]         → filler→holding→deep    premier son 215 ms  ✓ « Vous finissez à 15h40 »
[question ouverte]     → filler→deep            premier son 251 ms
```

L'escalade donne la **bonne** réponse là où les cinq modèles locaux échouent.

### Bug corrigé — sérieux

`asyncio.wait_for` **annule** son awaitable au timeout. En annulant
`agen.__anext__()`, la ligne d'attente lançait un `CancelledError` dans le
générateur et fermait le flux HTTP du canal profond — elle tuait le canal
qu'elle devait couvrir. Remplacé par `asyncio.wait`, qui laisse la tâche vivre.

---

## 5. Canal distant

**Retenu : `MiniMaxAI/MiniMax-M3`** via CommandCode
(`https://api.commandcode.ai/provider/v1`).

Raison unique et mesurée : **le seul modèle du plan qui émette zéro delta
`reasoning`**. TTFC sur 6 tirs : min 477 / **p50 612** / max 1054 ms.

### Time-to-first-content mesuré, par modèle

| Modèle | TTFC | Deltas de raisonnement |
|---|---|---|
| **MiniMaxAI/MiniMax-M3** | 477 – 1054 ms | **0** |
| deepseek/deepseek-v4-flash | 1336 – 1717 ms | 82 – 86 |
| xiaomi/mimo-v2.5 | 987 – 5086 ms | 5 – 53 |
| Qwen/Qwen3.7-Flash | 4094 – 4909 ms | 156 – 197 |
| stepfun/Step-3.7-Flash | 3399 ms au mieux | 289 — parfois **0 contenu** |
| zai-org/GLM-5.2-Fast | 5853 – 17369 ms | 147 – 759 |

`step-3.7-flash` via l'agrégateur consommait tout le budget de tokens en
raisonnement et renvoyait `finish_reason=length` sans jamais produire de contenu.

### Désactivation du raisonnement

Formes **rejetées** : `reasoning_effort:"none"` (n'accepte que
low/medium/high/xhigh/max), `reasoning:{exclude:true}`, `reasoning:{enabled:false}`,
`chat_template_kwargs:{enable_thinking:false}`, `thinking:{type:"disabled"}`,
`enable_thinking:false`.

Forme **acceptée** : `reasoning: {effort: "none"}` — imbriquée, pas plate.
DeepSeek passe de 1470 à **1057 ms**, deltas 74 → 43. Réduit, pas coupé.

Claude et Gemini : **403 MODEL_NOT_IN_PLAN** sur les deux formes d'API.
Claude passe par `/provider/v1/messages` (forme Anthropic), pas OpenAI.

**StepFun direct** (`api.stepfun.ai`) : clé valide (`/v1/models` → 200), mais
**402 quota_exceeded** sur toutes les complétions, six essais sur deux familles
de modèles. C'est du crédit, pas de la cadence. Modèles exposés par l'API mais
absents de la liste console : `stepaudio-2.5-chat`, `stepaudio-2.5-realtime`,
`stepaudio-2.5-asr-stream`.

### Contre-mesure : le distant en primaire est structurellement mauvais

Testé : distant-primaire + repli local avec échéance de 600 ms → **1477 ms**
bout-en-bout, contre **876 ms** en local seul. L'échéance est une perte sèche.
D'où l'inversion : local primaire, distant en escalade délibérée.

---

## 6. MOUTH

### Retenu : Kyutai Pocket TTS, voix `estelle`

`kyutai/pocket-tts-without-voice-cloning`, `languages/french_24l`, CC-BY-4.0.
C'est la voix nommée dans la spec MOTHER d'origine.

| | Piper | **Pocket TTS (GPU)** |
|---|---|---|
| Premier audio | 102 ms | **75 ms** (63 ms à chaud) |
| Streaming | 1 chunk / phrase | **104 chunks incrémentaux** |
| Fréquence | 22 050 Hz | **24 000 Hz** |
| Voix FR | 1 | **26** |
| RTF | **0,03** | 0,38 |
| VRAM | **0** | 1490 Mo |

Piper reste en repli : douze fois plus de marge et zéro VRAM.

> **Correction d'un rapport de recherche** : la variante non-gated était
> annoncée « anglais uniquement ». Faux — les deux dépôts contiennent les mêmes
> 379 fichiers dont `languages/french_24l/`. Le tag `language: ['en']` n'est
> qu'une métadonnée de carte. La variante non-gated donne bien le français.

### Rejeté : Qwen3-TTS-12Hz-1.7B via `llama-tts`

Testé, mesuré, écarté. Les 97 ms annoncés viennent de l'architecture dual-track
de Qwen, que llama.cpp ne reprend pas : le log dit
`generation 1.64s + vocoder 0.05s` — le vocodeur passe **à la fin**, aucun
streaming. RTF 0,21–0,30. `llama-server` n'expose **aucun endpoint TTS**, donc
chaque appel recharge le modèle (26 s à froid, 5,9 s à chaud). Conservé sur
disque pour l'offline (24 kHz, clonage en 3 s).

### La leçon de latence

**MOUTH n'a jamais été limité par la vitesse de synthèse.** Piper tourne déjà à
30× le temps réel. Le TTFA est fixé par **la quantité de texte attendue avant de
démarrer**. Le découpage à la ponctuation stallait quand BRAIN ouvre sans
virgule : mesuré, la première virgule tombait à 49 caractères, et trois réglages
différents produisaient donc le **même** fragment. Ajout d'une coupe de secours
au dernier mot → round-trip 911 → **500 ms**, sans changer de modèle.

### Deux défauts introduits puis corrigés

1. **Streaming bufférisé.** `PocketTTS.synthesize()` concaténait les 62 chunks
   avant de retourner, ce qui annulait la raison même de payer 1,5 Go de VRAM :
   75 ms de premier chunk devenaient **2147 ms** de latence perçue. Corrigé par
   une file entre le thread de génération et la boucle d'événements → **191 ms**.
2. **Markdown lu à voix haute.** Ministral sortait `**15h20**`, le TTS lisait
   « astérisque astérisque ». Ajout de `src/mouth/normalize.py` (markdown, emoji,
   listes) **et** d'un prompt vocal explicite. Le prompt règle le problème à la
   source : **0/4** de pollution mesurée ensuite ; le nettoyage reste le filet.

### Caractère de voix — `src/mouth/voice_design.py`

Profils `flat` / `mother` / `alert`. Le profil `mother` : débit ×1,16, variabilité
de hauteur et de durée réduites (diction impersonnelle), bande 90 Hz – 7,2 kHz,
petite salle métallique, doublage à 17 ms. Les graves sont gardés jusqu'à 90 Hz
délibérément : une bande téléphonique (300–3400) sonnerait « appel », pas « coque ».

Réverbération en **IIR vectorisé** (`scipy.signal.lfilter`, combs
`1/(1-g·z⁻ᴺ)` et allpass), pas en boucle par échantillon : sur un budget de
100 ms, une boucle Python aurait coûté plus que la synthèse. État persistant
entre chunks, sinon claquement à chaque jointure.

**Inachevé** : la sortie 5.1. Les jeux de retards sont décorrélés par canal
(sinon le stéréo n'est qu'un mono dupliqué qui s'effondre au centre) mais la
sortie multicanal n'est pas branchée. Cible : voix sèche au canal centre,
queue de réverbération dans les surrounds, LFE filtré. Ordre WAV Microsoft :
FL, FR, FC, LFE, BL, BR. `soundfile`/libsndfile gère le multicanal.

---

## 7. TURN — le blocage OQ-15 est levé

**Smart Turn v3** (`pipecat-ai/smart-turn`, BSD-2), chiffres **publiés** :

| | |
|---|---|
| Exactitude française | **96,01 %** sur 1253 échantillons |
| Faux positifs | **1,60 %** |
| Faux négatifs | 2,39 % |
| Latence | **12 ms** CPU (60 ms sur AWS c8g.medium) |
| Taille | **8 Mo** ONNX int8 |
| Base | Whisper Tiny, audio natif sans transcription |

C'est exactement la métrique que `MEASUREMENT_PLAN.md` réclamait. **Non encore
installé** — c'est le prochain gain de qualité disponible.

**Piste abandonnée** : utiliser les logits du LLM local comme classifieur
d'endpoint. Proposée deux fois comme si elle était établie, elle ne l'est pas —
aucun papier arXiv, aucun billet d'ingénierie (Deepgram, AssemblyAI, LiveKit,
Cartesia, Vapi, Retell) ne la documente. Smart Turn v3 la remplace, avec des
chiffres.

TURN-L1 actuel : Silero VAD ONNX, trames de 512 échantillons à 16 kHz, RTF 0,004.

> Défaut de banc corrigé : un fichier se termine pile à la fin de la parole,
> donc le silence de fin requis n'arrive jamais et aucun endpoint n'est émis.
> Un micro continue de streamer. Le démo ajoute maintenant du silence de queue.

---

## 8. EARS — le plan Voxtral était faible

llama.cpp a bien `PROJECTOR_TYPE_VOXTRAL`, mais **rien ne documente le support
de l'encodeur causal streaming** de la variante Realtime : l'auteur des GGUF
communautaires renvoie vers `voxtral.cpp`, pas llama.cpp. Voxtral demande
~16 Go en BF16.

Candidats à sa place, vérifiés :

| Modèle | Licence | Taille Q4 | Français | Streaming |
|---|---|---|---|---|
| `nvidia/nemotron-3.5-asr-streaming-0.6b` | OpenMDW-1.1 | ~0,3 Go | WER 9,03 % fr | RNN-T cache-aware, 6–140 ms/chunk |
| `nvidia/parakeet-tdt-0.6b-v3` | CC-BY-4.0 | ~0,3 Go | 25 langues, auto-détection | transducteur RNN-T |
| `kyutai/stt-1b-en_fr` | CC-BY-4.0 | ~0,5 Go | en+fr explicite | 500 ms annoncés |

EARS actuel : faster-whisper `large-v3-turbo`, CTranslate2 `int8_float16`.
C'est un **re-décodage de fenêtre grandissante**, pas du streaming — un
contournement assumé, à remplacer.

---

## 9. Frontière produit, décidée

**EARS, TURN et MOUTH restent locaux. BRAIN est la seule dépendance distante.**

Raison : une voix distante impose une clé API et du crédit à *chaque*
utilisateur — ça transforme un produit qui marche à l'installation en un produit
qui demande un compte. La contrainte de distribution coûte plus que le gain de
qualité. Les modèles `stepaudio-*` sont donc hors périmètre produit ; ils
peuvent servir d'**oracle de mesure** (transcripteur de référence pour noter
EARS), pas de dépendance.

Corollaire : la seule dépendance distante dégrade proprement, puisque le canal
local sait répondre seul.

---

## 10. Budget VRAM

12 282 Mo au total, ~9 500 Mo utiles bureau allumé. **7996 Mo libres mesurés**
avec Luth chargé.

| Composant | VRAM |
|---|---|
| BRAIN Luth-2-2B Q5_K_M + 8k ctx (KV q8_0) | 1,5 Go *(mesuré)* |
| EARS `large-v3-turbo` int8_float16 | ~1,6 Go |
| MOUTH Pocket TTS fp32 | 1,49 Go *(mesuré)* |
| TURN-L2 Smart Turn v3 | 8 Mo (CPU) |
| **marge** | **~4,4 Go** |

Un 8B à la place de Luth ne laisserait que ~2,6 Go : de quoi loger EARS **ou**
le TTS, pas les deux.

---

## 11. Inventaire disque

```
models/gguf/       18 Go  Luth-2-2B (actif), Ministral-3-8B, Luciole-8B,
                          LFM2.5-VL-3B, Qwen3-4B-Instruct-2507, Qwen3.5-4B
models/pocket-tts/ 724 Mo french_24l + estelle, eve, vera
models/hf-cache/   1,7 Go faster-whisper large-v3-turbo + base
models/tts/        1,4 Go Qwen3-TTS (écarté du temps réel, gardé pour l'offline)
models/whisper/    548 Mo ggml-large-v3-turbo-q5_0
models/piper/      268 Mo siwis, upmc, mls, tom (repli MOUTH)
```

Les six GGUF candidats sont **conservés à la demande de l'utilisateur** (pipeline
de dataset).

---

## 12. Code écrit cette session

```
src/brain/openai_compat.py     client OpenAI-compatible local+distant, TTFT, filtrage reasoning
src/brain/factory.py           sélection backend, FallbackBrain (SLA de latence), build_router
src/brain/router.py            routeur deux canaux, classification GBNF, meublage, lignes d'attente
src/brain/stepfun.py           réécrit en sous-classe mince
src/ears/faster_whisper_asr.py EARS CTranslate2, RTF, suivi des révisions
src/turn/silero_turn.py        TURN-L1, trames de 512
src/mouth/piper_tts.py         MOUTH streaming, coupe clause + coupe mot, profils
src/mouth/pocket_tts.py        MOUTH streaming incrémental, estelle
src/mouth/normalize.py         nettoyage markdown/emoji + prompt vocal partagé
src/mouth/voice_design.py      profils de voix + traitement DSP streamable

dev/scripts/smoke_test.py      vérification 9 points
dev/scripts/pipeline_demo.py   bout-en-bout + décomposition de latence honnête
dev/scripts/router_demo.py     démo deux canaux
dev/scripts/bench_brain.py     comparateur de modèles locaux (4 axes)
dev/scripts/loopback_test.py   MOUTH → EARS (RTF/WER réels)
dev/scripts/voice_lab.py       banc d'écoute A/B des voix et profils
dev/scripts/fetch_models.sh    téléchargement des poids
dev/scripts/serve_llama.sh     lancement llama-server
dev/scripts/serve_whisper.sh   lancement whisper-server
```

Documentation : `STACK.md` contient tout le raisonnement mesuré.

---

## 13. Reste à faire, par ordre d'impact

1. **Smart Turn v3** — 8 Mo, 96,01 % FR, 12 ms. Gain de qualité le plus net
   encore disponible. Non installé.
2. **EARS streaming** — remplacer le re-décodage de fenêtre par Nemotron-3.5-ASR
   ou Parakeet. EARS est le poste dominant du budget (370 des 500 ms).
3. **Sortie 5.1** — décorrélation faite, sortie multicanal à brancher.
4. **Agent hôte natif** — quatre primitives : `audio.capture`, `audio.render`,
   `input.inject`, `surface.draw`. Rien n'existe encore.
5. **Tool calling** sur le canal profond — le routeur escalade déjà, mais aucun
   outil n'est branché.
6. **Barge-in** — interruption pendant la parole. Chiffres de référence publiés :
   flush TTS < 60 ms, annulation LLM < 40 ms.
7. **Crédit StepFun** — bloqué par le compte, pas par le code.

---

## 14. Points de vigilance

- La source de vérité *spec* est `D:\BGB Training\Projet MOTHER\` ; le code vit
  dans `D:\BGB Training\MOTHER-dev\`. Deux dossiers distincts.
- `.env.local` contient des clés API en clair. Non versionné (`.gitignore`),
  monté en lecture seule dans le conteneur.
- `pocket-tts` a monté numpy en 2.4.6 et scipy en 1.17.1. Vérifié : `pip check`
  propre, smoke test 9/9, aucune régression.
- La quantisation int8 de Pocket TTS est **CPU seulement**
  (`quantized::linear_dynamic` n'a pas de noyau CUDA). Le chemin GPU est fp32.
