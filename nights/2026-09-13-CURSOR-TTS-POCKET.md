# Cursor TTS-POCKET — Pocket TTS estelle + aurora

Date : 2026-09-13 ~17:40

## Verdict

Voix active : **Pocket TTS `french_24l` / `estelle`** + profil **`aurora`**, device **CPU** (0 VRAM).

Host-agent relancé, PID `8400`. L’ancien PID `7562` (Piper tom+aurora) a reçu `TERM`. Un seul
processus `serve_hostagent.py`.

EARS (Qwen3-ASR 0.6B q4 CUDA) et le cerveau (routeur MiniMax + reflex local) sont inchangés.
Sample `pocket-estelle.wav` écrit. Rien n’a été poussé. Kokoro non touché.

## Voix active

| | |
|---|---|
| Backend | `MOUTH_BACKEND=pocket` |
| Langue | `french_24l` |
| Locuteur | `estelle` |
| Poids | `/workspace/models/pocket-tts/languages/french_24l/` |
| Embedding | `embeddings/estelle.safetensors` (32 Mo) |
| Profil | `aurora` (close-mic, pas de doublage, réverbe 5 %) |
| Device | `cpu` (0 VRAM — GPU laissé à EARS / llama-server) |
| Demi-tons | `+0` |
| SR natif → canal | 24000 Hz → 16000 Hz (`RechantillonneurContinu`) |

Env du PID live :

```text
MOUTH_BACKEND=pocket
MOUTH_VOICE_NAME=estelle
MOUTH_LANGUAGE=french_24l
MOUTH_DEVICE=cpu
MOUTH_PROFILE=aurora
```

EARS inchangé :

```text
EARS_BACKEND=qwen3
EARS_MODEL=0.6B
EARS_DEVICE=cuda
EARS_COMPUTE_TYPE=q4
```

Log au chargement :

```text
EARS  : chargement qwen3 / 0.6B sur cuda…
BRAIN : router @ reflex=http://localhost:8080/v1/chat/completions deep=https://api.commandcode.ai/provider/v1/chat/completions — reflex HTTP 200, deep HTTP 200
MOUTH : chargement pocket-tts french_24l / estelle profil=aurora device=cpu demi_tons=+0…
PocketTTS: french_24l/estelle on cpu profile=aurora demi_tons=+0
pocket-tts loaded in 3.5s @ 24000 Hz
mouth : préchauffé en 686 ms
resample : préchauffé en 719 ms
ears : préchauffé en 639 ms
écoute sur 0.0.0.0:8001 /hostagent
```

GPU après relance : **6224 / 12282 MiB** — même ordre de grandeur qu’avant Pocket
(llama-server + Qwen3-ASR). Pas de second modèle TTS sur CUDA.

## Wav

Même phrase FR que les samples Piper :

> Bonsoir Thomas. Je suis là. Dis-moi si cette voix te convient.

Dossier hôte : `D:\BGB Training\MOTHER-dev\data\out\voix-compare\`

| Fichier | Pairing | Durée | SR | Rôle |
|---|---|---:|---:|---|
| `pocket-estelle.wav` | estelle + aurora, CPU | 4.24 s | 24000 | **nouveau (en prod)** |
| `tom-aurora.wav` | tom + aurora | 4.59 s | 22050 | dernier Piper (rejeté) |
| `siwis-aurora.wav` | siwis + aurora | 3.92 s | 22050 | ancien validé 8 sept |
| `upmc-mother.wav` | upmc jessica + mother | 3.77 s | 22050 | switch de l’après-midi |
| `tom-mother.wav` | tom + mother | 5.16 s | 22050 | profil écarté |

`pocket-estelle.wav` : 1 canal, 16 bit, 24000 Hz, 101760 frames, 203564 octets.
TTFA 319 ms, RTF 1.231 (mesure pendant que l’ancien host-agent Piper tournait encore —
CPU partagé ; le préchauffage live est 686 ms sur « Bonjour. »).

Regénérer :

```powershell
docker exec -e PYTHONPATH=/workspace -w /workspace mother-core-dev python /workspace/dev/scripts/_voix_compare.py --pocket
```

Ne pas lancer ça **pendant** que le host-agent Pocket est chargé : second chargement
du modèle (~642 Mo) dans le plafond 8 Go du conteneur.

## Revenir à Piper tom+aurora en 1 commande

Runtime seulement (tient jusqu’au prochain `relancer_routeur.sh` sans `FORCE`) :

```powershell
docker exec -e MOUTH_BACKEND_FORCE=piper -e MOUTH_VOICE_FORCE=/workspace/models/piper/fr_FR-tom-medium.onnx -e MOUTH_PROFILE_FORCE=aurora mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Siwis+aurora (validé 8 sept) :

```powershell
docker exec -e MOUTH_BACKEND_FORCE=piper -e MOUTH_VOICE_FORCE=/workspace/models/piper/fr_FR-siwis-medium.onnx -e MOUTH_PROFILE_FORCE=aurora mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Pour figer Piper : `MOUTH_BACKEND=piper` + `MOUTH_VOICE=...onnx` + `MOUTH_PROFILE=aurora`
dans `.env.local` **et** le défaut de `dev/scripts/relancer_routeur.sh`, puis relancer
sans `FORCE`.

## Fichiers touchés

- `.env.local`, `.env.example` — `MOUTH_BACKEND=pocket`, voix `estelle`, `aurora`, CPU
- `dev/scripts/relancer_routeur.sh` — mêmes défauts + `MOUTH_*_FORCE`
- `dev/scripts/serve_hostagent.py` — défaut pocket `estelle` / `cpu` (plus `eponine` / `cuda`)
- `src/mouth/pocket_tts.py` — défauts constructeur `device=cpu`, `profile=aurora`
- `dev/scripts/swap_option2_models.py` — env suggéré aligné
- `dev/scripts/_voix_compare.py` — `--pocket` → `pocket-estelle.wav`

Non touchés : EARS/ASR, world, cerveau, Kokoro, pas de burn, pas de push.

## Preuves

### pytest

```text
.....                                                                    [100%]
5 passed in 0.88s
```

(`dev/tests/test_pocket_transposition.py`)

### Relance

```text
cle de 93 caracteres, routeur arme
TERM host-agent: 7562
host-agent relance, pid 8400
host-agent pret, pid 8400
```

### Unique PID

```text
8400 python dev/scripts/serve_hostagent.py
```

### Smoke mouth (préchauffage live)

```text
mouth : préchauffé en 686 ms
```

Phrase de préchauffage : « Bonjour. » Phrase d’amorce modèle : « Prête. »

### Sample

```text
pocket-estelle.wav duration=4.24s ttfa=319ms rtf=1.231 sr=24000 bytes=203564
```
