---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6)
auteur: Claude (lead technique)
lane: C9 — voix retenue dans MOTHER
---

# BRIEF Cursor — C9 : brancher Magpie Sofia comme voix de MOTHER

Décision Thomas (dégustation à l'aveugle) : **voix = nvidia/magpie_tts_multilingual_357m, voix Sofia**, CPU.
Magpie est installé : `/workspace/models/tts-bench/magpie` (`bin/nemo-speech`, `LD_LIBRARY_PATH=$M/lib`, GGUF sous `models/`).
Constat : Magpie **ne lit pas les nombres en chiffres** (« 24 », « 12 » sautés) ; pas de réglage de débit.

## À faire (TDD : rouge vu puis vert)
1. `src/mouth/magpie_tts.py` : backend `MOUTH_BACKEND=magpie`, même interface que `src/mouth/supertonic_tts.py`
   (`load_model`, `synthesize`, `synthesize_stream` par phrase). **Garder le modèle chargé** entre deux phrases
   (serveur/processus persistant, pas un exécutable relancé à chaque phrase — sinon latence). Voix via `MOUTH_VOICE_NAME=Sofia`, langue `fr`.
2. **Nombres → lettres (FR)** avant synthèse : heures (15h30 → quinze heures trente), dates, numéros de rue, entiers, décimaux, pourcentages.
   Dans `src/mouth/normalize.py` (fonction dédiée, sûre sur fragments streamés) ; pas de dépendance lourde (num2words accepté si pur Python).
3. Câblage dans `dev/scripts/serve_hostagent.py` : branche `elif backend == "magpie"` à côté de supertonic.
4. Tests : `dev/tests/test_mouth_magpie.py`, `dev/tests/test_normalize_nombres.py`.

## Preuve
Relance du host-agent **uniquement via** `/tmp/relance_hostagent.sh` après y avoir remplacé les variables MOUTH par
`MOUTH_BACKEND=magpie MOUTH_VOICE_NAME=Sofia` (garder `BRAIN_SERVICE=llamacpp`…). Log de boot « MOUTH : chargement magpie Sofia », puis
une synthèse test via le host-agent avec « Rendez-vous jeudi 24 septembre à 15h30, au 12 rue des Lilas. » → wav dans
`nights/degustation-19/c9-sofia-test.wav` + temps avant premier son.

## Périmètre
Fichiers : `src/mouth/magpie_tts.py`, `src/mouth/normalize.py`, bloc MOUTH de `serve_hostagent.py`, les 2 tests. Rien d'autre.
Un autre run Cursor fait un banc ASR sur le GPU : Magpie reste **CPU**. Ne pas toucher à llama-server. Pas de git, pas de `.env.local`.
OUT : `nights/2026-09-19-C9-MAGPIE-OUT.md`. Réponds OK.
