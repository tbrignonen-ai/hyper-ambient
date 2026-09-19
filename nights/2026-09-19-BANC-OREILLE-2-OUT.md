---
date: 2026-09-19
type: out
cible: Claude (lead technique)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-19-WS-OREILLE]]"]
---

# OUT — Banc oreille 2 (Canary + latence à chaud)

Exécution dans `mother-core-dev`. Host-agent et `llama-server` (`:8090`) non relancés. Pas de git, pas de `.env.local`. Un seul modèle ASR chargé à la fois.

Wav : `/workspace/data/in/oreille-reel` (5 phrases). `bruts.json` : 35 lignes conservées + 5 Canary (40). Tests : `dev/tests/test_banc_oreille.py` — rouge (`StopIteration` / `ImportError`) puis **17 passed**.

Voie Canary : **onnx-asr** (`nemo-canary-1b-v2` ← `istupakov/canary-1b-v2-onnx`), Windows natif oui. Venv `/workspace/models/asr-bench/canary`. Premier essai CUDA tombé sur `libcudnn.so.9` absent du `LD_LIBRARY_PATH` (repli CPU). Corrigé : `onnxruntime-gpu[cuda,cudnn]<1.27` + libs `nvidia-cudnn-cu12` déjà dans le site système. Mesures ci-dessous = **CUDA**.

## Latence à chaud (modèle chargé une fois)

Baseline GPU partagée (llama-server granite-4.2-3b + host-agent) : ~6200–6350 MiB used / ~5,6 Go libres.

| modèle | voie | device | chargement_s | p1 s | p2 s | p3 s | p4 s | p5 s | VRAM avant | VRAM après | VRAM propre |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| parakeet-tdt-0.6b-v3 | sherpa-onnx INT8 | cuda | 24.621 | 0.618 | 0.326 | 0.316 | 0.313 | 0.743 | 6355 | 6352 | **0** |
| whisper-large-v3 | faster-whisper | cuda / int8_float16 | 16.183 | 0.569 | 0.488 | 0.431 | 0.424 | 0.545 | 6356 | 8333 | **1977** |
| canary-1b-v2 | onnx-asr | cuda | 35.956 | 1.775 | 0.247 | 0.168 | 0.139 | 0.281 | 7306 | 11712 | **4406** |

Whisper sans hotwords (1er passage, poids encore froids au chargement 263.079 s) : p1 0.731 · p2 0.692 · p3 0.425 · p4 0.379 · p5 0.979 ; VRAM 6233 → 8333 = **2100**. Tableau : 2e passage (hotwords), chargement chaud.

Canary p1 = 1er decode CUDA (warmup). p2–p5 = régime. VRAM avant Canary était déjà haute (~7300, résidu provider CUDA) ; après déchargement retour ~6350. Occupation réelle ≈ **5,3 Go** (pic 11712 − repos 6350).

Parakeet : aucune hausse `nvidia-smi` après chargement (INT8 sherpa, delta 0). Inférence 0,3–0,7 s.

Durées wav : p1 7.228 · p2 5.746 · p3 5.096 · p4 5.408 · p5 13.910 s.

## Transcriptions Canary (CUDA, identiques à chaud et dans `bruts.json`)

Référence `phrases.txt` : « Salut MOTHER… Codex… » / « quinze heures trente » / « Aix-en-Provence » / « c'est pas ça » / « lis-moi … Camunda ».

| fichier | texte |
|---|---|
| phrase1.wav | Salut Moser, est-ce que tu peux me résumer ce que Codex a fait cette nuit? |
| phrase2.wav | Rappelle-moi jeudi à quinze heures trente d'appeler le docteur Lefebvre. |
| phrase3.wav | Cherche la météo à Aix-en-Provence pour ce week-end. |
| phrase4.wav | Attends, stop. c'est pas ce que je voulais dire. |
| phrase5.wav | Ouvre le dossier BGB et limois la section sur l'interopérabilité avec Camunda. |

**Moser** (pas MOTHER) · **limois** (pas lis-moi) · Camunda et Codex OK · nombres en lettres OK.

Froid (rechargement à chaque wav, CUDA) : ~19 s / phrase, VRAM max ~11620–11694 MiB.

## Effet hotwords Whisper large-v3 (`MOTHER Codex Camunda Claude`)

| fichier | sans hotwords | avec hotwords |
|---|---|---|
| phrase1.wav | salut mother est ce que tu peux me résumer ce que codex a fait cette nuit | Salut Mother, est-ce que tu peux me résumer ce que Codex a fait cette nuit ? |
| phrase2.wav | Rappelle-moi jeudi à 15h30 d'appeler le docteur Lefebvre. | identique |
| phrase3.wav | Cherche la météo à Aix-en-Provence pour ce week-end. | identique |
| phrase4.wav | Attends stop, c'est pas ce que je voulais dire. | identique |
| phrase5.wav | Ouvre le dossier BGB et lis-moi la section sur l'interopérabilité avec Camunda. | identique |

Effet : **casse + ponctuation** sur MOTHER/Codex (phrase 1). Camunda déjà juste sans hotwords. Pas de pénalité de latence (p1 0.57 s vs 0.73 s). Ne corrige pas « 15h30 » → lettres.

## Reco courte

À chaud, Parakeet reste le plus léger (VRAM 0 visible, ~0,3 s). Whisper large-v3 ~0,4–0,7 s + **2,0 Go** et seul levier hotwords. Canary 1B-v2 CUDA ~0,14–0,28 s après warmup, **~4,4–5,3 Go**, meilleur sur les nombres (quinze heures trente) mais rate MOTHER/lis-moi.
