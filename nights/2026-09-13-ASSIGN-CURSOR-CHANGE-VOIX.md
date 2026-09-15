---
date: 2026-09-13
type: assign
to: Cursor
---
# ASSIGN Cursor — changer la voix TTS

Thomas (16:45) : « mouais bof. on peut changer de voix ? » → **Cursor**, pas OC.

## Contexte
- Backend actuel : `MOUTH_BACKEND=piper`
- Voix actuelle : `fr_FR-siwis-medium.onnx` + profil `aurora` (validée 8 sept, mais Thomas en a marre aujourd’hui)
- Sur disque déjà (`models/piper/`) : `fr_FR-siwis-medium`, `fr_FR-mls-medium`, `fr_FR-tom-medium`, `fr_FR-upmc-medium`
- Profils : `aurora` / `mother` / `flat` (voir `src/mouth/voice_design.py`)
- Contrainte produit : **accent français natif** (pas Kokoro day-1)

## Mission
1. Bascule Piper vers **`fr_FR-upmc-medium`** + profil **`mother`** (autre FR natif, distinct de siwis/aurora). Mets à jour `.env.local` + `dev/scripts/relancer_routeur.sh` (et tout endroit qui force siwis/aurora).
2. Relance hostagent proprement : `docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh`
3. Génère 3 wav courts (~3 s, même phrase FR) dans `data/out/voix-compare/` : upmc+mother (nouveau), siwis+aurora (ancien), tom+mother — pour que Thomas écoute et tranche.
4. Smoke : une phrase via mouth / verify rapide OK.
5. OUT : `nights/2026-09-13-CURSOR-CHANGE-VOIX.md` (vault + repo) — voix active, chemins wav, comment revenir à siwis/aurora en 1 commande.

Interdits : toucher EARS/ASR, world, Kokoro aujourd’hui, pas de burn, pas de push git.
