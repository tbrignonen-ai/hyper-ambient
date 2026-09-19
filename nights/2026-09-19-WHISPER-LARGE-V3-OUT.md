---
date: 2026-09-19
type: out
cible: Claude (lead technique)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-19-BRIEF-CURSOR-BANC-OREILLE]]"]
---

# OUT — whisper-large-v3 (oreille réel)

Candidat `openai/whisper-large-v3` via faster-whisper, modèle `large-v3`.
Conteneur `mother-core-dev`. `--id whisper-large-v3` seulement, 5 wav de `/workspace/data/in/oreille-reel`.
Host-agent (PID 12602) et `llama-server` (PID 20383, granite-4.2-3b) non relancés.
`bruts.json` : 30 lignes conservées + 5 ajoutées (35). Pas de git, pas de `.env.local`.

Device : **cuda** / `int8_float16` (nvidia-smi : 5638 MiB libres ≥ 4 Go). VRAM max = `memory.used` pendant le worker (inclut llama-server + host-agent déjà résidents). Après déchargement : 6380 MiB used / 5631 MiB free.

Tests : `dev/tests/test_banc_oreille.py` — rouge (import manquant) puis **12 passed**.

| fichier | device | temps_s | RTF | VRAM max (MiB) | transcription |
|---|---|---:|---:|---:|---|
| phrase1.wav | cuda | 263.264 | 36.423 | 8702 | salut mother est ce que tu peux me résumer ce que codex a fait cette nuit |
| phrase2.wav | cuda | 13.944 | 2.427 | 8655 | Rappelle-moi jeudi à 15h30 d'appeler le docteur Lefebvre. |
| phrase3.wav | cuda | 12.708 | 2.494 | 8681 | Cherche la météo à Aix-en-Provence pour ce week-end. |
| phrase4.wav | cuda | 12.568 | 2.324 | 8681 | Attends stop, c'est pas ce que je voulais dire. |
| phrase5.wav | cuda | 12.961 | 0.932 | 8649 | Ouvre le dossier BGB et lis-moi la section sur l'interopérabilité avec Camunda. |

phrase1 inclut le 1er chargement (poids `Systran/faster-whisper-large-v3` absents du cache HF). Les 4 suivants sont le coût d'inférence une fois le venv prêt.
