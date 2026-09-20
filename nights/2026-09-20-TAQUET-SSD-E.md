---
date: 2026-09-20
type: out
lane: SSD-E
owner: codex
status: done
deadline: "11:35 Europe/Paris"
---

# TAQUET SSD-E — carte 0.1 et inventaire D:

## Résultat

La carte locale vérifiée sur `E:\HyperAmbient-models` est :

| Brique | Retenu | État E: |
|---|---|---|
| Cerveau | Granite 4.2 3B Q4_K_M | présent, lisible |
| Oreille | faster-whisper `large-v3` | blobs présents, snapshot réparé et lisible |
| Voix | Magpie multilingual 357M, voix Sofia | modèle + codec présents |

## SHA256 E:

Les neuf artefacts ont été relus avec SHA256. Les valeurs correspondent au relevé de la carte figée du 19/09.

| Chemin relatif à `E:\HyperAmbient-models` | Octets | SHA256 |
|---|---:|---|
| `granite-4.2-3b-Q4_K_M.gguf` | 2244011552 | `E0406663965846AE22A403456EB826CCCE5F450840491F71952F18A7CB78E7D5` |
| `faster-whisper-large-v3/blobs/0adcd01e7c237205d593b707e66dd5d7bc785d2d` | 1068114 | `C69260F2AB26D659B7C398F9A2B2B48ED0DF16C3B47D7326782FD9CBA71690C1` |
| `faster-whisper-large-v3/blobs/3a5e2ba63acdcac9a19ba56cf9bd27f185bfff61` | 2480617 | `6D8CBD7CD0D8D5815E478DAC67B85A26BBE77C1F5E0C6D76D1CE2ABC0E5F21CA` |
| `faster-whisper-large-v3/blobs/69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1` | 3087284237 | `69F74147E3334731BC3A76048724833325D2EC74642FB52620EDA87352E3D4F1` |
| `faster-whisper-large-v3/blobs/75336feae814999bae6ccccdecf177639ffc6f9d` | 2394 | `A9306624F5EC14270A014B647E5C316B6E03A662C369758D1B90697A7B0655B9` |
| `faster-whisper-large-v3/blobs/931c77a740890c46365c7ae0c9d350ba3cca908f` | 340 | `7CCC62C6F2765AF1F3B46C00C9B5894426835A05021C8B9C01EECB6DFB542711` |
| `faster-whisper-large-v3/refs/main` | 40 | `02327F60E1723B7B947A879563D3721444D308349CDB0BC52F490FE186043266` |
| `magpie/magpie_tts_multilingual_357m.v2602.f16.gguf` | 448604832 | `901D299A8B1DF016CF81CAE0089A7A7C15627B9633D033357E15A47D9A219A75` |
| `magpie/nemo_nano_codec_22khz_1.89kbps_21.5fps.decoder.f16.gguf` | 78823104 | `CC86D36D821A27CDC1D4EF600A3E2B0DABE76E88FCC2A8652D9543134C07EF2D` |

Les cinq liens de `faster-whisper-large-v3/snapshots/edaa852ec7e145841d8ffdb056a99866b5f0a478/` étaient des junctions relatives illisibles sous Windows. Les blobs étaient intègres; les cinq entrées ont été remplacées par des liens durs locaux vers ces blobs. Les cinq fichiers snapshot sont maintenant lisibles et ont les mêmes SHA256 que les blobs.

## Non-retenus recensés sur D:

Périmètre modèle: `D:\BGB Training\MOTHER-dev\models`. Les caches/venvs sont signalés comme caches, pas comme choix produit.

### Cerveau / GGUF (`models/gguf`)

`Accio-Lab_occamy-1.0-IQ2_XXS.gguf` (SKU 16 Go, hors profil 12 Go), `LFM2.5-2.6B-Q5_K_M.gguf`, `LFM2.5-8B-A1B-Q4_K_M.gguf`, `LFM2.5-VL-3B-Q4_K_M.gguf`, `Luciole-8B-Instruct-1.1-Q4_K_M.gguf`, `Luth-2-2B-Q5_K_M.gguf`, `MiniCPM5-2B-Q4_K_M.gguf`, `Ministral-3-8B-Instruct-2512-Q4_K_M.gguf`, `Nanbeige_Nanbeige4.2-3B-Q4_K_M.gguf`, `NeoHorse-1-4B-Q4_K_M.gguf`, `NeoHorse-1-9B-Q4_K_M.gguf`, `Qwen3-0.6B-Q8_0.gguf`, `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, `Qwen3.5-4B-Q4_K_M.gguf`, `Spark-X2.5-4B-Q4_K_M.gguf`.

`granite-4.2-3b-Q4_K_M.gguf` sur D: est la source conservée du retenu, en plus de la copie E: vérifiée.

### Oreille / ASR non retenus ou bancs (`models/whisper`, `models/asr-bench`)

- `whisper/ggml-large-v3-turbo-q5_0.bin` (fallback GGML).
- `asr-bench/poids/parakeet/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/` (banc Parakeet).
- `asr-bench/poids/nemotron/nemotron-3.5-asr-streaming-0.6b.q8_0.gguf` (banc Nemotron).
- `asr-bench/poids/canary/` (Canary ONNX, banc séparé).
- Caches HF `faster-whisper-large-v3-turbo`, `faster-whisper-base`, `Qwen3-ASR-0.6B` et `kyutai/stt-1b-en_fr`; ce dernier est documenté SIGSEGV à l’inférence.

### Voix / TTS non retenus ou bancs (`models/piper`, `models/supertonic`, `models/pocket-tts`, `models/tts*`)

Restent recensés: Piper `siwis` (référence/fallback) et `mls`, Supertonic, Pocket-TTS, Qwen3-TTS, OmniVoice, Audio8, FireRedTTS3, IndexTTS, Raon, Anka, Chatterbox, Dots, MMS-TTS, VoxCPM2, NeuTTS/AuK et les caches Magpie v2607. Les rapports du 19/09 documentent Magpie Sofia comme retenu; les autres sont historiques, bancs ou replis.

## Évacuation effectuée sur D:

Suppression limitée aux paires Piper explicitement rejetées dans les bancs (`siwis/upmc/tom` est décrit comme mauvais/entrecoupé; `siwis` a été conservé comme référence):

- `models/piper/fr_FR-upmc-medium.onnx` — 76733615 octets, SHA256 `9ABB3800C199148897A9ED64E100D224F3DE83579F100044174AD19418F1786F`
- `models/piper/fr_FR-upmc-medium.onnx.json` — 4996 octets, SHA256 `E8636EC15DFD5D72DB37A02CB5320A20F2B8D339F2A0E4337DA64C58A33A5868`
- `models/piper/fr_FR-tom-medium.onnx` — 63511038 octets, SHA256 `BF65074CCDEEEEAA832E75EDB1C0A513C01C9A972BDF085FF8A6E71EA234FD41`
- `models/piper/fr_FR-tom-medium.onnx.json` — 4959 octets, SHA256 `2F7F885AD5A0AAD802E3CC24E4F57239FEBDCB142B4876DE5D238094674361CC`

Aucun autre modèle D: n’a été supprimé. `D:\Hermes D drive`, `D:\sawb_v6` et `D:\sawb-dashboard` n’ont pas été touchés.

## EN note — Hyper Ambient 0.1

The frozen 0.1 local stack is **Granite Q4 + faster-whisper large-v3 + Magpie Sofia**. Assets are intentionally split: Whisper uses five blob files plus a snapshot view, while Magpie uses one TTS GGUF plus a separate codec GGUF. All required assets are present on E: and their SHA256 values match the recorded source values. The Windows snapshot view was repaired with local hardlinks so the separated Whisper assets are directly readable.
