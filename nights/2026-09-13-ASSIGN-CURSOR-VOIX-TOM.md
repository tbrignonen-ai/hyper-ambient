---
date: 2026-09-13
type: assign
to: Cursor
heure: ~17:15
---
# ASSIGN — autre voix Piper (mêmes modèles)

Thomas 17:14 : « le cerveau ca va MAIS la voix, change de type de voix, choisis une autre voix juste mais garde les meme modeles »

## Contraintes
- **Garder** : Piper backend, MiniCPM, Qwen ASR, stack actuelle. **Pas** Kokoro, pas nouveau moteur TTS.
- **Changer** : le fichier voix Piper (pas siwis).
- Profil : garder **`aurora`** (celui validé ; mother a coincidé avec l’entrecoupe).
- Choix OC pour Cursor (trancher, pas demander) : **`fr_FR-tom-medium.onnx` + `aurora`**.
  (upmc+mother = bof/entrecoupé ; siwis = « mieux avant » mais il veut *autre* type maintenant.)

## Mission
1. Figer dans `.env.local` + `relancer_routeur.sh` (+ defaults piper) :
   `MOUTH_VOICE=/workspace/models/piper/fr_FR-tom-medium.onnx`
   `MOUTH_PROFILE=aurora`
2. Relancer hostagent proprement.
3. Smoke mouth + 1 wav sample `data/out/voix-compare/tom-aurora.wav` (même phrase que les autres).
4. Vérifier sample rate cohérent avec le pipeline (si tom sort 44.1k, resample/aligner pour éviter entrecoupe).
5. OUT : `nights/2026-09-13-CURSOR-VOIX-TOM-AURORA.md` (vault + repo).

Interdits : toucher cerveau/EARS/world, push git.
