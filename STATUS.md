# hyper-ambient — État du projet (2026-09-02)

Première implémentation exécutable, bout-en-bout, mesurée. Machine : RTX 4070 12 Go.

---

## État des capacités

| Capacité | Modèle retenu | Mesure clé | État | VRAM | Notes |
|----------|---|---|---|---|---|
| **EARS** | faster-whisper `large-v3-turbo` int8_float16 | 370 ms RTF, WER 2,6 % | ✅ Actif | ~1,6 Go | CTranslate2 GPU. Remplacement : Nemotron-3.5 ou Parakeet (streaming natif). |
| **TURN-L1** | Silero VAD ONNX | 20 ms, RTF 0,004 | ✅ Actif | CPU | Endpoint à 4,30 s, trames 512 échantillons. |
| **TURN-L2** | Smart Turn v3 | **96,01 % FR**, 12 ms | ⏳ Levé, non installé | 8 Mo | OQ-15 résolu mathématiquement. Gain de qualité disponible, à intégrer. |
| **MOUTH** | Kyutai Pocket TTS `estelle` | 75 ms TTFA (63 ms à chaud), 104 chunks | ✅ Actif | 1,49 Go | 24 kHz, 26 voix FR. Repli : Piper (0 VRAM, 30× RTF). |
| **BRAIN-L1** | LFM2.5-2.6B Q5_K_M (`mother-local`) | ~26-38 ms TTFT, 660+ car/s | ✅ Actif | ~1,9 Go | llama.cpp CUDA (alias `mother-local` :8090). Défaut réflexe local (ex-Luth-2-2B). |
| **BRAIN-Escalade** | MiniMax-M3 (CommandCode) | 612 ms p50 TTFC, zéro delta reasoning | ✅ Actif | 0 (distant) | Routeur binaire : RÉFLEXE local → ESCALADE distant + meublage. |
| **Chaîne complète** | Composée | **500 ms round-trip perçu** | ✅ Exécutable | — | Budget NFR-01 1200 ms → marge ×2,4. Smoke test 9/9. |

---

## Blocages

### OQ-15 — Smart Turn v3 : levé sur papier, en attente d'intégration

| Aspect | Détail |
|---|---|
| **Mesure factuelle** | 96,01 % exactitude française (1253 échantillons), 1,60 % FP, 2,39 % FN, 12 ms latence CPU |
| **Spec réclamait** | Exactitude ≥ 90 %, FPR < 15 %. Critères satisfaits. |
| **État** | Pièce 8 Mo, licence BSD-2, prêt à installer. Non branchée actuellement. |
| **Prochain travail** | Remplacer Silero VAD par Smart Turn v3 ; cible : 3e étape des prochaines étapes. |

---

## Mesures brutes

### Latence globale (français 4,26 s, audio)

```
TURN-L1     20 ms  (VAD, endpoint à 4,30 s)
EARS       370 ms  (faster-whisper turbo, GPU)
BRAIN       27 ms  (TTFT local)
MOUTH      102 ms  (TTFA, Pocket TTS)
─────────────────
Round-trip 500 ms  (marge ×2,4 sur 1200 ms)
```

### Choix de modèle BRAIN — comparatif mesurés

| Modèle | Params | TTFT | car/s | Registre FR | Retenus |
|---|---|---|---|---|---|
| LFM2.5-VL-3B | 3 B | 26 ms | 667 | Faux (Ton → Tonne) | ✗ (banc 2026-08-21) |
| Luth-2-2B | 1,9 B | **38 ms** | **697** | Cohérent | historique 2026-08-21 |
| **LFM2.5-2.6B-Q5_K_M** | 2,6 B | ~26–38 ms | 660+ | — | **✅ défaut 2026-09-02** (`mother-local` :8090) |
| Ministral-3-8B-Instruct | 8 B | 39 ms | 331 | Mélange tu/vous | ✓ Bascule profondeur |
| Luciole-8B-Instruct | 8 B | 120 ms | 341 | Verbeux, fuyant | ✗ |
| Qwen3-4B-Instruct | 4 B | 43 ms | 389 | Hallucine | ✗ |

**Retenu** : LFM2.5-2.6B-Q5_K_M (remplace Luth-2-2B depuis le 2026-09-02, alias `mother-local` sur `:8090`). Double le débit d'un 8B, tiendrait seul sur 12 Go. Cohabitation EARS (1,6 Go) + MOUTH (1,49 Go) possible = solution MEDIUM. Luth-2-2B et Ministral restent en alternative.

### Arithmétique — zéro sur cinq

Tous les candidats, y compris 8B, répondent 15 h 20 au lieu de 15 h 40 sur « 14 h 40 + 20 min + 40 min = ? ». **C'est le prix de l'exigence « non-raisonneur ».**

### Distant en primaire : mesuré mauvais

Testé : distant-primaire + repli local 600 ms → 1477 ms total contre 876 ms local seul. L'échéance est une perte sèche. D'où : **local primaire, distant escalade intentionnelle.**

---

## Prochaines étapes (par ordre d'impact)

1. **Smart Turn v3** — 8 Mo, 96,01 % FR, 12 ms. Gain de qualité le plus net.
2. **EARS streaming** — Nemotron-3.5-ASR ou Parakeet. EARS est dominant (370 / 500 ms).
3. **Sortie 5.1** — Décorrélation faite, multicanal à brancher.
4. **Agent hôte natif** — `audio.capture`, `audio.render`, `input.inject`, `surface.draw`.
5. **Tool calling** — Escalade vers outils via le canal profond (routeur prêt).
6. **Barge-in** — Interruption pendant la parole ; flush TTS < 60 ms, annulation LLM < 40 ms.
7. **Crédit StepFun** — Bloqué par le compte.

---

## Points de vigilance

- Spec vit dans `D:\BGB Training\Projet MOTHER\` ; code dans `D:\BGB Training\MOTHER-dev\`. Deux dossiers.
- `.env.local` contient les clés API. Non versionné, monté R/O dans le conteneur.
- `pocket-tts` utilise numpy 2.4.6, scipy 1.17.1. `pip check` propre, aucune régression mesurée.
- **Quantisation int8 de Pocket TTS = CPU seulement.** Chemin GPU = fp32 (1,49 Go, non réducible à 1,5 Go).
- Réservation GPU dans `docker-compose.yml` **obligatoire.** Sans elle, `torch.cuda.is_available()` retourne `False`.
- `/dev/snd` ne contient que `timer` sous Docker Desktop Windows → pas d'ALSA. Audio = rôle de l'agent hôte natif.

---

## Inventaire disque

```
models/gguf/       20 Go  LFM2.5-2.6B (actif, mother-local), Luth, Ministral, Luciole, LFM2.5-VL, Qwen3-4B, Qwen3.5
models/pocket-tts/ 724 Mo estelle, eve, vera
models/hf-cache/   1,7 Go faster-whisper turbo + base
models/tts/        1,4 Go Qwen3-TTS (hors temps réel, offline)
models/whisper/    548 Mo ggml-large-v3-turbo
models/piper/      268 Mo repli MOUTH
```

Les six GGUF candidats conservés à la demande de l'utilisateur.

---

## Code exécutable cette session

- `src/brain/openai_compat.py`, `router.py`, `factory.py` : canal local + escalade
- `src/ears/faster_whisper_asr.py` : EARS CTranslate2
- `src/turn/silero_turn.py` : TURN-L1
- `src/mouth/piper_tts.py`, `pocket_tts.py`, `normalize.py`, `voice_design.py` : MOUTH streaming + profils DSP
- `dev/scripts/smoke_test.py` : 9 points, tout passe
- `dev/scripts/pipeline_demo.py`, `bench_brain.py`, `loopback_test.py`, `voice_lab.py`, `router_demo.py` : bancs de mesure

Voir `STACK.md` pour le raisonnement mesuré complet.

---

**Mise à jour** : 2026-09-02 — défaut BRAIN local LFM2.5-2.6B-Q5_K_M (`mother-local` :8090) ; Luth-2-2B en historique / repli.  
**Horizon prochaine étape** : Smart Turn v3 (intégration 1-2 h)
