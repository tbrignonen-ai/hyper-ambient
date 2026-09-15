---
date: 2026-09-13
type: assign
heure: ~18:35
---
# ASSIGN — 10 NOUVEAUX samples TTS (modeles NEUFS seulement)

Thomas 18:30 (strict) :
- Cosette + Supertonic F1 = mieux de l ancien pack, MAIS on peut mieux
- Ref **Aura Ray** : `D:\BGB Training\MOTHER-dev\data\voix\aurora_prompt_6s.wav`
- **Changer de modeles TTS** et refaire 10 samples
- Uniquement modeles **< 2 mois** (sortis / maj apres ~2026-07-13) **et qui fitent** (CPU ou petit GPU, budget stack ~8-10 Go)
- **Si vous ressortez les memes modeles TTS ca va chier**
- Cursor = champion recherche+exec ; **Muse aussi** recherche
- **Ne pas epuiser Claude** — Claude hors de ce chantier

## INTERDIT (deja samples / deja entendus) — ne PAS regenerer
- pocket-tts (estelle, cosette, tout pocket)
- piper (siwis, upmc, mls, tom, tout piper)
- supertonic (F1, F5, tout supertonic-3 deja utilise)
- Qwen3-TTS clone / qwen3tts deja sample
- facebook/mms-tts-fra

## Roles
### Muse (recherche high-level)
Lister 12–15 candidats TTS **nouveaux** (<2 mois), FR ou clonables FR, qui fitent. Classer : fit VRAM/CPU, licence, qualite attendue vs Aura Ray. Ecrire `nights/2026-09-13-MUSE-TTS-NEW.md` avec top picks pour Cursor.

### Cursor (recherche + code + samples)
1. Lire Muse si pret ; completer recherche web/HF toi-meme (nouveautes TTS ete/automne 2026)
2. Choisir **10 modeles DISTINCTS jamais dans la liste INTERDIT**
3. Telecharger poids dans `models/` (perimetre OK ; tu peux supprimer vieux poids inutiles Piper rejects etc. si place)
4. Generer 10 MP3 avec le script long `nights/2026-09-13-SCRIPT-VOIX-LONG.txt`
5. Dossier NEUF : `data/out/voix-10-samples-v2/` (ne pas ecraser v1)
6. `INDEX.md` + OUT `nights/2026-09-13-CURSOR-VOIX-10-V2.md`
7. Si docker eteint : `docker start mother-core-dev` seulement si besoin ; pas recreate
8. Restaurer stack propre a la fin si tu touches hostagent

Cible oreille : douce, presentielle, proche d Aura Ray (ref wav ci-dessus).
