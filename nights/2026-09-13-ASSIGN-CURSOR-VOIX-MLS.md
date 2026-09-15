---
date: 2026-09-13
type: assign
to: Cursor
heure: ~17:30
---
# ASSIGN — autre voix Piper (mls), mêmes modèles

Thomas 17:29 : « terrible . Garde le modele change la voix. »

## Déjà testé aujourd’hui
- siwis+aurora — ok historiquement, puis « change de type »
- upmc+mother — entrecoupé / bof
- tom+aurora — **terrible** (actuel)

## Choix
- Backend **Piper** inchangé (pas Kokoro)
- Voix : **`fr_FR-mls-medium.onnx`**
- Profil : **`aurora`** (pas mother)
- Stack cerveau/EARS inchangée

## Mission
1. Figer `.env.local` + `relancer_routeur.sh` (+ defaults) → mls + aurora
2. Relancer hostagent
3. Sample `data/out/voix-compare/mls-aurora.wav`
4. OUT `nights/2026-09-13-CURSOR-VOIX-MLS-AURORA.md` (vault+repo)
5. Confirmer log MOUTH charge mls+aurora

Interdits : EARS, cerveau, world, Kokoro, push.
