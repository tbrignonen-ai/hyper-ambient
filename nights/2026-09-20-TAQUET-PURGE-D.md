---
date: 2026-09-20
type: plan
lane: PURGE-D
owner: qwen
status: done
deadline: "11:55 Europe/Paris"
related: ["[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-20-TAQUET-SSD-E]]"]
---

# TAQUET PURGE-D — modèles non-retenus à dégager de D:

## Méthode

Périmètre modèle : `D:\BGB Training\MOTHER-dev\models`. Tailles mesurées réellement sur disque le 20/09 (PowerShell, somme des fichiers). Retenus de la carte figée du 19/09 (Granite + faster-whisper large-v3 + Magpie Sofia). **Aucune suppression n'a été effectuée** : ce document est un plan d'évacuation priorisé, classé pires d'abord (plus gros / plus inutiles en premier).

Potentiel total identifié : **~121 Go de modèles non-retenus** (dont 12 Go de replis documentés) + ~37 Go de caches/bâtis hors produit.

## Intouchables (à exclure de toute purge)

| Chemin | Raison |
|---|---|
| `models/gguf/granite-4.2-3b-Q4_K_M.gguf` | Cerveau retenu — source D: conservée en plus de la copie E: vérifiée |
| `models/hf-cache/hub/models--Systran--faster-whisper-large-v3` | Oreille retenue |
| `models/tts-bench/magpie/` | Voix retenue Magpie Sofia (GGUF v2602 + codec) |
| `models/asr-bench/nemotron.new` | Binaire nemo-speech **CUDA** requis par la voix (réserve C7 de la carte figée) |
| `D:\Hermes D drive`, `D:\sawb_v6`, `D:\sawb-dashboard` | Hermes/SAWB — hors périmètre, intouchables |

## Priorité 1 — modèles non-retenus sans valeur de repli (pires d'abord)

Classés par taille décroissante. Rien de tout cela n'est retenu, ni repli documenté.

| Rang | Taille | Chemin relatif à D:\BGB Training\MOTHER-dev\models | Raison |
|---|---|---|---|
| 1 | 11 732 Mo | `tts-v2/FireRedTTS3/` | Voix jamais retenue (retenu = Magpie Sofia) — plus gros dossier modèle |
| 2 | 10 293 Mo | `gguf/Accio-Lab_occamy-1.0-IQ2_XXS.gguf` | SKU 16 Go, hors profil 12 Go VRAM — éliminé par contrainte matérielle, jamais utilisable |
| 3 | 10 025 Mo | `tts-v2/IndexTTS-2.5/` | Voix non retenue au banc |
| 4 | 4 928 Mo | `hf-cache/hub/models--dots-studio--dots.tts-mf/` | TTS Dots, banc — non retenu |
| 5 | 4 917 Mo | `gguf/LFM2.5-8B-A1B-Q4_K_M.gguf` | Paire LFM2.5 non retenue (8B) |
| 6 | 4 732 Mo | `gguf/Luciole-8B-Instruct-1.1-Q4_K_M.gguf` | Cerveau non retenu au test à l'aveugle |
| 7 | 4 731 Mo | `hf-cache/hub/models--openbmb--VoxCPM2/` | TTS VoxCPM2, banc — non retenu |
| 8 | 3 782 Mo | `asr-bench/poids/canary/` | Canary 1B ONNX, banc oreille séparé |
| 9 | 3 247 Mo | `tts-bench/auk/` | Voix AuK, banc — non retenu |
| 10 | 3 062 Mo | `hf-cache/hub/models--ResembleAI--chatterbox/` | TTS Chatterbox, banc (cf. rang 19) |
| 11 | 2 447 Mo | `tts-v2/Audio8-TTS-Preview-0.6b/` | Voix Audio8 non retenue |
| 12 | 2 400 Mo | `hf-cache/hub/models--Qwen--Qwen3-TTS-12Hz-0.6B-Base/` | TTS Qwen3 non retenu (voix = Magpie) |
| 13 | 2 326 Mo | `tts-v2/Raon-OpenTTS-1B/` | Voix Raon non retenue |
| 14 | 2 254 Mo | `hf-cache/hub/models--kyutai--stt-1b-en_fr/` | ASR documenté **SIGSEGV à l'inférence** — inutilisable |
| 15 | 1 793 Mo | `hf-cache/hub/models--Qwen--Qwen3-ASR-0.6B/` | Oreille non retenue (retenu = faster-whisper large-v3) |
| 16 | 1 547 Mo | `hf-cache/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/` | Remplacé par large-v3 retenu |
| 17 | 1 417 Mo | `hf-cache/hub/models--kyutai--pocket-tts-without-voice-cloning/` | TTS Pocket-TTS non retenu (cache HF, cf. rang 24) |
| 18 | 1 414 Mo | `tts/Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf` + `mmproj-…` | TTS Qwen3 1.7B non retenu |
| 19 | 1 288 Mo | `hf-cache/hub/models--krmkayabasi--Anka-TTS/` | TTS Anka non retenu (cache HF, cf. rang 22) |
| 20 | 1 284 Mo | `tts-bench/audio8/` | Voix Audio8, banc |
| 21 | 999 Mo | `pocket-tts/languages/` | Modèles par langue Pocket-TTS, non retenu |
| 22 | 977 Mo | `tts-bench/omnivoice/` | Voix OmniVoice, banc |
| 23 | 804 Mo | `tts-v2-chatterbox/` | TTS Chatterbox, banc local (avec rang 10) |
| 24 | 708 Mo | `asr-bench/poids/nemotron/nemotron-3.5-asr-streaming-0.6b.q8_0.gguf` | Banc ASR Nemotron — **ne pas confondre avec `nemotron.new` (binaire à garder)** |
| 25 | 411 Mo | `tts-v2-anka/` | TTS Anka, banc local (avec rang 19) |
| 26 | 255 Mo | `hf-cache/hub/models--k2-fsa--OmniVoice/` | TTS OmniVoice, cache (avec rang 22) |
| 27 | 141 Mo | `hf-cache/hub/models--Systran--faster-whisper-base/` | Remplacé par large-v3 retenu |
| 28 | 140 Mo | `tts-v2-omnivoice/` | TTS OmniVoice, banc local |
| 29 | 139 Mo | `hf-cache/hub/models--facebook--mms-tts-fra/` | TTS MMS non retenu |
| 30 | 53 Mo | `tts-v2/Raon-vocoder/` | Vocoder du TTS Raon (rang 13) |
| 31 | 52 Mo | `hf-cache/hub/models--charactr--vocos-mel-24khz/` | Vocoder des TTS bancs — part avec eux |
| 32 | 16 Mo | `tts-v2-voxcpm/` + `tts-v2-neutts/` + `tts-bench/neutts/` | Bancs VoxCPM2/NeuTTS vestiges |

## Priorité 2 — replis documentés (dernière tranche : ne dégager que si l'on accepte de perdre le filet)

Replis officiels de la carte figée du 19/09. S'ils restent souhaités en secours, conserver NeoHorse (n°1), puis Ministral.

| Rang | Taille | Chemin | Raison |
|---|---|---|---|
| R1 | 5 368 Mo | `gguf/NeoHorse-1-9B-Q4_K_M.gguf` | Repli cerveau n°1 documenté (4,0/5) |
| R2 | 4 958 Mo | `gguf/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf` | Repli cerveau n°2 (5,0/5 mais jugé trop ancien) |
| R3 | 1 105 Mo | `asr-bench/poids/parakeet/` | Repli oreille documenté (Parakeet-TDT-0.6B, rate « Camunda ») |
| R4 | 547 Mo | `whisper/ggml-large-v3-turbo-q5_0.bin` | Fallback GGML remplacé par faster-whisper retenu |
| R5 | 385 Mo | `supertonic/` | Repli voix documenté (F5 ×0,88, CPU, 0 VRAM) |

## Priorité 3 — à vérifier avant purge (ne rien faire sans contrôle)

| Taille | Chemin | Question |
|---|---|---|
| 1 945 Mo | `hf-cache/hub/models--nvidia--magpie_tts_multilingual_357m/` | Cache v2607 historique (SSD-E) ou lu par nemo-speech ? Confirmer avant purge |
| non mesuré | `asr-bench/whisper-large-v3/`, `asr-bench/whisper-turbo/`, `asr-bench/qwen3-asr/`, `asr-bench/kyutai/`, `asr-bench/canary/`, `asr-bench/hf-cache/` | Doublons de banc présumés du retenu — mesurer, puis traiter comme rang 15/16 |
| — | `asr-bench/stepaudio/` | Intégration distante optionnelle (StepAudio TTS) — décision produit |
| 4 571 Mo | `nanojev/` (+ 203 Mo `nanojev-src/`) | Intégration distante optionnelle JeV (mains libres) — décision produit |

## Priorité 4 — caches / venvs / sources (hors choix produit, signalés comme caches)

| Taille | Chemin | Nature |
|---|---|---|
| 14 054 Mo | `uv-cache/` | Cache pip/uv — régénéré au besoin |
| 8 608 Mo | `tts-v2-src/` | Sources clonées des TTS bancs |
| 8 503 Mo | `tts-v2-firered-venv/` | venv du banc FireRed (rang 1) |
| 1 048 Mo | `tts-v2-venv/` | venv TTS courant |

## Synthèse

- **Priorité 1 (modèles sans valeur) : ~107 Go** — évacuation immédiate possible, sous réserve des contrôles de la priorité 3.
- **Priorité 2 (replis) : ~12,4 Go** — à décider selon l'acceptation d'un fonctionnement sans filet.
- **Priorité 4 (caches/bâtis) : ~32 Go** — inertes, purge sans risque produit.
- Rappel : toutes les tailles sont des sommes disque du 20/09 ; les copies E: vérifiées couvrent le stack retenu 0.1 ; aucune suppression effectuée à ce stade.