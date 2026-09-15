---
date: 2026-09-13
type: assign
to: Cursor
heure: ~17:30
---
# ASSIGN — changer le moteur TTS (hors Piper)

Thomas 17:29 : « ok donc faut changer le modele si y a que celles la » / « changer de modele de TTS »

## Contexte
- Piper siwis / upmc / tom = rejetés (terrible / entrecoupé / bof)
- Stack cerveau + EARS **inchangée**
- Backend déjà dans le code : **Pocket TTS** (`src/mouth/pocket_tts.py`), défaut historique du hostagent = `MOUTH_BACKEND=pocket`, voix FR **estelle**, 0 VRAM CPU
- Modèles sur disque : `/workspace/models/pocket-tts/`

## Mission
1. Basculer `MOUTH_BACKEND=pocket` (voix `estelle`, langue FR) dans `.env.local` + `relancer_routeur.sh` + defaults serve_hostagent
2. Profil : `aurora` si applicable / sinon le profil pocket le plus clean (pas mother doublage)
3. Relancer hostagent ; confirmer log `MOUTH : chargement pocket-tts … estelle`
4. Sample wav `data/out/voix-compare/pocket-estelle.wav`
5. Smoke : préchauffage mouth OK + une phrase
6. OUT : `nights/2026-09-13-CURSOR-TTS-POCKET.md` (vault + repo) — comment revenir Piper si besoin

Interdits : toucher EARS/cerveau/world, Kokoro day-1 sauf si pocket impossible, push git, burn.
Si pocket ne charge pas : OUT explicite + fallback documenté, ne pas inventer un 3e moteur sans preuve.
