# Cursor VOIX-10-SAMPLES — 10 MP3 FR, script long, cible Aura Ray

Date : 2026-09-13 ~17:55

## Verdict

**10 MP3** prêts, même texte long, **tous > 32 s**. Dossier :

`D:\BGB Training\MOTHER-dev\data\out\voix-10-samples\`

INDEX : `data/out/voix-10-samples/INDEX.md`

Host-agent live **restauré** : Pocket TTS `french_24l` / `estelle` + `aurora` CPU. PID `9841`. Un seul `serve_hostagent.py`. EARS inchangé (Qwen3-ASR 0.6B q4 CUDA).

Écouter d’abord **`09-qwen3tts-clone-aurora.mp3`** (clone de la réf YouTube Aura Ray), puis **`01`** (voix live).

Rien n’a été poussé. Piper siwis conservé (fallback).

## Mix livré

| # | Fichier | Moteur | Voix | Profil | Durée ffprobe |
|---|---|---|---|---|---:|
| 1 | `01-pocket-estelle-aurora.mp3` | Pocket TTS french_24l | estelle | aurora | 34.06 s |
| 2 | `02-pocket-cosette-aurora.mp3` | Pocket TTS french_24l | cosette | aurora | 38.38 s |
| 3 | `03-piper-siwis-aurora.mp3` | Piper | siwis | aurora | 33.52 s |
| 4 | `04-piper-upmc-jessica-aurora.mp3` | Piper | jessica (id 0) | aurora | 32.26 s |
| 5 | `05-piper-mls-7239-aurora.mp3` | Piper MLS | 7239 (id 38) | aurora | 46.16 s |
| 6 | `06-piper-tom-aurora.mp3` | Piper | tom (44100→22050) | aurora | 35.00 s |
| 7 | `07-supertonic-f5-aurora.mp3` | Supertonic-3 ONNX | F5 | aurora | 38.06 s |
| 8 | `08-supertonic-f1-aurora.mp3` | Supertonic-3 ONNX | F1 | aurora | 39.31 s |
| 9 | `09-qwen3tts-clone-aurora.mp3` | Qwen3-TTS 0.6B-Base | clone `aurora_prompt_6s` | aurora | 34.94 s |
| 10 | `10-mms-tts-fra-aurora.mp3` | facebook/mms-tts-fra | locuteur unique | aurora | 38.63 s |

Script : `nights/2026-09-13-SCRIPT-VOIX-LONG.txt` (apostrophes normalisées `Aujourd'hui`). 6 phrases, ~607 caractères.

## Notes timbre (Aura Ray)

- **09** = clone de la référence YouTube déjà nettoyée (`data/voix/aurora_prompt_6s.wav`). C’est le seul qui vise le grain Aura Ray, pas un catalogue.
- **01 estelle** = seule Française native du catalogue Pocket ; voix live actuelle.
- **02 cosette** = autre embedding Pocket, probablement Expresso/EN (accent possible).
- Piper 03–06 : déjà entendus aujourd’hui ; MLS 7239 est une locutrice grave du banc, pas le défaut 1840 (WER élevé).
- Supertonic F5 était le plus proche en brillance en août ; F1 pour un second timbre.
- MMS = 4ᵉ famille TTS, CPU, un locuteur.

Le host-agent a été arrêté le temps de générer (plafond 8 Go : second Pocket ~642 Mo interdit à côté du live). Relancé après.

## Live restauré

```text
MOUTH_BACKEND=pocket
MOUTH_VOICE_NAME=estelle
MOUTH_LANGUAGE=french_24l
MOUTH_DEVICE=cpu
MOUTH_PROFILE=aurora
EARS_BACKEND=qwen3
EARS_MODEL=0.6B
EARS_DEVICE=cuda
EARS_COMPUTE_TYPE=q4
```

Log :

```text
EARS  : chargement qwen3 / 0.6B sur cuda…
MOUTH : chargement pocket-tts french_24l / estelle profil=aurora device=cpu demi_tons=+0…
PocketTTS: french_24l/estelle on cpu profile=aurora demi_tons=+0
pocket-tts loaded in 8.6s @ 24000 Hz
écoute sur 0.0.0.0:8001 /hostagent
```

```text
9841 python dev/scripts/serve_hostagent.py
n_hostagent=1
```

## Preuves

10 fichiers `format_name=mp3`, durées 32.26 s … 46.16 s. Aucun < 20 s.

Régénérer (host-agent **arrêté**) :

```powershell
docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
# d'abord TERM le live, puis :
docker exec -e PYTHONPATH=/workspace -e PYTHONUNBUFFERED=1 -w /workspace mother-core-dev python /workspace/dev/scripts/_voix_10_samples.py
docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Paquets ajoutés dans le conteneur pour les samples 7–9 : `supertonic`, `qwen-tts`. `transformers` remis à **4.57.6** (contrat `qwen-asr`) après génération.

Non touchés : EARS/cerveau/world, `.env.local`, pas de burn, pas de push. Piper siwis toujours sur disque.
