---
date: 2026-09-14
type: diagnostic
role: Codex cerveau
---
# Diagnostic court — voix v2

- La note Muse du 14 n'était pas encore présente au moment de l'analyse; l'assignation du 13 et les artefacts réels ont servi de base.
- État réel : 2 MP3 décodés sans erreur par ffmpeg, Anka (42,00 s, 24 kHz mono) et Chatterbox MTL V3 (37,90 s, 24 kHz mono); `meta.jsonl` contient exactement ces deux lignes.
- Infrastructure prête : `mother-core-dev` UP, RTX 4070 12 Go avec environ 10,1 Go libres, venv TTS présent, 244 Go disque libres, `ffmpeg` et `espeak-ng` installés.
- Le driver actuel n'est pas reprenable : `ok=0`, il régénère Anka, compte seulement les succès du run, ignore les codes retour de certains installateurs et pourrait livrer plus de dix modèles.
- La sélection initiale contient deux mauvais candidats pour l'ordre final : Chatterbox EN duplique Chatterbox MTL et OmniVoice est mis à jour le 3 juillet, avant le cutoff du 13 juillet.
- Plusieurs adaptateurs sont fragiles : Raon n'est pas un simple checkpoint F5 générique; Magpie change de nom de classe selon NeMo; IndexTTS force `lang="EN"`; dots.tts devrait fixer sa graine; VoxCPM2 suppose un attribut de SR non garanti.
- Décision : conserver sans recalcul Anka et Chatterbox MTL; produire huit slots manquants, avec Audio8 0.6B à la place des deux candidats écartés. Chatterbox reste explicitement le seul repli hors cutoff.
- La réussite doit être décidée sur les 10 MP3 décodables et audibles, puis sur un `meta.jsonl` dédupliqué et un `INDEX.md`, jamais sur le seul code retour du modèle.
