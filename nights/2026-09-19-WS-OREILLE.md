---
date: 2026-09-19
type: veille
auteur: WS (+ OC mirroir)
source: Hugging Face Hub API + Open ASR Leaderboard CSV (2026-09-14/16)
demande: [[2026-09-19-DEMANDE-CLAUDE-POUR-GROK-WS-OREILLE]]
---

# Oreille STT MOTHER — veille HF API

**Méthode:** Hugging Face Hub API + CSV Open ASR Leaderboard (pas web-search seul).

### Sources HF
| Source | URL | lastModified |
|---|---|---|
| Space Open ASR Leaderboard | https://huggingface.co/spaces/hf-audio/open_asr_leaderboard | 2026-09-16 |
| EN short results | https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results (`english_short_latest.csv`) | 2026-09-14 |
| FR (FLEURS / MCV / MLS) | https://huggingface.co/datasets/hf-audio/multilingual_evals (`multilingual_fr.csv`) | 2026-09-14 |

**Contraintes:** FR d'abord + EN · streaming · Windows natif · 10 Go VRAM total · noms tech (Camunda, Codex, MOTHER).

**Mesures live Thomas:** Parakeet-TDT-0.6B-v3 **11%** · Whisper-turbo **13%** · Nemotron-3.5 **19%** · StepASR **23%** · Qwen3-ASR-0.6B **28%** · Kyutai **SIGSEGV**.

---

## Tableau (WER % — plus bas = mieux)

| Modèle | Live FR | FLEURS-fr | MCV-fr | MLS-fr | EN avg | RTFx FR/EN | Streaming | Windows | Hotwords |
|---|---|---|---|---|---|---|---|---|---|
| **nvidia/parakeet-tdt-0.6b-v3** | **11%** | **4,68** | **6,35** | **5,12** | **4,86** | 3618 / 6076 | chunked NeMo | **oui** sherpa-onnx + GGUF | NON TROUVÉ carte |
| **openai/whisper-large-v3-turbo** | **13%** | 4,90 | 11,06 | 4,22 | 6,36 | 591 / 797 | chunked | **oui** faster-whisper CT2 | **oui** hotwords/initial_prompt |
| openai/whisper-large-v3 | en cours | 4,84 | 9,97 | 3,90 | 5,78 | 340 / 470 | chunked | oui CT2 | oui |
| nvidia/nemotron-3.5-asr-streaming-0.6b | 19% | 9,86 | 10,97 | 7,36 | 7,88 | 1175 / 1345 | natif cache-aware | GGUF/ONNX partiel | NON TROUVÉ |
| Qwen/Qwen3-ASR-0.6B | 28% | 7,06 | 10,78 | 8,44 | 5,05 | 396 / 744 | vLLM | sherpa int8 | NON TROUVÉ |
| Qwen/Qwen3-ASR-1.7B | NON TROUVÉ live | **4,06** | 7,84 | 5,15 | **4,31** | 379 / 820 | vLLM | plus lourd ~2B | NON TROUVÉ |
| kyutai/stt-1b-en_fr | SIGSEGV | NON TROUVÉ | NON TROUVÉ | NON TROUVÉ | — | — | natif 0,5s | **crash** | NON TROUVÉ |
| **nvidia/canary-1b-v2** ★ | NON TROUVÉ live | **4,35** | 6,58 | **3,45** | 5,71 | 1457 / 1825 | offline-first | **oui** ONNX + GGUF | NON TROUVÉ |
| Voxtral-Mini-3B-2507 | NON TROUVÉ | 4,13 | 7,80 | 5,96 | 5,54 | 158 / 181 | offline | 3B+ VRAM | NON TROUVÉ |
| Voxtral-Mini-4B-Realtime-2602 | NON TROUVÉ | 8,19 | 9,57 | 5,59 | 6,46 | 50 / 103 | realtime | — | NON TROUVÉ |

---

## 3 modèles recommandés (FR + EN)

### 1. `nvidia/parakeet-tdt-0.6b-v3` — **primaire**
Meilleur live (11%) + boards FR/EN solides + Windows déjà validé (sherpa-onnx). Hotwords absents carte → compenser ailleurs.

### 2. `openai/whisper-large-v3-turbo` (faster-whisper) — **repli + hotwords**
Live 13%, CT2 Windows, **seul levier hotwords** clair pour Camunda/Codex/MOTHER.

### 3. `nvidia/canary-1b-v2` (+ ONNX) — **à déguster avant lock**
FLEURS/MLS FR **meilleurs que Parakeet** sur board HF, FR+EN, 1B, ONNX Windows. Pas encore mesuré live — priorité banc.  
Alt: `Qwen3-ASR-1.7B` (meilleur FLEURS open ≤2B) si Canary déçoit ; Voxtral-4B-Realtime board FR faible ; Kyutai hors jeu tant que SIGSEGV.

## Reco MOTHER (3 lignes)
1. **Parakeet v3** = oreille défaut (preuve live + board).
2. **Whisper turbo** = voie secondaire pour **hotwords** tech.
3. **Banc Canary-1B-v2** avant CARTE-FIGEE — meilleur candidat manqué boards FR+EN ≤2B.

*Fin WS 19 sept — HF API + Open ASR Leaderboard.*
