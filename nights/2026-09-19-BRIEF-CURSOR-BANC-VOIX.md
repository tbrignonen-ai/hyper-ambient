---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6) — run séparé du banc oreille
auteur: Claude (lead technique)
---

# BRIEF Cursor — Banc voix n°2 (nouveautés veille HF)

Phrase imposée (identique à la dégustation 1) :
« Bonjour Thomas. Je suis MOTHER. Aujourd'hui, un brouillard humide recouvre la rue ; prends ton parapluie, et dis-moi si tu veux que je te lise la suite. »

## Candidats (voix féminine, français)
1. `neuphonic/neutts-air` (GGUF q4 si possible)
2. `tencent/AuK-Flash` (sinon `tencent/AuK`)
3. `Edge0/audio8-TTS-0.1B-ONNX-INT8`
4. `nvidia/magpie_tts_multilingual_357m`
5. `Serveurperso/OmniVoice-GGUF` (licence non commerciale — le noter)

Si le modèle a une voix féminine française intégrée : la prendre (la plus grave/douce). S'il clone une voix : référence =
`/workspace/models/piper/fr_FR-siwis-medium.onnx` (générer 6–8 s de siwis sur une phrase neutre et fournir son texte). Débit lent si réglable (~0,9).

## Livrables
- WAV mono, même volume (RMS -20 dBFS), **anonymisés** `nights/degustation-19/voix2/degustation-voix2-P..T.wav` ; ajouter aussi la référence F5
  (`nights/degustation-19/.sources/voix-F5.wav`, renormalisée) sous une lettre au hasard. Correspondance : `nights/degustation-19/voix2/.carte-secrete.json`.
- Pour chacun : temps de synthèse, CPU ou GPU, VRAM max, voie « Windows natif : oui / non / à vérifier ».
- OUT : `nights/2026-09-19-BANC-VOIX2-OUT.md` (sans révéler les lettres ; échecs d'installation avec leur cause).

## Où et comment
Conteneur `mother-core-dev`, un venv par candidat sous `/workspace/models/tts-bench/<nom>/`. Écrire d'abord dans `/tmp` du conteneur puis `docker cp` (nights n'est pas monté). Un seul modèle GPU à la fois.
Un autre run Cursor fait le banc oreille sous `/workspace/models/asr-bench/` : n'y touche pas.

## Interdits
Ne pas relancer ni arrêter le host-agent ni `:8090` · ne toucher à aucun fichier de `src/`, `native/`, `workers/`, `dev/` · pas de `.env.local` · pas de git. Réponds seulement OK.
