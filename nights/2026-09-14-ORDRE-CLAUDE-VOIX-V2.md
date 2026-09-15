---
date: 2026-09-14
type: ordre
destinataire: Claude
duree_max: 2h
---
# ORDRE CLAUDE — finir les 10 MP3 voix v2

## Résultat exigé

Finir le paquet dans :

`D:\BGB Training\MOTHER-dev\data\out\voix-10-samples-v2\`

Entrées immuables :

- texte : `D:\BGB Training\MOTHER-dev\nights\2026-09-13-SCRIPT-VOIX-LONG.txt`
- référence : `D:\BGB Training\MOTHER-dev\data\voix\aurora_prompt_6s.wav`
- transcript référence déjà calculé : `data/out/voix-10-samples-v2/_aurora_prompt_6s.txt`
- script de génération amorcé : `dev/scripts/_voix_10_samples_v2.py`
- driver amorcé : `dev/scripts/_voix_10_v2_driver.py`
- conteneur : `mother-core-dev`, dépôt monté sous `/workspace` sauf `nights/`
- venv existant : `/workspace/models/tts-v2-venv`

Ne toucher ni au cerveau, ni à EARS, ni au backend voix live. Ne pas recréer le conteneur. Ne pas effacer de poids. Ne pas push.

Interdits absolus dans le paquet : Pocket/PocketTTS, Piper, Supertonic, Qwen3-TTS et `facebook/mms-tts-fra`.

## Les 10 slots à livrer

| Slot | Job | Modèle | Fichier OUT exact | État |
|---:|---|---|---|---|
| 01 | `voxcpm2` | `openbmb/VoxCPM2` | `01-voxcpm2-clone-aurora.mp3` | à faire |
| 02 | `neutts` | `neuphonic/neutts-nano-french` | `02-neutts-nano-french-clone-aurora.mp3` | à faire |
| 03 | `audio8` | `Edge0/Audio8-TTS-Preview-0.6b` | `03-audio8-tts-0.6b-clone-aurora.mp3` | à coder + faire |
| 04 | `dots_mf` | `dots-studio/dots.tts-mf` | `04-dots-tts-mf-clone-aurora.mp3` | à faire; renommer le slot codé 06 |
| 05 | `anka` | `krmkayabasi/Anka-TTS v0.1` | `05-anka-tts-clone-aurora.mp3` | **déjà bon; ne pas régénérer** |
| 06 | `indextts25` | `IndexTeam/IndexTTS-2.5` | `06-indextts25-clone-aurora.mp3` | à faire; renommer le slot codé 07 |
| 07 | `firered3` | `FireRedTeam/FireRedTTS3` | `07-fireredtts3-base-clone-aurora.mp3` | à faire; renommer le slot codé 08 |
| 08 | `raon` | `KRAFTON/Raon-OpenTTS-1B` | `08-raon-opentts-1b-clone-aurora.mp3` | à faire; renommer le slot codé 09 |
| 09 | `magpie` | `nvidia/magpie_tts_multilingual_357m`, voix Aria FR | `09-magpie-v2607-aria-fr.mp3` | à faire; renommer le slot codé 10 |
| 10 | `chatterbox_mtl` | `ResembleAI/chatterbox multilingual V3` | `10b-chatterbox-mtl-v3-clone-aurora.mp3` | **déjà bon; repli hors cutoff, ne pas régénérer** |

Le résultat est donc 9 modèles au cutoff (sortie ou mise à jour après le 13 juillet) et un repli Chatterbox déjà calculé. Ne pas remettre `chatterbox_nano` ni OmniVoice dans les dix : ils sont hors cutoff et Chatterbox ferait doublon de famille.

## 0. Préflight exact (PowerShell hôte)

```powershell
Set-Location 'D:\BGB Training\MOTHER-dev'
$C = 'mother-core-dev'

if (-not (docker ps --format '{{.Names}}' | Select-String -SimpleMatch $C)) {
    docker start $C
}

Get-Item 'nights\2026-09-13-SCRIPT-VOIX-LONG.txt','data\voix\aurora_prompt_6s.wav','data\out\voix-10-samples-v2\meta.jsonl'
Get-ChildItem 'data\out\voix-10-samples-v2' -Filter '*.mp3'
docker exec $C sh -lc 'nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader; df -h /workspace/models; test -x /workspace/models/tts-v2-venv/bin/python'
```

État constaté par Codex avant remise : conteneur UP, RTX 4070 12 282 MiB, environ 10 138 MiB libres, 244 Go disque libres, venv présent, `ffmpeg` et `espeak-ng` présents.

## 1. Corrections obligatoires avant lancement

Corriger seulement `dev/scripts/_voix_10_samples_v2.py` et `dev/scripts/_voix_10_v2_driver.py` :

1. Ajouter le job `audio8` d'après l'API/CLI officielle `Edge0-AI/Audio8_TTS`. Découper par phrases (chaque fragment < 150 caractères), utiliser `aurora_prompt_6s.wav` et son transcript exact, concaténer, appliquer une seule fois le profil DSP `aurora`, puis passer par `livrer()`.
2. Remplacer les noms OUT des slots 04/06/07/08/09 par ceux du tableau ci-dessus. Ne jamais renommer les deux MP3 déjà présents.
3. Faire de `livrer()` un upsert : si le MP3 cible est déjà valide, le job sort 0 sans synthèse; `meta.jsonl` doit contenir une seule ligne par `fichier`.
4. Le driver doit initialiser son avancement depuis les fichiers valides déjà sur disque, pas depuis `ok = 0`. Il doit voir Anka et Chatterbox comme acquis.
5. La séquence de production doit être exactement : `voxcpm2`, `neutts`, `audio8`, `dots_mf`, `indextts25`, `firered3`, `raon`, `magpie`. Retirer `chatterbox_nano`, `omnivoice` et `anka` de la séquence de reprise.
6. Chaque installateur doit vérifier son code retour. Le tuple actuel du slot Raon masque un éventuel échec de `pip`; le corriger.
7. Corriger les API déjà douteuses :
   - VoxCPM2 : `VoxCPM.from_pretrained(..., device=..., optimize=...)`; son SR ne doit pas dépendre de `model.tts_model.sample_rate` sans fallback.
   - dots.tts : fixer la graine avant chaque `generate`; l'API officielle renvoie un dict avec `audio` et `sample_rate`.
   - IndexTTS 2.5 : ne pas déclarer `lang="EN"` pour un texte français si l'API installée permet auto/multilingue; sinon documenter explicitement le cross-lingual.
   - FireRedTTS3 : modèle local `FireRedTeam/FireRedTTS3`, langue `French`, `do_tn=False` pour éviter le TN zh/en sur le français.
   - Raon : utiliser le dépôt officiel `krafton-ai/Raon-OpenTTS` et son config 1B; ne pas supposer qu'un checkpoint Raon se charge comme un F5 générique sans config/vocoder.
   - Magpie : prévoir le nom exporté par la version NeMo installée (`MagpieTTS_Model` puis fallback `MagpieTTSModel`), `language="fr"`, `speaker_index=0` (Aria).
8. Après chaque job, libérer le modèle et le cache CUDA. Un modèle à la fois; aucun parallélisme GPU.

Synchroniser ensuite le texte autoritatif vers le chemin monté dans le conteneur :

```powershell
$Text = (Get-Content -Raw 'nights\2026-09-13-SCRIPT-VOIX-LONG.txt').Replace("''", "'")
Set-Content -NoNewline -Encoding utf8 'dev\scripts\_voix_10_script.txt' $Text
```

Contrôle syntaxique sans produire d'audio :

```powershell
docker exec $C sh -lc 'cd /workspace && /workspace/models/tts-v2-venv/bin/python -m py_compile dev/scripts/_voix_10_samples_v2.py dev/scripts/_voix_10_v2_driver.py'
```

## 2. Installations et runs exacts

Journaliser chaque étape. Si un job casse, réparer ce job puis le relancer; ne pas relancer ceux dont le MP3 est valide.

### Base + VoxCPM2

```powershell
docker exec $C bash -lc 'set -euo pipefail; V=/workspace/models/tts-v2-venv; "$V/bin/pip" install -U pip huggingface_hub soundfile numpy voxcpm'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job voxcpm2' 2>&1 | Tee-Object 'logs\tts-v2-01-voxcpm2.log'
```

### NeuTTS Nano French

```powershell
docker exec $C bash -lc 'set -euo pipefail; /workspace/models/tts-v2-venv/bin/pip install -U neutts neucodec phonemizer'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job neutts' 2>&1 | Tee-Object 'logs\tts-v2-02-neutts.log'
```

### Audio8 TTS 0.6B

```powershell
docker exec $C bash -lc 'set -euo pipefail; SRC=/workspace/models/tts-v2-src/Audio8_TTS; mkdir -p /workspace/models/tts-v2-src; test -d "$SRC/.git" || git clone --depth 1 https://github.com/Edge0-AI/Audio8_TTS.git "$SRC"; /workspace/models/tts-v2-venv/bin/pip install -r "$SRC/requirements.txt"; /workspace/models/tts-v2-venv/bin/hf download Edge0/Audio8-TTS-Preview-0.6b --local-dir /workspace/models/tts-v2/Audio8-TTS-Preview-0.6b'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace:/workspace/models/tts-v2-src/Audio8_TTS PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job audio8' 2>&1 | Tee-Object 'logs\tts-v2-03-audio8.log'
```

### dots.tts MeanFlow

```powershell
docker exec $C bash -lc 'set -euo pipefail; /workspace/models/tts-v2-venv/bin/pip install -U dots.tts'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job dots_mf' 2>&1 | Tee-Object 'logs\tts-v2-04-dots.log'
```

### IndexTTS 2.5

```powershell
docker exec $C bash -lc 'set -euo pipefail; D=/workspace/models/tts-v2-src/index-tts; mkdir -p /workspace/models/tts-v2-src; test -d "$D/.git" || git clone --depth 1 --branch indextts-2.5 https://github.com/index-tts/index-tts.git "$D"; cd "$D"; /workspace/models/tts-v2-venv/bin/pip install -U uv; /workspace/models/tts-v2-venv/bin/uv sync --extra webui; /workspace/models/tts-v2-venv/bin/hf download IndexTeam/IndexTTS-2.5 --local-dir /workspace/models/tts-v2/IndexTTS-2.5'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace:/workspace/models/tts-v2-src/index-tts PYTHONUNBUFFERED=1; /workspace/models/tts-v2-src/index-tts/.venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job indextts25' 2>&1 | Tee-Object 'logs\tts-v2-06-indextts25.log'
```

### FireRedTTS3

```powershell
docker exec $C bash -lc 'set -euo pipefail; D=/workspace/models/tts-v2-src/FireRedTTS3; mkdir -p /workspace/models/tts-v2-src; test -d "$D/.git" || git clone --depth 1 https://github.com/FireRedTeam/FireRedTTS3.git "$D"; /workspace/models/tts-v2-venv/bin/pip install -e "$D"; /workspace/models/tts-v2-venv/bin/hf download FireRedTeam/FireRedTTS3 --local-dir /workspace/models/tts-v2/FireRedTTS3'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace:/workspace/models/tts-v2-src/FireRedTTS3 PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job firered3' 2>&1 | Tee-Object 'logs\tts-v2-07-firered3.log'
```

### Raon OpenTTS 1B

```powershell
docker exec $C bash -lc 'set -euo pipefail; D=/workspace/models/tts-v2-src/Raon-OpenTTS; mkdir -p /workspace/models/tts-v2-src; test -d "$D/.git" || git clone --depth 1 https://github.com/krafton-ai/Raon-OpenTTS.git "$D"; /workspace/models/tts-v2-venv/bin/pip install -e "$D"; /workspace/models/tts-v2-venv/bin/hf download KRAFTON/Raon-OpenTTS-1B --local-dir /workspace/models/tts-v2/Raon-OpenTTS-1B; /workspace/models/tts-v2-venv/bin/hf download speechbrain/tts-hifigan-libritts-16kHz generator.ckpt --local-dir /workspace/models/tts-v2/Raon-vocoder'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace:/workspace/models/tts-v2-src/Raon-OpenTTS PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job raon' 2>&1 | Tee-Object 'logs\tts-v2-08-raon.log'
```

### Magpie v2607, Aria FR

```powershell
docker exec $C bash -lc 'set -euo pipefail; /workspace/models/tts-v2-venv/bin/pip install -U "nemo_toolkit[tts]" kaldialign'
docker exec $C bash -lc 'set -euo pipefail; export HF_HOME=/workspace/models/hf-cache PYTHONPATH=/workspace PYTHONUNBUFFERED=1; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --job magpie' 2>&1 | Tee-Object 'logs\tts-v2-09-magpie.log'
```

## 3. Validation bloquante

Générer l'index, puis valider les fichiers réels. Un import Python réussi ou une ligne dans `meta.jsonl` ne vaut pas succès.

```powershell
docker exec $C bash -lc 'set -euo pipefail; export PYTHONPATH=/workspace; /workspace/models/tts-v2-venv/bin/python /workspace/dev/scripts/_voix_10_samples_v2.py --index'

$Expected = @(
  '01-voxcpm2-clone-aurora.mp3',
  '02-neutts-nano-french-clone-aurora.mp3',
  '03-audio8-tts-0.6b-clone-aurora.mp3',
  '04-dots-tts-mf-clone-aurora.mp3',
  '05-anka-tts-clone-aurora.mp3',
  '06-indextts25-clone-aurora.mp3',
  '07-fireredtts3-base-clone-aurora.mp3',
  '08-raon-opentts-1b-clone-aurora.mp3',
  '09-magpie-v2607-aria-fr.mp3',
  '10b-chatterbox-mtl-v3-clone-aurora.mp3'
)

$Actual = @(Get-ChildItem 'data\out\voix-10-samples-v2' -Filter '*.mp3' | Select-Object -ExpandProperty Name)
$Diff = Compare-Object $Expected $Actual
if ($Diff) { $Diff; throw 'La liste des MP3 ne correspond pas aux 10 slots' }
if ($Actual.Count -ne 10) { throw "Attendu 10 MP3, trouve $($Actual.Count)" }

foreach ($Name in $Expected) {
    $Path = "data\out\voix-10-samples-v2\$Name"
    if (-not (Test-Path $Path)) { throw "Manque $Path" }
    $ContainerPath = "/workspace/data/out/voix-10-samples-v2/$Name"
    docker exec $C ffmpeg -v error -i $ContainerPath -f null -
    if ($LASTEXITCODE -ne 0) { throw "MP3 illisible: $Path" }
    docker exec $C ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,sample_rate,channels -of json $ContainerPath
}

$Meta = Get-Content 'data\out\voix-10-samples-v2\meta.jsonl' | ForEach-Object { $_ | ConvertFrom-Json }
if ($Meta.Count -ne 10) { throw "Attendu 10 lignes meta uniques, trouve $($Meta.Count)" }
if (($Meta.fichier | Sort-Object -Unique).Count -ne 10) { throw 'Doublons dans meta.jsonl' }
```

Critères bloquants par MP3 : codec lisible, mono, durée 20–90 s, taille > 100 Ko, fin de la dernière phrase audible, pas de fuite du prompt anglais. Écouter au minimum le début, une jointure centrale et les cinq dernières secondes de chacun. Si une synthèse coupe ou parle anglais, elle ne compte pas.

## 4. Livraison

Écrire :

- `data/out/voix-10-samples-v2/INDEX.md`
- `nights/2026-09-14-CLAUDE-VOIX-V2.md`

Le rapport Claude doit donner pour chaque slot : modèle exact/révision, licence, commande, durée, SR, taille, temps de synthèse, VRAM max si observée, qualité FR, fidélité Aura, anomalie éventuelle. Signaler clairement que le slot 10 Chatterbox est le repli hors cutoff; ne pas falsifier sa date.

Copier `INDEX.md` et le rapport Claude dans `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\` aux mêmes chemins relatifs. Ne jamais copier les MP3 dans le vault.

## Sources techniques à suivre pour les API

- VoxCPM2 : https://github.com/OpenBMB/VoxCPM
- NeuTTS : https://github.com/neuphonic/neutts
- Audio8 : https://github.com/Edge0-AI/Audio8_TTS
- dots.tts : https://github.com/studio-dots-ai/dots.tts
- IndexTTS : https://github.com/index-tts/index-tts
- FireRedTTS3 : https://github.com/FireRedTeam/FireRedTTS3
- Raon OpenTTS : https://github.com/krafton-ai/Raon-OpenTTS
- Magpie : https://huggingface.co/nvidia/magpie_tts_multilingual_357m
