# Cursor CHANGE-VOIX — Piper upmc + mother

Date : 2026-09-13

## Verdict

Voix active : **Piper `fr_FR-upmc-medium` (jessica, speaker 0)** + profil **`mother`**.

Host-agent relancé, PID `6794`. L’ancien PID `6220` (siwis+aurora) a reçu `TERM`.

Thomas : écouter les trois wav ci-dessous et trancher. Rien n’a été poussé.

## Voix active

| | |
|---|---|
| Backend | `MOUTH_BACKEND=piper` |
| Modèle | `/workspace/models/piper/fr_FR-upmc-medium.onnx` |
| Locutrice | jessica (id 0, défaut du modèle ; pierre = id 1, non utilisé) |
| Profil | `mother` (coque de bord : bande 90–7200 Hz, réverbe, doublage) |
| Demi-tons | `+0` |

Log au chargement :

```text
MOUTH : chargement piper /workspace/models/piper/fr_FR-upmc-medium.onnx profil=mother demi_tons=+0…
PiperTTS: /workspace/models/piper/fr_FR-upmc-medium.onnx profile=mother cuda=False demi_tons=0.0
voice loaded in 0.86s @ 22050 Hz
mouth : préchauffé en 44 ms
écoute sur 0.0.0.0:8001 /hostagent
```

## Wav de comparaison

Même phrase FR :

> Bonsoir Thomas. Je suis là. Dis-moi si cette voix te convient.

Dossier hôte : `D:\BGB Training\MOTHER-dev\data\out\voix-compare\`

| Fichier | Pairing | Durée | SR | Rôle |
|---|---|---:|---:|---|
| `upmc-mother.wav` | upmc jessica + mother | 3.38 s | 22050 | **nouveau (en prod)** |
| `siwis-aurora.wav` | siwis + aurora | 3.75 s | 22050 | ancien (8 sept) |
| `tom-mother.wav` | tom + mother | 5.00 s | 44100 | troisième FR natif |

Regénérer :

```powershell
docker exec -e PYTHONPATH=/workspace -w /workspace mother-core-dev python /workspace/dev/scripts/_voix_compare.py
```

## Revenir à siwis+aurora en 1 commande

Runtime seulement (tient jusqu’au prochain `relancer_routeur.sh` sans `FORCE`) :

```powershell
docker exec -e MOUTH_VOICE_FORCE=/workspace/models/piper/fr_FR-siwis-medium.onnx -e MOUTH_PROFILE_FORCE=aurora mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Pour figer : remettre `MOUTH_VOICE=.../fr_FR-siwis-medium.onnx` et `MOUTH_PROFILE=aurora` dans `.env.local` **et** le défaut de `dev/scripts/relancer_routeur.sh`, puis relancer sans `FORCE`.

## Fichiers touchés

- `.env.local`, `.env.example` — défauts MOUTH
- `dev/scripts/relancer_routeur.sh` — défaut upmc+mother + `MOUTH_VOICE_FORCE` / `MOUTH_PROFILE_FORCE`
- `dev/scripts/serve_hostagent.py` — `VOIX_PIPER`
- `src/mouth/piper_tts.py` — `DEFAULT_VOICE`
- `dev/scripts/swap_option2_models.py`, `smoke_test.py`, `pipeline_demo.py` — mêmes défauts
- `dev/scripts/_voix_compare.py` — générateur des 3 wav

Non touchés : EARS/ASR, world, Kokoro, pas de burn, pas de push.

Les bancs historiques (`banc_piper.py`, `fetch_models.sh`, `dev/out/siwis6.py`…) gardent siwis comme corpus de labo.

## Preuves

### Relance

```text
cle de 93 caracteres, routeur arme
TERM host-agent: 6220
host-agent relance, pid 6794
host-agent pret, pid 6794
```

### Unique PID

```text
6794 python dev/scripts/serve_hostagent.py
```

### Smoke mouth (préchauffage live)

```text
mouth : préchauffé en 44 ms
```

### Recette pont audio (`verify_hostagent_loop.py`)

```text
=== Rapport de recette du pont audio ===
  durée audio envoyé     : 4.26 s
  trames envoyées        : 213
  trames reçues          : 441
  mic_to_audible         : 1250 ms  (budget NFR-01 : 1200 ms, > budget)
  durée audio reçu       : 8.82 s
  texte transcrit        : Peux-tu me dire en une phrase pourquoi le facteur temps réel doit rester inférieur à un ?
  réponse du modèle      : Le facteur temps réel compare la durée de simulation au temps écoulé dans la réalité, et il doit rester inférieur à un pour que la simulation avance plus vite que la réalité, sinon elle ne peut pas suivre le phénomène qu'elle modélise.
  fichier écrit          : /workspace/data/out/verify_loop_reponse.wav
VERDICT : OK — audio reçu, mais NFR-01 dépassé (1250 ms > 1200 ms)
```

Tour depuis la relance :

```text
EARS  : "Peux-tu me dire en une phrase pourquoi le facteur temps réel doit rester inférieur à un ?" — 1092 ms
BRAIN : filler — "Un instant."
MOUTH : premier audio après 4061 ms
BRAIN : TTFT 3790 ms
```

NFR-01 hors critère de cet ordre (1250 ms vs 1200 ms). La bouche a parlé.
