---
date: 2026-09-19
heure: ~20:15
type: decision
statut: FIGÉE (validée par Thomas au test live du 19/09 soir)
auteur: Claude (lead technique) — choix : Thomas, à l'aveugle
related: ["[[2026-09-19-PROTOCOLE-DEGUSTATION]]", "[[2026-09-19-DEGUSTATION-CERVEAUX-RESULTATS]]", "[[2026-09-19-BANC-OREILLE-2-OUT]]", "[[2026-09-19-C9-MAGPIE-OUT]]", "[[2026-09-19-CLAUDE-POUR-GROK-SUITE]]"]
---

# CARTE FIGÉE — modèles locaux embarqués dans Hyper Ambient 0.1

| Brique | Modèle retenu | Format / exécution | Fichiers (conteneur `mother-core-dev`) | Taille |
|---|---|---|---|---|
| **Cerveau** | **ibm-granite/granite-4.2-3b** | GGUF **Q4_K_M**, llama-server CUDA, ctx 4096, `--no-mmap`, alias `mother-local` | `/workspace/models/gguf/granite-4.2-3b-Q4_K_M.gguf` | 2,24 Go |
| **Oreille** | **openai/whisper-large-v3** | faster-whisper (CTranslate2) **int8_float16**, CUDA, `EARS_LANGUAGE=fr` | `/workspace/models/hf-cache/hub/models--Systran--faster-whisper-large-v3/` | 2,9 Go |
| **Voix** | **nvidia/magpie_tts_multilingual_357m — voix Sofia** | GGUF f16 via `nemo-speech serve` **CUDA**, `MOUTH_BACKEND=magpie MOUTH_VOICE_NAME=Sofia MOUTH_DEVICE=cuda` | `/workspace/models/tts-bench/magpie/models/nvidia/magpie_tts_multilingual_357m/…/magpie_tts_multilingual_357m.v2602.f16.gguf` + codec `…/nemo_nano_codec_22khz_1.89kbps_21.5fps.decoder.f16.gguf` | 449 Mo + 79 Mo |

**Replis documentés** : cerveau NeoHorse-1-9B (4,0/5) puis Ministral-3-8B (5,0/5 mais jugé trop ancien) · oreille Parakeet-TDT-0.6B-v3 (plus léger, ~0,3 s, rate « Camunda ») · voix Supertonic F5 ×0,88 (CPU, 0 VRAM).
**Intégrations distantes (optionnelles, clés facultatives)** : JeV (mains libres, entrée) · StepAudio TTS (voix distante) · modèle texte distant (Step-5, routeur commandcode…) · recherche web multi-fournisseurs.

## Mesures au test live final (19/09 ~20h, stack réelle, voix de Thomas)
- Oreille : transcription **0,45 à 0,7 s** par phrase ; noms propres justes (Camunda, Lefebvre, Codex) ; nombres justes (« 8376 divisé par 2,8 »).
- Cerveau : 1er jeton **25 à 70 ms** ; identité « Hyper Ambient » correcte.
- Voix : **~1,1 s avant le premier son** (phrase courte), jusqu'à 3,2–4,8 s sur phrase longue / nombres ; nombres convertis en lettres avant synthèse.
- **VRAM au repos : 7,3 Go / 12** (cerveau + oreille + voix + Windows) → dans le budget 10 Go ; marge ≈ 2,7 Go.

## Pourquoi ces choix (dossier §1.2 / §4)
Choix faits **à l'aveugle par l'utilisateur final**, à volume égalisé pour les voix, questions improvisées pour les cerveaux, sur ses propres enregistrements pour l'oreille ;
candidats issus d'une veille par l'**API Hugging Face** + classements publics (Open ASR Leaderboard, Artificial Analysis) ; contraintes éliminatoires : français + anglais, 10 Go VRAM, Windows natif, licence commerciale
(Granite : Apache-2.0 · Whisper : MIT · Magpie : NVIDIA Open Model License, usage commercial autorisé).

## Réserves connues (non bloquantes pour la carte)
1. Magpie tourne avec le binaire **CUDA** de `nemo-speech` pris dans `asr-bench/nemotron.new` (le build installé avec Magpie n'a pas CUDA) → à packager proprement (C7).
2. Magpie n'a **pas de réglage de débit** ni de flux intra-phrase (découpe aux virgules en place).
3. Granite se trompe en calcul mental → outil `calculer` (C12).
4. Mots imposés Whisper (`hotwords`) validés au banc mais **pas encore câblés** dans EARS.

## Problèmes ouverts au 19/09 soir (constat de Thomas, non réglés)
1. **Première requête qui tombe dans le vide** : souvent, la première question d'une séance n'obtient pas de réponse et il faut la répéter (peu grave, mais à régler). Le correctif C10 (appui avant l'ouverture du WebSocket) n'a pas suffi ; C13 (appli lancée en pythonw) est peut-être lié.
2. **La recherche web ne trouve rien** : l'outil est bien appelé, mais il répond « rien trouvé ». SearXNG rend 0 résultat (moteurs sous captcha) et le repli ne se déclenche pas. **À traiter lors de l'intégration de tous les fournisseurs web (C4)**, pas avant.

## Reprendre la session Claude
Session Claude Code « MOTHER-PLAN-19 » : `claude --resume 0856de03-e253-472c-9877-1b3f421c6441`. Journal : `~/.claude/projects/D--BGB-Training-MOTHER-dev/0856de03-e253-472c-9877-1b3f421c6441.jsonl`.
