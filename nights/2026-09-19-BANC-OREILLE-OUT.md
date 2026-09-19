---
date: 2026-09-19
type: out
cible: Claude (lead technique)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-19-BRIEF-CURSOR-BANC-OREILLE]]"]
---

# OUT — Banc oreille

Exécution dans `mother-core-dev`. Host-agent et `:8090` non relancés. Aucun fichier de `src/`, `native/`, `workers/` modifié. `.env.local` lu seulement par le script. Pas de git.

Wav de test : `nights/degustation-19/.sources/voix-F5.wav` (13,026 s, 44,1 kHz), copié vers `/workspace/data/in/oreille-bench/` (volume monté : `nights/` n'est pas dans le compose).
Texte connu : « Bonjour Thomas. Je suis MOTHER. Aujourd'hui, un brouillard humide recouvre la rue ; prends ton parapluie, et dis-moi si tu veux que je te lise la suite. »

Script : `dev/scripts/banc_oreille.py`. Venvs + poids : `/workspace/models/asr-bench/`. Tests unitaires : `dev/tests/test_banc_oreille.py` — 8 passed.

## Voies retenues (transcription obtenue)

| # | voie | Windows natif | temps_s | RTF | VRAM max nvidia-smi (MiB) |
|---|---|---|---:|---:|---:|
| 1 | faster-whisper `large-v3-turbo` | oui | 47.990 | 3.684 | 6769 |
| 2 | Qwen3-ASR-0.6B via `src.ears.qwen3_asr` (venv isolé, PYTHONPATH) | à vérifier | 87.754 | 6.737 | 6647 |
| 3 | parakeet-tdt-0.6b-v3 INT8 **sherpa-onnx** | oui | 108.020 | 8.292 | 3841 |
| 4 | nemotron-3.5-asr GGUF **nemo-speech** (CUDA) | oui | 5.319 | 0.408 | 10355 |
| 6 | stepaudio-2.5-asr HTTP `…/step_plan/v1/audio/asr/sse` | oui | 3.535 | 0.271 | 3776 |

VRAM = `nvidia-smi memory.used` pendant le worker (inclut llama-server + host-agent déjà résidents). Un modèle ASR à la fois ; process worker terminé ensuite.

## Échecs d'installation / d'inférence

| candidat | stade | cause |
|---|---|---|
| nemotron | install.sh 1er essai | `--prefix` = dossier du venv → `rename …/nemotron → nemotron.old: Permission denied`. Binaire récupéré dans `nemotron.new`. |
| nemotron | 1re inférence | `undefined symbol: ggml_fused_relpos_attn_cached` (RPATH charge le `libggml` système de llama.cpp). Corrigé : `LD_LIBRARY_PATH` vers `nemotron.new/lib` + `LD_PRELOAD` libstdc++ système (le libstdc++ bundlé n'a pas GLIBCXX_3.4.29). 2e mesure OK. |
| kyutai/stt-1b-en_fr | pip `moshi>=0.2.6` | OK (venv `--system-site-packages`, rien écrit dans le Python système). |
| kyutai | inférence `moshi.run_inference` | **SIGSEGV exit 139** après « mimi loaded / moshi loaded / starting inference ». Pas de transcription. |

## Résultat du test (anonymisé)

Fichiers : `nights/degustation-19/oreille/resultats.md` + `nights/degustation-19/oreille/.carte-secrete.json`.

# Banc oreille — résultats anonymisés

Correspondance des codes : `oreille/.carte-secrete.json` (hors lecture publique).

| oreille | fichier | temps_s | RTF | VRAM max (MiB) | Windows natif | erreur | transcription |
|---|---|---:|---:|---:|---|---|---|
| O1 | voix-F5.wav | 47.990 | 3.684 | 6769 | oui |  | Bonjour Thomas, je suis Motter. Aujourd'hui, un brouillard humide recouvre la rue. Prends ton parapluie et dis-moi si tu veux que je te lise la suite. |
| O2 | voix-F5.wav | 87.754 | 6.737 | 6647 | à vérifier |  | Bonjour Thomas, je suis moteur. Aujourd'hui, un brouillard humide recouvre la rue, prend ton parapluïe et dit : « Moi, si tu veux que je te lise la suite. » |
| O3 | voix-F5.wav | 108.020 | 8.292 | 3841 | oui |  | Bonjour Thomas. Je suis Mauter. Aujourd'hui, un brouillard humide recouvre la rue. Prends ton parapluie, et dis-moi si tu veux que je te lise la suite. |
| O4 | voix-F5.wav | 5.319 | 0.408 | 10355 | oui |  | Bonjour Thomas, je suis Moter aujourd'hui un brouillard humide recouvre la rue Prends-on parapluie et dis moi si tu veux que je te lise la suite. |
| O5 | voix-F5.wav | 254.980 | 19.574 | 6495 | à vérifier | SIGSEGV (exit 139) pendant l'inférence |  |
| O6 | voix-F5.wav | 3.535 | 0.271 | 3776 | oui |  | Bonjour Thomas. Je suis aujourd'hui. Un brouillard humide recouvre la rue. Prends ton parapluie et dis-moi si tu veux que je te lise la suite. |
