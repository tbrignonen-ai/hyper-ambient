# MUSE TTS NEW — 10 nouveaux modèles (< 2 mois), fit CPU / petit GPU — 2026-09-14

Date : 2026-09-14. Demande Thomas : 10 NOUVEAUX modèles TTS sortis depuis le 2026-07-13, qui FITENT (CPU ou petit GPU, stack ~8-10 Go), cible Aura Ray douce. Référence clone : data/voix/aurora_prompt_6s.wav.
Pas de code. Pas Cursor. Ce fichier = tableau candidats + TOP 10 pour Claude (échantillonnage).

Miroir local de : /mnt/c/Users/thoma/obsidian-vault/10-Projects/MOTHER/nights/2026-09-14-MUSE-TTS-NEW.md (écriture directe vault refusée par le sandbox, voir note en fin de fichier).

## Exclusions respectées (INTERDIT absolu)

- pocket-tts, piper (siwis, upmc-jessica, mls-7239, tom), supertonic-3 (F5/F1 déjà samplés), qwen3-tts (déjà samplé), mms-tts-fra.
- Tout déjà dans data/out/voix-10-samples/ (01 à 10 + INDEX + run.log) et data/out/voix-10-samples-v2/ (anka-tts clone, chatterbox-mtl-v3 clone, meta.jsonl).
- Cas spécial : anka + chatterbox déjà partiels = OK à compléter, mais HORS TOP 10 ci-dessous (priorité aux autres). Les finir en bonus si temps, ne pas les recompter comme "nouveaux".

## Tableau candidats (vérifié ce jour, avec confiance de date)

| # | Modèle (ID HF / repo) | Signal de date observé | Taille / format fit | FR | Clone 6 s | Fit CPU / petit GPU 8-10 Go | Intérêt Aura douce |
|---|---|---|---|---|---|---|---|
| 1 | Audio8 / Audio8-TTS-Preview-0.6b (miroir Edge0 / Audio8-TTS-Preview-0.6b) | ✅ Trending HF 03-08-2026 et 06-08-2026, ajout bench le 04-08-2026 | 0,6 B, variantes ONNX / INT4 | Oui (multilingue, 11 langues reco) | Oui, zero-shot + transcript-conditioned | Oui, CPU-ONNX possible, ~2-4 Go | Prosodie naturelle, doux, premier choix |
| 2 | Audio8 / Audio8-TTS-Preview-0.1b (+ build ONNX INT8) | ✅ Base le 19-08-2026, ONNX INT8 le 25-08-2026 (commit tts-bench) | 0,1 B, ONNX INT8 | Oui (multilingue) | Oui (pipeline preview) | Oui, CPU pur, < 1 Go | Version ultra-légère du n°1, test A/B idéal |
| 3 | OPPOer / CuteTTS (repo oppo-mente-lab / cutetts) | ✅ Activité repo mi-août 2026 (~24-08), papier + Space récents | ~230 M, AR continu, CPU/GPU/Apple silicon | Oui (EN, ZH, FR, DE, ES) | Oui (continu latent, style fin) | Oui, CPU, < 2 Go | Léger + FR natif, bon candidat douceur |
| 4 | IndexTTS2 (famille, via audio.cpp Release 0.3) | ✅ Release audio.cpp 0.3 le 14-07-2026 (5 nouvelles familles TTS) | ~0,5-1 B selon variante, ggml possible | À confirmer (tester FR) | Oui, zero-shot | Oui, petit GPU / CPU ggml | Industrielle, stable, à tester sur ref Aura |
| 5 | Aratako / Irodori-TTS-500M-v3 + v4.1-Small + VoiceDesign | ✅ Même release 14-07-2026, branches v3/v4 actives été 2026 | 500-600 M, RF-DiT + DACVAE | À confirmer (base JP/EN, tester FR) | Oui + voice design (caption/emoji) | Oui, petit GPU ~4-6 Go | Contrôle style/émotion = douceur réglable |
| 6 | KittenML / kitten-tts-nano-0.8-fp32 (et 0.1) | ✅ Famille 2026 active, release 0.8 récente (page HF 2026) | 15 M, < 25 Mo, CPU-only | Oui (set initial : EN US/UK, ES, FR, DE, IT, JA) | Non, voix fixes (pas de vrai clone) | Oui, CPU extrême, ~100 Mo | Tester voix fixe la plus douce proche d'Aura, pas un clone |
| 7 | MOSS-TTS-Local-Transformer-v1.5 (MOSI AI, servi day-0 par SGLang-Omni) | ✅ Via audio.cpp 0.3 (14-07-2026) + annonce SGLang-Omni récente | ~4 B (backbone Qwen3-4B), 48 kHz stéréo | Oui (multilingue) | Oui | Limite : quantifié INT4 sur petit GPU ~5-6 Go, hors CPU | À ne tester qu'en quantifié, sinon écarter |
| 8 | DiFlow-TTS (fsoft-aic / diflowtts, Interspeech 2026) | ⚠️ Papier v5 du 17-06-2026 (avant fenêtre), code/forks actifs juillet-août 2026 | Compact, discrete flow matching, ~100-300 M | Base EN (LibriTTS neutre), tester FR | Oui, zero-shot low-latency | Oui, CPU/petit GPU | Neutre/doux par construction, parfait pour Aura si FR passe |
| 9 | Neuphonic / NeuTTS on-device (famille, forks 2026) | ⚠️ Famille 2026, forks actifs, date exacte du checkpoint FR à confirmer sur la fiche | Petit backbone LLM, on-device | Oui selon variante (EN, ES, DE, FR) | Selon variante (voix fixes et/ou clone) | Oui, CPU / edge | Backup léger FR, à valider fiche par fiche |
| 10 | LEMAS-Project / LEMAS-TTS (10 langues, base F5-TTS stabilisée, 150 k h) | ❌ Papier janv. 2026 (hors fenêtre stricte), Space/forks actifs 2026 | Moyen (~300 M-1 B selon variante) | Oui (ZH, EN, ES, RU, FR, DE, IT, PT, ID, VI) | Oui, zero-shot multilingue | Oui, petit GPU | Backup FR explicite, honnêtement hors fenêtre, ne pas le vendre comme nouveau |

## Écartés consciemment (et pourquoi)

- Fish Audio S2 / S2 Pro : excellent mais trop gros pour stack 8-10 Go avec le reste, hors gabarit.
- Higgs TTS v3 4 B (bosonai) : benchmark août/sept. 2026 intéressant mais 4 B = même limite que n°7, prioriser n°7.
- GLM-TTS (zai-org) : clone 3-10 s + contrôle émotion séduisant, mais date non établie dans la fenêtre (semble fin 2025/début 2026) → pas dans le TOP 10, re-tester plus tard.
- MOSS-TTS-Nano-100M / ONNX (avril 2026) : parfait CPU mais trop vieux (> 2 mois) → exclu par la règle de fraîcheur.
- Kokoro-82M et variantes : base 2025, pas nouveau même si l'écosystème (streaming Wyoming sept. 2026) bouge.
- VibeVoice / Step-Audio-2-mini / MiniMax : dialogue long ou speech-to-speech, 7-8 B, hors budget 8-10 Go.

## TOP 10 pour Claude (ordre d'échantillonnage, même ref, même texte FR)

Ordre : 1 Audio8-0.6b → 2 Audio8-0.1b-ONNX-INT8 → 3 CuteTTS → 4 IndexTTS2 → 5 Irodori v4.1-Small (puis v3 si échec FR) → 6 KittenTTS-0.8 voix fixe FR la plus douce → 7 MOSS-Local-v1.5 quantifié INT4 (écarter si > 8 Go) → 8 DiFlow-TTS → 9 NeuTTS variante FR → 10 LEMAS-TTS (backup, signalé hors fenêtre).

Protocole suggéré (sans code ici) : même prompt ref aurora_prompt_6s.wav, même phrase FR douce, même niveau, écoute aveugle, note douceur / proximité Aura / artefacts. Bonus hors TOP 10 : finir anka + chatterbox partiels de voix-10-samples-v2.

## Risques et honnêteté

- Dates n°8, n°9, n°10 : marquées borderline ou hors fenêtre, à ne pas présenter comme des nouveautés strictes.
- FR n°4, n°5, n°8 : à confirmer à l'écoute, base d'entraînement non-FR.
- N°6 n'est pas un clone : comparer en voix fixe, ne pas le noter sur la fidélité de clone.
- N°7 : à écarter immédiatement si la stack quantifiée dépasse ~8 Go.

## Note sandbox (livraison vault)

L'écriture directe vers /mnt/c/Users/thoma/obsidian-vault/10-Projects/MOTHER/nights/2026-09-14-MUSE-TTS-NEW.md a été refusée par le sandbox (chemin hors workspace). Ce miroir est déposé à nights/2026-09-14-MUSE-TTS-NEW.md dans le repo. Commande de transfert à lancer côté Windows/WSL avec accès /mnt/c : cp "nights/2026-09-14-MUSE-TTS-NEW.md" "/mnt/c/Users/thoma/obsidian-vault/10-Projects/MOTHER/nights/2026-09-14-MUSE-TTS-NEW.md".
