---
date: 2026-09-19
type: out
lane: C9
cible: magpie-sofia
---

# C9 OUT — Magpie Sofia voix de MOTHER

CPU only. llama-server `:8080` non touché. `.env.local` non touché. Pas de git.

## TDD

**Rouge** (modules absents) :

```
$ docker exec -w /workspace mother-core-dev python3 -m pytest -q \
    dev/tests/test_normalize_nombres.py dev/tests/test_mouth_magpie.py
ERROR test_normalize_nombres.py — ImportError: cannot import name 'nombres_en_lettres'
ERROR test_mouth_magpie.py — ModuleNotFoundError: No module named 'src.mouth.magpie_tts'
2 errors in 0.19s
```

**Vert** :

```
$ docker exec -w /workspace mother-core-dev python3 -m pytest -q \
    dev/tests/test_normalize_nombres.py dev/tests/test_mouth_magpie.py
............                                                             [100%]
12 passed in 0.74s
```

## Diff résumé

- `src/mouth/normalize.py` — `nombres_en_lettres` (heures, dates, rues, entiers, décimaux, %). Fragment streamé : un entier collé en fin de chaîne reste en chiffres.
- `src/mouth/magpie_tts.py` — `MOUTH_BACKEND=magpie`, même contrat que Supertonic (`load_model` / `synthesize` / `synthesize_stream` par phrase). Serveur persistant `nemo-speech serve` `:8092` CPU (pas `:8080`).
- `dev/scripts/serve_hostagent.py` — `elif backend == "magpie"` → log `MOUTH : chargement magpie Sofia`.
- Tests : `dev/tests/test_normalize_nombres.py`, `dev/tests/test_mouth_magpie.py`.

## Relance

`/tmp/relance_hostagent.sh` : `MOUTH_BACKEND=magpie MOUTH_VOICE_NAME=Sofia` (BRAIN_SERVICE=llamacpp conservé).

```
$ docker exec mother-core-dev sh /tmp/relance_hostagent.sh
relancé
```

Log boot `/workspace/logs/hostagent-degustation.log` :

```
BRAIN : llama.cpp @ http://localhost:8080/v1/chat/completions — HTTP 200
OUTILS: ask_claude, ask_codex, web_search — porte en mode auto
MOUTH : chargement magpie Sofia…
mouth : préchauffé en 947 ms
écoute sur 0.0.0.0:8001 /hostagent
```

Process : `nemo-speech serve --host 127.0.0.1 --port 8092 --device cpu` (PID 25208). llama-server PID 20383 inchangé.

## Synthèse test via le host-agent

Phrase : « Rendez-vous jeudi 24 septembre à 15h30, au 12 rue des Lilas. »

Verbalisé : « Rendez-vous jeudi vingt-quatre septembre à quinze heures trente, au douze rue des Lilas. »

Client MagpieTTS reconnecté au `serve` déjà lancé au boot (`proc_reused: true`).

```
ttfa_ms=4473.2
sample_rate=22050
duree_s=4.923
wav=nights/degustation-19/c9-sofia-test.wav (217132 octets)
```

Temps avant premier son : **4473 ms** (Magpie tamponne le WAV entier avant la réponse HTTP ; pas de flux intra-phrase).

## GPU

`nemo-speech serve --device cuda` (variable `MOUTH_DEVICE`, défaut cuda, repli cpu si `CUDA_VISIBLE_DEVICES` vide ou `nvidia-smi` absent). llama-server PID **20383** inchangé. `.env.local` non touché. Pas de git.

Le binaire Magpie (`/workspace/models/tts-bench/magpie/bin/nemo-speech`) refuse CUDA : `this build has no CUDA backend` (exit 2). Serveur lancé avec le `nemo-speech` CUDA de `asr-bench/nemotron.new`, modèles GGUF Magpie inchangés. `/v1/audio/speech` tamponne toujours le WAV entier (pas de flux intra-phrase ; le WebSocket `/v1/realtime` est ASR seulement). Repli : coupe des phrases longues aux virgules dans `synthesize_stream`.

### TDD

**Rouge** :

```
$ docker exec -w /workspace mother-core-dev python3 -m pytest -q dev/tests/test_mouth_magpie.py
FFF....F.                                                                [100%]
FAILED test_defauts_sofia_fr_cuda — assert 'cpu' == 'cuda'
FAILED test_repli_cpu_si_cuda_indisponible — assert 'cuda' == 'cpu'
FAILED test_mouth_device_env_cuda — assert 'cpu' == 'cuda'
FAILED test_stream_phrase_longue_coupe_a_la_virgule — assert 1 == 2
4 failed, 5 passed in 4.50s
```

**Vert** :

```
$ docker exec -w /workspace mother-core-dev python3 -m pytest -q dev/tests/test_mouth_magpie.py
.........                                                                [100%]
9 passed in 0.68s
```

### Relance

Banc ASR whisper-large-v3 d’abord laissé finir (VRAM ensuite 5830 MiB libres > 1,5 Go).

`/tmp/relance_hostagent.sh` : `MOUTH_BACKEND=magpie MOUTH_VOICE_NAME=Sofia MOUTH_DEVICE=cuda` (tue le serve CPU `:8092`, pas llama-server).

```
$ docker exec mother-core-dev sh /tmp/relance_hostagent.sh
relancé
```

Log boot :

```
BRAIN : llama.cpp @ http://localhost:8080/v1/chat/completions — HTTP 200
OUTILS: ask_claude, ask_codex, web_search — porte en mode auto
MOUTH : chargement magpie Sofia…
mouth : préchauffé en 218 ms
écoute sur 0.0.0.0:8001 /hostagent
```

`/ready` : `{"capabilities":["tts"],"device":"cuda","ready":true}`

Process : `nemotron.new/bin/nemo-speech serve --host 127.0.0.1 --port 8092 --device cuda` (PID 32755). llama-server PID 20383 inchangé.

### ttfa_ms avant / après + VRAM

Même phrase : « Rendez-vous jeudi 24 septembre à 15h30, au 12 rue des Lilas. »

Verbalisé : « Rendez-vous jeudi vingt-quatre septembre à quinze heures trente, au douze rue des Lilas. »

`proc_reused: true` (client recollé au serve CUDA du boot).

| | CPU (avant) | CUDA (après) |
|---|---:|---:|
| ttfa_ms `synthesize` phrase entière | 4473.2 | **1341.1** |
| premier morceau `synthesize_stream` (coupe virgule) | — | 1498.8 |
| sample_rate | 22050 | 22050 |
| duree_s | 4.923 | 4.690 |
| wav | 217132 octets | 206892 octets |

La virgule de cette phrase est tardive : le 1er morceau ≈ toute la phrase, le stream ne gagne pas sur `synthesize`. Gain réel = CUDA (**4473 → 1341 ms**, −70 %).

VRAM `nvidia-smi` (llama-server + EARS déjà résidents) :

| moment | used | free | Δ used vs CPU avant relance |
|---|---:|---:|---:|
| avant relance (serve CPU `:8092`) | 6181 MiB | 5830 MiB | — |
| après boot CUDA (`/ready`) | 7310 MiB | 4701 MiB | **+1129 MiB** |
| après synthèse test | 8512 MiB | 3498 MiB | +2331 MiB |
