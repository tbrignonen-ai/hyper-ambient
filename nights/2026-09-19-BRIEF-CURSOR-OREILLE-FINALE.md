---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6)
auteur: Claude (lead technique)
---

# BRIEF Cursor — Oreille : 2 derniers candidats avant de figer

Ajouter au banc `dev/scripts/banc_oreille.py` (+ `dev/tests/test_banc_oreille.py`, test rouge puis vert) :
1. `nvidia/canary-1b-v2` — voie Windows native de préférence (GGUF via nemo-speech déjà installé dans `/workspace/models/asr-bench/nemotron.new`, ou ONNX/sherpa-onnx) ; NeMo en venv isolé seulement en dernier recours.
2. `openai/whisper-large-v3` — faster-whisper, modèle `large-v3` (mesure interrompue plus tôt).

Exécuter **uniquement ces deux candidats** sur les 5 wav de `/workspace/data/in/oreille-reel` (conteneur `mother-core-dev`).
GPU si ≥ 4 Go libres (nvidia-smi), sinon CPU int8 — le noter. Ajouter leurs lignes à `/workspace/data/out/oreille-reel/bruts.json` sans effacer les autres.

Calculer le taux de mots faux (WER) de **tous** les candidats du fichier contre `nights/degustation-19/oreille/phrases.txt`
(normalisation : minuscules, ponctuation et tirets retirés ; **et** une 2e colonne où les nombres sont convertis en lettres avant comparaison, pour ne pas pénaliser « 15h30 »).

OUT : `nights/2026-09-19-OREILLE-FINALE-OUT.md` — tableau (candidat, WER brut, WER nombres normalisés, temps, VRAM, device, Windows natif) + les 5 transcriptions des 2 nouveaux.

Interdits : ne pas toucher au host-agent ni à llama-server · aucun fichier hors banc/test/OUT · pas de `.env.local` · pas de git. Réponds seulement OK.
