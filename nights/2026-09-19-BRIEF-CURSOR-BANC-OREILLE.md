---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6)
auteur: Claude (lead technique)
---

# BRIEF Cursor — Banc oreille (dégustation ASR)

But : transcrire les mêmes enregistrements de Thomas avec 5 oreilles locales + 1 repère distant, et mesurer.

## Candidats
1. `openai/whisper-large-v3-turbo` via faster-whisper (déjà utilisé par le host-agent — référence)
2. `Qwen/Qwen3-ASR-0.6B` (backend `qwen3` déjà prévu dans `src/ears/` — le réutiliser si possible)
3. `nvidia/parakeet-tdt-0.6b-v3` — **préférer une voie ONNX** (sherpa-onnx ou onnx-asr) plutôt que NeMo
4. `nvidia/nemotron-3.5-asr-streaming-0.6b` — idem, GGUF/ONNX si disponible, sinon NeMo en venv isolé
5. `kyutai/stt-1b-en_fr` — voie Python `moshi` en venv isolé
6. Repère distant : `stepaudio-2.5-asr` via `https://api.stepfun.ai/step_plan/v1` (clé `STEPFUN_API_KEY` : lue par le script à l'exécution, jamais affichée ni écrite)

## Livrables
- `dev/scripts/banc_oreille.py` : prend un dossier de `.wav`, sort pour chaque candidat : transcription, temps de calcul, RTF, VRAM max (nvidia-smi), et « Windows natif : oui/non/à vérifier » selon la voie utilisée.
- Sortie : `nights/degustation-19/oreille/resultats.md` avec transcriptions **anonymisées** (O1…O6, correspondance dans `nights/degustation-19/oreille/.carte-secrete.json`).
- Tester le banc sur `nights/degustation-19/.sources/voix-F5.wav` (voix de synthèse, texte connu : « Bonjour Thomas. Je suis MOTHER. Aujourd'hui, un brouillard humide recouvre la rue ; prends ton parapluie, et dis-moi si tu veux que je te lise la suite. ») et coller le résultat dans l'OUT.

## Où et comment
Exécution dans le conteneur `mother-core-dev`. Chaque candidat dans **son propre venv** sous `/workspace/models/asr-bench/<nom>/` (ne rien installer dans le Python système ni dans les venvs existants). Poids sous `/workspace/models/asr-bench/`.
Un seul modèle chargé à la fois sur le GPU, déchargé après.

## Interdits
Ne pas relancer ni arrêter le host-agent ni `:8090` · ne toucher à aucun fichier de `src/`, `native/`, `workers/` · ne pas lire `.env.local` hors du script · pas de git.
OUT : `nights/2026-09-19-BANC-OREILLE-OUT.md` (voies retenues, échecs d'installation avec cause, résultat du test). Réponds seulement OK.
