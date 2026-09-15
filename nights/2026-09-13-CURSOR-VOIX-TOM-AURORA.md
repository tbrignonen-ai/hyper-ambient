# Cursor VOIX-TOM-AURORA — Piper tom + aurora

Date : 2026-09-13 ~17:20

## Verdict

Voix active : **Piper `fr_FR-tom-medium`** + profil **`aurora`**.

Host-agent relancé, PID `7562`. L’ancien PID `7100` a reçu `TERM`. Un seul
processus `serve_hostagent.py`.

Tom sort nativement à **44 100 Hz**. Le PCM est ramené à **22 050 Hz** avant
le canal (anti-entrecoupe). Sample `tom-aurora.wav` écrit. Rien n’a été poussé.

## Voix active

| | |
|---|---|
| Backend | `MOUTH_BACKEND=piper` |
| Modèle | `/workspace/models/piper/fr_FR-tom-medium.onnx` |
| Locuteur | tom (1 speaker, français natif) |
| Profil | `aurora` (close-mic, pas de doublage, réverbe 5 %) |
| Demi-tons | `+0` |
| SR natif → pipeline | 44100 Hz → 22050 Hz |

Env du PID live :

```text
MOUTH_BACKEND=piper
MOUTH_VOICE=/workspace/models/piper/fr_FR-tom-medium.onnx
MOUTH_PROFILE=aurora
```

Log au chargement :

```text
MOUTH : chargement piper /workspace/models/piper/fr_FR-tom-medium.onnx profil=aurora demi_tons=+0…
PiperTTS: /workspace/models/piper/fr_FR-tom-medium.onnx profile=aurora cuda=False demi_tons=0.0
voice loaded in 0.86s @ 44100 Hz -> 22050 Hz
mouth : préchauffé en 171 ms
écoute sur 0.0.0.0:8001 /hostagent
```

## Sample rate (anti-entrecoupe)

`fr_FR-tom-medium.onnx.json` déclare `sample_rate: 44100`. siwis/upmc sont à
22 050. Un PCM 44,1 kHz lu à 22 050 se joue deux fois trop lent et se hache.

`ramener_au_taux_pipeline` (soxr, énoncé complet) aligne Tom sur 22 050 Hz
après le traitement aurora au taux natif. Le host-agent continue ensuite
22 050 → 16 000 via `RechantillonneurContinu` (état porté d’un bloc à l’autre,
pas librosa par chunk).

## Wav

Même phrase FR :

> Bonsoir Thomas. Je suis là. Dis-moi si cette voix te convient.

Dossier hôte : `D:\BGB Training\MOTHER-dev\data\out\voix-compare\`

| Fichier | Pairing | Durée | SR | Rôle |
|---|---|---:|---:|---|
| `tom-aurora.wav` | tom + aurora | 4.59 s | 22050 | **nouveau (en prod)** |
| `siwis-aurora.wav` | siwis + aurora | 3.92 s | 22050 | ancien validé 8 sept |
| `upmc-mother.wav` | upmc jessica + mother | 3.77 s | 22050 | switch de l’après-midi |
| `tom-mother.wav` | tom + mother | 5.16 s | 22050 | même locuteur, profil écarté |

`tom-aurora.wav` : 1 canal, 16 bit, 22050 Hz, 101248 frames, 202540 octets.
TTFA 55 ms, RTF 0.151.

Regénérer :

```powershell
docker exec -e PYTHONPATH=/workspace -w /workspace mother-core-dev python /workspace/dev/scripts/_voix_compare.py
```

## Revenir à siwis+aurora en 1 commande

Runtime seulement (tient jusqu’au prochain `relancer_routeur.sh` sans `FORCE`) :

```powershell
docker exec -e MOUTH_VOICE_FORCE=/workspace/models/piper/fr_FR-siwis-medium.onnx -e MOUTH_PROFILE_FORCE=aurora mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Pour figer : `MOUTH_VOICE=.../fr_FR-siwis-medium.onnx` et `MOUTH_PROFILE=aurora`
dans `.env.local` **et** le défaut de `dev/scripts/relancer_routeur.sh`, puis
relancer sans `FORCE`.

## Fichiers touchés

- `.env.local`, `.env.example` — `tom-medium` + `aurora`
- `dev/scripts/relancer_routeur.sh` — mêmes défauts
- `dev/scripts/serve_hostagent.py` — `VOIX_PIPER` + défaut `MOUTH_PROFILE=aurora`
- `src/mouth/piper_tts.py` — `DEFAULT_VOICE`, profil par défaut `aurora`, alignement 44100→22050
- `dev/tests/test_piper_taux.py` — contrat SR
- `dev/scripts/swap_option2_models.py`, `smoke_test.py`, `pipeline_demo.py` — mêmes défauts
- `dev/scripts/_voix_compare.py` — case `tom-aurora.wav`

Non touchés : EARS/ASR, world, cerveau, Kokoro, pas de burn, pas de push.

## Preuves

### pytest

```text
.....                                                                    [100%]
5 passed in 0.77s
```

(`dev/tests/test_piper_taux.py`)

### Relance

```text
cle de 93 caracteres, routeur arme
TERM host-agent: 7100
host-agent relance, pid 7562
host-agent pret, pid 7562
```

### Unique PID

```text
7562 python dev/scripts/serve_hostagent.py
```

### Smoke mouth (préchauffage live)

```text
mouth : préchauffé en 171 ms
```

### Sample

```text
tom-aurora.wav duration=4.59s ttfa=55ms rtf=0.151 sr=22050 bytes=202540
```
